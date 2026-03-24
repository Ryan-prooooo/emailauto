# QQ邮箱智能生活事件助手

智能分析QQ邮箱中的邮件，提取重要事件并推送通知。支持 AI 智能分类、事件提取、定时摘要推送，以及 AI 对话智能助手功能。

## 功能特性

- 📥 自动收取QQ邮箱邮件（IMAP）
- 🧠 AI智能解析邮件内容（DeepSeek/ChatGPT）
- 🏷️ 自动分类（购物、账单、物流、社交、工作、订阅等）
- ⏰ 定时推送每日摘要
- 🤖 AI 智能对话助手（可查询邮件、事件，甚至自动回复邮件）
- 🧩 LangGraph 工作流智能体（与现有 ReAct 并存）
- 🔌 支持 MCP 工具扩展

## 项目结构

```
MailLife/
├── frontend/                 # Vue 3 前端界面
│   ├── src/
│   │   ├── App.vue          # 主应用
│   │   └── main.ts          # 入口
│   ├── index.html           # HTML 模板
│   ├── package.json         # 前端依赖
│   └── vite.config.ts       # Vite 配置
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── api/             # API 路由定义 (位于 __init__.py)
│   │   ├── agents/          # AI 智能体/Agent
│   │   ├── core/            # 核心配置 (config.py 位于此处)
│   │   ├── db/              # 数据库模型
│   │   ├── imap/            # IMAP 邮件收取
│   │   ├── parser/          # 邮件解析（AI）
│   │   ├── scheduler/       # 定时任务
│   │   ├── mailer/          # 邮件发送
│   │   ├── mcp/             # MCP 客户端
│   │   ├── main.py          # 应用入口
│   ├── .env                 # 环境变量配置
│   └── requirements.txt     # 后端依赖
└── README.md
```

## 快速开始

### 1. 安装依赖

#### 后端依赖

```bash
cd backend/app
pip install -r requirements.txt
```

#### 前端依赖（仅开发模式需要）

```bash
cd frontend
npm install
```

### 2. 配置环境变量

编辑 `backend/.env` 文件（注意：项目直接使用 `.env`，而非 `.env.example`）：

```env
# QQ邮箱配置
QQ_EMAIL=your_email@qq.com
# 授权码（必须在QQ邮箱设置中开启IMAP/SMTP后获取）
QQ_AUTH_CODE=your_auth_code

# AI 配置 (支持 DeepSeek 或 OpenAI)
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat

# 可选：MCP EML Parser 配置（用于解析eml文件）
# MCP_EML_PARSER_COMMAND=uv
# MCP_EML_PARSER_ARGS=--directory,/path/to/eml_parser_mcp,run,eml_parser_mcp.py
# MCP_EML_PARSER_CWD=/path/to/eml_parser_mcp
```

> **注意**：QQ邮箱需要开启 IMAP/SMTP 服务并获取**授权码**（不是QQ密码）。

### 3. 启动应用

#### 方式一：直接启动后端（推荐，后端自动托管前端）

```bash
cd backend/app
python main.py
```

启动后访问 http://localhost:8001 即可使用完整功能（前端 + API）。

#### 方式二：分别启动前后端（仅开发调试）

1. 启动后端：
   ```bash
   cd backend/app
   python main.py
   ```

2. 启动前端：
   ```bash
   cd frontend
   npm run dev
   ```

### 4. 访问应用

- **前端界面**: http://localhost:8001/ （仪表盘、邮件、事件、设置、AI助手）
- **API 文档**: http://localhost:8001/docs
- **健康检查**: http://localhost:8001/health

## API 接口概览

### 邮件管理
- `GET /api/emails` - 获取邮件列表
- `POST /api/emails/sync` - 同步邮件
- `POST /api/emails/parse-all` - 解析所有未处理邮件

### 事件管理
- `GET /api/events` - 获取事件列表

### AI 对话
- `POST /api/chat` - AI 智能对话（支持 Function Calling）
- `POST /api/reply/draft/{email_id}` - 生成邮件回复草稿
- `POST /api/reply/send/{email_id}` - 发送邮件回复

### LangGraph（新增）
- `POST /api/agents/langgraph/chat` - 使用 LangGraph 的 AI 对话（返回 `tool_calls`/`tool_results`）

### 定时任务
- `POST /api/scheduler/trigger-sync` - 手动触发同步

### 设置
- `GET /api/settings` - 获取设置
- `POST /api/settings/test-connection` - 测试IMAP连接

## 配置说明

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `QQ_EMAIL` | QQ邮箱地址 | - |
| `QQ_AUTH_CODE` | QQ邮箱授权码 | - |
| `OPENAI_API_KEY` | OpenAI/DeepSeek API Key | - |
| `OPENAI_BASE_URL` | API 地址 | `https://api.deepseek.com/v1` |
| `OPENAI_MODEL` | 使用模型 | `deepseek-chat` |
| `CHECK_INTERVAL_MINUTES` | 邮件检查间隔(分钟) | `5` |
| `SCHEDULED_SEND_HOUR` | 每日推送时间(小时) | `9` |
| `SCHEDULED_SEND_MINUTE` | 每日推送时间(分钟) | `0` |

## 常见问题

### 1. 启动失败，提示 "ModuleNotFoundError"

确保在 `backend/app` 目录下运行 `pip install -r requirements.txt`，并且 Python 环境已正确激活。

### 2. 无法连接 QQ 邮箱

- 确认已开启 IMAP/SMTP 服务。
- 确认使用的是**授权码**而非 QQ 密码。
- 尝试在网页端登录 QQ 邮箱检查是否安全策略阻止。

### 3. AI 功能无法使用

检查 `.env` 中的 `OPENAI_API_KEY` 是否填写正确，以及网络能否访问 `OPENAI_BASE_URL`。

### 4. LangGraph 接口调用失败 / ImportError

- 确认已在后端环境安装依赖：`langgraph`、`langchain-core`（见 `backend/app/requirements.txt`）。
- 如果报 `No module named 'langchain_openai'`：LangGraph 节点实现使用了 `langchain_openai.ChatOpenAI`，需要额外安装：
  - `pip install langchain-openai`

## License

MIT
