# B-Bot

本项目仅提供学习和参考，请勿违法操作，请于24小时内删除!

一个类似AutMan的机器人框架，通过python实现，具有多协议接入、插件化架构、规则引擎、持久化存储和可视化面板的自动化工具。
win电脑需要有python环境

ntqq的llonebot插件配置ws：ws://127.0.0.1:port/ws/qq

对接QQ教程：<a href="https://bchome.dpdns.org/index.php/archives/157/" target="_blank">llonebot(win/docker)</a>

docker教程：<a href="https://bchome.dpdns.org/index.php/archives/168/" target="_blank">部署docker</a>

```docker
docker run -d \
  -p 8888:8888 \
  -p 5000:5000 \
  -e KAMI=卡密 \
  -e WEB_UI_PORT=5000 \
  -e qq_PORT=8888 \
  -v 你的docker文件夹地址/data:/app/data \
  -v 你的docker文件夹地址/plugins:/app/plugins \
  --name b-bot-container \
  --restart unless-stopped \
  b-bot


 docker run -d `
  -p 8888:8888 `
  -p 5000:5000 `
  -e KAMI="卡密" `
  -e WEB_UI_PORT="5000" `
  -e qq_PORT="8888" `
  -v "你的docker文件夹地址\data:/app/data" `
  -v "你的docker文件夹地址\plugins:/app/plugins" `
  --name b-bot-container `
  --restart unless-stopped `
  b-bot
```
## 功能特性

- **多协议接入器**: 支持WebSocket等协议，可对接QQ等平台
- **插件化架构**: 支持Python插件的动态加载、卸载和管理
- **规则引擎**: 基于正则表达式、关键词的消息匹配和处理
- **持久化存储**: 支持数据桶存储机制
- **中间件系统**: 提供统一的消息处理接口
- **可视化面板**: 完整的Web管理界面

## 快速开始

### 1. 启动框架

```bash
B-BOT.exe一键运行
```

### 2. 访问Web管理界面

打开浏览器访问 `http://127.0.0.1:5000`

### 3. WebSocket连接
.env文件可以更改端口
客户端可以连接到 `ws://127.0.0.1:8888` 发送和接收消息
ntqq的llonebot插件配置ws：ws://127.0.0.1:port/ws/qq

### 适配器管理

### 插件管理

### 规则管理
- 查看系统规则
- 添加新规则（支持正则表达式、关键词、完全匹配）

### 数据桶管理

### 日志管理

## WebSocket协议

### 消息格式

发送消息格式：
```json
{
  "id": "消息唯一ID",
  "type": "message",
  "content": "消息内容",
  "user_id": "用户ID",
  "group_id": "群ID",
  "timestamp": "时间戳",
  "raw_message": "原始消息"
}
```

接收消息格式：
```json
{
  "content": "回复内容",
  "to_user_id": "目标用户ID"
}
```

## 插件开发

### 开发规范
- 中间遵循异步运行，插件调用时需使用await异步操作
- 所有插件必须遵循插件开发规范
- 插件文件名应使用下划线命名法
- 规则名称应具有唯一性
- 代码应包含适当的错误处理
#### 基本插件结构
- 一些参数：platform: reverse_ws(ws对接的渠道)、web_ui(web端)

##### 插件编写方法一
```python
"""
插件名称
插件描述
"""

__description__ = "插件描述"
__version__ = "1.0.0"
__author__ = "开发者"
__imType__="渠道，例如qq"
__admin__=False#是否仅管理员
#配参
__param__ = {"required":True,"key":"桶名.key","bool":False,"placeholder":"","name":"输入框的名字","desc":"介绍"}
import asyncio
async def handle_message(msg, middleware):
    """
    处理消息的函数
    """
    content = msg["content"]#消息内容{}
    user_id = msg["user_id"]
    platform = msg["platform"]
    #这种为推送消息的方式，连续交互时使用，需要填写多种参数
    await middleware.send_message(platform, user_id, "要发送的消息",msg)
    #这种为直接回复消息，适合结束的地方使用，只支持rules里面绑定的函数使用（例如：handle_message）
    return {
        "content": "回复内容",
        "to_user_id": user_id
    }

# 插件规则
rules = [
    {
        "name": "规则名称",
        "pattern": r"匹配模式",
        "handler": handle_message,
        "rule_type": "regex",  # regex, keyword, fullmatch,匹配类型
        "priority": 1,
        "description": "规则描述"
    }
]

```
##### 插件编写方法二
```python
"""
插件名称
插件描述
"""

__description__ = "插件描述"
__version__ = "1.0.0"
__author__ = "开发者"
#配参
__param__ = {"required":True,"key":"桶名.key","bool":False,"placeholder":"","name":"输入框的名字","desc":"介绍"}
import asyncio,re
async def handle_message(msg, middleware):
    #相当于全局监听框架信息，需要自己写匹配规则
    content = msg["content"]
    if content:
       if re.match("^你好$",content):
          return {"content": "你也好", "to_user_id": msg["user_id"]}

def register(middleware):
    """
    当框架加载此插件时，会调用这个函数。
    """
    # 通过中间件注册你的消息处理器
    middleware.register_message_handler(handle_message)
    print(f"示例插件 '{__description__}' 已加载并注册了消息处理器。")

```
## 配置

