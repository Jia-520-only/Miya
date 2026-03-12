# 弥娅 Web 前端启动指南

## 快速启动

### Windows

#### 方法一：使用启动菜单
```batch
start.bat
```
然后选择 `4. Start Web UI (Frontend + Backend)`

#### 方法二：直接启动
```batch
run\web_start.bat
```

### Linux/macOS

```bash
# 添加执行权限
chmod +x run/web_start.sh

# 启动
./run/web_start.sh
```

## 访问地址

启动成功后，访问以下地址：

- **前端界面**: http://localhost:5173
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs

## 功能说明

Web 前端提供以下功能：

1. **博客系统**
   - 文章列表、详情查看
   - 文章编辑、发布
   - GitHub 仓库集成

2. **对话系统**
   - 实时对话
   - 多会话管理
   - 对话历史

3. **仪表盘**
   - 系统状态监控
   - 数据统计图表
   - 性能指标

4. **安全监控**
   - 访问日志
   - IP 封禁管理
   - 安全事件

5. **用户管理**
   - 登录注册
   - 权限控制
   - 个人设置

## 技术栈

- **后端**: FastAPI + Python
- **前端**: React 18 + TypeScript + Vite
- **UI**: Tailwind CSS
- **状态管理**: Zustand
- **路由**: React Router

## 配置

### 后端配置

编辑 `config/.env` 文件：

```env
# Web API 配置
WEB_API_HOST=0.0.0.0
WEB_API_PORT=8000

# AI 配置
AI_API_KEY=your_api_key
AI_API_BASE_URL=your_api_url
AI_MODEL=your_model_name
```

### 前端配置

前端配置在 `miya-pc-ui/src/services/api.ts` 中修改 API 基础地址。

## 故障排除

### 后端无法启动

1. 检查 Python 虚拟环境是否存在
2. 检查 `config/.env` 配置文件
3. 检查端口 8000 是否被占用

### 前端无法启动

1. 检查 Node.js 是否安装（需要 18+）
2. 删除 `miya-pc-ui/node_modules` 重新安装依赖
3. 检查端口 5173 是否被占用

### 依赖安装失败

```bash
# Python 依赖
pip install -r requirements.txt

# Node.js 依赖
cd miya-pc-ui
npm install
```

## 开发模式

### 只启动后端 API

```bash
# Windows
python run/web_main.py

# Linux/macOS
./venv/bin/python run/web_main.py
```

### 只启动前端开发服务器

```bash
cd miya-pc-ui
npm run dev:web
```

## 生产部署

### 构建前端

```bash
cd miya-pc-ui
npm run build:renderer
```

### 部署说明

前端构建产物在 `miya-pc-ui/dist` 目录，可以使用 Nginx 或其他 Web 服务器托管。

后端使用 uvicorn 或 gunicorn 部署：

```bash
uvicorn core.web_api:app --host 0.0.0.0 --port 8000 --workers 4
```

## 与其他模式的区别

| 模式 | 交互方式 | 特点 |
|------|---------|------|
| 终端模式 | 命令行 | 直接交互，适合开发调试 |
| QQ 机器人 | QQ 消息 | 群聊/私聊，适合社交 |
| PC UI | Electron 桌面应用 | 图形界面，适合日常使用 |
| Web UI | 浏览器 | 跨平台，远程访问 |

选择适合你的模式启动弥娅！
