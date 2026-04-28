---
name: backend-architecture.md
owner: Backend Lead
audience: 后端工程师 + AI 工具
last_review: 2026-04-19
review_cycle: quarterly
related_docs:
  - docs/AI_ENGINEERING_GUIDE.md
  - docs/plan.md
summary: 后端技术架构文档，包含 Python 3.12 + FastAPI + SQLAlchemy + APScheduler + LangGraph 的完整模块说明。
---

# 后端架构

Python 3.12 + FastAPI + SQLAlchemy + APScheduler，使用阿里百炼 DashScope 作为 LLM 提供者。

## 技术栈

| 类别 | 技术 | 说明 |
| --- | --- | --- |
| Web 框架 | FastAPI | async/await 全覆盖，Pydantic 验证 |
| 数据库 | SQLAlchemy 2.0 + asyncpg | async ORM，PostgreSQL |
| 调度 | APScheduler | 邮件同步 + 每日摘要定时任务 |
| LLM | DashScope OpenAI 兼容接口 | qwen-plus / qwen-max 等模型 |
| Agent | LangGraph | LangGraph Supervisor |
| 邮件收取 | imaplib + QQ邮箱授权码 | IMAP UID 增量同步 |
| 邮件解析 | BeautifulSoup + lxml | HTML 清洗 + MIME 解析 |
| 邮件发送 | smtplib + email | SMTP QQ 邮箱推送 |
| 扩展 | MCP (Model Context Protocol) | Notion 归档 + EML Parser |
| 日志 | Python logging | 分级日志，不得使用 print |

## 功能模块

### 1. 邮件收取 (imap/)

IMAP 协议从 QQ 邮箱拉取邮件。

- QQ 邮箱 IMAP 地址: `imap.qq.com:993`
- 使用授权码（非 QQ 密码）认证
- UID 增量拉取，记录 last_uid 避免重复
- MIME 解析提取: 主题、发件人、收件人、日期、正文（text/html + text/plain）、附件

### 2. 邮件解析 (parser/)

清洗邮件内容，提取结构化信息。

- BeautifulSoup + lxml 清洗 HTML，移除脚本、样式、广告
- 纯文本提取（降级处理）
- AI 解析: 调用 DashScope 提取邮件分类和关键事件信息

### 3. 数据库 (db/)

SQLAlchemy 2.0 async ORM，PostgreSQL。

**表结构（events）**：id / email_id / title / event_type / start_time / end_time / organizer / attendees（JSON）/ rsvp_status（pending/accepted/declined/tentative）/ meeting_link / status

**表结构（chat_messages）**：id / session_id / role / content / message_type / agent_name / memory_type / summary

### 4. AI Agent 系统 (agents/)

#### ReAct Agent (`agents.py`)

[已废弃] 原基于 langchain-community + DashScope 的 ReAct 实现，现统一走 LangGraph Supervisor。

- 工具: search_emails、get_events、draft_reply、send_reply
- 对话记忆: PostgreSQL 存储历史消息
- Function Calling 支持

#### LangGraph Agent (`graph/`)

Supervisor 模式，多节点编排:

```
classify_intent → [意图路由]
  ├─ parser_only       → parser_agent → aggregate
  ├─ summarizer_only   → summarizer_agent → aggregate
  ├─ reply_only        → reply_agent → confirm/cancel → reflect → aggregate
  ├─ meeting_only      → meeting_agent → aggregate      ← Phase 2 新增
  ├─ query_only       → query_agent → aggregate
  ├─ general_only      → general_agent → aggregate
  └─ multi_intent     → fan-out 并行
```

状态定义见 `state.py`：`EmailAgentState`（messages / intents / action_params / agent_outputs / pending_draft）

| 节点 | 职责 | 输出 key |
|------|------|---------|
| classify_intent | LLM 结构化输出意图分类 | intents / intent_reasoning / action_params |
| parser_agent | IMAP 同步 + AI 解析邮件 | agent_outputs["parser"] |
| summarizer_agent | 生成摘要 + 归档 Notion | agent_outputs["summarizer"] |
| reply_agent | 生成邮件回复草稿 → interrupt 挂起 | pending_draft |
| confirm_reply / cancel_reply | 确认/取消后处理 | agent_outputs["send"] |
| reflect_check | 安全检查（密码/银行卡/API Key） | agent_outputs["reflect"] |
| meeting_agent | 会议 RSVP 决策 + LLM 建议 | agent_outputs["meeting"] |
| query_agent | 查询邮件/事件列表 | agent_outputs["query"] |
| general_agent | 通用 LLM 问答 | agent_outputs["general"] |
| aggregate_and_respond | 汇总所有节点输出为最终响应 | final_response |

### 5. 定时任务 (scheduler/)

APScheduler 管理后台任务。

- **邮件同步任务**: 每 `CHECK_INTERVAL_MINUTES` 分钟拉取新邮件
- **每日摘要任务**: 每天 `SCHEDULED_SEND_HOUR:MINUTE` 推送摘要到 QQ 邮箱
- 任务持久化到数据库，支持重启恢复

### 6. MCP 扩展 (mcp/)

Model Context Protocol 客户端，支持工具扩展。
- `client.py`: stdio 进程通信，执行 MCP 工具
- `notion_adapter.py`: 将 AI 对话记忆归档到 Notion 数据库
- 配置: `MCP_NOTION_COMMAND` / `MCP_NOTION_ARGS` / `MCP_NOTION_CWD`

