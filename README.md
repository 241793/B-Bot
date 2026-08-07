# 🤖 B-Bot

> **一个 AI 驱动的跨平台机器人框架** —— 把大模型装进 QQ、Telegram、企业微信、钉钉、飞书……让机器人真正「会思考、能执行、可扩展」。

[![Version](https://img.shields.io/badge/version-1.1.2-blue.svg)](https://github.com/241793/B-Bot/releases)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](./LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](./docs/docker)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

---

## ✨ 一句话理解 B-Bot

B-Bot 不是一个简单的「关键词自动回复机器人」，而是一套 **AI Agent 运行时**：

- **多协议接入** —— 一个框架，同时连接 QQ、微信、Telegram、企业微信、钉钉、飞书……
- **AI 大脑** —— 内置大模型对话、RAG 知识库、MCP 工具调用、可视化工作流编排
- **插件生态** —— Python / JavaScript 双语言热加载插件，支持奥特曼(ATM)插件兼容
- **内置青龙** —— 环境变量、定时任务、脚本管理一站式搞定，告别单独部署青龙面板
- **可视化运维** —— Web 管理面板，多主题、移动端适配，点点鼠标就能配置一切

---

## 🏗 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                      Web 管理面板 (Port 5000)                 │
│   控制台 │ 插件 │ 规则 │ AI大脑 │ 青龙 │ 支付 │ 系统配置      │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                      B-Bot 核心引擎                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ 适配器层  │  │ 规则引擎  │  │ AI 大脑  │  │ 插件系统  │  │
│  │ QQ/TG/微信│  │ 正则/关键词│  │ LLM+RAG │  │ Py/JS    │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
│       └──────────────┴──────────────┴──────────────┘        │
│                        Middleware (统一消息总线)                │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                      能力扩展层                               │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────┐    │
│  │ 内置青龙    │  │ 本地图床    │  │ 支付系统(支付宝) │    │
│  │ 定时任务    │  │ 文件上传    │  │ 订单管理         │    │
│  │ 环境变量    │  │ 公开直链    │  │ 回调通知         │    │
│  └────────────┘  └────────────┘  └──────────────────┘    │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────┐    │
│  │ 知识库(RAG)│  │ 工作流编排  │  │ 子智能体(Agent)  │    │
│  │ 向量检索    │  │ 可视化画布  │  │ 独立技能/知识    │    │
│  │ .bbotkb    │  │ 条件分支    │  │ 唤醒词隔离      │    │
│  └────────────┘  └────────────┘  └──────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 方式一：Docker 部署（推荐）

```bash
docker run -d \
  --name bbot \
  --restart unless-stopped \
  -p 5000:5000 \
  -p 8888:8888 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /your/path/data:/app/mount \
  241793/b-bot:latest
```

> 💡 **首次启动后**，建议进入容器执行一次「更新」命令，拉取最新内置数据。  
> 💡 **端口说明**：`5000` = Web 管理面板，`8888` = WebSocket 消息通道。

启动成功后访问 **http://你的服务器IP:5000** 即可进入 Web 管理界面。

### 方式二：本地运行

```bash
# 克隆仓库
git clone https://github.com/241793/B-Bot.git
cd B-Bot

# 安装依赖（建议使用虚拟环境）
pip install -r requirements.txt

# 启动
python main.py
```

访问 **http://127.0.0.1:5000**，WebSocket 地址：**ws://127.0.0.1:8888**

### 方式三：Windows 一键运行

下载 `B-BOT.exe`（v0.0.9），双击运行即可。⚠️ Win 版已停更，仅建议体验。

---

## 📦 核心功能详解

### 1️⃣ 多协议适配器

B-Bot 通过适配器层统一接入各大 IM 平台，新增渠道只需实现一个适配器接口。

| 适配器 | 协议 | 说明 |
|--------|------|------|
| `qq` | WebSocket (llonebot) | 对接 NTQQ + llonebot 插件，`ws://127.0.0.1:8888/ws/qq` |
| `qqbot` | HTTP + WebSocket | 官方 QQ Bot 开放平台，AppID + Secret 直连 |
| `wxclaw` | WebSocket | 微信 ClawBot，支持 24h 主动回复窗口管理 |
| `tgbot` | Telegram Bot API | 标准 Telegram Bot，Token 配置即用 |
| `wechat_work` | 企业微信 API | 企业微信应用消息推送 |
| `dingtalk` | 钉钉机器人 | 钉钉群机器人 Webhook |
| `feishu` | 飞书开放平台 | 飞书机器人事件订阅 |
| `web_ui` | HTTP | Web 端调试入口，无需客户端 |
| `custom` | Webhook | 自定义外部系统对接，支持双向通信 + 签名校验 |

#### Custom 适配器：对接你的业务系统

```python
import requests

# 外部系统 → B-Bot（入站）
resp = requests.post(
    "http://127.0.0.1:5000/api/adapters/custom/inbound",
    headers={"X-Custom-Token": "YOUR_TOKEN"},
    json={"user_id": "u_001", "content": "查询订单状态", "source": "crm"}
)
```

B-Bot 处理后会回调你的业务系统：

```json
{
  "event": "bot_reply",
  "target_id": "u_001",
  "content": "您的订单已发货，预计明天送达。",
  "meta": {"source": "ai_workflow"}
}
```

---

### 2️⃣ AI 大脑

B-Bot 的 AI 大脑不是简单的「调一下 ChatGPT API」，而是一套完整的 **Agent 运行时**。

#### 配置中心

支持多模型配置、自动 Failover、累计 Token 统计：

| 字段 | 说明 |
|------|------|
| `provider` | 模型供应商标识 |
| `base_url` | OpenAI 兼容 API 地址 |
| `api_key` | 认证密钥 |
| `model` | 模型名称（如 `gpt-4o`、`deepseek-chat`） |
| `temperature` | 采样温度（0~2） |
| `max_tokens` | 最大输出长度 |
| `system_prompt` | 全局系统提示词 |

**Failover 机制**：当主模型返回 429/5xx/超时，自动切换到其他已启用的模型；主模型恢复后自动切回。

#### 知识库（RAG）

```
文本/文件/URL → 自动切片 → 向量化 → 存储
                                    ↓
用户提问 → 向量检索 TopK → 拼入 Prompt → LLM 生成回答
```

支持导入格式：`txt`、`md`、`pdf` 等。知识包 `.bbotkb` 可导出/导入，主库与子智能体库**完全隔离**。

#### 工作流编排

可视化拖拽式 AI 流水线，支持 4 种节点：

| 节点类型 | 作用 | 典型用法 |
|----------|------|----------|
| `knowledge` | 知识检索 | 先查知识库，再决定如何回答 |
| `llm` | 模型推理 | 基于上下文生成回答 |
| `mcp` | 工具调用 | 调用外部 API（天气、搜索、数据库…） |
| `condition` | 条件分支 | 根据上一步结果走不同路径 |

**完整工作流示例**（知识库路由问答）：

```json
[
  {"id": "k1", "type": "knowledge", "query": "{{input}}",
   "bucket": "ai_knowledge", "top_k": 5, "output_var": "kb", "next": "c1"},
  {"id": "c1", "type": "condition", "expr": "kb != []",
   "true_next": "l1", "false_next": "l2", "output_var": "passed"},
  {"id": "l1", "type": "llm",
   "prompt": "用户问题：{{input}}\n检索知识：{{kb}}\n请基于知识回答。",
   "output_var": "answer"},
  {"id": "l2", "type": "llm",
   "prompt": "用户问题：{{input}}\n知识库未命中，请给通用建议。",
   "output_var": "answer"}
]
```

#### AI 定时任务

```yaml
名称: daily_report
Cron: "0 9 * * *"     # 每天早上9点
适配器: tgbot
目标类型: group
目标ID: "-1001234567890"
工作流ID: demo_kb_answer
固定Prompt: "请生成今日运营简报"
```

到点自动执行 → 调用工作流 → 推送结果到指定群/用户。

---

### 3️⃣ 插件系统

#### 插件开发模式

B-Bot 支持 **两种插件风格**，按需选择：

| 模式 | 特点 | 适合场景 |
|------|------|----------|
| **B-Bot 原生** | 异步优先、Middleware API 完整 | 新项目、高性能需求 |
| **奥特曼(ATM)兼容** | 同步风格、`Sender` 对象、兼容现有 ATM 插件 | 迁移旧插件、快速上手 |

#### 最小可用插件（B-Bot 原生）

```python
"""
Ping 测试插件
检测机器人连通性
"""
__description__ = "Ping 测试"
__version__ = "1.0.0"
__author__ = "your_name"
__imType__ = "qq,web_ui"
__admin__ = False

import asyncio, requests

async def handle(msg, mw):
    content = str(msg.get("content", "")).strip()
    if content != "ping":
        return None

    # 阻塞操作放线程池，不卡主循环
    def _req():
        return requests.get("https://httpbin.org/get", timeout=(5, 15)).status_code
    code = await asyncio.to_thread(_req)

    return {"content": f"🏓 pong! (HTTP {code})"}

rules = [{
    "name": "ping",
    "pattern": r"^ping$",
    "handler": handle,
    "rule_type": "regex",
    "priority": 0,
    "description": "连通性测试"
}]
```

#### 插件热加载

- 放入 `plugins/` 目录 → 自动发现 → 页面启用/禁用
- Web 在线编辑器修改 → 保存即重载，无需重启
- 支持 Python 语法预检，保存前自动检查

#### 插件 Webhook

每个插件可暴露独立 HTTP 端点：

```
POST /api/plugins/my_plugin/webhook
```

实现 `handle_webhook(data, request_method, request_headers, ...)` 即可接收外部回调，常用于支付通知、CI/CD 触发、IoT 事件等。

---

### 4️⃣ Middleware API 速查

`Middleware` 是插件与框架交互的唯一桥梁，以下是核心方法：

| 方法 | 说明 |
|------|------|
| `send_message(platform, target_id, content, msg)` | 主动发消息（异步） |
| `send_response(msg, {"content": "..."})` | 回复当前消息 |
| `wait_for_input(msg, timeout_ms)` | 等待用户下一次输入（多轮对话） |
| `at_user(msg, user_id, content)` | 群内 @某人 |
| `at_all(msg, content)` | 群内 @全体成员 |
| `reply_with_image(msg, url_or_base64)` | 回复图片 |
| `reply_with_video(msg, url)` | 回复视频 |
| `bucket_get/set/delete/keys/clear(name, key)` | 持久化键值存储 |
| `is_admin(user_id)` | 权限校验 |
| `notify_admin(message, platforms)` | 通知所有管理员 |
| `push_to_group/platform, group_id, content)` | 推送群消息（不受撤回影响） |
| `get_http_session()` | 获取共享 aiohttp 会话 |
| `run_sync(func, *args)` | 线程池跑同步代码 |

---

### 5️⃣ 内置青龙

不再需要单独部署青龙面板 —— B-Bot 把青龙的核心能力**内嵌**了。

| 能力 | 说明 |
|------|------|
| 环境变量管理 | 增删改查、启用/禁用、模糊搜索 |
| 定时任务 | Cron 表达式、手动触发、运行日志 |
| 脚本管理 | Python / JavaScript，文件夹树展示 |
| 依赖管理 | pip / npm 依赖统一安装 |
| API Key | 生成 OpenAPI Token 供外部调用 |

#### 脚本内管理环境变量（QLEnv SDK）

运行时自动注入 `QL_API_BASE` 和 `QL_INTERNAL_KEY`，脚本内直接操作：

```python
# Python 脚本
from ql_env import QLEnv

# 读取
row = QLEnv.get_env("JD_COOKIE")
if row:
    print(f"ID={row['id']}, Value={row['value']}")

# 写入（有则更新，无则新增）
QLEnv.set_env("JD_COOKIE", "pt_key=xxx;pt_pin=yyy;", "京东账号")

# 按名删除全部
QLEnv.delete_env_by_name("OLD_COOKIE")
```

```javascript
// JavaScript 脚本
const { QLEnv } = require('ql_env');

// 读取
const row = await QLEnv.getEnv('JD_COOKIE');
console.log(row?.value);

// 写入
await QLEnv.setEnv('JD_COOKIE', 'pt_key=xxx;', '京东账号');
```

> **`setEnv` 语义**：同名 0 条 → 新增；1 条 → 更新；多条 → 更新 id 最小的一条。要追加同名账号池，用 `addEnv`。

---

### 6️⃣ 内置支付系统

集成支付宝码支付能力，插件可直接调用：

```python
# 创建订单
result = await middleware.create_payment(
    money="9.99",
    name="VIP会员",
    out_trade_no="ORDER_001"
)

if result["code"] == 1:
    qr_code = result["qr_code"]  # base64 二维码
    await middleware.send_message("qq", user_id, f"[CQ:image,file=base64://{qr_code}]")

# 查询订单
status = await middleware.query_order("ORDER_001")
if status["status"] == 1:
    print("✅ 支付成功")
```

支持**经营码模式**（自动分配唯一金额防重复）、**传统模式**（固定金额）、**订单超时自动过期**、**前端轮询 + 后端自动检测**双保险。

---

## 🗂 项目结构

```
B-Bot/
├── main.py                    # 入口
├── middleware/                # 核心中间件
│   ├── middleware.py          # 异步 Middleware（推荐）
│   ├── atm_middleware.py      # ATM 兼容层
│   └── atm_context.py         # 上下文管理
├── adapters/                 # 适配器
│   ├── qq.py                  # llonebot WebSocket
│   ├── qqbot.py               # 官方 QQ Bot
│   ├── wxclaw.py              # 微信 ClawBot
│   ├── tgbot.py               # Telegram
│   ├── wechat_work.py         # 企业微信
│   ├── dingtalk.py            # 钉钉
│   ├── feishu.py              # 飞书
│   └── custom.py              # 自定义 Webhook
├── plugins/                   # 插件目录
│   ├── qinglong_lib/          # 青龙 SDK
│   │   ├── python/ql_env.py
│   │   └── js/ql_env.js
│   └── js/                    # JS 插件
├── ai/                       # AI 大脑
│   ├── config.py              # 模型配置
│   ├── knowledge.py           # 知识库(RAG)
│   ├── workflow.py            # 工作流引擎
│   ├── mcp.py                 # MCP 工具
│   └── agent.py               # 子智能体
├── qinglong/                 # 内置青龙
│   ├── container.py
│   └── qinglong_client.py
├── web/                      # Web 管理面板
│   ├── static/
│   └── templates/
├── docs/                     # 在线文档
├── data/                     # 持久化数据（Docker 挂载）
│   └── jobs.db
├── .env                      # 环境变量配置
└── requirements.txt
```

---

## ⚙️ 环境变量配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `qq_HOST` | `0.0.0.0` | WebSocket 监听地址 |
| `qq_PORT` | `8888` | WebSocket 端口 |
| `WEB_UI_HOST` | `0.0.0.0` | Web 面板地址 |
| `WEB_UI_PORT` | `5000` | Web 面板端口 |
| `plugin_secret_key` | 自动生成 | 插件/青龙内部鉴权密钥 |

更多配置项在 Web「系统配置」页面可视化设置（GitHub 代理、日志清理策略、Docker 代理等）。

---

## 📖 开发指南

### 插件开发最佳实践

1. **异步优先**：handler 用 `async def`，阻塞操作放 `asyncio.to_thread()` 或 `middleware.run_sync()`
2. **超时控制**：所有网络请求必须设超时 `timeout=(5, 20)`
3. **异常兜底**：插件内捕获异常并回复可读错误，不要抛出到顶层
4. **空值判断**：`msg.get("content")` 可能为 `None`，务必判空
5. **幂等设计**：Webhook 插件保证重复回调不产生副作用

### 规则引擎

| rule_type | 说明 | 示例 |
|-----------|------|------|
| `regex` | 正则匹配 | `r"^签到$"` |
| `keyword` | 关键词包含 | `"天气"` |
| `fullmatch` | 完全匹配 | `"help"` |

> 规则优先级：数值越大越先匹配。多条规则命中时，高优先级先执行。

---

## 🔄 更新日志

### v1.1.2 (2026-07-20)

**🧠 AI / Agent**
- 子智能体：独立技能、知识库、提示词、唤醒词
- 知识包 `.bbotkb` 统一导出/导入（条目 + 附件）
- 技能中心、MCP、工作流、AI 定时任务、记忆管理、Bot-Chat 人工客服
- 管理员可通过 AI 对话管理内置青龙

**🔌 适配器**
- 官方 QQ Bot 对接（AppID / Secret）
- 多账号能力（QQbot / 企业微信 / TG / wxclaw）
- wxclaw 24h 回复窗口自动管理
- Custom 适配器：入站 Webhook + 出站回调验签

**🐍 内置青龙**
- 脚本内 `QLEnv` SDK（JS + Python）
- 自动注入 `QL_API_BASE` / `QL_INTERNAL_KEY`
- 空文件夹显示、缓存过滤、语法预检

**🧩 插件系统**
- AI 辅助编写插件 + 行级 diff 高亮
- `register()` / `test` 入口 + `wait_for_input` 多轮对话
- 调试日志精准匹配

### v1.1.1 (2026-06-16)
- 完善 Agent 能力、内置支付系统、UI 优化

### v1.0.2 (2026-03-03)
- 授权逻辑、更新指令、主题切换、移动端适配

### v1.0.1 (2026-02-28)
- 内置青龙，告别独立青龙面板

### v1.0.0
- 多适配器架构、插件热加载、规则引擎

---

## ❓ 常见问题

| 问题 | 解决方案 |
|------|----------|
| AI 不回复 | 检查 AI 大脑是否启用 → 模型是否保存并启用 → 唤醒词/管理员权限 |
| 适配器连不上 | 检查 Token / 回调地址 / 代理设置 → 查看系统日志 |
| 插件调试无输出 | 确认代码已应用 → 检查 `__pattern__` / `register` → 多轮对话在超时内回复 |
| 青龙任务不跑 | 任务是否启用 → Cron 表达式是否正确 → 脚本是否存在 → 依赖是否安装 |
| `QLEnv` 报未注入密钥 | 必须在内置青龙里运行脚本 → 重启后端后再试 |
| Docker 更新后数据丢失 | 确认 `data` 卷挂载到 `/app/mount` → 更新前先备份 |
| 在线文档不更新 | 清空 GitHub 代理缓存 → 刷新页面 → 检查页脚 hash |

---

## 📋 使用声明

> ⚠️ **本项目仅供学习与研究使用**，请勿用于任何违法违规场景。  
> 请于下载后 **24 小时内删除**。因使用本项目产生的任何后果，作者不承担法律责任。

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📄 License

[MIT License](./LICENSE)

---

<div align="center">

**⭐ 如果 B-Bot 对你有帮助，请给一个 Star 支持一下！**

[GitHub](https://github.com/241793/B-Bot) · [在线文档](https://241793.github.io/B-Bot/)

</div>
