# 弥娅(MIYA)零基础搭建教程

## 前言

欢迎使用弥娅AI系统！本教程将手把手教你从零开始搭建完整的弥娅系统。即使你完全没有编程经验，只要按照步骤操作，也能成功运行。

---

## 准备工作

### 1.1 电脑要求

- **操作系统**: Windows 10/11 或 Linux (Ubuntu 20.04+)
- **内存**: 至少 8GB (推荐 16GB)
- **硬盘**: 至少 20GB 可用空间
- **网络**: 能够访问 GitHub 和 API 服务

### 1.2 需要安装的软件

| 软件 | 用途 | 下载地址 |
|------|------|----------|
| Git | 代码版本管理 | https://git-scm.com |
| Python 3.11 | 运行环境 | https://www.python.org |
| Docker Desktop | 数据库容器 | https://www.docker.com |
| Node.js 18+ | 桌面端前端 | https://nodejs.org |

### 1.3 注册API账号

弥娅需要调用大语言模型API，你需要一个API密钥：

1. **DeepSeek** (推荐，便宜):
   - 访问 https://platform.deepseek.com
   - 注册账号，获取 API Key

2. **硅基流动** (国内可访问):
   - 访问 https://cloud.siliconflow.cn
   - 注册账号，获取 API Key

---

## 第一步：下载代码

### 1. 打开终端/命令行

**Windows**: 
- 按 `Win + R`
- 输入 `cmd` 
- 按回车

**Linux**:
- 按 `Ctrl + Alt + T`

### 2. 克隆项目

```bash
# 进入你的工作目录（如D盘）
cd D:

# 克隆代码
git clone https://github.com/Jia-520-only/Miya.git

# 进入项目目录
cd Miya
```

> ⚠️ 如果没有安装Git，可以直接去 GitHub 下载 ZIP 文件：
> 访问 https://github.com/Jia-520-only/Miya
> 点击绿色 "Code" 按钮 → "Download ZIP"

---

## 第二步：安装依赖

### 1. 安装 Python

1. 下载 Python 3.11: https://www.python.org/downloads/
2. **重要**: 安装时勾选 "Add Python to PATH"
3. 验证安装:
```bash
python --version
```
应该显示: `Python 3.11.x`

### 2. 创建虚拟环境

```bash
# 在项目目录下创建虚拟环境
python -m venv venv
```

### 3. 激活虚拟环境

**Windows**:
```bash
venv\Scripts\activate
```

**Linux/Mac**:
```bash
source venv/bin/activate
```

激活成功后，命令行前会有 `(venv)` 标记。

### 4. 安装Python依赖

**Windows** (双击运行):
```
install_deps_fixed.ps1
```

**Linux**:
```bash
bash install.sh
```

或者手动安装:
```bash
pip install -r requirements.txt
```

---

## 第三步：启动数据库

弥娅需要三个数据库来存储不同类型的数据。我们使用 Docker 快速启动。

### 1. 安装 Docker Desktop

1. 下载: https://www.docker.com/products/docker-desktop
2. 安装并启动
3. 等待 Docker 图标显示 "Running"

### 2. 启动数据库服务

创建一个 `docker-compose.yml` 文件，内容如下：

```yaml
version: '3.8'

services:
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  milvus:
    image: milvusdb/milvus:latest
    ports:
      - "19530:19530"
    environment:
      ETCD_USE_EMBED: "true"
      COMMON_STORAGE_TYPE: local
    volumes:
      - milvus_data:/var/lib/milvus

  neo4j:
    image: neo4j:latest
    ports:
      - "7687:7687"
      - "7474:7474"
    environment:
      NEO4J_AUTH: neo4j/password
    volumes:
      - neo4j_data:/data

volumes:
  redis_data:
  milvus_data:
  neo4j_data:
```

然后启动:
```bash
docker-compose up -d
```

> 💡 首次启动需要下载镜像，可能需要几分钟。

### 3. 验证数据库运行

```bash
docker ps
```

应该看到三个容器正在运行:
- redis
- milvus
- neo4j

---

## 第四步：配置环境

### 1. 复制配置文件

```bash
copy config\.env.example config\.env
```

### 2. 编辑配置文件

用记事本或 VS Code 打开 `config/.env`，填入以下内容：

```env
# ==================== API 配置 ====================

# DeepSeek API (推荐)
DEEPSEEK_API_KEY=你的DeepSeek_API_Key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# 硅基流动 API (国内可用)
SILICONFLOW_API_KEY=你的硅基流动_API_Key

# ==================== 数据库配置 ====================

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Milvus
MILVUS_HOST=localhost
MILVUS_PORT=19530

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# ==================== 系统配置 ====================

# AI模型配置
DEFAULT_MODEL=Qwen/Qwen2.5-72B-Instruct

# 管理员ID
ADMIN_USER_ID=system_admin
```

> ⚠️ 记得把 `你的API_Key` 替换成你注册获取的真实密钥！

---

## 第五步：初始化鉴权系统

```bash
python init_auth.py
```

选择 `1` 然后按回车初始化。

---

## 第六步：启动弥娅

### 方式一：启动主程序（终端模式）

```bash
python run/main.py
```

然后输入数字 `1` 选择 "Start Main Program"

### 方式二：启动桌面应用

```bash
python run/desktop_main.py
```

然后输入数字 `4` 选择 "Start Desktop UI"

### 方式三：启动Web界面

```bash
python run/web_main.py
```

然后输入数字 `3` 选择 "Start Web UI"

---

## 常见问题

### Q1: 启动报错 "ModuleNotFoundError"

**解决方法**: 确保已激活虚拟环境
```bash
# Windows
venv\Scripts\activate

# Linux
source venv/bin/activate
```

### Q2: 数据库连接失败

**解决方法**: 确保 Docker 已启动
```bash
docker start redis milvus neo4j
```

### Q3: API Key 错误

**解决方法**: 检查 `config/.env` 中的 API Key 是否正确填入

### Q4: 端口被占用

**解决方法**: 
```bash
# Windows
cleanup_port.bat

# 或手动杀死进程
netstat -ano | findstr :8000
taskkill /PID <进程ID> /F
```

---

## 使用指南

### 1. 基本命令

| 命令 | 说明 |
|------|------|
| `status` | 查看系统状态 |
| `exit` 或 `退出` | 退出程序 |

### 2. 与弥娅对话

直接在终端输入你想说的话：
```
你好，弥娅！
```

### 3. 执行终端命令

使用 `!` 或 `>>` 前缀执行命令：
```
!ls
>>pwd
```

---

## 目录结构说明

```
Miya/
├── core/          # 核心大脑（人格、思考）
├── hub/           # 认知中枢（记忆、决策）
├── memory/        # 记忆系统
├── webnet/        # 网络通信
├── tools/         # 工具函数
├── run/           # 启动入口
├── config/        # 配置文件
├── data/          # 数据存储
├── logs/          # 运行日志
├── docs/          # 文档
└── miya-desktop/  # 桌面应用
```

---

## 视频教程

更多详细操作请查看视频教程:
- [B站: 弥娅系统搭建教程](https://www.bilibili.com)
- [YouTube: MIYA Setup Tutorial](https://www.youtube.com)

---

## 获取帮助

- GitHub Issues: https://github.com/Jia-520-only/Miya/issues
- 加入交流群: [QQ群]

---

*祝你使用愉快！*
*如果觉得有帮助，欢迎 Star ⭐ 项目*