win框架支持以下环境变量配置：

- `REVERSE_WS_HOST`: 反向WebSocket服务器主机，默认 `0.0.0.0`
- `REVERSE_WS_PORT`: 反向WebSocket服务器端口，默认 `8888/ws/qq` (用于发送回复给QQ等平台)
- `WEB_UI_HOST`: Web界面主机，默认 `0.0.0.0`
- `WEB_UI_PORT`: Web界面端口，默认 `5000`

## 特殊说明

1. **插件热加载**: 支持动态启用/禁用、在线编辑和实时保存
2. **WebSocket服务器**: 提供WebSocket服务供客户端连接
3. **规则优先级**: 数值越大优先级越高
4. **日志轮转**: 自动管理日志文件大小和数量
5. **QQ集成**: 支持与QQ平台集成，通过双WebSocket架构实现消息收发
   - 一些功能: 自动同意好友请求、自动撤回、群管、点赞
6. **反向WebSocket**: 用于将处理结果发送回消息平台
7. **外部容器对接青龙面板**: 支持青龙面板对接，规则运行，插件异步调用内置青龙函数

---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 插件开发指南

本文档旨在帮助开发者了解如何在 `B-BOT` 中创建和开发插件。插件是扩展机器人功能的核心。

## 1. 插件基础
插件本质上是一个遵循特定规范的 Python 模块，框架会自动加载并运行它。

- **位置**: 所有插件都应放置在 `plugins/` 目录下。
- **入口**: 框架会寻找并执行插件模块中的 `register` 函数来初始化插件。

一个最简单的插件结构如下：

```python
# /plugins/my_awesome_plugin.py
__description__ = "插件描述"
__version__ = "1.0.0"
__author__ = "开发者"
__imType__="qq"#插件仅某渠道可用
__admin__=False#是否仅管理员可用
#配参：可选
__param__ = {"required":True,"key":"桶名.key","bool":False,"placeholder":"","name":"输入框的名字","desc":"介绍"}

# 插件的主体功能
async def my_message_handler(message: dict):
    """
    这是一个消息处理器，它会接收所有通过框架的消息。
    """
    content = message.get("content", "").strip()
    if content == "你好":
        # 当收到“你好”时，返回一个响应字典
        return {"content": "你好！我是你的机器人助手。"}
    # 如果不处理此消息，则不返回任何内容
    return None

# 插件注册函数（必需）
def register(middleware):
    """
    当框架加载此插件时，会调用这个函数。
    """
    # 通过中间件注册你的消息处理器
    middleware.register_message_handler(my_message_handler)
    print("示例插件 'my_awesome_plugin' 已加载并注册了消息处理器。")

```

## 2. 如何使用 Middleware 功能

`Middleware` 对象是插件与框架交互的唯一桥梁。当框架调用你的 `register` 函数时，会将一个 `Middleware` 实例作为参数传递给你。你应该将其保存下来，以便在插件的其他地方使用。

虽然在上面的简单示例中我们只在 `register` 函数里用了一次 `middleware`，但更复杂的插件可能需要在多个地方调用它。你可以将它保存在一个类或者全局变量中。

### 2.1 接收和响应消息

最常见的插件功能是响应用户的消息。

- **注册处理器**: 使用 `middleware.register_message_handler(your_handler_function)` 来监听所有消息。
- **处理消息**: 你的处理器函数会收到一个 `message` 字典，它包含了消息的所有信息（如内容、发送者ID、群组ID等）。
- **快速响应**: 如果你的处理器函数返回一个包含 `content` 键的字典，框架会自动将该 `content` 作为回复发送到消息的来源地（私聊或群聊）。这是最简单的响应方式。

