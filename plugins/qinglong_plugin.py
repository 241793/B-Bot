"""
青龙面板集成插件
允许通过聊天指令与青龙面板进行交互，并接收青龙面板的通知。
"""
from containers.qinglong_client import QinglongClient
from containers.qinglong import QinglongContainer
from utils.logger import get_logger
import asyncio
from middleware.middleware import Middleware

__description__ = "通过聊天指令与青龙面板交互，并接收通知,通知功能，底部看指令，使用指令ql notify开启通知，可以多用户渠道，ql filter title，添加白名单，例如青龙调用notify.py,notify.send(title,'内容')"
__version__ = "1.2.0"
__author__ = "bucai"
__system__ = True
logger = get_logger(__name__)

async def handle_ql_command(message, middleware):
    """处理ql指令"""
    if not await middleware.is_admin(message["user_id"]):
        return {"content": "您没有权限执行此操作。", "to_user_id": message["user_id"]}
    content = message.get('content', '').strip()
    parts = content.split()
    if len(parts) < 3 or parts[0].lower() != 'ql' or parts[1].lower() != 'run':
        return
    task_identifier = parts[2]
    container_name = parts[3] if len(parts) > 3 else None
    containers_config = await middleware.bucket_manager.get("system", "containers", {})
    if not containers_config:
        return {"content": "尚未配置任何青龙容器。", "to_user_id": message["user_id"]}

    target_container = None
    if container_name:
        if container_name in containers_config and containers_config[container_name].get('enabled'):
            target_container = containers_config[container_name]
            target_container['name'] = container_name
        else:
            return {
                "content": f"未找到名为 '{container_name}' 的已启用容器。",
                "to_user_id": message["user_id"]
            }
    else:
        # 查找第一个启用的容器作为默认容器
        for name, config in containers_config.items():
            if config.get('enabled'):
                target_container = config
                target_container['name'] = name
                break
    
    if not target_container:
        return {
                "content": "没有可用的已启用青龙容器。",
                "to_user_id": message["user_id"]
            }

    client = QinglongClient(
        url=target_container['url'],
        client_id=target_container['client_id'],
        client_secret=target_container['client_secret']
    )

    try:
        await middleware.send_message(platform=message["platform"], target_id=message["user_id"], content=f"正在容器 '{target_container['name']}' 中查找任务 '{task_identifier}'...", msg=message)

        crons_response = await asyncio.get_running_loop().run_in_executor(None, client.get_crons)
        if crons_response.get('code') != 200:
            return {
                "content": f"无法从容器 '{target_container['name']}' 获取任务列表: {crons_response.get('message', '未知错误')}",
                "to_user_id": message["user_id"]
            }

        all_crons = crons_response["data"].get('data', [])
        target_cron_id = None

        # 尝试按ID或名称查找任务
        for cron in all_crons:
            if str(cron.get('id')) == task_identifier or task_identifier in cron.get('name', ''):
                target_cron_id = cron.get('id')
                break
        
        if not target_cron_id:
            return {
                "content": f"在容器 '{target_container['name']}' 中未找到任务 '{task_identifier}'。",
                "to_user_id": message["user_id"]
            }
        await middleware.send_message(platform=message["platform"], target_id=message["user_id"],content=f"正在运行任务 '{task_identifier}' (ID: {target_cron_id})...", msg=message)
        run_response = await asyncio.get_running_loop().run_in_executor(None, lambda: client.run_cron([target_cron_id]))

        if run_response.get('code') == 200:
            return {
                "content": f"任务 '{task_identifier}' 已成功触发。",
                "to_user_id": message["user_id"]
            }

        else:
            return {
                "content": f"任务 '{task_identifier}' 运行失败: {run_response.get('message', '未知错误')}",
                "to_user_id": message["user_id"]
            }


    except Exception as e:
        logger.error(f"处理ql指令时出错: {e}")
        return {
            "content": f"执行指令时发生错误: {e}",
            "to_user_id": message["user_id"]
        }

