# Automan Framework

一个类似傻妞机器人和AutMan的机器人框架，具有多协议接入、插件化架构、规则引擎、持久化存储和可视化面板。

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
cd automan_framework
python main.py
```

### 2. 访问Web管理界面

打开浏览器访问 `http://127.0.0.1:5000`

### 3. WebSocket连接

客户端可以连接到 `ws://127.0.0.1:8080` 发送和接收消息

## Web管理功能

### 适配器管理
- 适配器状态监控
- 适配器配置（主机、端口、访问令牌等）

### 插件管理
- 扫描插件目录
- 在线编辑插件代码
- 创建新插件
- 插件热加载
- 启用/禁用插件
- 重载/卸载插件

### 规则管理
- 查看系统规则
- 添加新规则（支持正则表达式、关键词、完全匹配）

### 数据桶管理
- 查看桶列表
- 查看桶内容

### 日志管理
- 实时日志显示
- 历史日志查看

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

### 基本插件结构

```python
"""
插件名称
插件描述
"""

__description__ = "插件描述"
__version__ = "1.0.0"
__author__ = "开发者"

# 插件规则
rules = [
    {
        "name": "规则名称",
        "pattern": r"匹配模式",
        "handler": lambda msg, mw: {"content": "响应内容"},
        "rule_type": "regex",  # regex, keyword, fullmatch
        "priority": 1,
        "description": "规则描述"
    }
]

def handle_message(msg, middleware):
    """
    处理消息的函数
    """
    pass

def unload():
    """
    插件卸载时的清理函数
    """
    pass
```

## API接口

### 插件相关
- `GET /api/plugins` - 获取插件列表
- `GET /api/plugins/scan` - 扫描插件
- `GET /api/plugins/{name}/content` - 获取插件内容
- `POST /api/plugins/{name}/content` - 保存插件内容
- `POST /api/plugins/create` - 创建插件
- `POST /api/plugins/{name}/enable` - 启用插件
- `POST /api/plugins/{name}/disable` - 禁用插件
- `POST /api/plugins/{name}/reload` - 重载插件
- `POST /api/plugins/{name}/unload` - 卸载插件

### 规则相关
- `GET /api/rules` - 获取规则列表
- `POST /api/rules/add` - 添加规则

### 适配器相关
- `GET /api/adapters` - 获取适配器状态
- `GET /api/adapters/config` - 获取适配器配置
- `POST /api/adapters/config` - 保存适配器配置

### 其他
- `GET /api/buckets` - 获取桶列表
- `GET /api/buckets/{name}` - 获取桶数据
- `GET /api/logs` - 获取日志
- `GET /api/status` - 获取框架状态

## 配置

框架支持以下环境变量配置：

- `WS_HOST`: WebSocket服务器主机，默认 `0.0.0.0`
- `WS_PORT`: WebSocket服务器端口，默认 `8080` (用于接收QQ等平台消息)
- `REVERSE_WS_HOST`: 反向WebSocket服务器主机，默认 `0.0.0.0`
- `REVERSE_WS_PORT`: 反向WebSocket服务器端口，默认 `8081` (用于发送回复给QQ等平台)
- `WEB_UI_HOST`: Web界面主机，默认 `0.0.0.0`
- `WEB_UI_PORT`: Web界面端口，默认 `5000`
- `PLUGINS_DIR`: 插件目录，默认 `plugins`

## 测试

框架包含全面的测试脚本：

```bash
# WebSocket测试
python test_ws_client.py

# 全面功能测试
python comprehensive_test.py
```

## 架构说明

- `adapters/`: 协议适配器，处理不同平台的消息协议
- `middleware/`: 中间件层，提供统一接口给插件使用
- `plugins/`: 插件管理系统
- `rule_engine/`: 规则引擎，处理消息匹配
- `storage/`: 持久化存储系统
- `web_ui/`: Web管理界面
- `utils/`: 工具类

## 特殊说明

1. **插件热加载**: 支持动态启用/禁用、在线编辑和实时保存
2. **WebSocket服务器**: 提供WebSocket服务供客户端连接
3. **规则优先级**: 数值越大优先级越高
4. **日志轮转**: 自动管理日志文件大小和数量
5. **QQ集成**: 支持与QQ平台集成，通过双WebSocket架构实现消息收发
   - 端口8080: 接收来自QQ的消息
   - 端口8081: 发送回复到QQ
6. **反向WebSocket**: 用于将处理结果发送回消息平台

## 开发规范

- 所有插件必须遵循插件开发规范
- 插件文件名应使用下划线命名法
- 规则名称应具有唯一性
- 代码应包含适当的错误处理
