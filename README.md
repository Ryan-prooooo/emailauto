# QQ邮箱智能生活事件助手

智能分析 QQ 邮箱中的邮件，提取重要事件并推送通知。支持 AI 智能分类、事件提取、定时摘要推送，以及 AI 对话智能助手功能。

## 功能特性

- 📥 自动收取 QQ 邮箱邮件（IMAP）
- 🧠 AI 智能解析邮件内容（阿里百炼/通义千问）
- 🏷️ 自动分类（购物、账单、物流、社交、工作、订阅等）
- ⏰ 定时推送每日摘要
- 🤖 AI 智能对话助手（可查询邮件、事件，自动回复邮件）
- 🧩 LangGraph 工作流智能体（Supervisor 模式）
- 🔌 支持 MCP 工具扩展（Notion 归档、EML Parser）

## 技术栈概览

| 层级 | 前端 | 后端 |
| --- | --- | --- |
| 框架 | React 18 + Vite + TypeScript | Python 3.12 + FastAPI |
| 状态 | Zustand | - |
| UI | Ant Design | - |
| 路由 | React Router v6 | - |
| 数据库 | - | SQLAlchemy 2.0 (PostgreSQL) |
| AI | - | DashScope + LangGraph |
| 调度 | - | APScheduler |
| 扩展 | - | MCP (Notion, EML Parser) |

详细技术栈和实现方法见各模块架构文档：

- [AI 工程指南（文档索引）](docs/AI_ENGINEERING_GUIDE.md)
- [前端架构](docs/frontend-architecture.md)
- [后端架构](docs/backend-architecture.md)

## 快速开始

### 1. 配置环境变量

编辑项目根目录 `.env` 文件：

```env
# QQ邮箱配置
QQ_EMAIL=your_email@qq.com
QQ_AUTH_CODE=your_auth_code

# AI 配置 (阿里百炼 DashScope)
DASHSCOPE_API_KEY=your_api_key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_MODEL=qwen-plus
```

> **注意**：QQ 邮箱需要开启 IMAP/SMTP 服务并获取**授权码**（不是 QQ 密码）。

### 2. 启动应用

#### 方式一：直接启动后端（推荐，后端自动托管前端）

```bash
cd backend
pip install -r requirements.txt
python -m app.main
```

启动后访问 http://localhost:8000 即可使用完整功能（前端 + API）。

#### 方式二：Docker 本地开发

```bash
cd docker
docker compose up -d
```

访问 http://localhost

### 3. 访问应用

- **源码模式**
- 前端界面: http://localhost:8000/
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health
- 默认会先进入 AI 对话页，仪表盘通过左侧导航进入

- **Docker Compose 模式**
- 前端界面: http://localhost
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health
- 默认会先进入 AI 对话页，仪表盘通过左侧导航进入

Docker Compose 模式下，`frontend` 容器会通过内置 Nginx 将 `/api` 反向代理到
`backend:8000`，因此浏览器访问前端页面时无需额外配置 API 地址。

## 项目结构

```
MailLife-Ryyyyy/
├── frontend/                        # React 前端
│   └── src/
│       ├── api/                   # API 调用封装
│       ├── pages/                 # 页面组件
│       ├── stores/                # Zustand 状态管理
│       └── router/                # React Router 配置
├── backend/                        # FastAPI 后端
│   └── app/
│       ├── api/                   # API 路由
│       ├── agents/                # AI 智能体（LangGraph Supervisor）
│       ├── db/                    # 数据库模型
│       ├── imap/                  # IMAP 邮件收取
│       ├── parser/                # 邮件解析
│       ├── scheduler/             # 定时任务
│       ├── mailer/                # 邮件发送
│       ├── mcp/                   # MCP 客户端
│       ├── main.py                # 应用入口
│       └── requirements.txt       # 依赖
├── docs/                           # 项目文档
│   ├── AI_ENGINEERING_GUIDE.md    # 文档索引 + RACI
│   ├── backend-architecture.md    # 后端架构
│   ├── frontend-architecture.md   # 前端架构
│   ├── plan.md                    # 实施计划
│   └── feishu-integration.md     # 飞书集成（可选）
├── docker/                         # Docker 配置
├── scripts/                        # 部署脚本
├── .github/                        # GitHub Actions
├── AGENTS.md                       # AI 开发约束（最高优先级）
└── README.md
```

