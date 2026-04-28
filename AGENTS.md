---
name: AGENTS.md
owner: Tech Lead
audience: AI 工具（Cursor/Cline）+ 全员工程师
last_review: 2026-04-19
review_cycle: quarterly
doc_rank: top
summary: AI 辅助开发最高约束，所有其他文档从本文件索引。
---

# AGENTS.md

本文件为 AI 辅助开发约束，供 Cursor / Cline 等 AI 工具遵循。

> **元规则（最高优先级）**：本文件的约束条款优先于 `docs/` 下所有其他文档。当本文件与其他文档冲突时，以本文件为准，不可擅自调和冲突而绕过本文件条款。

## 1. 先读什么

开始任何分析、修改或文档更新前，AI 必须先阅读：

1. `README.md`（了解项目整体功能与结构）
2. `AGENTS.md`（本文件）
3. 涉及模块的架构文档（`docs/backend-architecture.md` 或 `docs/frontend-architecture.md`）
4. 涉及模块的源代码

> 本项目所有开发文档索引见 [`docs/AI_ENGINEERING_GUIDE.md`](docs/AI_ENGINEERING_GUIDE.md)，包含文档关系、受众声明和 RACI 说明。

## 2. 规则优先级

发生冲突时，按以下顺序执行：

1. 用户当前明确要求
2. 本文件
3. 项目既有实现风格
4. AI 工具默认行为

## 3. 技术栈

- **前端**：React 18 + Vite + TypeScript + Zustand + Ant Design
- **后端**：Python 3.12 + FastAPI + SQLAlchemy + APScheduler
- **数据库**：PostgreSQL（`postgresql+asyncpg://`）
- **LLM**：阿里百炼（DashScope）OpenAI 兼容接口
- **容器化**：Docker + Docker Compose
- **CI/CD**：GitHub Actions

## 4. 代码规范

### Python（后端）

- 使用 `async/await` 处理所有 I/O 操作
- 类型注解覆盖所有公开函数和类
- Pydantic 模型用于 API 请求/响应验证
- 日志使用标准库 `logging`，不得使用 `print`

### React + TypeScript（前端）

- 使用函数组件 + Hooks，不使用类组件
- 状态管理使用 Zustand（`create`），不得混用其他状态库
- API 调用统一通过 `src/api/` 封装
- 组件 Props 使用 TypeScript 接口
- 路由使用 `react-router-dom` v6，`Outlet` 布局模式

## 5. LLM 配置规范

- 使用阿里百炼（DashScope）OpenAI 兼容接口
- 兼容模型：`qwen-plus` / `qwen-max` 等
- 配置变量：`DASHSCOPE_API_KEY` / `DASHSCOPE_BASE_URL` / `DASHSCOPE_MODEL`
- **不得擅自切换为非 DashScope 接口**（如 DeepSeek / OpenAI 直连）
- `EmailParser` 使用 OpenAI SDK + DashScope base_url，修改时不得改变接口签名

## 6. QQ 邮箱规范

- IMAP/SMTP 配置通过环境变量注入，**不得硬编码**
- 使用授权码而非 QQ 密码
- IMAP 连接失败时应检查网络代理设置（`HTTP_PROXY` / `HTTPS_PROXY`）

## 7. 数据库规范

- 后端使用 PostgreSQL，通过 `DATABASE_URL` 环境变量配置连接字符串
- 修改数据库模型后需同步更新 `configs/docker/postgres/init.sql`

## 8. MCP 工具扩展规范

- 项目支持 MCP 工具（Notion 归档 + EML Parser）
- 新增 MCP 工具需在 `.env` 中添加对应 `MCP_*_COMMAND` / `MCP_*_ARGS` 配置
- 不得在未说明影响的情况下增删 MCP 工具

## 9. AI Agent 规范

- 新增 agent 必须明确选择其中一种，并说明选择理由
- 在执行代码之前，需要同步先更新和此次代码有关的文档

## 10. Git 工作流

- 功能开发在 `feature/` 分支
- 发布使用 `release/` 分支
- 所有合并需经过 Pull Request + 代码审查
- Commit message 格式：`feat:` / `fix:` / `docs:` / `chore:`

## 11. Docker 规范

- 前端镜像：多阶段构建，基于 `node:20-alpine`
- 后端镜像：基于 `python:3.12-slim`
- 开发环境使用 `docker-compose.yml`，生产环境使用 `docker-compose.prod.yml`
- 所有密钥通过环境变量注入，**不得硬编码**

## 12. CI/CD 约束

