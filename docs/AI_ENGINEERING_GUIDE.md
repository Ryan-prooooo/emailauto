---
name: AI_ENGINEERING_GUIDE.md
owner: Tech Lead
audience: 全员工程师 + AI 工具（Cursor/Cline）
last_review: 2026-04-19
review_cycle: quarterly
doc_rank: index
summary: 项目开发文档统一入口，包含文档索引、受众声明、RACI 说明和变更管理规范。所有新增文档必须在本文件注册。
---

# AI 工程指南

本文档是 `MailLife-Ryyyyy` 项目的**文档统一入口**，AI 工具和工程师应首先阅读本文件以了解文档结构和职责边界。

> **重要**：`AGENTS.md` 的约束条款优先于本文档及其他所有文档，发生冲突时以 `AGENTS.md` 为准。

## 受众声明

| 受众 | 说明 |
| --- | --- |
| 全员工程师 | 阅读 `AGENTS.md` + 本文件 + 相关架构文档 |
| AI 工具（Cursor/Cline） | 必须遵循 `AGENTS.md`，从本文件索引了解文档关系 |
| Tech Lead | 负责维护本文档索引和 RACI 表 |

## 文档索引

所有文档按以下分类组织，新增文档必须在本文档注册：

### 顶层约束

| 文档 | 说明 |
| --- | --- |
| `AGENTS.md` | AI 辅助开发最高约束，**优先级最高** |
| `README.md` | 项目整体介绍和快速开始 |

### docs/ 核心文档

| 文档 | 说明 | 负责人 |
| --- | --- | --- |
| `docs/AI_ENGINEERING_GUIDE.md` | 本文档，文档索引和 RACI | Tech Lead |
| `docs/backend-architecture.md` | 后端架构（FastAPI + LangGraph） | Backend Lead |
| `docs/frontend-architecture.md` | 前端架构（React + Zustand） | Frontend Lead |
| `docs/plan.md` | 实施计划 | Tech Lead |

### docs/ 功能文档

| 文档 | 说明 | 负责人 |
| --- | --- | --- |
| `docs/feishu-integration.md` | 飞书集成方案（可选扩展） | 待定 |

### docs/ 部署文档

| 文档 | 说明 |
| --- | --- |
| `docker/deploy-aliyun.md` | 阿里云生产部署指南 |
| `scripts/deploy.sh` | 部署脚本 |

## RACI 说明

RACI = Responsible（负责）、Accountable（审批）、Consulted（咨询）、Informed（知情）。

### 文档变更 RACI

| 变更类型 | Tech Lead | Backend Lead | Frontend Lead | AI 工具 |
| --- | --- | --- | --- | --- |
| 架构设计变更 | A | R | R | I |
| 新增 API 接口 | C | R | C | I |
| 前端页面变更 | I | C | R | C |
| 文档内容更新 | A | C | C | R |
| 安全相关变更 | R | C | C | I |
| 部署配置变更 | A | R | I | I |

### 决策流程

1. **小型变更**（文档修正、配置调整）：AI 工具直接执行，Tech Lead 事后审阅
2. **中型变更**（新增接口、页面调整）：Backend/Frontend Lead 确认后执行
3. **大型变更**（架构调整、多模块联动）：三方评审后执行

## 文档维护约定

1. 所有 `docs/` 下的 Markdown 文档必须包含 frontmatter 元信息（name、owner、audience、last_review、review_cycle）
2. 文档路径以 `docs/` 为准，不得在 `backend/` 或 `frontend/` 下创建架构文档
3. `AGENTS.md` 和 `AI_ENGINEERING_GUIDE.md` 变更需 Tech Lead 审批
4. 每个文档的 `last_review` 字段在变更后更新
5. 季度审阅（`review_cycle: quarterly`）时检查所有文档有效性

## 相关文档

- [AGENTS.md](../AGENTS.md) - AI 辅助开发约束（最高优先级）
- [docs/plan.md](./plan.md) - 完整实施计划
- [docs/backend-architecture.md](./backend-architecture.md) - 后端架构
- [docs/frontend-architecture.md](./frontend-architecture.md) - 前端架构
- [docs/feishu-integration.md](./feishu-integration.md) - 飞书集成
