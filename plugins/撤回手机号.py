"""
撤回手机号 插件
"""

__description__ = "Q群自动撤回手机号"
__version__ = "1.0.0"
__author__ = "bucai"



async def handle_message(msg, middleware):
    msg_id = msg.get("message_id") if msg.get("message_id",False) else msg.get("raw_data")["message_id"]
    platform = msg["platform"]
    await middleware.recall_message({"platform":platform,"message_id":msg_id})
    return {
        "content": "已撤回手机号"
    }



rules = [
    {
    "name": "phone",#匹配规则名，别重复
    "pattern": r"^1[3-9]\d{9}$",#匹配正则
    "handler": handle_message,#调用的函数
    "rule_type": "regex",#keyword:关键词，fullmatch:完全匹配，regex:正则
    "priority": 10,#优先级
    "description": "匹配问候语并回应"#插件介绍不用填
    }

]