- 所有 PR 必须通过 CI（测试 + 构建）才能合并
- 生产部署必须经过手动审批
- 部署脚本使用 `docker compose up -d --pull always`
- 部署前自动备份数据库

## 13. 核心强制规则

- 先理解上下文，再修改代码
- 优先做最小必要改动，不做无关重构
- 保持现有前后端架构、数据链路与模块边界稳定
- 优先复用现有实现模式，不擅自发明新结构
- 涉及接口、数据库、SSE 协议、配置或部署时，必须评估影响面
- 修复 bug 或新增核心逻辑时，必须补充相应验证
- 未经验证，不得声称"已修复""已完成""可上线"

## 14. 明确禁止事项

除非用户明确要求，否则 AI 禁止：

- 在 `main` 分支直接开发
- 提交真实 API Key / 授权码 / JWT Secret
- 绕过 QQ 邮箱 IMAP 鉴权
- 修改数据库连接字符串后未同步更新 `docker-compose`
- 批量改代码风格或批量重命名文件
- 删除用户现有功能或兼容逻辑
- 伪造测试结果、构建结果或运行结果
- 切换 LLM 供应商（DeepSeek / OpenAI 直连等）而不经用户确认

## 15. 完成任务前必须检查

在输出"完成"之前，AI 必须确认：

1. 改动范围与任务目标一致
2. 已在本地启动服务验证（`docker compose up` 或 `python main.py`）
3. 未改动未涉及模块的代码
4. 相关文档（README / AGENTS.md / 架构文档）已同步更新
5. 未引入 lint 错误

## 16. 输出要求

AI 完成任务后，输出应至少包含：

- **改了什么**
- **为什么这样改**
- **验证了什么**（附命令/结果）
- **还剩什么风险或待确认项**

如果因为环境限制未能完成测试或构建，必须明确说明，不得省略。

## 17. 文件结构

```
MailLife-Ryyyyy/
├── frontend/              # React 前端
│   └── src/
│       ├── api/          # API 调用封装
│       ├── pages/        # 页面组件 (.tsx)
│       ├── stores/       # Zustand 状态管理
│       ├── router/       # React Router v6 配置
│       ├── App.tsx       # 根组件
│       └── main.tsx      # 入口
├── backend/              # FastAPI 后端
│   └── app/
│       ├── api/          # API 路由
│       ├── agents/       # AI 智能体（LangGraph Supervisor）
│       ├── db/           # 数据库模型
│       ├── imap/         # IMAP 邮件收取
│       ├── parser/       # 邮件解析（AI）
│       ├── scheduler/    # 定时任务
│       ├── mailer/       # 邮件发送
│       ├── mcp/          # MCP 客户端
│       └── main.py       # 应用入口
├── docs/                 # 项目文档（统一入口：AI_ENGINEERING_GUIDE.md）
│   ├── AI_ENGINEERING_GUIDE.md  # 文档索引 + 受众 + RACI
│   ├── backend-architecture.md  # 后端架构
│   ├── frontend-architecture.md # 前端架构
│   ├── plan.md                  # 实施计划
│   └── feishu-integration.md    # 飞书集成（可选）
├── docker/               # Docker 配置
│   ├── Dockerfile.frontend
│   ├── Dockerfile.backend
│   ├── docker-compose.yml
│   └── docker-compose.prod.yml
├── configs/             # 配置文件
│   └── docker/
│       ├── nginx.conf
│       └── postgres/
├── scripts/             # 部署脚本
├── .github/             # GitHub Actions
│   └── workflows/
├── .env                 # 环境变量（勿提交）
├── .env.prod.example    # 生产环境变量模板
├── AGENTS.md            # AI 开发约束（最高优先级）
└── README.md
```

## 19. 文档引用约束

AI 在引用项目文件时，必须遵守以下约束：

1. **禁止硬编码绝对路径**：不得在代码或文档中写入类似 `D:\demo\MailLife-Ryyyyy\...` 或 `/home/user/project/...` 的绝对路径。统一使用相对于项目根目录的相对路径（如 `docs/plan.md`、`backend/app/main.py`）。
2. **文档路径以 `docs/` 为准**：`backend-architecture.md` 和 `frontend-architecture.md` 的权威路径为 `docs/`，不得引用 `backend/` 或 `frontend/` 目录下的同名文件。
3. **新增文档必须更新索引**：在 `docs/AI_ENGINEERING_GUIDE.md` 的索引表中注册新增文档路径，否则视为"未索引文档"，AI 工具可能忽略。

## 20. 一句话原则

> AI 代理的首要职责不是"尽快改代码"，而是"**做最小、可验证、不破坏现有架构的正确修改**"。
