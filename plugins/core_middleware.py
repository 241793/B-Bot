import asyncio
import inspect
import json, re
from typing import Dict, Any, Optional, List, Callable, Tuple
from storage.bucket import BucketManager
from utils.logger import get_logger
from containers.base import BaseContainer
from containers.qinglong import QinglongContainer
from utils.variable_processor import process_variables

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
        self.logger = get_logger("middleware")
        self.containers: Dict[str, BaseContainer] = {} # 存储容器实例
        # 使用 (user_id, group_id) 元组作为键，确保等待的上下文精确
        self.waiting_for_input: Dict[Tuple[str, Optional[str]], asyncio.Future] = {}
        
        # 适配器状态缓存
        self.adapter_status_cache = {}
        self.adapter_status_loaded = False
        
        # 授权检查器
        self.auth_checker = None

        # 捕获主事件循环，用于在非异步线程中调度任务
        try:
            self.main_loop = asyncio.get_running_loop()
        except RuntimeError:
            self.main_loop = None
            self.logger.warning("Middleware initialized without a running event loop. Some features may not work.")

    def set_auth_checker(self, checker: Callable[[], bool]):
        """设置授权检查器"""
        self.auth_checker = checker

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
        if not isinstance(container_configs, list):
            self.logger.error("容器配置格式不正确，应为列表。")
            return

        for config in container_configs:
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
        """
        在后台任务中运行消息处理器和拦截逻辑。
        """
        # --- 授权检查 ---
        if self.auth_checker and not self.auth_checker():
            self.logger.warning("系统未授权或授权已过期，拒绝处理消息。")
            # 可以选择发送一条提示消息，或者直接忽略
            # await self.send_response(message, {"content": "系统未授权或授权已过期。"})
            return
        # ----------------

        # 首先处理变量提交
        await process_variables(message, self)

        user_id = message.get("user_id")
        group_id = message.get("group_id")
        is_admin_user = await self.is_admin(user_id)

        # --- 拦截逻辑 ---
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

        self.logger.info(f"后台处理消息: {message.get('content', '')}")

        # 获取当前事件循环
        loop = asyncio.get_running_loop()

        # 调用所有注册的消息处理器
        all_handlers = [handler for handlers in self.message_handlers.values() for handler in handlers]
        for handler in all_handlers:
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
                    result = await loop.run_in_executor(None, handler, *args)

                if result:
                    await self.send_response(message, result)
                    break
            except Exception as e:
                self.logger.error(f"处理消息时插件 {getattr(handler, '__module__', 'unknown')} 的处理器 {getattr(handler, '__name__', 'unknown')} 发生错误: {e}",
                                  exc_info=True)

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

    async def send_message(self, platform: str, target_id: str, content: str, *,msg: Optional[Dict[str, Any]] = None):
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
    async def reply_with_voice(self, original_message: Dict[str, Any], voice_source: str):
        """
        回复原始消息，并携带视频。
        :param original_message: 原始消息对象，用于获取回复目标。
        :param voice_source: 音频源，通常是音频的URL。
        :return: 如果成功，返回True，否则返回False。
        """
        if re.match(r'^https?://', voice_source):
            cq_code = f"[CQ:video,file={voice_source}]"
        else:
            self.logger.error(f"无效的音频源: {voice_source[:50]}... (目前仅支持URL)")
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
        return str(user_id) in admin_list

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