### 7. API 路由 (api/)

FastAPI 路由，按职责拆分:

- `routes_core.py`: 系统状态、设置管理、IMAP 连接测试
- `routes_chat.py`: AI 对话与会话管理（统一走 LangGraph Supervisor）
- `routes_agents.py`: LangGraph Agent 对话
- `routes_core.py` 还承载邮件、事件、调度器和系统设置的 REST 接口，包括
  `GET /api/events`、`GET /api/events/{event_id}`、`DELETE /api/events/{event_id}`、
  `PUT /api/events/{event_id}/rsvp` 等过渡态 Web 前端仍在使用的路由。

### Chat Interrupt / Resume

- `POST /api/chat`: 普通请求返回会话消息；如果 `reply_agent` 或 `meeting_agent`
  触发 `interrupt`，则返回 `status="interrupted"` 和待确认载荷。
- `GET /api/chat/{session_id}`: 返回会话消息；如果对应 `thread_id` 仍存在未确认的
  `pending_draft` / `pending_meeting`，则同时返回 `status="interrupted"` 和待确认载荷。
- `POST /api/chat/resume`: 前端提交 `thread_id + confirmed`，后端调用
  `EmailAgent.resume(...)` 恢复 LangGraph，继续执行确认发送或 RSVP 更新。
- `thread_id` 使用 `email-{session_id}` 规则，与 `EmailAgent.chat()` 的 checkpoint key 保持一致。

## 目录规范

```
backend/app/
├── api/                  # API 路由
│   ├── __init__.py
│   ├── deps.py           # 依赖注入（get_db、get_current_user 等）
│   ├── schemas.py        # Pydantic 请求/响应模型
│   ├── routes_core.py    # 系统/设置 API
│   ├── routes_chat.py    # AI 对话 API
│   └── routes_agents.py  # LangGraph Agent API
├── agents/               # AI Agent 实现
│   ├── __init__.py
│   ├── base.py           # Agent 基类
│   ├── agents.py         # [已废弃] 原 ReAct Agent
│   ├── tools.py          # 工具注册表
│   ├── tools_impl.py     # 工具具体实现
│   ├── memory.py         # 对话记忆管理
│   ├── email_reply.py    # 邮件回复工具
│   └── graph/            # LangGraph 实现
│       ├── __init__.py
│       ├── state.py      # AgentState 定义
│       ├── nodes.py      # 各节点实现
│       └── email_agent.py # Email Agent 入口
├── db/                   # 数据库层
│   ├── __init__.py
│   ├── database.py       # 异步连接管理（postgresql+asyncpg）
│   ├── models.py         # SQLAlchemy 模型
│   └── migrate.py        # 数据库迁移脚本
├── imap/                 # IMAP 邮件收取
│   └── __init__.py
├── parser/               # 邮件解析
│   └── __init__.py
├── scheduler/            # 定时任务
│   └── __init__.py
├── mailer/               # 邮件发送
│   └── __init__.py
├── mcp/                  # MCP 扩展
│   ├── __init__.py
│   ├── client.py         # MCP 客户端
│   └── notion_adapter.py # Notion 归档适配器
├── core/                 # 核心配置
│   └── __init__.py
├── config.py             # 配置加载（pydantic-settings）
├── logger.py             # 日志配置
├── main.py               # FastAPI 应用入口 + 静态文件托管
└── requirements.txt      # Python 依赖
```

## 核心配置

通过 `pydantic-settings` 从 `.env` 加载:

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # QQ 邮箱
    qq_email: str
    qq_auth_code: str
    qq_imap_host: str = "imap.qq.com"
    qq_imap_port: int = 993

    # 阿里百炼
    dashscope_api_key: str
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_model: str = "qwen-plus"

    # 数据库
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mailife"

    # 调度
    check_interval_minutes: int = 5
    scheduled_send_hour: int = 9
    scheduled_send_minute: int = 0

    class Config:
        env_file = ".env"
        extra = "ignore"
```

## API 设计规范

### 路由拆分原则

- `routes_core.py`: 纯数据读写，无 AI 调用
- `routes_chat.py`: AI 对话与会话管理，统一走 LangGraph Supervisor
- `routes_agents.py`: AI 对话，LangGraph 模式

### Pydantic Schema

所有 API 请求/响应使用 Pydantic 模型验证:

```python
# schemas.py
from pydantic import BaseModel
from typing import Optional, List

class ChatRequest(BaseModel):
    message: str
    history: List[dict] = []

class ChatResponse(BaseModel):
    reply: str
    tool_calls: Optional[List[dict]] = None
```

### SSE 流式响应

LangGraph 对话使用 Server-Sent Events 流式返回:

```python
@router.post("/agents/langgraph/chat")
async def langgraph_chat(request: ChatRequest):
    async def generate():
        async for chunk in agent.astream(request.message):
            yield f"data: {json.dumps(chunk)}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")
```

## 与前端交互

- 前端通过 Axios 调用 REST API
- SSE 流式响应用于 AI 对话
- CORS 配置允许前端开发服务器访问
- 静态文件托管: FastAPI 通过 `StaticFiles` 托管前端构建产物（生产模式）