## API 接口概览

### 邮件管理
- `GET /api/emails` - 获取邮件列表
- `POST /api/emails/sync` - 同步邮件
- `POST /api/emails/parse-all` - 解析所有未处理邮件

### 事件管理
- `GET /api/events` - 获取事件列表
- `DELETE /api/events/{event_id}` - 删除事件

当前 Web 前端属于过渡态实现。为兼容既有后端返回结构，`frontend/src/api/` 会在请求封装层
对邮件和事件字段做一次归一化映射，再交给页面和 Zustand store 使用。

### AI 对话
- `POST /api/chat` - AI 智能对话（LangGraph Supervisor）
- `POST /api/chat/resume` - 恢复被 `interrupt` 挂起的回复/会议确认流程
- `GET /api/chat/sessions` - 获取会话列表
- `POST /api/chat/sessions` - 创建会话
- `GET /api/chat/{session_id}` - 获取会话消息
- `DELETE /api/chat/{session_id}` - 删除会话

`POST /api/chat` 在普通对话时返回完整消息列表；当 `reply_agent` 或 `meeting_agent`
触发 LangGraph `interrupt` 时，接口会返回待确认动作，前端展示确认卡片后再调用
`POST /api/chat/resume`，由后端继续执行真正的发送或 RSVP 写入。
`GET /api/chat/{session_id}` 会在该会话仍处于挂起状态时一并返回当前待确认动作，
用于刷新页面或重新进入会话后的状态恢复。
- `POST /api/reply/draft/{email_id}` - 生成邮件回复草稿
- `POST /api/reply/send/{email_id}` - 发送邮件回复

### 系统
- `GET /api/settings` - 获取设置
- `POST /api/settings/test-connection` - 测试 IMAP 连接
- `GET /health` - 健康检查

## 常见问题

### 1. 启动失败，提示 "ModuleNotFoundError"
确保在 `backend` 目录下运行 `pip install -r requirements.txt`，并使用 `python -m app.main` 启动。

### 2. 无法连接 QQ 邮箱
- 确认已开启 IMAP/SMTP 服务
- 确认使用的是**授权码**而非 QQ 密码
- 检查网络代理设置（`HTTP_PROXY` / `HTTPS_PROXY`）

### 3. AI 功能无法使用
检查 `.env` 中的 `DASHSCOPE_API_KEY` 是否填写正确。

### 4. LangGraph 接口调用失败
确认已安装依赖：`langgraph`、`langchain-core`、`langchain-openai`（见 `requirements.txt`）。

## Docker 部署

### 本地开发
```bash
cd docker
docker compose up -d
```

### 生产环境
详见 [docker/deploy-aliyun.md](docker/deploy-aliyun.md)

## CI/CD

本项目使用 GitHub Actions：
- **CI** (`ci.yml`): 提交/PR 时自动运行测试和构建
- **CD** (`deploy.yml`): 手动审批后自动部署到阿里云 ECS

详见 [.github/README.md](.github/README.md)

## Routing Note

For LangGraph conditional routing, `classify_intent` must return `MultiIntentType` label values such as `query_only`, `general_only`, and `meeting_only`. The graph maps those labels to concrete nodes through `add_conditional_edges(...)`; returning node names like `query_agent` directly will break route lookup.

When reading LangGraph execution results, prefer the top-level merged state returned by `graph.invoke(...)`. If `final_response` already exists at the top level, do not skip it and fall back to a generic "处理完成" message.

When LangGraph uses fan-out parallel execution, any shared state keys written by multiple nodes in the same step must declare reducers. In this project, keys such as `agent_outputs`, `executed_nodes`, and `execution_status` cannot remain plain scalar fields during parallel sub-agent execution.

Agent output payloads must be treated as nullable at field boundaries. Even when an agent call succeeds, nested payloads like `agent_outputs["summarizer"]["data"]` may still be `None`, so downstream nodes must normalize them before calling `.get(...)`.

The same rule applies to intent-classifier params: if the LLM returns `"params": null`, downstream nodes must coerce it back to `{}` before reading keys such as `email_id`, `tone`, or `query_type`.

## License

MIT
