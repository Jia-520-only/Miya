# 弥娅 Web 公网访问快速开始

## 三分钟快速公网部署

### Windows

1. **运行部署助手**
```batch
deploy_public.bat
```

2. **选择访问方式**
   - 方式1: 仅使用公网 IP（最简单）
   - 方式2: 使用域名（需要购买域名）

3. **配置防火墙**
```powershell
# Windows 防火墙
New-NetFirewallRule -DisplayName "Miya Web API" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
New-NetFirewallRule -DisplayName "Miya Web UI" -Direction Inbound -Protocol TCP -LocalPort 5173 -Action Allow
```

4. **启动服务**
```batch
run\web_start.bat
```

5. **访问**
```
http://你的公网IP:5173
```

---

### Linux/macOS

1. **运行部署助手**
```bash
chmod +x deploy_public.sh
./deploy_public.sh
```

2. **选择访问方式**
   - 方式1: 仅使用公网 IP
   - 方式2: 使用域名

3. **配置防火墙**
```bash
sudo ufw allow 8000/tcp
sudo ufw allow 5173/tcp
sudo ufw reload
```

4. **启动服务**
```bash
./run/web_start.sh
```

5. **访问**
```
http://你的公网IP:5173
```

---

## 使用域名访问（推荐）

### 1. 购买域名
- 阿里云: https://wanwang.aliyun.com
- 腾讯云: https://dnspod.cloud.tencent.com
- Cloudflare: https://www.cloudflare.com

### 2. 配置 DNS 解析
```
A 记录: yourdomain.com -> 你的公网IP
A 记录: www.yourdomain.com -> 你的公网IP
A 记录: api.yourdomain.com -> 你的公网IP
```

### 3. 安装 Nginx
```bash
# Ubuntu/Debian
sudo apt install nginx -y

# CentOS/RHEL
sudo yum install nginx -y
```

### 4. 使用生成的配置文件
部署助手会生成 `nginx_config_example.conf`，将其复制到 Nginx 配置目录：

```bash
sudo cp nginx_config_example.conf /etc/nginx/sites-available/miya
sudo ln -s /etc/nginx/sites-available/miya /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 5. 配置 SSL（免费）
```bash
# 安装 certbot
sudo apt install certbot python3-certbot-nginx -y

# 自动配置证书
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com -d api.yourdomain.com
```

### 6. 访问
```
https://www.yourdomain.com     # 前端
https://api.yourdomain.com     # API
https://api.yourdomain.com/docs # API 文档
```

---

## 路由器端口转发（如果使用 NAT）

如果服务器在内网，需要配置路由器端口转发：

1. 登录路由器管理页面（通常是 192.168.1.1）
2. 找到"端口转发"或"虚拟服务器"设置
3. 添加规则：

| 规则名称 | 外部端口 | 内部端口 | 内部 IP | 协议 |
|---------|---------|---------|---------|------|
| Miya Web UI | 5173 | 5173 | 192.168.1.x | TCP |
| Miya Web API | 8000 | 8000 | 192.168.1.x | TCP |

4. 保存并重启路由器

---

## 查看公网 IP

### Windows
```batch
curl ifconfig.me
```

### Linux/macOS
```bash
curl ifconfig.me
```

或访问: https://www.whatismyip.com/

---

## 安全建议

1. **使用 HTTPS**（配置 SSL 证书）
2. **修改默认端口**（避免使用 8000, 5173）
3. **启用 API 认证**（在 `.env` 中设置 `API_AUTH_KEY`）
4. **使用 Cloudflare**（提供 CDN 和 DDoS 防护）

---

## 常见问题

**Q: 无法访问？**
- 检查防火墙是否开放端口
- 检查路由器是否配置端口转发
- 使用 `curl http://localhost:8000` 测试本地是否正常

**Q: 域名无法解析？**
- 等待 DNS 传播（5-10 分钟）
- 使用 `nslookup yourdomain.com` 检查解析

**Q: SSL 证书配置失败？**
```bash
sudo certbot --force-renewal --nginx -d yourdomain.com
```

---

## 更详细的文档

完整部署指南: [PUBLIC_DEPLOYMENT_GUIDE.md](./PUBLIC_DEPLOYMENT_GUIDE.md)

---

## 一键命令总结

```bash
# Windows
deploy_public.bat        # 配置公网访问
run\web_start.bat       # 启动服务

# Linux/macOS
chmod +x deploy_public.sh
./deploy_public.sh       # 配置公网访问
./run/web_start.sh      # 启动服务
```
