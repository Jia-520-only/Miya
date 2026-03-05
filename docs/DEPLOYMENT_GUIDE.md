# 弥娅 MIYA - 完整部署指南

> 版本：2.0.0
> 更新时间：2026-02-28

---

## 📋 目录

1. [系统要求](#系统要求)
2. [快速开始](#快速开始)
3. [详细安装](#详细安装)
4. [配置说明](#配置说明)
5. [启动方式](#启动方式)
6. [使用指南](#使用指南)
7. [故障排查](#故障排查)
8. [性能优化](#性能优化)
9. [安全建议](#安全建议)
10. [常见问题](#常见问题)

---

## 系统要求

### 最低配置

- **操作系统**: Windows 10+, macOS 10.15+, Linux (Ubuntu 20.04+)
- **Python**: 3.10 或更高版本
- **内存**: 4GB RAM
- **磁盘**: 10GB 可用空间

### 推荐配置

- **操作系统**: Windows 11, macOS 12+, Linux (Ubuntu 22.04+)
- **Python**: 3.11 或更高版本
- **内存**: 8GB RAM 或更多
- **磁盘**: 20GB SSD
- **CPU**: 4核心或更多

### 依赖服务（可选）

- **Redis** 6.0+ （用于涨潮记忆）
- **Milvus** 2.4+ （用于向量长期记忆）
- **Neo4j** 5.20+ （用于知识图谱）
- **OneBot** 11+ （用于QQ机器人功能）

---

## 快速开始

### Windows 用户

```batch
# 1. 安装依赖
install.bat

# 2. 配置环境变量（编辑 config/.env）
notepad config\.env

# 3. 启动弥娅
start.bat
```

### Linux/Mac 用户

```bash
# 1. 安装依赖
chmod +x install.sh
./install.sh

# 2. 配置环境变量（编辑 config/.env）
nano config/.env

# 3. 启动弥娅
chmod +x start.sh
./start.sh
```

---

## 详细安装

### 1. 安装Python

#### Windows
1. 访问 https://www.python.org/downloads/
2. 下载 Python 3.10+ 安装包
3. 运行安装程序，勾选 "Add Python to PATH"
4. 验证安装: `python --version`

#### Linux
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.10 python3.10-venv python3-pip

# CentOS/RHEL
sudo yum install python3.10 python3.10-pip
```

#### macOS
```bash
# 使用Homebrew
brew install python@3.10
```

### 2. 克隆/下载项目

```bash
# 如果是Git仓库
git clone <repository-url>
cd Miya

# 如果是压缩包
unzip Miya.zip
cd Miya
```

### 3. 安装依赖

#### Windows
```batch
install.bat
```

#### Linux/Mac
```bash
chmod +x install.sh
./install.sh
```

安装脚本会自动：
- 创建Python虚拟环境
- 升级pip到最新版本
- 安装所有依赖包
- 创建必要的目录

### 4. 配置环境变量

```bash
# 复制配置文件模板
cp config/.env.example config/.env

# 编辑配置文件
# Windows: notepad config\.env
# Linux/Mac: nano config\.env
```

**最少必需配置**:
```env
# QQ机器人配置（如果使用QQ功能）
QQ_BOT_QQ=你的机器人QQ号
QQ_SUPERADMIN_QQ=你的超级管理员QQ号

# 如果使用OneBot，配置WebSocket地址
QQ_ONEBOT_WS_URL=ws://your-onebot-server:3001
```

### 5. 安装依赖服务（可选）

#### Redis（可选）

**Windows**:
```batch
# 使用Docker
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

**Linux/Mac**:
```bash
# 使用Docker
docker run -d --name redis -p 6379:6379 redis:7-alpine

# 或直接安装
# Ubuntu/Debian
sudo apt install redis-server
# macOS
brew install redis
```

#### Milvus（可选）

使用Docker Compose：
```bash
docker-compose -f docker-compose.yml up -d milvus
```

#### Neo4j（可选）

使用Docker：
```bash
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your_password \
  neo4j:5.20
```

#### OneBot（可选，用于QQ机器人）

参考各OneBot实现的文档：
- [NapCat](https://github.com/NapNeko/NapCatQQ)
- [LLOneBot](https://github.com/LLOneBot/LLOneBot)
- [Shamrock](https://github.com/whitechi73/Shamrock)

---

## 配置说明

### 核心配置项

| 配置项 | 说明 | 默认值 | 必需 |
|-------|------|--------|------|
| `DEBUG` | 调试模式 | false | 否 |
| `LOG_LEVEL` | 日志级别 | INFO | 否 |
| `QQ_BOT_QQ` | 机器人QQ号 | 0 | QQ功能必需 |
| `QQ_SUPERADMIN_QQ` | 超级管理员QQ | 0 | QQ功能必需 |
| `QQ_ONEBOT_WS_URL` | OneBot地址 | ws://localhost:3001 | QQ功能必需 |
| `REDIS_HOST` | Redis地址 | localhost | 否 |
| `MILVUS_HOST` | Milvus地址 | localhost | 否 |
| `NEO4J_URI` | Neo4j地址 | bolt://localhost:7687 | 否 |

### 人格配置

弥娅的五维人格向量（0.0-1.0）：

- `PERSONALITY_WARMTH`: 温暖度 - 影响回应的亲和力
- `PERSONALITY_LOGIC`: 逻辑性 - 影响推理的严谨度
- `PERSONALITY_CREATIVITY`: 创造力 - 影响回答的多样性
- `PERSONALITY_EMPATHY`: 共情力 - 影响情感理解
- `PERSONALITY_RESILIENCE`: 韧性 - 影响抗压能力

示例配置：
```env
PERSONALITY_WARMTH=0.8      # 温暖友善
PERSONALITY_LOGIC=0.7       # 逻辑清晰
PERSONALITY_CREATIVITY=0.6  # 富有创意
PERSONALITY_EMPATHY=0.75    # 共情力强
PERSONALITY_RESILIENCE=0.7   # 抗压能力强
```

### 情绪配置

```env
EMOTION_DECAY_RATE=0.1              # 情绪衰减率
EMOTION_COLORING_THRESHOLD=0.7      # 情绪染色阈值
EMOTION_PROPAGATION_COEFF=0.3        # 情绪传播系数
```

### Runtime API配置

```env
API_ENABLED=true             # 启用API
API_HOST=0.0.0.0            # 监听地址
API_PORT=8000               # 监听端口
API_OPENAPI_ENABLED=true    # 启用OpenAPI文档
```

---

## 启动方式

### 方式1：使用启动脚本（推荐）

#### Windows
```batch
start.bat
```

#### Linux/Mac
```bash
chmod +x start.sh
./start.sh
```

启动菜单选项：
1. 启动主程序（完整模式）
2. 启动QQ机器人
3. 启动PC端
4. 启动Runtime API服务器
5. 启动健康检查
6. 查看系统状态

### 方式2：直接运行Python脚本

#### 主程序
```bash
python run/main.py
```

#### QQ机器人
```bash
python run/qq_main.py
```

#### PC端
```bash
python pc_ui/main.py
```

### 方式3：使用Docker

```bash
# 构建镜像
docker build -t miya:latest .

# 运行容器
docker run -d --name miya \
  -p 8000:8000 \
  -p 8080:8080 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/logs:/app/logs \
  miya:latest
```

---

## 使用指南

### 1. QQ机器人使用

#### 基本命令
```
/help      - 查看帮助
/stats     - 查看统计
/config    - 查看配置
/memory    - 查看记忆
```

#### 管理员命令（仅超级管理员）
```
/addadmin <QQ号>      - 添加管理员
/addgroup <群号>      - 添加群聊白名单
/reload               - 重载配置
/restart              - 重启机器人
```

### 2. PC端管理面板使用

#### 启动管理面板
```bash
# 启动Runtime API
python -c "from core.runtime_api_server import RuntimeAPIServer; import asyncio; server = RuntimeAPIServer(); asyncio.run(server.start())"

# 在浏览器中打开管理面板
# 方式1: 直接打开HTML文件
pc_ui/manager.html

# 方式2: 使用本地服务器（推荐）
cd pc_ui
python -m http.server 8080
# 访问 http://localhost:8080/manager.html
```

#### 管理面板功能
- 📊 系统状态监控
- 🎮 交互端管理（启动/停止）
- 🤖 Agent管理
- 🧠 记忆系统查询
- 📈 队列统计
- ⚙️ 配置管理

### 3. API使用

#### 健康检查
```bash
curl http://localhost:8000/api/probe
```

#### 获取系统状态
```bash
curl http://localhost:8000/api/status
```

#### 获取所有交互端
```bash
curl http://localhost:8000/api/endpoints
```

#### 启动交互端
```bash
curl -X POST http://localhost:8000/api/endpoints/{id}/start
```

#### 停止交互端
```bash
curl -X POST http://localhost:8000/api/endpoints/{id}/stop
```

详细API文档: http://localhost:8000/docs

---

## 故障排查

### 问题1：安装失败

**症状**: `install.bat` 或 `install.sh` 执行失败

**解决方案**:
1. 检查Python版本是否为3.10+
2. 检查网络连接
3. 尝试使用国内镜像源
4. 手动创建虚拟环境并安装依赖

```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 问题2：启动失败

**症状**: 运行 `start.bat` 或 `start.sh` 后程序无法启动

**解决方案**:
1. 检查配置文件 `config/.env` 是否存在
2. 检查配置项是否正确
3. 查看日志文件 `logs/miya.log`
4. 检查依赖服务（Redis/Milvus/Neo4j）是否正常运行

### 问题3：QQ机器人无法连接

**症状**: QQ机器人无法连接到OneBot

**解决方案**:
1. 检查OneBot是否正常运行
2. 检查 `QQ_ONEBOT_WS_URL` 配置是否正确
3. 检查网络连接
4. 查看OneBot日志

### 问题4：Redis连接失败

**症状**: 无法连接到Redis

**解决方案**:
1. 检查Redis是否启动: `redis-cli ping`
2. 检查 `REDIS_HOST` 和 `REDIS_PORT` 配置
3. 检查Redis密码配置
4. 检查防火墙设置

### 问题5：内存不足

**症状**: 程序运行缓慢或崩溃

**解决方案**:
1. 增加系统内存
2. 减少并发任务数
3. 限制记忆存储容量
4. 清理无用数据

---

## 性能优化

### 1. 启用异步处理

弥娅默认使用异步处理，确保高性能。

### 2. 使用缓存

```env
# 启用向量缓存
VECTOR_CACHE_ENABLED=true

# 缓存大小（MB）
VECTOR_CACHE_SIZE=512
```

### 3. 限制并发任务

```env
# 最大并发任务数
MAX_CONCURRENT_TASKS=10
```

### 4. 优化数据库连接

```env
# Redis连接池大小
REDIS_MAX_CONNECTIONS=10

# Neo4j连接池大小
NEO4J_MAX_CONNECTIONS=10
```

### 5. 使用SSD

将日志和数据目录放在SSD上，大幅提升性能。

---

## 安全建议

### 1. 保护敏感信息

- 不要将 `config/.env` 提交到版本控制
- 使用环境变量存储密码和密钥
- 定期更换密码

### 2. 启用认证

```env
# API认证密钥
API_AUTH_KEY=your_strong_api_key

# WebUI密码
WEBUI_PASSWORD=your_strong_password
```

### 3. 限制访问

```env
# 仅监听本地地址
API_HOST=127.0.0.1

# 或使用防火墙限制访问
```

### 4. 启用注入检测

```env
INJECTION_DETECTION_ENABLED=true
SENSITIVE_WORD_FILTER_ENABLED=true
```

### 5. 限流保护

```env
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=30
```

---

## 常见问题

### Q1: 弥娅支持哪些语言模型？

A: 弥娅支持任何兼容OpenAI API格式的模型，包括：
- GPT-4/GPT-3.5
- Claude
- 文心一言
- 通义千问
- 智谱AI
- 其他兼容模型

### Q2: 如何更换语言模型？

A: 在配置文件中设置对应的API地址和密钥。

### Q3: 弥娅可以部署在云端吗？

A: 可以。弥娅支持Docker部署，可以部署在任何云平台（阿里云、腾讯云、AWS等）。

### Q4: 如何更新弥娅？

A: 使用Git拉取最新代码，然后重新安装依赖。

```bash
git pull
pip install -r requirements.txt --upgrade
```

### Q5: 如何查看日志？

A: 日志文件位于 `logs/miya.log`，可以使用文本编辑器或日志查看工具查看。

### Q6: 如何备份数据？

A: 定期备份以下目录和文件：
- `config/.env` - 配置文件
- `data/` - 数据目录
- `memory/semantic_groups.json` - 语义组配置
- Redis数据（如果使用）
- Milvus数据（如果使用）
- Neo4j数据（如果使用）

### Q7: 如何重置弥娅？

A: 删除 `data/` 目录下的数据文件，然后重新启动。

### Q8: 弥娅支持多实例吗？

A: 支持。但需要使用不同的配置文件和端口。

### Q9: 如何监控弥娅性能？

A: 使用PC端管理面板或API获取系统状态和统计数据。

### Q10: 如何贡献代码？

A: 欢迎提交Pull Request或Issue到项目仓库。

---

## 技术支持

如有问题，请：
1. 查看本文档的故障排查部分
2. 查看日志文件
3. 提交Issue到项目仓库
4. 加入用户社区讨论

---

## 更新日志

### v2.0.0 (2026-02-28)
- ✅ 整合NagaAgent、VCPChat、VCPToolBox、Undefined
- ✅ 新增PC端管理面板
- ✅ 新增Runtime API服务器
- ✅ 新增Skills插件系统
- ✅ 新增认知记忆系统
- ✅ 新增队列管理系统
- ✅ 新增配置热更新

---

## 许可证

[MIT License](LICENSE)

---

**感谢使用弥娅！** 🚀✨
