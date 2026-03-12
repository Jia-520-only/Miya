# 弥娅 Web 后端集成完成

## ✅ 已完成的工作

### 1. WebNet 子网 (`webnet/web.py`)
- ✅ BlogStore - 博客存储层（SQLite + Markdown）
- ✅ AuthManager - 认证管理器（JWT）
- ✅ SecurityGuard - 安全防护系统
- ✅ WebNet 主类 - 统一接口

### 2. Web API 路由器 (`core/web_api.py`)
- ✅ 博客 API（列表、详情、创建）
- ✅ 认证 API（注册、登录）
- ✅ 对话 API（通过 DecisionHub）
- ✅ 系统状态 API（情绪、记忆）
- ✅ 安全 API（扫描、封禁 IP）
- ✅ 健康检查 API

### 3. 集成到 Miya 主类 (`run/main.py`)
- ✅ 初始化 WebNet
- ✅ 初始化 Web API 路由器
- ✅ 传递 memory_engine 和 emotion_manager

---

## 🚀 使用方法

### 启动弥娅系统

```bash
cd d:/AI_MIYA_Facyory/MIYA/Miya
python run/main.py
```

系统启动后，Web API 会自动初始化。

### API 端点

| 方法 | 端点 | 功能 | 认证 |
|------|--------|------|------|
| GET | `/api/health` | 健康检查 | ❌ |
| GET | `/api/blog/posts` | 博客列表 | ❌ |
| GET | `/api/blog/posts/{slug}` | 博客详情 | ❌ |
| POST | `/api/blog/posts` | 创建博客 | ✅ |
| POST | `/api/auth/register` | 用户注册 | ❌ |
| POST | `/api/auth/login` | 用户登录 | ❌ |
| POST | `/api/chat` | 聊天对话 | ❌ |
| GET | `/api/status` | 系统状态 | ❌ |
| GET | `/api/emotion` | 情绪状态 | ❌ |
| POST | `/api/security/scan` | 安全扫描 | ❌ |
| POST | `/api/security/block-ip` | 封禁 IP | ✅ (管理员) |

---

## 📦 数据库

### 博客数据库
- 路径: `data/blog/blog.db`
- 表:
  - `posts` - 博客文章
  - `comments` - 评论

### 认证数据库
- 路径: `data/auth.db`
- 表:
  - `users` - 用户信息

**默认管理员账户:**
- 用户名: `admin`
- 密码: `admin123`
- 权限: 5 (管理员)

---

## 🔒 安全特性

### 攻击检测
- SQL 注入检测
- XSS 检测
- 路径遍历检测
- 恶意命令检测

### 频率限制
- API 调用: 100次/分钟
- 自动封禁超限 IP

### 权限系统
- 6级权限 (0-5)
- JWT Token 认证
- 基于用户等级的访问控制

---

## 🎯 下一步

1. ✅ 后端已完成
2. ⏳ 搭建前端项目 (miya-web)
3. ⏳ 开发前端页面组件
4. ⏳ 测试和部署

---

## 📝 注意事项

1. **FastAPI 依赖**: 如果未安装 FastAPI，Web API 功能将被禁用
   ```bash
   pip install fastapi uvicorn
   ```

2. **SQLite 自动创建**: 数据库文件会在首次使用时自动创建

3. **Markdown 存储**: 博客内容以 `.md` 文件存储在 `data/blog/posts/`

4. **Token 过期**: JWT Token 有效期为 24 小时

---

## 🧪 测试 API

### 健康检查
```bash
curl http://localhost:8000/api/health
```

### 获取博客列表
```bash
curl http://localhost:8000/api/blog/posts?page=1
```

### 用户登录
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

### 发送聊天消息
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "你好，弥娅！", "session_id": "test"}'
```

---

## 📚 技术栈

### 后端
- Python 3.9+
- FastAPI (API 框架)
- SQLite (数据库)
- JWT (认证)
- Pydantic (数据验证)

### 前端（待开发）
- Astro + React
- Tailwind CSS
- TypeScript
- Zustand (状态管理)

---

**状态**: ✅ 后端已完成，等待前端开发
