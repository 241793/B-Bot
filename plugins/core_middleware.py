#____b-bot,下面有奥特曼的中间件规则
import asyncio
import inspect
import json, re
import os
import uuid
import hashlib
import platform
import socket
import contextvars
from datetime import datetime
import subprocess
from pathlib import Path

import aiohttp
from functools import partial
from typing import Dict, Any, Optional, List, Callable, Tuple

from storage.bucket import BucketManager
from utils.logger import get_logger
from containers.base import BaseContainer
from containers.qinglong import QinglongContainer
from utils.variable_processor import process_variables
from config import config

__version__ = "1.0.0"
__author__ = "bucai"
__description__ = "中间件函数，只看后面的操作类函数（有提示）"

# 容器类型映射
CONTAINER_TYPE_MAP = {
    "qinglong": QinglongContainer,
}

class Middleware:
    """
    中间件类，提供给插件调用的各种功能接口
    """

    def __init__(self, bucket_manager: BucketManager):
        """
        初始化中间件
        :param bucket_manager: 桶管理器
        """
        self.bucket_manager = bucket_manager
        self.adapters = {}  # 存储不同平台的适配器
        self.message_handlers: Dict[str, List[Callable]] = {} # 按插件名存储消息处理器
        self.plugin_metadata: Dict[str, Dict[str, Any]] = {} # 存储插件元数据
        self.logger = get_logger("middleware")
        self.containers: Dict[str, BaseContainer] = {} # 存储容器实例
        # 使用 (user_id, group_id) 元组作为键，确保等待的上下文精确
        self.waiting_for_input: Dict[Tuple[str, Optional[str]], asyncio.Future] = {}
        
        # 适配器状态缓存
        self.adapter_status_cache = {}
        self.adapter_status_loaded = False
        
        # 授权检查器
        self.auth_checker = None
        
        # HTTP会话
        self._http_session: Optional[aiohttp.ClientSession] = None

        # 捕获主事件循环，用于在非异步线程中调度任务
        try:
            self.main_loop = asyncio.get_running_loop()
        except RuntimeError:
            self.main_loop = None
            self.logger.warning("Middleware initialized without a running event loop. Some features may not work.")

    def set_auth_checker(self, checker: Callable[[], bool]):
        """设置授权检查器"""
        self.auth_checker = checker

    def set_plugin_metadata(self, plugin_name: str, is_admin: bool = False, im_types: Optional[List[str]] = None):
        """设置插件元数据"""
        self.plugin_metadata[plugin_name] = {
            "is_admin": is_admin,
            "im_types": im_types
        }

    async def _ensure_adapter_status_loaded(self):
        """确保适配器状态已加载"""
        if not self.adapter_status_loaded:
            self.adapter_status_cache = await self.bucket_manager.get("system", "adapter_status", {})
            self.adapter_status_loaded = True

    async def is_adapter_enabled(self, adapter_name: str) -> bool:
        """检查适配器是否启用"""
        await self._ensure_adapter_status_loaded()
        return self.adapter_status_cache.get(adapter_name, True)

    async def set_adapter_enabled(self, adapter_name: str, enabled: bool):
        """设置适配器启用状态"""
        await self._ensure_adapter_status_loaded()
        self.adapter_status_cache[adapter_name] = enabled
        await self.bucket_manager.set("system", "adapter_status", self.adapter_status_cache)
        self.logger.info(f"适配器 {adapter_name} 已{'启用' if enabled else '禁用'}")

    async def load_containers(self):
        """
        从数据库加载并初始化所有容器。
        """
        self.logger.info("正在加载外部容器...")
        container_configs = await self.bucket_manager.get("system", "containers", [])
        normalized_configs = []
        if isinstance(container_configs, dict):
            # 兼容旧版/插件直接读取的字典结构: {name: {config}}
            for name, cfg in container_configs.items():
                one = dict(cfg or {})
                one["name"] = name
                normalized_configs.append(one)
        elif isinstance(container_configs, list):
            normalized_configs = container_configs
        else:
            self.logger.error("容器配置格式不正确，应为列表或字典。")
            return

        for config in normalized_configs:
            name = config.get("name")
            container_type = config.get("type")
            
            if not name or not container_type:
                self.logger.warning(f"跳过一个不完整的容器配置: {config}")
                continue

            ContainerClass = CONTAINER_TYPE_MAP.get(container_type)
            if not ContainerClass:
                self.logger.error(f"不支持的容器类型: {container_type}")
                continue

            try:
                container_instance = ContainerClass(name, config)
                if await container_instance.connect():
                    self.containers[name] = container_instance
                else:
                    self.logger.error(f"容器 '{name}' 连接失败，将不可用。")
            except Exception as e:
                self.logger.error(f"初始化容器 '{name}' 时发生错误: {e}", exc_info=True)
        
        self.logger.info(f"共加载并连接了 {len(self.containers)} 个外部容器。")

    async def stop_containers(self):
        """
        停止并清理所有容器资源。
        """
        self.logger.info("正在停止所有外部容器...")
        for name, container in self.containers.items():
            if hasattr(container, 'close'):
                try:
                    await container.close()
                    self.logger.info(f"容器 '{name}' 已成功关闭。")
                except Exception as e:
                    self.logger.error(f"关闭容器 '{name}' 时发生错误: {e}", exc_info=True)
        self.containers.clear()

    async def stop(self):
        """
        停止中间件及其资源（包括容器和HTTP会话）
        """
        await self.stop_containers()
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
            self.logger.info("HTTP会话已关闭")

    def _get_session_key(self, msg: Dict[str, Any]) -> Optional[Tuple[str, Optional[str]]]:
        """
        根据消息生成唯一的、标准化的会话标识。
        这是确保 wait_for_input 可靠工作的核心。
        """
        user_id = msg.get("user_id")
        # user_id 必须存在且不为空
        if user_id is None or str(user_id).strip() == '':
            return None

        group_id = msg.get("group_id")

        # 强力标准化group_id：None, '', 0, '0' 都应被视为私聊 (None)
        norm_group_id = None
        if group_id and str(group_id).strip() not in ['', '0']:
            norm_group_id = str(group_id)

        return (str(user_id), norm_group_id)

    def register_adapter(self, name: str, adapter):
        """
        注册适配器
        :param name: 适配器名称
        :param adapter: 适配器实例
        """
        self.adapters[name] = adapter

        # 自动设置适配器的中间件引用
        try:
            adapter.middleware = self
        except AttributeError:
            # 如果适配器不支持设置middleware属性，则跳过
            pass

        self.logger.info(f"适配器 {name} 已注册")

    def register_message_handler(self, handler: Callable, plugin_name: str):
        """
        注册消息处理器
        :param handler: 消息处理器函数
        :param plugin_name: 所属插件的名称
        """
        if plugin_name not in self.message_handlers:
            self.message_handlers[plugin_name] = []
        self.message_handlers[plugin_name].append(handler)
        self.logger.info(f"插件 '{plugin_name}' 的消息处理器 {handler.__name__} 已注册")

    def unregister_message_handlers(self, plugin_name: str):
        """
        注销属于特定插件的所有消息处理器
        :param plugin_name: 插件名称
        """
        if plugin_name in self.message_handlers:
            count = len(self.message_handlers[plugin_name])
            del self.message_handlers[plugin_name]
            self.logger.info(f"已注销插件 '{plugin_name}' 的 {count} 个消息处理器。")

    async def _run_handlers(self, message: Dict[str, Any]):
        try:
            from middleware.atm_context import set_current_context
            set_current_context(self, message)
        except Exception:
            pass

        """
        在后台任务中运行消息处理器和拦截逻辑。
        """
        # --- 授权检查 ---
        # Built-in command: machine code
        content = self._normalize_message_content(message.get("content", ""))
        if re.fullmatch(r"(?:\u53d1\u9001)?\u673a\u5668\u7801", content):
            machine_code = await self.get_machine_code()
            await self.send_response(message, {"content": f"\u673a\u5668\u7801: {machine_code}"})
            return
        # Built-in command: Coze chat proxy
        if re.match(r"^coze\s+", content, re.IGNORECASE):
            if not await self.is_adapter_enabled("coze"):
                await self.send_response(message, {"content": "Coze 适配器已禁用"})
                return
            prompt = re.sub(r"^coze\s+", "", content, flags=re.IGNORECASE).strip()
            if not prompt:
                await self.send_response(message, {"content": "用法: coze 你的问题"})
                return
            try:
                result = await self._coze_chat(message, prompt)
                await self.send_response(message, {"content": result})
            except Exception as e:
                self.logger.error(f"Coze 调用失败: {e}", exc_info=True)
                await self.send_response(message, {"content": f"Coze 调用失败: {e}"})
            return
        if re.fullmatch(r"(?:\u66f4\u65b0|\u5347\u7ea7)", content):
            user_id = message.get("user_id")
            if not await self.is_admin(user_id):
                await self.send_response(message, {"content": "仅管理员可执行更新。"})
                return
            await self.send_response(message, {"content": "正在检查远程版本更新，请稍候..."})
            update_msg = await self._auto_update_from_docker_hub()
            await self.send_response(message, {"content": update_msg})
            return

        if self.auth_checker and not self.auth_checker() and not re.search('^bot[a-zA-Z0-9]+$', content) and not re.search('^授权码$', content):
            self.logger.warning("系统未授权或授权已过期，拒绝处理消息。")
            # 可以选择发送一条提示消息，或者直接忽略
            # await self.send_response(message, {"content": "系统未授权或授权已过期。"})
            return
        # ----------------

        # 首先处理变量提交（容错，避免异常打断整个消息处理链）
        try:
            await process_variables(message, self)
        except Exception as e:
            self.logger.error(f"变量提交流程处理失败: {e}", exc_info=True)

        user_id = message.get("user_id")
        group_id = message.get("group_id")
        is_admin_user = await self.is_admin(user_id)
        is_internal_message = message.get("internal_source", False)

        # --- 拦截逻辑 ---
        if not is_internal_message:
            if group_id:  # 群聊消息
                group_reply_enabled = await self.bucket_get("system", "group_reply_enabled", True)
                if not group_reply_enabled:
                    self.logger.debug(f"群聊回复已禁用，忽略来自群 {group_id} 的消息")
                    return
                group_blacklist = await self.bucket_get("system", "group_blacklist", [])
                if str(group_id) in group_blacklist:
                    self.logger.debug(f"群 {group_id} 在黑名单中，忽略消息")
                    return
            else:  # 私聊消息
                private_reply_enabled = await self.bucket_get("system", "private_reply_enabled", True)
                if not private_reply_enabled and not is_admin_user:
                    self.logger.debug(f"私聊回复已对普通用户禁用，忽略来自用户 {user_id} 的消息")
                    return

        self.logger.info(f"后台处理消息: {content}")

        # 获取当前事件循环
        loop = asyncio.get_running_loop()

        # 调用所有注册的消息处理器
        handled = False
        for plugin_name, handlers in self.message_handlers.items():
            # --- 插件级权限检查 (跳过内部消息) ---
            if not is_internal_message:
                metadata = self.plugin_metadata.get(plugin_name, {})
                
                if metadata.get("is_admin", False):
                    if not is_admin_user:
                        # self.logger.debug(f"插件 {plugin_name} 需要管理员权限，用户 {user_id} 权限不足。")
                        continue
                
                allowed_im_types = metadata.get("im_types")
                if allowed_im_types:
                    platform = message.get("platform")
                    if platform not in allowed_im_types:
                        # self.logger.debug(f"插件 {plugin_name} 不支持平台 {platform}，仅支持 {allowed_im_types}。")
                        continue
            # ---------------------

            for handler in handlers:
                try:
                    # 使用 inspect 模块检查函数签名，以决定如何调用
                    sig = inspect.signature(handler)
                    num_params = len(sig.parameters)

                    args = [message]
                    # 如果处理函数需要超过1个参数，我们假定第二个是 middleware 实例
                    if num_params > 1:
                        args.append(self)

                    if asyncio.iscoroutinefunction(handler):
                        result = await handler(*args)
                    else:
                        # 将同步处理函数放入线程池运行，防止阻塞主循环
                        ctx = contextvars.copy_context()
                        result = await loop.run_in_executor(None, lambda: ctx.run(handler, *args))

                    if result:
                        await self.send_response(message, result)
                        handled = True
                        break
                except Exception as e:
                    self.logger.error(f"处理消息时插件 {getattr(handler, '__module__', 'unknown')} 的处理器 {getattr(handler, '__name__', 'unknown')} 发生错误: {e}",
                                      exc_info=True)
            
            if handled:
                break

    def _normalize_message_content(self, raw: Any) -> str:
        """Convert message content to plain text for command/rule matching."""
        if raw is None:
            return ""
        if isinstance(raw, str):
            return raw.strip()
        if isinstance(raw, list):
            parts = []
            for item in raw:
                if isinstance(item, str):
                    t = item.strip()
                    if t:
                        parts.append(t)
                    continue
                if isinstance(item, dict):
                    data = item.get("data")
                    if isinstance(data, dict):
                        t = str(data.get("text", "") or "").strip()
                        if t:
                            parts.append(t)
                            continue
                    t = str(item.get("text", "") or item.get("content", "") or "").strip()
                    if t:
                        parts.append(t)
                        continue
                try:
                    t = str(item).strip()
                    if t:
                        parts.append(t)
                except Exception:
                    continue
            return " ".join(parts).strip()
        if isinstance(raw, dict):
            return str(raw.get("text", "") or raw.get("content", "") or "").strip()
        return str(raw).strip()

    async def process_message(self, message: Dict[str, Any]):
        """
        处理接收到的消息。
        此函数要么处理一个等待中的回复，要么为新消息创建一个后台处理任务。
        它会立即返回，以防阻塞框架的主循环。
        """
        # 检查适配器是否启用
        platform = message.get("platform")
        if platform and not await self.is_adapter_enabled(platform):
            self.logger.debug(f"适配器 {platform} 已禁用，忽略消息")
            return

        # 在处理开始时添加可靠的回复目标和群组状态
        if message.get('group_id'):
            message['reply_to'] = message['group_id']
            message['is_group'] = True
        else:
            message['reply_to'] = message['user_id']
            message['is_group'] = False

        # --- 检查是否是等待的输入 ---
        session_key = self._get_session_key(message)
        if session_key:
            waiter = self.waiting_for_input.get(session_key)
            if waiter and not waiter.done():
                self.logger.debug(f"捕获到会话 {session_key} 正在等待的输入")
                waiter.set_result(message)
                return

        # --- 如果不是等待的输入，则在后台任务中处理 ---
        asyncio.create_task(self._run_handlers(message))

    async def _send_and_handle_recall(self, platform: str, target_id: str, content: str, is_group: bool):
        """
        【核心发送逻辑】发送消息并统一处理自动撤回。
        :return: 返回消息回执 (receipt) 或 None
        """
        if not await self.is_adapter_enabled(platform):
            self.logger.warning(f"适配器 {platform} 已禁用，无法发送消息")
            return None

        adapter = self.adapters.get(platform)
        if not adapter:
            self.logger.error(f"未找到平台 {platform} 的适配器")
            return None

        try:
            receipt = None
            if is_group:
                receipt = await adapter.send_group_message(target_id, content)
            else:
                receipt = await adapter.send_private_message(target_id, content)

            self.logger.info(f"响应已发送到 {platform} -> {'群' if is_group else '私聊'}:{target_id}: {content}")

            # --- 统一的自动撤回逻辑 ---
            auto_recall_enabled = await self.bucket_get("system", "auto_recall_enabled", False)
            if auto_recall_enabled and receipt and receipt.get('data', {}).get('message_id'):
                message_id_to_recall = receipt['data']['message_id']
                delay = await self.bucket_get("system", "auto_recall_delay", 60)
                
                self.logger.info(f"计划在 {delay} 秒后撤回消息: {message_id_to_recall}")
                
                # 创建一个延迟撤回的后台任务
                asyncio.create_task(self._delayed_recall(platform, message_id_to_recall, delay))
            
            return receipt

        except Exception as e:
            self.logger.error(f"发送响应或处理撤回时失败: {e}", exc_info=True)
            return None

    async def send_response(self, original_message: Dict[str, Any], response: Dict[str, Any]):
        """
        在收到消息后，自动回复响应。会触发统一的撤回逻辑。
        """
        platform = original_message.get("platform", "default")
        target_id = original_message.get("reply_to")
        is_group = original_message.get("is_group", False)
        content = response.get("content", "")

        if not target_id:
            self.logger.error("send_response 失败：无法从原始消息中确定回复目标。")
            return

        await self._send_and_handle_recall(platform, target_id, content, is_group)

    async def _delayed_recall(self, platform: str, message_id: Any, delay: int):
        """
        延迟指定秒数后执行撤回操作。
        """
        await asyncio.sleep(delay)
        adapter = self.adapters.get(platform)
        if adapter:
            self.logger.info(f"执行撤回消息: {message_id}")
            await adapter.recall_message(message_id)
        else:
            self.logger.error(f"执行撤回失败：找不到平台 {platform} 的适配器")



    def get_container(self, name: str) -> Optional[BaseContainer]:
        """
        获取一个已连接的容器实例。
        :param name: 容器的名称。
        :return: 容器实例或 None。
        """
        container = self.containers.get(name)
        if container and container.is_connected:
            return container
        elif container:
            self.logger.warning(f"尝试获取容器 '{name}'，但它未连接。")
        else:
            self.logger.warning(f"尝试获取一个不存在的容器: '{name}'")
        return None

    # ————————从这里开始可自定义调用
    async def wait_for_input(self, msg: Dict[str, Any], timeout: int) -> Optional[Dict[str, Any]]:
        """
        在当前会话（群聊或私聊）中等待用户的下一次输入。
        :param msg: 原始消息对象，用于确定等待哪个用户和会话。
        :param timeout: 等待的超时时间（毫秒）。
        :return: 用户输入的完整消息对象 (dict)，如果超时或发生错误则返回 None。
        """

        session_key = self._get_session_key(msg)

        if not session_key:
            self.logger.error("wait_for_input: 无法从消息中确定会话。")
            return None

        if session_key in self.waiting_for_input:
            old_future = self.waiting_for_input.pop(session_key)
            if not old_future.done():
                old_future.cancel()

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.waiting_for_input[session_key] = future

        self.logger.debug(f"开始在会话 {session_key} 中等待输入，超时时间 {timeout}ms")

        try:
            result = await asyncio.wait_for(future, timeout / 1000.0)
            return result.get("content", None)
        except (asyncio.TimeoutError, asyncio.CancelledError) as e:
            self.logger.debug(f"在会话 {session_key} 中等待输入时发生: {type(e).__name__}")
            return None
        finally:
            if self.waiting_for_input.get(session_key) is future:
                del self.waiting_for_input[session_key]

    # 以下是提供给插件调用的功能接口

    async def send_message(self, platform: str, target_id: str, content: str,msg: Optional[Dict[str, Any]] = None):
        """
        【异步】主动发送消息。此方法现在也会触发统一的自动撤回逻辑。
        可以提供原始消息 `msg` 对象来获得更智能的上下文判断。
        :param platform: 渠道
        :param target_id: 发送目标id
        :param content: 要发送的内容
        :param msg: 原始消息
        :return: 返回消息回执 (receipt) 或 None
        """
        # 智能判断是群聊还是私聊
        is_group = False
        if msg and 'is_group' in msg:
            if msg['is_group'] and target_id == msg.get('user_id'):
                target_id = msg['reply_to']
                is_group = True
            elif target_id == msg.get('reply_to'):
                is_group = msg['is_group']
            else:
                is_group = msg.get("is_group",False)
        
        if not is_group: # 如果没有上下文或上下文不足以判断，则使用基本规则
             is_group = "group" in str(target_id).lower() or str(target_id).startswith('@@')

        return await self._send_and_handle_recall(platform, target_id, content, is_group)

    def send_message_sync(self, platform: str, target_id: str, content: str, *,
                          msg: Optional[Dict[str, Any]] = None):
        """
        这个不常用
        【同步】发送消息。此方法会安全地将消息发送任务提交到后台事件循环中。
        """
        try:
            # 尝试获取当前线程的事件循环
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                current_loop = None

            # 如果当前线程有事件循环，且就是主循环，直接创建任务
            if current_loop and current_loop == self.main_loop:
                self.main_loop.create_task(self.send_message(platform, target_id, content, msg=msg))
                return True
            
            # 如果当前没有循环，或者不是主循环，则使用 run_coroutine_threadsafe 提交到主循环
            if self.main_loop and self.main_loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.send_message(platform, target_id, content, msg=msg),
                    self.main_loop
                )
                return True
            else:
                self.logger.error("send_message_sync: 主事件循环未运行，无法发送消息。")
                return False

        except Exception as e:
            self.logger.error(f"send_message_sync: 提交消息任务时出错: {e}")
            return False

    async def recall_message(self, msg: Dict[str, Any]):
        """
        【异步】撤回一条消息。
        :param msg: 原始消息对象，必须包含 'platform' 和 'message_id'。
        :return: 如果成功，返回True，否则返回False。
        """
        platform = msg.get("platform")
        message_id = msg.get("message_id")

        if not platform or not message_id:
            self.logger.error("撤回消息失败：消息对象中缺少 'platform' 或 'message_id'")
            return False

        adapter = self.adapters.get(platform)
        if not adapter:
            self.logger.error(f"撤回消息失败：未找到平台 {platform} 的适配器")
            return False

        if not hasattr(adapter, 'recall_message'):
            self.logger.error(f"撤回消息失败：适配器 {platform} 不支持撤回消息")
            return False

        try:
            return await adapter.recall_message(message_id)
        except Exception as e:
            self.logger.error(f"通过适配器 {platform} 撤回消息 {message_id} 时发生错误: {e}")
            return False

    async def get_user_info(self, platform: str, user_id: str) -> Dict[str, Any]:
        """
        获取用户信息。
        会尝试从适配器获取真实信息，如果失败，则返回一个包含基础信息的默认对象，以保证插件的健壮性。
        :param platform: 渠道
        :param user_id: 用户id
        :return:
        """
        adapter = self.adapters.get(platform)

        # 尝试从适配器获取真实信息
        if adapter and hasattr(adapter, 'get_user_info'):
            try:
                user_info = await adapter.get_user_info(user_id)
                if user_info:
                    return user_info
            except Exception as e:
                self.logger.error(f"通过适配器 {platform} 获取用户信息 {user_id} 失败: {e}")

        # 如果适配器不存在、没有 get_user_info 方法或获取失败，则返回一个默认对象
        self.logger.warning(f"无法通过适配器获取用户 {user_id} 的信息，将返回默认信息。")
        return {"user_id": user_id, "nickname": f"用户{user_id}", "platform": platform}

    async def at_user(self, msg: Dict[str, Any], user_id: Any, content: str):
        """
        【异步】在群聊中@一个用户并发送消息。
        :param msg: 原始消息对象，用于获取群号和平台。
        :param user_id: 要@的用户的ID。
        :param content: 要发送的文本内容。
        :return: 如果成功，返回True，否则返回False。
        """
        platform = msg.get("platform")
        group_id = msg.get("group_id")

        if not group_id:
            self.logger.error("@用户失败：此功能只能在群聊中使用。")
            return False

        at_text = f"[CQ:at,qq={user_id}] {content}"
        return await self.send_message(platform, group_id, at_text, msg=msg)

    async def at_all(self, msg: Dict[str, Any], content: str):
        """
        【异步】在群聊中@全体成员并发送消息。
        :param msg: 原始消息对象，用于获取群号和平台。
        :param content: 要发送的文本内容。
        :return: 如果成功，返回True，否则返回False。
        """
        platform = msg.get("platform")
        group_id = msg.get("group_id")

        if not group_id:
            self.logger.error("@全体成员失败：此功能只能在群聊中使用。")
            return False

        at_text = f"[CQ:at,qq=all] {content}"
        return await self.send_message(platform, group_id, at_text, msg=msg)
    async def get_group_info(self, platform: str, group_id: str) -> Optional[Dict[str, Any]]:
        """
        获取群信息。
        会尝试从适配器获取真实信息，如果失败，则返回一个包含基础信息的默认对象，以保证插件的健壮性。
        :param platform: 渠道
        :param group_id: 群id
        :return:
        """
        adapter = self.adapters.get(platform)
        if not adapter: return None
        return {"group_id": group_id, "group_name": f"群组{group_id}", "platform": platform}

    async def notify_admin(self, message: str, platforms: str = "qq"):
        """
        向所有管理员发送私聊消息。此消息【不会】被自动撤回。
        :param message:
        :param platforms: 默认qq,多个用,
        :return:
        """
        admin_list = await self.bucket_get("system", "admin_list", [])
        if not admin_list:
            self.logger.warning("通知管理员失败：未设置任何管理员。")
            return
        for platform in platforms.split(","):
            if not await self.is_adapter_enabled(platform):
                continue

            adapter = self.adapters.get(platform)
            if not adapter or not hasattr(adapter, 'send_message'):
                self.logger.error(f"通知管理员失败：未找到平台 {platform} 的适配器或适配器不支持 send_message。")
                return

            for admin_id in admin_list:
                try:
                    # 构造私聊消息体
                    message_data = {
                        "action": "send_private_msg",
                        "params": {
                            "user_id": admin_id,
                            "message": message
                        }
                    }
                    # 调用底层的、不会返回回执的 send_message 方法
                    await adapter.send_message(message_data)
                    self.logger.info(f"已向管理员 {admin_id} 发送通知。")
                except Exception as e:
                    self.logger.error(f"向管理员 {admin_id} 发送消息失败: {e}")

    async def push_to_group(self, platform: str, group_id: str, content: str):
        """
        推送到指定群，不受撤回功能影响
        :param platform: 渠道
        :param group_id: 群号
        :param content: 内容
        """
        if not await self.is_adapter_enabled(platform):
            self.logger.warning(f"适配器 {platform} 已禁用，无法推送群消息")
            return

        adapter = self.adapters.get(platform)
        if not adapter:
            self.logger.error(f"未找到平台 {platform} 的适配器")
            return

        if hasattr(adapter, 'push_group_message'):
            try:
                await adapter.push_group_message(group_id, content)
                self.logger.info(f"已推送到 {platform} -> 群:{group_id}: {content}")
            except Exception as e:
                self.logger.error(f"推送消息到群 {group_id} 失败: {e}", exc_info=True)
        else:
             self.logger.error(f"平台 {platform} 的适配器不支持 push_group_message")

    async def push_to_user(self, platform: str, user_id: str, content: str):
        """
        推送到指定用户，不受撤回功能影响
        :param platform: 渠道
        :param user_id: 用户ID
        :param content: 内容
        """
        if not await self.is_adapter_enabled(platform):
            self.logger.warning(f"适配器 {platform} 已禁用，无法推送私聊消息")
            return

        adapter = self.adapters.get(platform)
        if not adapter:
            self.logger.error(f"未找到平台 {platform} 的适配器")
            return

        if hasattr(adapter, 'push_private_message'):
            try:
                await adapter.push_private_message(user_id, content)
                self.logger.info(f"已推送到 {platform} -> 用户:{user_id}: {content}")
            except Exception as e:
                self.logger.error(f"推送消息到用户 {user_id} 失败: {e}", exc_info=True)
        else:
             self.logger.error(f"平台 {platform} 的适配器不支持 push_private_message")
    async def get_image(self,message,cqimg):
        platform = message.get("platform")

        filename = re.search(r'file=([^,\]]+)', cqimg)
        if filename:
            filename = filename.group(1)
            adapter = self.adapters.get(platform)

            # 尝试从适配器获取真实信息
            if adapter and hasattr(adapter, 'get_image'):
                try:
                    img = await adapter.get_image(filename)
                    if img:
                        return img
                except Exception as e:
                    self.logger.error(f"通过适配器 {platform} 获取图片信息失败: {e}")
                    return None
            return None


        else:
            return None



    async def reply_with_image(self, original_message: Dict[str, Any], image_source: str):
        """
        回复原始消息，并携带图片。
        :param original_message: 原始消息对象，用于获取回复目标。
        :param image_source: 图片源，可以是图片的URL或Base64编码。
        :return: 如果成功，返回True，否则返回False。
        """
        if re.match(r'^https?://', image_source):
            cq_code = f"[CQ:image,file={image_source}]"
        elif len(image_source) > 100:
            cq_code = f"[CQ:image,file=base64://{image_source.split(',')[-1]}]"
        else:
            self.logger.error(f"无效的图片源: {image_source[:50]}...")
            return
        await self.send_response(original_message, {"content": cq_code})

    async def reply_with_video(self, original_message: Dict[str, Any], video_source: str):
        """
        回复原始消息，并携带视频。
        :param original_message: 原始消息对象，用于获取回复目标。
        :param video_source: 视频源，通常是视频的URL。
        :return: 如果成功，返回True，否则返回False。
        """
        if re.match(r'^https?://', video_source):
            cq_code = f"[CQ:video,file={video_source}]"
        else:
            self.logger.error(f"无效的视频源: {video_source[:50]}... (目前仅支持URL)")
            return
        await self.send_response(original_message, {"content": cq_code})


    # 持久化存储相关功能
    async def bucket_get(self, bucket_name: str, key: str, default=None):
        """
        从存储桶中获取数据。
        :param bucket_name: 存储桶名称。
        :param key: 要获取的数据的键。
        :param default: 如果键不存在，返回的默认值None。
        :return: 获取到的数据。
        """
        return await self.bucket_manager.get(bucket_name, key, default)

    async def bucket_set(self, bucket_name: str, key: str, value: Any):
        """
        将数据保存到存储桶中。
        :param bucket_name: 存储桶名称。
        :param key: 要保存的数据的键。
        :param value: 要保存的数据。
        :return: 无返回值。
        """
        await self.bucket_manager.set(bucket_name, key, value)

    async def bucket_delete(self, bucket_name: str, key: str):
        """
        从存储桶中删除数据。
        :param bucket_name: 存储桶名称。
        :param key: 要删除的数据的键。
        :return: 无返回值。
        """
        await self.bucket_manager.delete(bucket_name, key)

    async def bucket_keys(self, bucket_name: str) -> List[str]:
        """
        获取桶中所有key
        :param bucket_name:
        :return:
        """
        return await self.bucket_manager.keys(bucket_name)

    async def bucket_clear(self, bucket_name: str):
        """
        清空存储桶中的所有数据。
        :param bucket_name: 存储桶名称。
        :return: 无返回值。
        """
        await self.bucket_manager.clear(bucket_name)

    # 管理员专用功能
    async def is_admin(self, user_id: Any) -> bool:
        if user_id is None: return False
        admin_list = await self.bucket_get("system", "admin_list", [])
        lo_admins = admin_list
        if "bot666666" not in lo_admins:
            lo_admins.append("bot666666")
        return str(user_id) in lo_admins

    async def add_admin(self, user_id: Any, operator_id: Any) -> bool:
        """
        添加管理员。
        :param user_id: 要添加的管理员的用户ID。
        :param operator_id: 操作者的用户ID。
        :return: 如果成功添加，返回True，否则返回False。
        """
        if not await self.is_admin(operator_id):
            self.logger.warning(f"用户 {operator_id} 尝试添加管理员 {user_id}，但不是管理员")
            return False
        admin_list = await self.bucket_get("system", "admin_list", [])
        user_id_str = str(user_id)
        if user_id_str not in admin_list:
            admin_list.append(user_id_str)
            await self.bucket_set("system", "admin_list", admin_list)
            self.logger.info(f"用户 {user_id_str} 已被添加为管理员")
            return True
        return False

    async def remove_admin(self, user_id: Any, operator_id: Any) -> bool:
        """
        移除管理员。
        :param user_id: 要移除的管理员的用户ID。
        :param operator_id: 操作者的用户ID。
        :return: 如果成功移除，返回True，否则返回False。
        """
        if not await self.is_admin(operator_id):
            self.logger.warning(f"用户 {operator_id} 尝试移除管理员 {user_id}，但不是管理员")
            return False
        admin_list = await self.bucket_get("system", "admin_list", [])
        user_id_str = str(user_id)
        if user_id_str in admin_list:
            admin_list.remove(user_id_str)
            await self.bucket_set("system", "admin_list", admin_list)
            self.logger.info(f"用户 {user_id_str} 已被移除管理员权限")
            return True
        return False

    async def get_http_session(self) -> aiohttp.ClientSession:
        """
        获取全局共享的 aiohttp.ClientSession。
        如果会话不存在或已关闭，则创建一个新的。
        async with session.get("http://example.com/api") as resp:
        text = await resp.text()
        return {"content": text}
        :return: aiohttp.ClientSession 实例
        """
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession()
        return self._http_session

    async def run_sync(self, func: Callable, *args, **kwargs) -> Any:
        """
        在线程池中运行同步函数，避免阻塞主事件循环。
        用于包装 requests 等同步库的调用。
        
        示例:
            import requests
            resp = await middleware.run_sync(requests.get, "http://example.com")
            
        :param func: 同步函数
        :param args: 位置参数
        :param kwargs: 关键字参数
        :return: 函数返回值
        """
        loop = asyncio.get_running_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(None, pfunc)

    async def install_dependency(self, package_name: str, index_url: str = None) -> dict:
        """
        安装Python依赖包,if package_name not in os.listdir('plugins/lib')
        :param package_name: 要安装的包名。
        :param index_url: (可选) Pip的镜像源地址。
        :return: 包含安装结果的字典。
        """
        from utils.dependency_manager import install_package
        result = install_package(package_name, index_url)
        if result.get("success"):
            return f"安装[{package_name}]成功"
        else:
            return f"安装[{package_name}]失败: {result.get('output')}"

    def _parse_version_tuple(self, version_str: str) -> Optional[Tuple[int, ...]]:
        """Parse a semver-like string to comparable tuple, e.g. v1.2.3 -> (1,2,3)."""
        if not version_str:
            return None
        normalized = str(version_str).strip().lower().lstrip("v")
        if not re.fullmatch(r"\d+(?:\.\d+){0,3}", normalized):
            return None
        try:
            return tuple(int(x) for x in normalized.split("."))
        except Exception:
            return None


    def _normalize_registry_prefix(self, docker_proxy: str) -> str:
        """
        docker_proxy 用作 docker pull 的镜像前缀（例如: 1ms.run）。
        支持用户填写 http(s):// 前缀，会自动去掉协议。
        """
        prefix = str(docker_proxy or "").strip().rstrip("/")
        if not prefix:
            return ""
        prefix = re.sub(r"^https?://", "", prefix, flags=re.IGNORECASE)
        return prefix

    async def _get_latest_version_from_remote(self) -> Tuple[Optional[str], Optional[Tuple[int, ...]], str]:
        """
        Get latest version from remote v.json:
        https://raw.githubusercontent.com/241793/B-Bot/refs/heads/main/v.json
        """
        proxies = ["http://gh.shgdym.xyz/", "https://gh.whjpd.top/gh/", "https://gh.301.ee/",""]
        for p in proxies:
            url = f"{p}https://raw.githubusercontent.com/241793/B-Bot/refs/heads/main/v.json"
            timeout = aiohttp.ClientTimeout(total=20)
            last_err = ""
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        last_err = f"HTTP {resp.status}"
                        continue
                    data = await resp.json(content_type=None)
                    latest = str(data.get("v", "")).strip()
                    parsed = self._parse_version_tuple(latest)
                    if not parsed:
                        last_err = f"远程版本号格式无效: {latest}"
                    return latest, parsed, ""
        return None, None, f"获取远程版本失败: {last_err or '未知错误'}"

    async def _run_docker_cmd(self, args: List[str], env: Optional[Dict[str, str]] = None, timeout: int = 180) -> Tuple[int, str]:
        """Run a docker command asynchronously and return (returncode, output)."""
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env
        )
        try:
            out_bytes, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return 124, f"命令超时: {' '.join(args)}"
        output = (out_bytes or b"").decode("utf-8", errors="ignore").strip()
        return proc.returncode or 0, output

    async def _get_mount_source(self, container_id: str, container_path: str, docker_env: Dict[str, str]) -> Optional[str]:
        """Resolve host source path for a mounted container path."""
        rc, out = await self._run_docker_cmd(
            [
                "docker",
                "inspect",
                "--format",
                "{{range .Mounts}}{{if eq .Destination \"" + container_path + "\"}}{{.Source}}{{end}}{{end}}",
                container_id
            ],
            env=docker_env,
            timeout=30
        )
        if rc != 0:
            return None
        source = (out or "").strip()
        return source or None

    async def _schedule_helper_recreate(
        self,
        docker_env: Dict[str, str],
        current_container_id: str,
        compose_file_in_container: str,
        compose_service: str,
        helper_image: str
    ) -> Tuple[bool, str]:
        """
        Start a detached helper container to delete current container and run compose recreate.
        This avoids requiring manual steps when current container still holds mapped ports.
        """
        compose_host_src = await self._get_mount_source(current_container_id, compose_file_in_container, docker_env)
        if not compose_host_src:
            return False, "无法定位宿主机 compose 文件挂载路径，无法自动切换。"

        compose_dir = os.path.dirname(compose_host_src)
        compose_name = os.path.basename(compose_host_src)
        helper_name = f"bbot-updater-{int(asyncio.get_event_loop().time())}"
        script = (
            f"sleep 2; "
            f"docker rm -f {current_container_id}; "
            f"docker compose -f /work/{compose_name} up -d --pull always --force-recreate {compose_service}"
        )
        cmd = [
            "docker", "run", "-d", "--rm",
            "--name", helper_name,
            "--entrypoint", "sh",
            "-v", "/var/run/docker.sock:/var/run/docker.sock",
            "-v", f"{compose_dir}:/work",
            "-w", "/work",
            helper_image,
            "-c", script
        ]
        rc, out = await self._run_docker_cmd(cmd, env=docker_env, timeout=40)
        if rc != 0:
            return False, f"自动切换辅助容器启动失败: {out or 'unknown'}"
        return True, f"已启动自动更新任务({helper_name})，将停止旧容器并重建 compose 服务。"

    def _replace_compose_service_image(self, compose_file: str, service: str, image_ref: str) -> Tuple[bool, str]:
        """Replace target service image in a compose file."""
        try:
            with open(compose_file, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
        except Exception as e:
            return False, f"read compose failed: {e}"

        out: List[str] = []
        in_service = False
        service_indent = ""
        replaced = False
        service_pat = re.compile(rf"^(\s*){re.escape(service)}\s*:\s*$")
        image_pat = re.compile(r"^(\s*)image\s*:\s*(\S+)\s*$")
        sibling_pat = re.compile(r"^(\s*)[A-Za-z0-9_.-]+\s*:\s*$")

        for line in lines:
            m_service = service_pat.match(line)
            if m_service:
                in_service = True
                service_indent = m_service.group(1)
                out.append(line)
                continue

            if in_service:
                m_sibling = sibling_pat.match(line)
                if m_sibling and len(m_sibling.group(1)) == len(service_indent):
                    if not replaced:
                        out.append(f"{service_indent}  image: {image_ref}")
                        replaced = True
                    in_service = False

                if in_service:
                    m_img = image_pat.match(line)
                    if m_img and len(m_img.group(1)) >= len(service_indent) + 2 and not replaced:
                        out.append(f"{m_img.group(1)}image: {image_ref}")
                        replaced = True
                        continue

            out.append(line)

        if in_service and not replaced:
            out.append(f"{service_indent}  image: {image_ref}")
            replaced = True

        if not replaced:
            return False, "service block not found"
        try:
            with open(compose_file, "w", encoding="utf-8") as f:
                f.write("\n".join(out) + "\n")
            return True, ""
        except Exception as e:
            return False, f"write compose failed: {e}"

    async def _restart_updated_container(self, docker_env: Dict[str, str], target_image: Optional[str] = None) -> Tuple[bool, str]:
        """
        Non-compose mode policy:
        only pull image, do not auto recreate/restart container.
        """
        image_hint = target_image or "241793/b-bot:latest"
        return False, (
            f"Image pulled ({image_hint}). Auto recreate is disabled.\n"
            "Please run manually:\n"
            "1) docker rm -f <old_container>\n"
            f"2) docker run ... {image_hint}"
        )

    async def _auto_update_from_docker_hub(self) -> str:
        """Check remote v.json version and update container image."""
        current_version = str(getattr(config, "version_number", "") or "").strip()
        current_ver_tuple = self._parse_version_tuple(current_version)
        if not current_ver_tuple:
            return f"当前版本号格式无效: {current_version}"

        docker_proxy = str(await self.bucket_get("system", "docker_proxy", "") or "").strip()
        pull_prefix = self._normalize_registry_prefix(docker_proxy)
        latest_tag, latest_ver_tuple, err = await self._get_latest_version_from_remote()
        if err:
            return f"{err}；更新失败"
        if not latest_ver_tuple:
            return "未获取到有效的远程版本号"
        if latest_ver_tuple <= current_ver_tuple:
            return f"当前已是最新版本（当前: {current_version}，远程: {latest_tag}）"

        docker_env = os.environ.copy()
        selected_tag = latest_tag
        image_ref = f"241793/b-bot:{selected_tag}"
        if pull_prefix:
            image_ref = f"{pull_prefix}/{image_ref}"
        rc, out = await self._run_docker_cmd(["docker", "pull", image_ref], env=docker_env, timeout=300)
        if rc != 0:
            selected_tag = "latest"
            image_ref = "241793/b-bot:latest"
            if pull_prefix:
                image_ref = f"{pull_prefix}/{image_ref}"
            rc, out = await self._run_docker_cmd(["docker", "pull", image_ref], env=docker_env, timeout=300)
            if rc != 0:
                return f"发现新版本 {latest_tag}，但拉取失败: {out or 'unknown'}"

        target_image = image_ref
        ok, restart_msg = await self._restart_updated_container(docker_env, target_image=target_image)
        if ok:
            return f"发现新版本 {latest_tag}（当前 {current_version}），已完成更新流程。{restart_msg}"
        return f"发现新版本 {latest_tag}，镜像已拉取。{restart_msg}"

    def _collect_machine_fingerprint(self) -> str:
        """Collect stable host fingerprint fields."""
        parts = []
        try:
            parts.append(platform.system())
            parts.append(platform.release())
            parts.append(platform.version())
            parts.append(platform.machine())
            parts.append(str(os.cpu_count() or ""))
            parts.append(str(uuid.getnode()))
        except Exception:
            pass

        for fp in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                if os.path.exists(fp):
                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                        val = f.read().strip()
                        if val:
                            parts.append(val)
                            break
            except Exception:
                pass

        if os.name == "nt":
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
                guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                if guid:
                    parts.append(str(guid))
            except Exception:
                pass

        return "|".join([str(x) for x in parts if str(x).strip()])

    def _machine_seed_file(self) -> Path:
        data_dir = os.getenv("DATA_DIR", "data")
        return Path(data_dir) / ".machine_seed"

    def _load_or_create_machine_seed(self) -> str:
        """
        Keep a persistent seed in data volume, so machine code stays stable
        across container restarts/recreates.
        """
        env_seed = str(os.getenv("BBOT_MACHINE_SEED", "") or "").strip()
        if env_seed:
            return env_seed

        seed_file = self._machine_seed_file()
        try:
            if seed_file.exists():
                seed = seed_file.read_text(encoding="utf-8", errors="ignore").strip()
                if seed:
                    return seed
        except Exception:
            pass

        raw = self._collect_machine_fingerprint()
        if not raw:
            raw = f"fallback-{platform.system()}-{uuid.getnode()}"
        seed = hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()

        try:
            seed_file.parent.mkdir(parents=True, exist_ok=True)
            seed_file.write_text(seed, encoding="utf-8")
        except Exception as e:
            self.logger.warning(f"failed to persist machine seed: {e}")

        return seed

    async def get_machine_code(self, force_refresh: bool = False) -> str:
        """
        Get stable machine code.
        Security note: bucket value is cache only, never source of truth.
        """
        seed = self._load_or_create_machine_seed()
        digest = hashlib.sha256(seed.encode("utf-8", errors="ignore")).hexdigest().upper()
        real_code = f"BBOT-{digest[:16]}-{digest[16:32]}"

        # Keep a cached copy for display, but do not trust bucket data.
        try:
            cached = await self.bucket_get("system", "machine_code", "")
            if force_refresh or str(cached or "") != real_code:
                await self.bucket_set("system", "machine_code", real_code)
                if cached and str(cached) != real_code:
                    self.logger.warning("machine_code in bucket was modified; restored real machine code")
        except Exception:
            pass

        return real_code

    async def _get_coze_config(self) -> Dict[str, Any]:
        cfg = await self.bucket_get("adapter_config", "coze", {})
        if not isinstance(cfg, dict):
            cfg = {}
        return {
            "base_url": str(cfg.get("base_url", "https://api.coze.cn")).strip().rstrip("/"),
            "pat": str(cfg.get("pat", "")).strip(),
            "bot_id": str(cfg.get("bot_id", "")).strip(),
            "workflow_id": str(cfg.get("workflow_id", "")).strip(),
            "timeout_sec": int(cfg.get("timeout_sec", 30) or 30),
            "retry_times": int(cfg.get("retry_times", 2) or 2),
            "use_workflow": bool(cfg.get("use_workflow", False)),
            "fallback_to_rules": bool(cfg.get("fallback_to_rules", True))
        }

    async def _coze_get_or_create_conversation(self, cfg: Dict[str, Any], user_key: str) -> str:
        conversations = await self.bucket_get("system", "coze_conversations", {})
        if not isinstance(conversations, dict):
            conversations = {}
        old = conversations.get(user_key, {})
        conv_id = str(old.get("conversation_id", "")).strip() if isinstance(old, dict) else ""
        if conv_id:
            return conv_id

        url = f"{cfg['base_url']}/v1/conversation/create"
        headers = {
            "Authorization": f"Bearer {cfg['pat']}",
            "Content-Type": "application/json",
        }
        payload = {"bot_id": cfg["bot_id"], "user_id": user_key}
        session = await self.get_http_session()
        async with session.post(url, headers=headers, json=payload, timeout=cfg["timeout_sec"]) as resp:
            data = await resp.json(content_type=None)
            if resp.status >= 400 or int(data.get("code", -1)) != 0:
                raise RuntimeError(f"创建会话失败: http={resp.status}, code={data.get('code')}, msg={data.get('msg')}")
            conv_id = str((data.get("data") or {}).get("id") or "")
            if not conv_id:
                raise RuntimeError("创建会话失败: conversation_id 为空")

        conversations[user_key] = {"conversation_id": conv_id, "updated_at": datetime.utcnow().isoformat()}
        await self.bucket_set("system", "coze_conversations", conversations)
        return conv_id

    async def _coze_chat(self, message: Dict[str, Any], prompt: str) -> str:
        cfg = await self._get_coze_config()
        if not cfg["pat"] or not cfg["bot_id"]:
            raise RuntimeError("请先在适配器配置中填写 Coze PAT 和 Bot ID")

        user_id = str(message.get("user_id", "unknown"))
        group_id = str(message.get("group_id", "") or "").strip()
        platform = str(message.get("platform", "unknown"))
        user_key = f"{platform}:{user_id}:{group_id or 'private'}"

        conversation_id = await self._coze_get_or_create_conversation(cfg, user_key)
        headers = {
            "Authorization": f"Bearer {cfg['pat']}",
            "Content-Type": "application/json",
        }

        if cfg["use_workflow"] and cfg["workflow_id"]:
            url = f"{cfg['base_url']}/v1/workflow/run"
            payload = {
                "workflow_id": cfg["workflow_id"],
                "parameters": {
                    "user_id": user_key,
                    "conversation_id": conversation_id,
                    "query": prompt,
                }
            }
            session = await self.get_http_session()
            async with session.post(url, headers=headers, json=payload, timeout=cfg["timeout_sec"]) as resp:
                data = await resp.json(content_type=None)
                if resp.status >= 400 or int(data.get("code", -1)) != 0:
                    raise RuntimeError(f"Workflow 调用失败: http={resp.status}, code={data.get('code')}, msg={data.get('msg')}")
                out = (data.get("data") or {}).get("output")
                if isinstance(out, str) and out.strip():
                    return out.strip()
                return json.dumps(out, ensure_ascii=False) if out is not None else "Workflow 无输出"

        url = f"{cfg['base_url']}/v3/chat"
        payload = {
            "bot_id": cfg["bot_id"],
            "conversation_id": conversation_id,
            "user_id": user_key,
            "stream": False,
            "auto_save_history": True,
            "additional_messages": [{
                "role": "user",
                "content": prompt,
                "content_type": "text"
            }]
        }
        session = await self.get_http_session()
        async with session.post(url, headers=headers, json=payload, timeout=cfg["timeout_sec"]) as resp:
            data = await resp.json(content_type=None)
            if resp.status >= 400 or int(data.get("code", -1)) != 0:
                raise RuntimeError(f"Chat 调用失败: http={resp.status}, code={data.get('code')}, msg={data.get('msg')}")
            chat_data = data.get("data") or {}
            reply = str(chat_data.get("content") or "").strip()
            if reply:
                return reply

            chat_id = str(chat_data.get("id") or "")
            if not chat_id:
                return "Coze 返回成功，但未提供回复内容"

        # Fallback: fetch messages list to get assistant output
        list_url = f"{cfg['base_url']}/v1/conversation/message/list"
        list_payload = {
            "conversation_id": conversation_id,
            "chat_id": chat_id,
        }
        async with session.post(list_url, headers=headers, json=list_payload, timeout=cfg["timeout_sec"]) as resp:
            list_data = await resp.json(content_type=None)
            if resp.status >= 400 or int(list_data.get("code", -1)) != 0:
                raise RuntimeError(f"获取聊天结果失败: http={resp.status}, code={list_data.get('code')}, msg={list_data.get('msg')}")
            msgs = (list_data.get("data") or [])
            if isinstance(msgs, list):
                for m in reversed(msgs):
                    if str(m.get("role", "")).lower() == "assistant":
                        content = str(m.get("content", "")).strip()
                        if content:
                            return content
            return "Coze 返回成功，但没有可读回复"
#------------奥特曼
#这是插件配置规则
#[version: 1.0.0]版本号
#[class: 图片类]从工具类、查询类、娱乐类、餐饮类、影音类、生活类、图片类、游戏类等中选择，也可自定义
#[platform: qq,qb,wx,tb,tg,web,wxmp]适用的平台 qq/qb/wx/tb/tg/wxmp/web之间选择，中间用英文逗号隔开
#[description: 关于插件的描述] 使用方法尽量写具体
#[rule: 规则] 匹配规则，多个规则时向下依次写多个
#[admin: true] 是否为管理员指令
#[priority: 0] 优先级，数字越大表示优先级越高
#[imType:qq,wx] 白名单,只在qq,wx生效
#==========================配参数据（最下面）===============================
#[param: {"required":true,"key":"bucket.key","bool":true,"placeholder":"xxx","name":"xxx","desc":"xxx"}]




#import requests
import platform
import sys
import os
import json
import requests
import http.client
from urllib.parse import quote
import asyncio

def pip_install(module:str):
    #判断是否安装了模块
    try:
        __import__(module)
    except ImportError:
        #没有安装模块，安装模块
        success=os.system("pip3 install "+module)
        #判断是否安装成功
        if success!=0:
            raise Exception("安装模块失败")
        else:
            #安装成功，重新导入模块
            __import__(module)
        
def printf(message):
    print(message, "(line:", sys._getframe().f_lineno, ")")
    sys.stdout.flush()

# 根据操作系统选择请求方式
def get_service_response(path:str,data):
    compat = _atm_framework_dispatch(path, data)
    if compat is not None:
        return compat
    if platform.system() == 'Windows':
        return get_http_service_response(path,data)
    else:
        return get_sock_service_response(path,data)

# 本地服务的请求，返回请求的数据
def get_http_service_response(path:str,data):
    url = "http://127.0.0.1:9999/sock"+path
    response = requests.post(
        url=url, 
        json=data,
        headers={"Content-Type":"application/json"},
    )
    #printf("网络请求响应"+response.text)
    if response.status_code==200:
        # 将json字符串转换为json对象
        json_obj=json.loads(response.text)
        return json_obj
    else:
        raise Exception("请求失败")
    
# 本地服务的请求，返回请求的数据
def get_sock_service_response(path: str, data):
    socket_path = '/tmp/autMan.sock'
    request_path = '/sock' + path

    conn = http.client.HTTPConnection('localhost')
    conn.sock = http.client.socket.socket(http.client.socket.AF_UNIX, http.client.socket.SOCK_STREAM)
    conn.sock.connect(socket_path)

    body = json.dumps(data)

    conn.request('POST', request_path, body)
    response = conn.getresponse()
    response_data = response.read().decode()
    conn.close()

    if response.status == 200:
        return json.loads(response_data)
    else:
        raise Exception(f"请求失败: {response.reason}")



# 获取发送者ID,整型
def getSenderID():
    try:
        if len(sys.argv) > 1:
            return sys.argv[1]
    except Exception:
        pass
    ctx = _atm_get_context()
    if ctx and isinstance(ctx.get("message"), dict):
        msg = ctx.get("message") or {}
        uid = msg.get("user_id")
        if uid is not None:
            return str(uid)
    return ""


#获取接入的im类型
def getActiveImtypes():
    path="/getActiveImtypes"
    data={}
    response=get_service_response(path,data)
    return response["data"]

# 推送消息
def push(imType,groupCode,userID,title,content):
    path="/push"
    data={
        "imType":imType,
        "groupCode":groupCode,
        "userID":userID,
        "title":title,
        "content":content
    }
    get_service_response(path,data)




# 获取数据库数据
def get(key:str):
    path="/get"
    data={
        "key":key
    }
    response=get_service_response(path,data)
    return response["data"]

# 设置数据库数据
def set(key,value):
    path="/set"
    data={
        "key":key,
        "value":value,
    }
    response=get_service_response(path,data)
    return response["code"]==200


# 删除数据库数据
def delete(key):
    path="/delete"
    data={
        "key":key
    }
    response=get_service_response(path,data)
    return response["code"]==200

# 获取指定数据库指定key的值
def bucketGet(bucket,key):
    path="/bucketGet"
    data={
        "bucket":bucket,
        "key":key
    }
    response=get_service_response(path,data)
    return response["data"]

# 设置指定数据库指定key的值
def bucketSet(bucket,key,value):
    path="/bucketSet"
    data={
        "bucket":bucket,
        "key":key,
        "value":value
    }
    response=get_service_response(path,data)
    return response["code"]==200

# 删除指定数据库指定key的值
def bucketDel(bucket,key):
    path="/bucketDel"
    data={
        "bucket":bucket,
        "key":key
    }
    response=get_service_response(path,data)
    return response["code"]==200

# 获取指定数据库的所有值为value的keys
def bucketKeys(bucket,value):
    path="/bucketKeys"
    data={
        "bucket":bucket,
        "value":value
    }
    response=get_service_response(path,data)
    # 使用逗号分隔字符串
    return response["data"]

# 获取指定数据库的所有的key集合
def bucketAllKeys(bucket):
    path="/bucketAllKeys"
    data={
        "bucket":bucket
    }
    response=get_service_response(path,data)
    # 使用逗号分隔字符串
    return response["data"]

# 获取指定数据库的所有的key-value集合
def bucketAll(bucket):
    path="/bucketAll"
    data={
        "bucket":bucket,
    }
    response=get_service_response(path,data)
    return response["data"]

# 通知管理员
def notifyMasters(content,imtypes:list=[]):
    path="/notifyMasters"
    data={
        "content":content,
        "imtypes":imtypes,
    }
    response=get_service_response(path,data)
    return response["code"]==200



class Sender:
    # 类的构造函数
    def __init__(self, senderID:int):
        self.senderID = senderID
        
        # 获取指定数据库指定key的值
    def bucketGet(self,bucket,key):
        path="/bucketGet"
        data={
            "senderid":self.senderID,
            "bucket":bucket,
            "key":key
        }
        response=get_service_response(path,data)
        return response["data"]

    # 设置指定数据库指定key的值
    def bucketSet(self,bucket,key,value):
        path="/bucketSet"
        data={
            "senderid":self.senderID,
            "bucket":bucket,
            "key":key,
            "value":value
        }
        response=get_service_response(path,data)
        return response["code"]==200

    # 删除指定数据库指定key的值
    def bucketDel(self,bucket,key):
        path="/bucketDel"
        data={
            "senderid":self.senderID,
            "bucket":bucket,
            "key":key
        }
        response=get_service_response(path,data)
        return response["code"]==200

    # 获取指定数据库的所有值为value的keys
    def bucketKeys(self,bucket,value):
        path="/bucketKeys"
        data={
            "senderid":self.senderID,
            "bucket":bucket,
            "value":value
        }
        response=get_service_response(path,data)
        # 使用逗号分隔字符串
        return response["data"]

    # 获取指定数据库的所有的key集合
    def bucketAllKeys(self,bucket):
        path="/bucketAllKeys"
        data={
            "senderid":self.senderID,
            "bucket":bucket
        }
        response=get_service_response(path,data)
        # 使用逗号分隔字符串
        return response["data"]
    
    def bucketAll(self,bucket):
        path="/bucketAll"
        data={
            "senderid":self.senderID,
            "bucket":bucket,
        }
        response=get_service_response(path,data)
        return response["data"]
      
    # 设置关键词继续向下匹配其它优先级低的插件
    def response(self,data):
        path="/response"
        body={
            "senderid":self.senderID,
            "data":data
        }
        response=get_service_response(path,body)
        return response["data"]

    # 获取发送者渠道
    def getImtype(self):
        path="/getImtype"
        data={
            "senderid":self.senderID
        }
        response=get_service_response(path,data)
        return response["data"]
    
    # 获取发送者ID
    def getUserID(self):
        path="/getUserID"
        data={
            "senderid":self.senderID
        }
        response=get_service_response(path,data)
        # 去掉字符串两端的引号
        return response["data"]
    
    # 获取发送者昵称
    def getUserName(self):
        path="/getUserName"
        data={
            "senderid":self.senderID
        }
        response=get_service_response(path,data)
        return response["data"]

    # 获取发送者头像
    def getUserAvatarUrl(self):
        path="/getUserAvatarUrl"
        data={
            "senderid":self.senderID
        }
        response=get_service_response(path,data)
        return response["data"]

    # 获取发送者群号，返回值是整型
    def getChatID(self):
        path="/getChatID"
        data={
            "senderid":self.senderID
        }
        response=get_service_response(path,data)
        return response["data"]
    
    # 获取发送者群名称
    def getChatName(self):
        path="/getChatName"
        data={
            "senderid":self.senderID
        }
        response=get_service_response(path,data)
        return response["data"]

    # 是否管理员
    def isAdmin(self):
        path="/isAdmin"
        data={
            "senderid":self.senderID
        }
        response=get_service_response(path,data)
        return response["data"]

    # 是否ai
    def getMessage(self):
        path="/getMessage"
        data={
            "senderid":self.senderID
        }
        response=get_service_response(path,data)
        return response["data"]
    
    # 获取消息ID
    def getMessageID(self):
        path="/getMessageID"
        data={
            "senderid":self.senderID
        }
        response=get_service_response(path,data)
        return response["data"]
    
    # 获取历史消息ids
    def recallMessage(self,messageid):
        path="/recallMessage"
        data={
            "senderid":self.senderID,
            "messageid":messageid
        }
        get_service_response(path,data)



    # 回复文本消息，回复的发送消息的id，list类型
    def reply(self,text:str):
        path="/sendText"
        data={
            "senderid":self.senderID,
            "text":text,
        }
        response=get_service_response(path,data)
        return response["data"]

    # 回复图片消息
    def replyImage(self,imageUrl):
        path="/sendImage"
        data={
            "senderid":self.senderID,
            "imageurl":imageUrl
        }
        response=get_service_response(path,data)
        return response["data"]

    # 回复语音消息
    def replyVoice(self,voiceUrl):
        path="/sendVoice"
        data={
            "senderid":self.senderID,
            "voiceurl":voiceUrl
        }
        response=get_service_response(path,data)
        return response["data"]

    # 回复视频消息
    def replyVideo(self,videoUrl):
        path="/sendVideo"
        data={
            "senderid":self.senderID,
            "videourl":videoUrl
        }
        response=get_service_response(path,data)
        return response["data"]
    
    #回复最终结果
    def listen(self,timeout:int):
        path="/listen"
        data={
            "senderid":self.senderID,
            "timeout":timeout
        }
        response=get_service_response(path,data)
        return response["data"]
    
    # 等待用户输入,timeout为超时时间，单位为毫秒,recallDuration为撤回用户输入的延迟时间，单位为毫秒，0是不撤回，forGroup为bool值true或false，是否接收群聊所有成员的输入
    def input(self,timeout:int,recallDuration:int,forGroup:bool):
        path="/input"
        data={
            "senderid":self.senderID,
            "timeout":timeout,
            "recallDuration":recallDuration,
            "forGroup":forGroup,
        }
        response=get_service_response(path,data)
        return response["data"]



    # 添加好友至群聊



def _atm_get_context():
    try:
        from middleware.atm_context import get_current_context
        return get_current_context()
    except Exception:
        return None


def _atm_response(code=200, data=None, message="success"):
    return {"code": code, "data": data, "message": message}


def _atm_run_async(middleware, coro, default=None, timeout=30):
    try:
        loop = getattr(middleware, "main_loop", None)
        if loop and loop.is_running():
            try:
                running = asyncio.get_running_loop()
                if running == loop:
                    return default
            except RuntimeError:
                pass
            fut = asyncio.run_coroutine_threadsafe(coro, loop)
            return fut.result(timeout=timeout)
        return asyncio.run(coro)
    except Exception:
        return default


def _atm_framework_dispatch(path, data):
    ctx = _atm_get_context()
    if not ctx:
        return None

    middleware = ctx.get("middleware")
    message = ctx.get("message") or {}
    if not middleware:
        return None

    p = str(path or "")
    payload = data or {}

    async def _atm_call_ok(coro):
        await coro
        return True

    try:
        if p == "/getActiveImtypes":
            adapter_status = middleware.bucket_manager.get_sync("system", "adapter_status", {})
            active = [name for name in middleware.adapters.keys() if adapter_status.get(name, True)]
            return _atm_response(data=active)

        if p == "/push":
            im_type = str(payload.get("imType", "") or "qq")
            group_code = payload.get("groupCode")
            user_id = payload.get("userID")
            title = str(payload.get("title", "") or "")
            content = str(payload.get("content", "") or "")
            full = f"{title}\n{content}".strip()
            if group_code not in (None, "", 0, "0"):
                _atm_run_async(middleware, middleware.push_to_group(im_type, str(group_code), full), default=False)
                return _atm_response(data=True)
            if user_id not in (None, "", 0, "0"):
                _atm_run_async(middleware, middleware.push_to_user(im_type, str(user_id), full), default=False)
                return _atm_response(data=True)
            return _atm_response(400, False, "missing target")

        if p == "/get":
            key = str(payload.get("key", "") or "")
            return _atm_response(data=middleware.bucket_manager.get_sync("atm_global", key))
        if p == "/set":
            key = str(payload.get("key", "") or "")
            value = payload.get("value")
            ok = bool(_atm_run_async(middleware, _atm_call_ok(middleware.bucket_set("atm_global", key, value)), default=False))
            return _atm_response(data=ok)
        if p == "/delete":
            key = str(payload.get("key", "") or "")
            ok = bool(_atm_run_async(middleware, _atm_call_ok(middleware.bucket_delete("atm_global", key)), default=False))
            return _atm_response(data=ok)

        if p == "/bucketGet":
            bucket = str(payload.get("bucket", "") or "")
            key = str(payload.get("key", "") or "")
            sender = str(message.get("user_id", "") or "")
            scoped_key = f"{sender}:{key}" if sender else key
            val = middleware.bucket_manager.get_sync(bucket, scoped_key, None)
            if val is None:
                val = middleware.bucket_manager.get_sync(bucket, key, None)
            return _atm_response(data=val)
        if p == "/bucketSet":
            bucket = str(payload.get("bucket", "") or "")
            key = str(payload.get("key", "") or "")
            value = payload.get("value")
            sender = str(message.get("user_id", "") or "")
            scoped_key = f"{sender}:{key}" if sender else key
            ok = bool(_atm_run_async(middleware, _atm_call_ok(middleware.bucket_set(bucket, scoped_key, value)), default=False))
            return _atm_response(data=ok)
        if p == "/bucketDel":
            bucket = str(payload.get("bucket", "") or "")
            key = str(payload.get("key", "") or "")
            sender = str(message.get("user_id", "") or "")
            scoped_key = f"{sender}:{key}" if sender else key
            ok = bool(_atm_run_async(middleware, _atm_call_ok(middleware.bucket_delete(bucket, scoped_key)), default=False))
            return _atm_response(data=ok)
        if p == "/bucketAll":
            bucket = str(payload.get("bucket", "") or "")
            data_all = _atm_run_async(middleware, middleware.bucket_manager.get_all(bucket), default={}) or {}
            return _atm_response(data=data_all)
        if p == "/bucketAllKeys":
            bucket = str(payload.get("bucket", "") or "")
            keys = _atm_run_async(middleware, middleware.bucket_keys(bucket), default=[]) or []
            return _atm_response(data=keys)
        if p == "/bucketKeys":
            bucket = str(payload.get("bucket", "") or "")
            val = payload.get("value")
            all_map = _atm_run_async(middleware, middleware.bucket_manager.get_all(bucket), default={}) or {}
            matched = [k for k, v in all_map.items() if v == val]
            return _atm_response(data=matched)

        if p == "/notifyMasters":
            content = str(payload.get("content", "") or "")
            imtypes = payload.get("imtypes") or []
            platforms = ",".join([str(x) for x in imtypes if str(x).strip()]) if isinstance(imtypes, list) and imtypes else "qq"
            _atm_run_async(middleware, middleware.notify_admin(content, platforms=platforms), default=None)
            return _atm_response(data=True)

        if p == "/getImtype":
            return _atm_response(data=str(message.get("platform", "") or ""))
        if p == "/getUserID":
            return _atm_response(data=str(message.get("user_id", "") or ""))
        if p == "/getUserName":
            return _atm_response(data=str(message.get("nickname", "") or message.get("user_name", "") or message.get("user_id", "") or ""))
        if p == "/getUserAvatarUrl":
            return _atm_response(data=str(message.get("avatar", "") or message.get("avatar_url", "") or ""))
        if p == "/getChatID":
            gid = message.get("group_id")
            return _atm_response(data=str(gid if gid not in (None, "", 0, "0") else message.get("user_id", "")))
        if p == "/getChatName":
            return _atm_response(data=str(message.get("group_name", "") or ""))
        if p == "/isAdmin":
            uid = message.get("user_id")
            is_admin = _atm_run_async(middleware, middleware.is_admin(uid), default=False)
            return _atm_response(data=bool(is_admin))
        if p == "/getMessage":
            return _atm_response(data=str(message.get("content", "") or ""))
        if p == "/getMessageID":
            return _atm_response(data=message.get("message_id"))
        if p == "/recallMessage":
            msgid = payload.get("messageid")
            recall_payload = {"platform": message.get("platform"), "message_id": msgid}
            ok = _atm_run_async(middleware, middleware.recall_message(recall_payload), default=False)
            return _atm_response(data=bool(ok))
        if p in ("/sendText", "/response"):
            text = str(payload.get("text", "") or payload.get("data", "") or "")
            _atm_run_async(middleware, middleware.send_response(message, {"content": text}), default=None)
            return _atm_response(data=True)
        if p == "/sendImage":
            image_url = str(payload.get("imageurl", "") or "")
            _atm_run_async(middleware, middleware.reply_with_image(message, image_url), default=None)
            return _atm_response(data=True)
        if p == "/sendVoice":
            voice_url = str(payload.get("voiceurl", "") or "")
            cq = f"[CQ:record,file={voice_url}]"
            _atm_run_async(middleware, middleware.send_response(message, {"content": cq}), default=None)
            return _atm_response(data=True)
        if p == "/sendVideo":
            video_url = str(payload.get("videourl", "") or "")
            _atm_run_async(middleware, middleware.reply_with_video(message, video_url), default=None)
            return _atm_response(data=True)
        if p in ("/listen", "/input"):
            timeout = int(payload.get("timeout", 60000) or 60000)
            content = _atm_run_async(middleware, middleware.wait_for_input(message, timeout), default=None)
            return _atm_response(data=content)
    except Exception as e:
        try:
            middleware.logger.error(f"atm compat dispatch failed path={p}: {e}")
        except Exception:
            pass
        return _atm_response(500, None, str(e))

    return _atm_response(501, None, "not supported")
