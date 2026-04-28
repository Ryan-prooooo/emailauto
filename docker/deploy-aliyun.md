# 阿里云 ECS 部署指南

## 前置条件

- 阿里云 ECS 实例（Ubuntu 22.04）
- 域名（可选，用于 HTTPS）
- GitHub 仓库配置好 Actions Secrets

## 一、服务器配置

### 1.1 安装 Docker

```bash
ssh root@your-ecs-ip
curl -fsSL https://get.docker.com | sh
docker --version
usermod -aG docker ubuntu
```

### 1.2 安装 Docker Compose

```bash
apt install docker-compose-plugin
docker compose version
```

### 1.3 创建目录

```bash
mkdir -p /opt/maillife
cd /opt/maillife
```

### 1.4 拉取部署文件

```bash
git clone https://github.com/YOUR_USERNAME/MailLife-Ryyyyy.git .
cd docker
cp ../.env.prod.example .env
```

## 二、配置环境变量

编辑 `.env`：

```env
# 数据库（生产使用更强密码）
DATABASE_URL=postgresql+psycopg2://maillife:YOUR_SECURE_PASSWORD@postgres:5432/maillife

# JWT（生产必须使用强随机密钥）
JWT_SECRET_KEY=$(openssl rand -hex 32)

# QQ邮箱
QQ_EMAIL=your_email@qq.com
QQ_AUTH_CODE=your_auth_code

# AI
DASHSCOPE_API_KEY=sk-your-key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_MODEL=qwen-plus

# 前端
VITE_API_BASE_URL=https://your-domain.com/api
VITE_APP_NAME=MailLife
```

## 三、配置 Nginx + SSL

```bash
# 安装 Certbot
apt install certbot python3-certbot-nginx
certbot --nginx -d your-domain.com
```

## 四、手动部署（首次）

```bash
cd /opt/maillife/docker
docker compose -f docker-compose.prod.yml up -d
```

## 五、自动部署（GitHub Actions）

详见 [.github/README.md](../.github/README.md)

每次合并到 `main` 分支并审批后，Actions 自动执行 `scripts/deploy.sh`，流程如下：

1. SSH 连接到 ECS
2. 拉取最新代码和镜像
3. 执行 `docker compose -f docker-compose.prod.yml up -d --pull always`
4. 自动回滚（如果启动失败）

## 六、运维

### 查看状态

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f
```

### 更新部署

```bash
cd /opt/maillife
git pull
cd docker
docker compose -f docker-compose.prod.yml up -d --pull always
```

### 备份数据库

```bash
docker compose -f docker-compose.prod.yml exec postgres pg_dump -U maillife maillife > backup_$(date +%Y%m%d).sql
```

### 恢复数据库

```bash
cat backup_20250101.sql | docker compose -f docker-compose.prod.yml exec -T postgres psql -U maillife maillife
```

### 日志管理

```bash
# 限制日志大小
cat > /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

重启 Docker：`systemctl restart docker`

## 七、故障排查

### 容器启动失败

```bash
docker compose -f docker-compose.prod.yml logs backend
docker compose -f docker-compose.prod.yml ps
```

### 数据库连接失败

检查 `DATABASE_URL` 是否正确，容器网络是否正常：

```bash
docker network ls
docker compose -f docker-compose.prod.yml exec backend ping postgres
```

### 502 Bad Gateway

检查后端是否正常运行，Nginx 配置是否正确。