async def handle_ql_notify_config(message, middleware):
    """配置青龙通知目标"""
    if not await middleware.is_admin(message["user_id"]):
         return {"content": "您没有权限执行此操作。", "to_user_id": message["user_id"]}
    
    # 确定目标ID (群组ID 或 用户ID)


    if message.get("group_id"):
        target_id = message.get("group_id")
        platform = message.get("platform") + "_group"
    else:
        target_id = message.get("user_id")
        platform = message.get("platform")
    
    if not target_id or not platform:
        return {"content": "无法获取当前会话信息。", "to_user_id": message["user_id"]}

    config = await middleware.bucket_manager.get("qinglong", "notify_targets", [])
    
    # 检查是否已存在
    exists = False
    for t in config:
        if t['platform'] == platform and t['target_id'] == target_id:
            exists = True
            break
    
    if exists:
        # 移除 (关闭)
        config = [t for t in config if not (t['platform'] == platform and t['target_id'] == target_id)]
        await middleware.bucket_manager.set("qinglong", "notify_targets", config)
        return {"content": "已关闭本会话的青龙面板通知。", "to_user_id": target_id}
    else:
        # 添加 (开启)
        config.append({'platform': platform, 'target_id': target_id})
        await middleware.bucket_manager.set("qinglong", "notify_targets", config)
        return {"content": "已开启本会话的青龙面板通知。", "to_user_id": target_id}

async def handle_ql_filter_config(message, middleware):
    """配置青龙通知过滤关键词"""
    if not await middleware.is_admin(message["user_id"]):
         return {"content": "您没有权限执行此操作。", "to_user_id": message["user_id"]}
    
    content = message.get('content', '').strip()
    parts = content.split()
    
    # ql filter <keyword>
    if len(parts) < 3:
        # 列出当前过滤器
        whitelist = await middleware.bucket_manager.get("qinglong", "notify_whitelist", [])
        if not whitelist:
            return {"content": "当前未配置通知过滤，所有通知都会发送。\n使用 'ql filter <关键词>' 添加过滤。", "to_user_id": message["user_id"]}
        else:
            return {"content": f"当前通知白名单关键词：\n{', '.join(whitelist)}\n使用 'ql filter <关键词>' 移除。", "to_user_id": message["user_id"]}

    keyword = parts[2]
    whitelist = await middleware.bucket_manager.get("qinglong", "notify_whitelist", [])
    
    if keyword in whitelist:
        whitelist.remove(keyword)
        await middleware.bucket_manager.set("qinglong", "notify_whitelist", whitelist)
        return {"content": f"已移除过滤关键词: {keyword}", "to_user_id": message["user_id"]}
    else:
        whitelist.append(keyword)
        await middleware.bucket_manager.set("qinglong", "notify_whitelist", whitelist)
        return {"content": f"已添加过滤关键词: {keyword}", "to_user_id": message["user_id"]}

async def handle_webhook(title, content):
    """处理来自青龙面板的Webhook通知"""
    # 获取配置的通知目标
    # 使用 global middleware (由 PluginManager 注入)
    if 'middleware' not in globals():
        logger.error("Middleware not injected into plugin")
        return False
    
    mw = globals()['middleware']
    
    # --- 过滤逻辑 ---
    whitelist = await mw.bucket_manager.get("qinglong", "notify_whitelist", [])
    if whitelist:
        matched = False
        for keyword in whitelist:
            if keyword in title:
                matched = True
                break
        if not matched:
            logger.info(f"青龙通知 '{title}' 被过滤，因为不包含白名单关键词。")
            return False
    # ----------------

    targets = await mw.bucket_manager.get("qinglong", "notify_targets", [])
    
    if not targets:
        logger.warning("收到青龙通知，但未配置任何通知目标。请在群组或私聊中使用 'ql notify' 开启通知。")
        return False

    for target in targets:
        try:
            # 构造消息内容
            msg_content = f"【青龙通知】{title}\n{content}"
            msg_content += f"\n\n此消息来自 {target['platform']} {target['target_id']}"
            if '_group' in target['platform']:
                await mw.push_to_group(target['platform'].replace("_group",""), target['target_id'], msg_content)
            else:
                await mw.push_to_user(target['platform'], target['target_id'], msg_content)
        except Exception as e:
            logger.error(f"发送通知到 {target} 失败: {e}")
    return True

# 定义规则
rules = [
    {
        "name": "ql_command_rule",
        "pattern": r"^ql\s+run\s+.*",
        "handler": handle_ql_command,
        "priority": 100,
        "description": "处理青龙面板运行任务的指令"
    },
    {
        "name": "ql_notify_config_rule",
        "pattern": r"^ql\s+notify$",
        "handler": handle_ql_notify_config,
        "priority": 100,
        "description": "开启/关闭当前会话的青龙面板通知"
    },
    {
        "name": "ql_filter_config_rule",
        "pattern": r"^ql\s+filter.*",
        "handler": handle_ql_filter_config,
        "priority": 100,
        "description": "配置青龙通知过滤关键词"
    }
]