```python
# /plugins/echo_plugin.py


async def echo_handler(message: dict):
    response_content = f"你刚才说的是：{message.get('content')}"
    return {"content": response_content}

def register(middleware):
    middleware.register_message_handler(echo_handler)
```

### 2.2 主动发送消息

除了被动响应，插件也可以主动向任何地方发送消息。

- **函数**: `await middleware.send_message(platform, target_id, content,msg=None)`
- **参数**:
    - `platform`: 平台名称 (例如: `'qq'`, `'websocket'`)。
    - `target_id`: 目标ID。对于私聊，是用户ID；对于群聊，是群ID。
    - `content`: 你想发送的消息内容。
    - `msg`: 原始消息对象, 用于获取发送者信息。

**示例：一个定时提醒插件**

```python
# /plugins/reminder_plugin.py
import asyncio


class ReminderPlugin:
    def __init__(self, middleware):
        self.middleware = middleware
        self.reminders = {}

    async def add_reminder_handler(self, message: dict):
        content = message.get("content", "")
        parts = content.split()
        if content.startswith("!提醒我"):
            try:
                seconds = int(parts[1])
                reminder_text = " ".join(parts[2:])
                user_id = message["user_id"]
                
                # 安排一个定时任务
                asyncio.create_task(self.schedule_reminder(seconds, user_id, reminder_text, message["platform"]))
                
                return {"content": f"好的，我会在 {seconds} 秒后提醒你。"}
            except (IndexError, ValueError):
                return {"content": "格式错误！请使用：!提醒我 [秒数] [提醒内容]"}

    async def schedule_reminder(self, delay, user_id, text, platform):
        await asyncio.sleep(delay)
        # 使用 send_message 主动发送消息,msg这里为空是因为不需要判断用户在群内，私发消息
        await self.middleware.send_message(
            platform=platform,
            target_id=user_id,
            content=f"提醒时间到！\n提醒内容：{text}"
        )

def register(middleware):
    plugin = ReminderPlugin(middleware)
    middleware.register_message_handler(plugin.add_reminder_handler)
    print("提醒插件已加载。")
```

### 2.3 使用持久化存储 (Bucket)

插件经常需要存储数据，例如用户配置、游戏得分等。`Middleware` 提供了基于 "Bucket" 的简单键值存储。

- **概念**: Bucket 是一个数据容器，类似于一个字典。每个插件可以拥有一个或多个独立的 Bucket。
- **函数**:
    - `await middleware.bucket_set(bucket_name, key, value)`: 保存数据。
    - `await middleware.bucket_get(bucket_name, key, default=None)`: 读取数据。
    - `await middleware.bucket_delete(bucket_name, key)`: 删除一个键。
    - `await middleware.bucket_keys(bucket_name)`: 获取所有键。

**示例：一个计数器插件,异步写法**

```python
# /plugins/counter_plugin.py


BUCKET_NAME = "counter_plugin_data"

async def counter_handler(message: dict,middleware):
    user_id = message["user_id"]
    
    # 从 bucket 中读取用户发言次数
    current_count = await middleware.bucket_get(BUCKET_NAME, user_id, default=0)
    
    # 次数加一并存回
    new_count = current_count + 1
    await middleware.bucket_set(BUCKET_NAME, user_id, new_count)
    
    if new_count % 10 == 0:
        return {"content": f"恭喜！你已经在这个机器人面前发言 {new_count} 次了！"}

def register(middleware):

    middleware.register_message_handler(counter_handler)
    print("计数器插件已加载。")
```

### 2.4 管理员权限

你可以使用 `middleware` 来检查一个用户是否是管理员，从而创建只有管理员才能使用的命令。

- `middleware.is_admin(user_id)`: 返回 `True` 或 `False`。

**示例：一个只能由管理员使用的插件**

```python
__description__ = "插件描述"
__version__ = "1.0.0"
__author__ = "开发者"
#配参
__param__ = {"required":True,"key":"桶名.key","bool":False,"placeholder":"","name":"输入框的名字","desc":"介绍"}
# /plugins/admin_only_plugin.py
from middleware.middleware import Middleware

async def admin_command_handler(message: dict):
    content = message.get("content", "")
    user_id = message["user_id"]
    
    if content == "!shutdown" and middleware.is_admin(user_id):
        # 这里只是示例，实际的关机逻辑会更复杂
        return {"content": "机器人正在关闭... (仅为演示)"}
    elif content == "!shutdown" and not middleware.is_admin(user_id):
        return {"content": "抱歉，你没有权限执行此操作。"}

def register(m: Middleware):
    global middleware
    middleware = m
    middleware.register_message_handler(admin_command_handler)
    print("管理员插件已加载。")
```

