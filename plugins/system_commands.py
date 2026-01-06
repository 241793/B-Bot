# 插件：系统指令
# 功能：提供框架内置的基础指令，如时间查询、管理员设置等。
__system__ = True


import datetime
import asyncio
import os
import sys
import psutil  # 用于获取系统状态
from middleware.middleware import Middleware

# 将 middleware 实例存储在模块级别
middleware_instance: Middleware = None

async def system_command_handler(message: dict):
    """
    处理系统内置指令的消息处理器
    """
    content = message.get("content", "").strip()
    user_id = str(message.get("user_id"))
    group_id = message.get("group_id")

    # --- 无需管理员权限的指令 ---

    # 1. 时间指令
    if content.lower() in ["时间", "time"]:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return {"content": f"当前时间是：{now}"}

    # 2. 版本指令
    if content.lower() in ["v", "v", "版本"]:
        version_num = await middleware_instance.bucket_get("system", "version_number", "未知")
        version_content = await middleware_instance.bucket_get("system", "version_content", "没有版本说明")
        return {"content": f"版本号: {version_num}\n{version_content}"}
    platform = message.get("platform")
    # 新增：赞我指令
    if content == "赞我":

        adapter = middleware_instance.adapters.get(platform)
        if adapter and hasattr(adapter, 'qq_zang'):
            try:

                await adapter.qq_zang(user_id, 10)
                return {"content": "好感度+10！"}
            except Exception as e:
                middleware_instance.logger.error(f"执行'赞我'指令失败: {e}")
                return {"content": "点赞失败了，稍后再试试吧。"}
        else:
            return {"content": "当前平台不支持点赞哦。"}

    # --- 需要管理员权限的指令 ---
    
    is_admin = await middleware_instance.is_admin(user_id)
    if content == "banall" and is_admin:

        adapter = middleware_instance.adapters.get(platform)
        if adapter and hasattr(adapter, 'ban_all'):
            try:
                await adapter.ban_all(group_id, True)
                return {"content": "全体禁言中..."}
            except Exception as e:
                middleware_instance.logger.error(f"执行'全体禁言'指令失败: {e}")
                return {"content": "全体禁言失败了，稍后再试试吧。"}
        else:
            return {"content": "当前平台不支持全体禁言哦。"}
    if content == "cbanall" and is_admin:

        adapter = middleware_instance.adapters.get(platform)
        if adapter and hasattr(adapter, 'ban_all'):
            try:
                await adapter.ban_all(group_id, False)
                return {"content": "解除全体禁言"}
            except Exception as e:
                middleware_instance.logger.error(f"执行'解除全体禁言'指令失败: {e}")
                return {"content": "解除全体禁言失败了，稍后再试试吧。"}
        else:
            return {"content": "当前平台不支持解除全体禁言哦。"}
    if content.startswith("ban ") and is_admin:
        ban_qq = content.split(" ")[1]
        duration = int(content.split(" ")[2])
        if not ban_qq:
            return {"content": "请输入要禁言的Q号。"}
        adapter = middleware_instance.adapters.get(platform)
        if adapter and hasattr(adapter, 'ban'):
            try:
                await adapter.ban(ban_qq,group_id, duration)
                return {"content": f"{ban_qq}被禁言{duration}秒"}
            except Exception as e:
                middleware_instance.logger.error(f"执行'禁言'指令失败: {e}")
                return {"content": "禁言失败了，稍后再试试吧。"}
        else:
            return {"content": "当前平台不支持禁言哦。"}
    if content.startswith("踢 ") and is_admin:
        ban_qq = content.split(" ")[1]


        add2 = False
        tt = "允许"
        if len(content.split(" ")) == 3 and int(content.split(" ")[2]) == "1":
            add2 = True
            tt = "禁止"
        if not ban_qq:
            return {"content": "请输入要踢的Q号。"}
        adapter = middleware_instance.adapters.get(platform)
        if adapter and hasattr(adapter, 'ban'):
            try:
                await adapter.kick(ban_qq,group_id, add2)
                return {"content": f"{ban_qq}被踢出群,{tt}再次加群"}
            except Exception as e:
                middleware_instance.logger.error(f"执行'踢人'指令失败: {e}")
                return {"content": "踢人失败了，稍后再试试吧。"}
        else:
            return {"content": "当前平台不支持踢人哦。"}
    # 3. 重启指令
    if content == "重启" and is_admin:
        await middleware_instance.send_response(message, {"content": "机器人正在重启..."})
        await asyncio.sleep(1) # 留出时间发送消息
        
        # 使用 os.execv 重启脚本
        python = sys.executable
        os.execv(python, [python] + sys.argv)
        return None # 这行代码实际上不会执行
    if content == "myuid":
        return {"content": f"{user_id}"}
    # 4. 系统状态指令
    if content.startswith("botsystem") and is_admin:
        cpu_usage = psutil.cpu_percent(interval=1)
        memory_info = psutil.virtual_memory()
        disk_info = psutil.disk_usage('/')
        
        status_report = (
            f"💻 系统状态报告:\n"
            f"-------------------\n"
            f"CPU 使用率: {cpu_usage}%\n"
            f"内存使用率: {memory_info.percent}% ({memory_info.used/1024**3:.2f}G / {memory_info.total/1024**3:.2f}G)\n"
            f"磁盘使用率: {disk_info.percent}% ({disk_info.used/1024**3:.2f}G / {disk_info.total/1024**3:.2f}G)"
        )
        return {"content": status_report}

    # 5. 管理员设置指令
    if content.startswith("set admin ") and is_admin:
        try:
            admin_ids_str = content[len("set admin "):].strip()
            new_admins = [admin.strip() for admin in admin_ids_str.split('&') if admin.strip()]
            if not new_admins:
                return {"content": "未提供有效的管理员ID。"}
            await middleware_instance.bucket_set("system", "admin_list", new_admins)
            return {"content": f"管理员已重置为：{', '.join(new_admins)}"}
        except Exception as e:
            return {"content": f"处理指令时出错: {e}"}

    if content.startswith("add admin ") and is_admin:
        try:
            new_admin_id = content[len("add admin "):].strip()
            if not new_admin_id:
                 return {"content": "指令格式错误。用法: add admin <user_id>"}
            success = await middleware_instance.add_admin(new_admin_id, user_id)
            if success:
                return {"content": f"管理员 {new_admin_id} 添加成功！"}
            else:
                return {"content": f"添加失败，用户 {new_admin_id} 可能已经是管理员了。"}
        except Exception as e:
            return {"content": f"处理指令时出错: {e}"}

    # 6. 群聊控制指令
    if content.startswith("关闭群聊回复") and is_admin:
        await middleware_instance.bucket_set("system", "group_reply_enabled", False)
        return {"content": "所有群聊的自动回复功能已关闭。"}
    
    if content.startswith("开启群聊回复") and is_admin:
        await middleware_instance.bucket_set("system", "group_reply_enabled", True)
        return {"content": "所有群聊的自动回复功能已开启。"}

    if content.startswith("拉黑群 ") and is_admin:
        group_to_block = content[len("拉黑群 "):].strip()
        if not group_to_block:
            return {"content": "请输入要拉黑的群号。"}
        blacklist = await middleware_instance.bucket_get("system", "group_blacklist", [])
        if group_to_block not in blacklist:
            blacklist.append(group_to_block)
            await middleware_instance.bucket_set("system", "group_blacklist", blacklist)
            return {"content": f"群 {group_to_block} 已被拉黑。"}
        else:
            return {"content": f"群 {group_to_block} 已在黑名单中。"}

    if content.startswith("解黑群 ") and is_admin:
        group_to_unblock = content[len("解黑群 "):].strip()
        if not group_to_unblock:
            return {"content": "请输入要解黑的群号。"}
        blacklist = await middleware_instance.bucket_get("system", "group_blacklist", [])
        if group_to_unblock in blacklist:
            blacklist.remove(group_to_unblock)
            await middleware_instance.bucket_set("system", "group_blacklist", blacklist)
            return {"content": f"群 {group_to_unblock} 已从黑名单移除。"}
        else:
            return {"content": f"群 {group_to_unblock} 不在黑名单中。"}

    # 7. 私聊控制指令
    if content == "关闭私聊" and is_admin:
        await middleware_instance.bucket_set("system", "private_reply_enabled", False)
        return {"content": "面向普通用户的私聊回复功能已关闭。"}
        
    if content == "开启私聊" and is_admin:
        await middleware_instance.bucket_set("system", "private_reply_enabled", True)
        return {"content": "面向普通用户的私聊回复功能已开启。"}

    return None

def register(middleware: Middleware):
    """
    注册插件和消息处理器
    """
    global middleware_instance
    middleware_instance = middleware
    middleware.register_message_handler(system_command_handler)
    print("插件 'system_commands' 已加载。")
