---
name: frontend-architecture.md
owner: Frontend Lead
audience: 前端工程师 + AI 工具
last_review: 2026-04-19
review_cycle: quarterly
related_docs:
  - docs/AI_ENGINEERING_GUIDE.md
  - docs/plan.md
summary: 前端技术架构文档，包含 React 18 + Vite + TypeScript + Zustand + Ant Design 的完整模块说明。
---

# 前端架构

React 18 + Vite + TypeScript + Zustand + Ant Design 单页应用，通过 Axios 调用后端 REST API。

## 技术栈

| 类别 | 技术 | 说明 |
| --- | --- | --- |
| 框架 | React 18 | 函数组件 + Hooks，不使用类组件 |
| 构建 | Vite | 快速 HMR 开发体验 |
| 语言 | TypeScript | 严格模式，类型注解全覆盖 |
| 状态 | Zustand | `create()` API，集中在 `src/stores/` |
| UI | Ant Design 5 | 企业级 React 组件库 |
| 路由 | React Router v6 | `Outlet` 布局模式 |
| HTTP | Axios | API 调用封装，拦截器统一处理 |
| 样式 | CSS Modules + Ant Design Token | 组件级样式隔离 |

## 功能模块

### 1. 仪表盘 (Dashboard)

系统状态概览页，通过侧边栏进入。

- 邮箱接入状态卡片（已连接/未连接）
- 邮件统计（总数、已分类、待处理）
- 事件统计（按分类分组）
- 最近事件时间线（最近 5 条）

### 2. 时间线 (Timeline)

按时间倒序展示所有邮件和事件的页面。

- 分页加载（每页 20 条）
- 按分类筛选（购物、账单、物流、社交、工作、订阅等）
- 按日期范围筛选
- 邮件/事件类型标签区分

### 3. AI 对话助手 (Chat)

调用后端 `/api/chat`，并在收到 `status="interrupted"` 时展示确认卡片，再通过
`/api/chat/resume` 恢复 LangGraph 执行。重新进入已有会话时，前端通过
`GET /api/chat/{session_id}` 恢复消息列表和待确认动作。

- 流式消息展示（SSE）
- 切换 LangGraph 模式（ReAct 已废弃）
- 支持查询邮件内容、事件信息
- 支持生成回复草稿、发送邮件

### 4. 设置 (Settings)

配置 QQ 邮箱、AI 参数、定时推送。

- QQ 邮箱 IMAP/SMTP 配置（地址、授权码）
- AI 配置（模型选择）
- 定时推送时间设置
- 连接测试按钮
- IMAP 连接状态检测

## 目录规范

```
frontend/src/
├── api/              # API 调用封装
│   ├── index.ts      # Axios 实例（baseURL、拦截器）
│   ├── types.ts      # API 请求/响应 TypeScript 类型
│   ├── emails.ts     # 邮件 API（sync, list, parse-all）
│   ├── events.ts      # 事件 API（list）
│   ├── chat.ts        # AI 对话 API（LangGraph）
│   └── system.ts      # 系统 API（settings, health）
├── pages/            # 页面组件（.tsx）
│   ├── Layout.tsx    # 布局（Sidebar + Outlet）
│   ├── Dashboard.tsx
│   ├── Timeline.tsx
│   ├── Chat.tsx
│   └── Settings.tsx
├── stores/           # Zustand 状态
│   ├── email.ts      # 邮件列表、筛选状态
│   └── event.ts      # 事件列表、统计
├── router/
│   └── index.ts      # React Router v6 路由配置
├── App.tsx           # 根组件（RouterProvider）
└── main.tsx          # 入口（createRoot）
```

## API 调用规范

### Axios 实例封装

所有请求通过 `src/api/index.ts` 的 Axios 实例，baseURL 指向后端地址（开发模式 `http://localhost:8000`）。

请求拦截器自动注入 `Content-Type: application/json`。
当前 Web 过渡态中，`src/api/` 同时承担接口适配层职责：后端历史字段会在这里统一映射为
前端页面继续使用的 `received_at`、`processed`、`event_time`、`important` 等字段，
避免把兼容逻辑分散到页面组件和 Zustand store。
同样地，调度器、设置、测试连接等系统接口也应在这里完成返回值类型收口，页面层不再依赖
`as { ... }` 形式的临时强转去猜测后端响应结构。
界面层的默认文案、筛选项和导航落点也应与当前后端能力保持一致，例如首页默认进入 AI 对话，
时间线分类以现有邮件/事件分类字段为准，而不是继续沿用历史占位文案。

### 接口调用示例

```typescript
// GET /api/emails?page=1&limit=20&category=shopping
import { getEmails } from '@/api/emails';
const { data } = await getEmails({ page: 1, limit: 20, category: 'shopping' });

// POST /api/chat
import { chatApi } from '@/api/chat';
const response = await chatApi.sendMessage(null, '帮我查一下最近的订单');

// POST /api/chat/resume
await chatApi.resumeAction(response.thread_id!, true);
```

## 状态管理规范

使用 Zustand `create()`，每个 store 单一职责：

```typescript
// stores/email.ts
import { create } from 'zustand';
import { getEmails } from '@/api/emails';

interface EmailState {
  emails: Email[];
  loading: boolean;
  fetchEmails: (params: EmailQuery) => Promise<void>;
}

export const useEmailStore = create<EmailState>((set) => ({
  emails: [],
  loading: false,
  fetchEmails: async (params) => {
    set({ loading: true });
    const { data } = await getEmails(params);
    set({ emails: data.items, loading: false });
  },
}));
```

## 组件规范

- 函数组件 + Hooks，**不使用类组件**
- Props 使用 TypeScript `interface`
- 业务组件放在 `pages/`，通用 UI 组件放在 `components/`
- 组件文件 `.tsx`，纯工具函数 `.ts`
- 样式使用 CSS Modules（`*.module.css`）或 Ant Design Token

## 路由规范

使用 React Router v6 `Outlet` 布局模式：

```typescript
// router/index.ts
export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Navigate to="/chat" replace /> },
      { path: 'dashboard', element: <Dashboard /> },
      { path: 'timeline', element: <Timeline /> },
      { path: 'chat', element: <Chat /> },
      { path: 'settings', element: <Settings /> },
    ],
  },
]);
```

## 与后端交互

- 前端**不直接操作数据库**，所有数据通过 API 获取
- SSE 流式响应用于 AI 对话（`fetch` + `ReadableStream`）
- 错误处理：API 返回非 2xx 时显示 Ant Design `message.error`
- 前端**不处理邮件同步逻辑**，仅调用 `/api/emails/sync` 触发后端任务

Chat 会话删除遵循“本地状态优先、后端列表再对齐”的交互约定：删除接口成功后，前端应先立即从 Zustand `sessions` 中移除该会话，并在需要时清空当前选中会话，再异步刷新 `/api/chat/sessions`，避免用户看到删除按钮点击后列表仍短暂停留。