## 3. 总结

通过 `middleware` 对象，插件可以实现强大而丰富的功能：
1.  **创建 `register` 函数**作为插件入口。
2.  在 `register` 函数中获取 `Middleware` 实例。
3.  调用 `middleware.register_message_handler()` 来**监听消息**。
4.  在消息处理器中，通过返回字典来**快速响应**，或使用 `middleware.send_message()` **主动发送**。
5.  使用 `middleware.bucket_*` 函数来**存储和读取数据**。
6.  使用 `middleware.is_admin()` 来实现**权限控制**。

遵循以上模式，你就可以开始构建你自己的插件了！

## middleware中间件基础功能函数

```python
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
            asyncio.create_task(self.send_message(platform, target_id, content, msg=msg))
            return True
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

    async def notify_admin(self, message: str, platform: str = "reverse_ws"):
        """
        向所有管理员发送私聊消息。此消息【不会】被自动撤回。
        :param message: 
        :param platform: 默认reverse_ws
        :return: 
        """
        admin_list = await self.bucket_get("system", "admin_list", [])
        if not admin_list:
            self.logger.warning("通知管理员失败：未设置任何管理员。")
            return

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

```

# 青龙调用

## 方法一

```python
#插件填写下方路径,例子：
from containers.qinglong_client import QinglongClient
import asyncio
containers_config = await middleware.bucket_manager.get("system", "containers", {})
for name, config in containers_config.items():
    if config.get('enabled'):
        target_container = config
        target_container['name'] = name
        break
client = QinglongClient(
        url=target_container['url'],
        client_id=target_container['client_id'],
        client_secret=target_container['client_secret']
    )
get_envs = await asyncio.get_running_loop().run_in_executor(None, client.get_envs(searchValue))

#这是可以调用的函数，
def get_envs(self, searchValue: str = None):
    """获取环境变量"""
    self._get_token()
    params = {'searchValue': searchValue} if searchValue else {}
    try:
        response = requests.get(f"{self.url}/open/envs", headers=self.headers, params=params, timeout=10)
        response.raise_for_status()
        return response.json().get('data', [])
    except requests.RequestException as e:
        raise Exception(f"获取环境变量失败: {e}")

def add_envs(self, envs: list):
    """添加环境变量"""
    self._get_token()
    try:
        response = requests.post(f"{self.url}/open/envs", headers=self.headers, json=envs, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise Exception(f"添加环境变量失败: {e}")

def update_env(self, env: dict):
    """更新环境变量"""
    self._get_token()
    try:
        response = requests.put(f"{self.url}/open/envs", headers=self.headers, json=env, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise Exception(f"更新环境变量失败: {e}")

def delete_envs(self, ids: list):
    """删除环境变量"""
    self._get_token()
    try:
        response = requests.delete(f"{self.url}/open/envs", headers=self.headers, json=ids, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise Exception(f"删除环境变量失败: {e}")
```



## 方法二

```python
#插件填写下方路径
from containers.qinglong import QinglongContainer
containers_config = await middleware.bucket_get("system", "containers")
target_container = {}
qlname = ""
for name, config in containers_config.items():
    if config.get('enabled'):
        target_container["url"] = config.get("url")
        target_container["client_id"] = config.get("client_id")
        target_container["client_secret"] = config.get("client_secret")

        qlname = name
        break
client = QinglongContainer(
    qlname,
    target_container
)
get_envs = await client.get_envs(searchValue)


#---
async def get_envs(self,  searchValue: str = "") -> List[Dict[str, Any]]:
    """
    获取青龙面板中的所有环境变量。
    """
    data = await self._request("GET", "envs",params={"searchValue": searchValue})
    return data if data is not None else []

async def add_env(self, name: str, value: str, remarks: Optional[str] = None) -> bool:
    """
    添加一个环境变量。
    """
    payload = [{"name": name, "value": value, "remarks": remarks or ''}]
    result = await self._request("POST", "envs", json=payload)
    return result is not None

async def update_env(self, env_id: Any, name: str, value: str, remarks: Optional[str] = None) -> bool:
    """
    更新一个环境变量。
    """
    payload = {"id": env_id, "name": name, "value": value, "remarks": remarks or ''}
    result = await self._request("PUT", "envs", json=payload)
    return result is not None

async def delete_env(self, env_ids: List[Any]) -> bool:
    """
    删除一个或多个环境变量。
    """
    result = await self._request("DELETE", "envs", json=env_ids)
    return result is not None
```
