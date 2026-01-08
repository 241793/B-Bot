"""
青龙面板集成插件
允许通过聊天指令与青龙面板进行交互。
"""
from containers.qinglong_client import QinglongClient
from containers.qinglong import QinglongContainer
from utils.logger import get_logger
import asyncio
from middleware.middleware import Middleware
__description__ = "通过聊天指令与青龙面板交互，一个示例插件"
__version__ = "1.0.0"
__author__ = "bucai"

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


# 定义规则
rules = [
    {
        "name": "ql_command_rule",
        "pattern": r"^ql\s+run\s+.*",
        "handler": handle_ql_command,
        "priority": 100,
        "description": "处理青龙面板运行任务的指令"
    }
]
