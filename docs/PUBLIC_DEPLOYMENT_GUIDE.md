# 弥娅 Web 公网部署指南

## 概述

弥娅 Web 前端支持使用你的域名和公网 IP 进行公网访问，让你可以在任何地方通过浏览器访问弥娅。

## 部署方式

### 方式一：直接使用公网 IP（最简单）

#### 1. 修改配置文件

编辑 `config/.env` 文件：

```env
# Web API 配置
WEB_API_HOST=0.0.0.0
WEB_API_PORT=8000
```

#### 2. 开放端口

- **后端 API 端口**: 8000
- **前端开发端口**: 5173

在防火墙中开放这些端口：

**Windows 防火墙**:
```powershell
# 添加入站规则
New-NetFirewallRule -DisplayName "Miya Web API" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
New-NetFirewallRule -DisplayName "Miya Web UI" -Direction Inbound -Protocol TCP -LocalPort 5173 -Action Allow
```

**Linux (ufw)**:
```bash
sudo ufw allow 8000/tcp
sudo ufw allow 5173/tcp
sudo ufw reload
```

**Linux (firewalld)**:
```bash
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --permanent --add-port=5173/tcp
sudo firewall-cmd --reload
```

#### 3. 路由器端口转发（如果使用 NAT）

访问路由器管理页面（通常是 192.168.1.1），添加端口转发规则：

- **外部端口**: 8000, 5173
- **内部 IP**: 你的服务器内网 IP（如 192.168.1.100）
- **内部端口**: 8000, 5173
- **协议**: TCP

#### 4. 启动服务

```batch
run\web_start.bat
```

#### 5. 访问地址

```
http://你的公网IP:5173        # 前端
http://你的公网IP:8000        # API
http://你的公网IP:8000/docs   # API 文档
```

---

### 方式二：使用域名 + 反向代理（推荐）

#### 1. 准备域名

- 购买域名（推荐使用阿里云、腾讯云、Cloudflare）
- 配置 DNS 解析，将域名指向你的公网 IP

#### 2. 安装 Nginx（反向代理）

**Ubuntu/Debian**:
```bash
sudo apt update
sudo apt install nginx -y
```

**CentOS/RHEL**:
```bash
sudo yum install nginx -y
```

**Windows**: 下载 [Nginx for Windows](http://nginx.org/en/download.html)

#### 3. 配置 Nginx

创建配置文件 `/etc/nginx/sites-available/miya`:

```nginx
# 后端 API 反向代理
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

# 前端反向代理
server {
    listen 80;
    server_name www.yourdomain.com yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:5173;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

启用配置:

```bash
sudo ln -s /etc/nginx/sites-available/miya /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 4. 配置 SSL（HTTPS，强烈推荐）

使用 Let's Encrypt 免费证书:

```bash
# 安装 certbot
sudo apt install certbot python3-certbot-nginx -y

# 自动获取并配置证书
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com -d api.yourdomain.com

# 设置自动续期
sudo certbot renew --dry-run
```

Nginx 配置会自动更新为 HTTPS，无需手动修改。

#### 5. 更新前端配置

修改 `miya-pc-ui/src/services/api.ts` 中的 API 地址：

```typescript
const API_BASE_URL = process.env.REACT_APP_API_URL || 'https://api.yourdomain.com';
```

#### 6. 启动服务

```bash
run/web_start.sh
```

#### 7. 访问地址

```
https://www.yourdomain.com     # 前端
https://api.yourdomain.com     # API
https://api.yourdomain.com/docs # API 文档
```

---

### 方式三：使用云服务部署（最稳定）

#### 1. 使用 CloudBase（腾讯云）

弥娅已集成 CloudBase，可以直接一键部署。

**步骤**:
1. 在 IDE 中点击集成菜单 → CloudBase
2. 登录腾讯云账号
3. 创建环境
4. 一键部署

#### 2. 使用 Vercel（前端）

```bash
cd miya-pc-ui
npm install -g vercel
vercel
```

#### 3. 使用 Railway/Render（后端）

- 连接 GitHub 仓库
- 选择 `run/web_main.py` 作为启动命令
- 设置环境变量
- 自动部署

---

## 安全配置

### 1. 修改 CORS 配置

编辑 `run/web_main.py`，限制允许的域名：

```python
# 配置 CORS（限制特定域名）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # 只允许你的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. 添加认证中间件

在 `config/.env` 中配置：

```env
# API 认证密钥
API_AUTH_KEY=your_secure_random_key
```

### 3. 启用限流

```env
# 限流配置
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=30
```

### 4. 使用 Cloudflare（可选）

- 将域名接入 Cloudflare
- 启用 CDN 和 DDoS 防护
- 配置防火墙规则

---

## 性能优化

### 1. 构建前端生产版本

```bash
cd miya-pc-ui
npm run build:renderer
```

将 `dist` 目录部署到 Nginx 或 CDN。

### 2. 使用 PM2 管理后端进程

```bash
# 安装 PM2
npm install -g pm2

# 启动后端
pm2 start run/web_main.py --name miya-web

# 开机自启
pm2 startup
pm2 save
```

### 3. 启用 Gzip 压缩

在 Nginx 配置中添加：

```nginx
gzip on;
gzip_types text/plain text/css application/json application/javascript text/xml;
```

---

## 监控和日志

### 1. 查看实时日志

```bash
# PM2 日志
pm2 logs miya-web

# 系统日志
tail -f logs/miya_web_*.log
```

### 2. 使用 Docker（推荐）

创建 `Dockerfile.web`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "run/web_main.py"]

EXPOSE 8000
```

构建和运行：

```bash
docker build -f Dockerfile.web -t miya-web .
docker run -d -p 8000:8000 --name miya-web miya-web
```

---

## 故障排除

### 问题1: 无法访问

**检查**:
1. 防火墙是否开放端口
2. 路由器是否配置端口转发
3. 服务是否正常启动

**命令**:
```bash
# 检查端口监听
netstat -tlnp | grep 8000

# 检查防火墙
sudo ufw status
```

### 问题2: 域名无法解析

**检查**:
1. DNS 解析是否生效（使用 `nslookup yourdomain.com`）
2. 等待 DNS 传播（通常 5-10 分钟）

### 问题3: SSL 证书错误

**解决**:
```bash
# 重新申请证书
sudo certbot --force-renewal --nginx -d yourdomain.com
```

---

## 成本估算

### 域名费用
- .com 域名：约 50-100 元/年
- .cn 域名：约 30-50 元/年

### 服务器费用（如果使用云服务器）
- 阿里云/腾讯云：约 50-100 元/月（2核4G）
- 轻量服务器：约 30-50 元/月

### SSL 证书
- Let's Encrypt：免费
- 商业证书：约 100-500 元/年

---

## 推荐方案

| 需求 | 推荐方案 | 成本 |
|------|---------|------|
| 个人测试 | 公网 IP | 免费 |
| 小团队 | 域名 + SSL | 50-100 元/年 |
| 生产环境 | 域名 + VPS + SSL | 50-150 元/月 |
| 企业级 | CloudBase + CDN | 按量计费 |

---

## 快速开始

选择适合你的部署方式，按照上述步骤操作即可！

如有问题，查看 [故障排除](#故障排除) 或提交 Issue。
