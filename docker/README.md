# Docker 部署指南

## 快速开始

### 本地开发

```bash
cd docker
cp ../.env.prod.example .env
# 编辑 .env 填入实际配置
docker compose up -d
```

访问 http://localhost:80

停止服务：

```bash
docker compose down
```

### 生产环境

详见 [deploy-aliyun.md](deploy-aliyun.md)

## 服务架构

| 服务 | 端口 | 说明 |
|------|------|------|
| nginx | 80/443 | 反向代理 |
| frontend | 8080 | Vue 前端静态文件 |
| backend | 8000 | FastAPI API 服务 |
| postgres | 5432 | PostgreSQL 数据库 |

## 环境变量

详见 [.env.prod.example](../.env.prod.example)

## 常用命令

```bash
# 查看日志
docker compose logs -f

# 重启服务
docker compose restart

# 重新构建镜像
docker compose build --no-cache

# 进入容器调试
docker compose exec backend bash
```
