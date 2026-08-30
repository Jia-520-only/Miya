#!/bin/bash

echo "========================================"
echo "  弥娅 Web 公网部署助手"
echo "  Miya Web Public Deployment"
echo "========================================"
echo ""

cd "$(dirname "$0")"

# 检查配置文件
echo "[1/6] 检查配置文件..."
if [ ! -f "config/.env" ]; then
    echo "错误: 配置文件不存在 config/.env"
    echo "请先运行 ./install.sh 安装"
    exit 1
fi
echo "  ✓ 配置文件已找到"
echo ""

# 检查虚拟环境
echo "[2/6] 检查虚拟环境..."
if [ ! -d "venv" ]; then
    echo "错误: 虚拟环境不存在"
    echo "请先运行 ./install.sh 安装"
    exit 1
fi
echo "  ✓ 虚拟环境已找到"
echo ""

# 配置公网访问
echo "[3/6] 配置公网访问..."
read -p "是否启用公网访问？(y/n): " enable_public

if [ "$enable_public" = "y" ]; then
    echo ""
    echo "请选择公网访问方式:"
    echo "1. 仅使用公网 IP"
    echo "2. 使用域名 + 反向代理"
    echo ""
    read -p "请选择 (1/2): " access_mode

    if [ "$access_mode" = "1" ]; then
        echo ""
        echo "配置: 仅使用公网 IP 访问"
        echo ""
        read -p "请输入你的公网 IP 地址: " public_ip

        echo ""
        echo "正在更新配置..."
        sed -i 's/^WEB_API_HOST=.*/WEB_API_HOST=0.0.0.0/' config/.env
        echo "  ✓ 已将监听地址设置为 0.0.0.0"
        echo ""
        echo "========================================"
        echo "  重要: 请确保开放以下端口"
        echo "========================================"
        echo "  后端 API 端口: 8000"
        echo "  前端端口: 5173"
        echo ""
        echo "UFW 防火墙配置:"
        echo "  sudo ufw allow 8000/tcp"
        echo "  sudo ufw allow 5173/tcp"
        echo "  sudo ufw reload"
        echo ""
        echo "如果使用路由器，请在路由器中配置端口转发:"
        echo "  外部端口: 8000, 5173"
        echo "  内部端口: 8000, 5173"
        echo "  内部 IP: 你的服务器内网 IP"
        echo "========================================"
        echo ""
        echo "配置完成！访问地址:"
        echo "  http://$public_ip:5173     # 前端"
        echo "  http://$public_ip:8000     # API"
        echo "  http://$public_ip:8000/docs # API 文档"
        echo ""

    elif [ "$access_mode" = "2" ]; then
        echo ""
        echo "配置: 使用域名访问"
        echo ""
        read -p "请输入你的域名 (如: yourdomain.com): " domain
        read -p "请输入 API 子域名 (如: api.yourdomain.com, 可选): " api_domain

        echo ""
        echo "正在更新配置..."
        sed -i 's/^WEB_API_HOST=.*/WEB_API_HOST=0.0.0.0/' config/.env

        if [ -n "$api_domain" ]; then
            sed -i "s/^WEB_API_DOMAIN=.*/WEB_API_DOMAIN=$api_domain/" config/.env
            cors_value="https://$domain,https://www.$domain,https://$api_domain"
        else
            sed -i "s/^WEB_API_DOMAIN=.*/WEB_API_DOMAIN=$domain/" config/.env
            cors_value="https://$domain,https://www.$domain"
        fi

        sed -i "s/^WEB_API_CORS_ORIGINS=.*/WEB_API_CORS_ORIGINS=$cors_value/" config/.env

        echo "  ✓ 已将监听地址设置为 0.0.0.0"
        echo "  ✓ 已配置域名: $domain"
        if [ -n "$api_domain" ]; then
            echo "  ✓ 已配置 API 域名: $api_domain"
        fi
        echo "  ✓ 已配置 CORS: $cors_value"
        echo ""
        echo "========================================"
        echo "  后续步骤"
        echo "========================================"
        echo "1. 配置 DNS 解析"
        echo "   $domain          -> 你的公网 IP"
        if [ -n "$api_domain" ]; then
            echo "   $api_domain     -> 你的公网 IP"
        fi
        echo ""
        echo "2. 安装和配置 Nginx"
        echo "   sudo apt install nginx"
        echo "   配置文件已保存到: nginx_config_example.conf"
        echo ""
        echo "3. 配置 SSL 证书"
        echo "   sudo certbot --nginx -d $domain -d www.$domain"
        if [ -n "$api_domain" ]; then
            echo "   sudo certbot --nginx -d $api_domain"
        fi
        echo ""
        echo "4. 更新前端 API 地址"
        echo "   编辑 miya-pc-ui/src/services/api.ts"
        echo "   修改 API_BASE_URL 为: https://$api_domain"
        echo "========================================"
        echo ""
        echo "配置完成！访问地址:"
        echo "  https://www.$domain      # 前端"
        if [ -n "$api_domain" ]; then
            echo "  https://$api_domain    # API"
        fi
        echo ""

        # 生成 Nginx 配置
        if [ -n "$domain" ]; then
            cat > nginx_config_example.conf <<EOF
# 弥娅 Web Nginx 配置示例

# 前端配置
server {
    listen 80;
    server_name $domain www.$domain;

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

EOF

            if [ -n "$api_domain" ]; then
                cat >> nginx_config_example.conf <<EOF
# API 配置
server {
    listen 80;
    server_name $api_domain;

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

EOF
            fi

            echo "  ✓ Nginx 配置已保存到: nginx_config_example.conf"
        fi
    fi
else
    echo ""
    echo "跳过公网配置，将使用本地访问模式"
    echo ""
fi

# 检查 Node.js
echo "[4/6] 检查 Node.js..."
if ! command -v node &> /dev/null; then
    echo "警告: 未找到 Node.js，前端将无法启动"
    echo "请先安装 Node.js: https://nodejs.org/"
    exit 1
fi
echo "  ✓ Node.js 已安装"
node --version
echo ""

# 检查前端依赖
echo "[5/6] 检查前端依赖..."
cd miya-pc-ui
if [ ! -d "node_modules" ]; then
    echo "首次部署，正在安装前端依赖..."
    npm install
    if [ $? -ne 0 ]; then
        echo "错误: 前端依赖安装失败"
        exit 1
    fi
fi
echo "  ✓ 前端依赖已就绪"
cd ..
echo ""

echo "[6/6] 部署配置完成"
echo ""

echo "========================================"
echo "  部署配置完成！"
echo "========================================"
echo ""
echo "下一步:"
echo "  1. 运行 ./run/web_start.sh 启动服务"
echo "  2. 按照上述提示配置防火墙/DNS/Nginx"
echo "  3. 通过公网地址访问"
echo ""
