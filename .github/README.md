# GitHub Actions CI/CD

## 概览

本项目使用 GitHub Actions 实现自动化：

| Workflow | 触发条件 | 说明 |
|----------|---------|------|
| `ci.yml` | Push/PR | 测试 + 构建 + 推送镜像 |
| `deploy.yml` | 手动审批 | SSH 部署到阿里云 ECS |

## CI：持续集成

### 流程

```
Push / Pull Request
  ↓
ci.yml
  ├── 前端单元测试 (Vitest)
  ├── 后端单元测试 (pytest)
  ├── 构建 Docker 镜像
  │   ├── frontend (ghcr.io/owner/maillife-frontend:tag)
  │   └── backend  (ghcr.io/owner/maillife-backend:tag)
  └── 推送镜像到 GitHub Container Registry
```

### 状态检查

所有检查通过后，PR 才能合并到 `main` 分支。

## CD：持续部署（手动审批）

### 流程

```
合并到 main
  ↓
deploy.yml 等待审批
  ↓
[手动点击 Approve]
  ↓
  ├── SSH 连接到阿里云 ECS
  ├── 拉取最新镜像
  └── 执行 docker compose up -d --pull always
```

### 审批要求

需要以下人员之一审批：
- Repository Admin
- 指定的 Reviewer

## 环境变量配置

### CI Secrets（仓库设置 → Secrets and variables → Actions）

| Secret | 说明 |
|--------|------|
| `GHCR_TOKEN` | GitHub Container Registry 访问令牌 |
| `DEPLOY_SSH_KEY` | ECS SSH 私钥 |
| `DEPLOY_SSH_KNOWN_HOSTS` | ECS 指纹（用于验证 SSH 连接） |

### 部署变量（仓库设置 → Secrets and variables → Variables）

| Variable | 说明 |
|----------|------|
| `DEPLOY_HOST` | 阿里云 ECS 公网 IP |
| `DEPLOY_USER` | SSH 用户名（如 `ubuntu`） |
| `DEPLOY_PATH` | 部署路径（如 `/opt/maillife`） |

## 本地测试 Actions

安装 [act](https://github.com/nektos/act) 本地运行 Actions：

```bash
# 运行 CI
act -j ci

# 运行 CD（需要 Secrets）
act -j deploy
```

## 镜像管理

镜像存储在 GitHub Container Registry：

- 前端：`ghcr.io/YOUR_USERNAME/maillife-frontend`
- 后端：`ghcr.io/YOUR_USERNAME/maillife-backend`

查看镜像：

```bash
# 本地登录
echo $GHCR_TOKEN | docker login ghcr.io -u YOUR_USERNAME --password-stdin

# 查看镜像
docker images ghcr.io/YOUR_USERNAME/maillife-*
```

## 回滚

如果部署失败，可以手动回滚：

```bash
ssh ubuntu@DEPLOY_HOST
cd /opt/maillife/docker
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```
