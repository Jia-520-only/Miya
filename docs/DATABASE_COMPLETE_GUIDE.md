# MIYA 数据库系统完整指南

> 最后更新: 2026-03-04
> 版本: 1.0.0

---

## 目录

1. [系统概述](#系统概述)
2. [数据库介绍](#数据库介绍)
3. [环境要求](#环境要求)
4. [安装部署](#安装部署)
5. [配置说明](#配置说明)
6. [启动停止](#启动停止)
7. [使用方法](#使用方法)
8. [故障排除](#故障排除)
9. [性能优化](#性能优化)
10. [备份恢复](#备份恢复)

---

## 系统概述

### 记忆系统架构

MIYA 的记忆系统由四个核心组件构成:

```
┌─────────────────────────────────────────────────────────────┐
│                      MIYA 记忆系统                            │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │   Redis      │    │    Neo4j     │    │    Milvus    │   │
│  │ 潮汐记忆     │    │   关系记忆   │    │ 向量长期记忆 │   │
│  │ (短期记忆)   │    │  (知识图谱)  │    │  (梦境记忆)  │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
│                                                               │
│  ┌──────────────────────────────────────────────────┐       │
│  │         Undefined Memory (手动轻量记忆)           │       │
│  │         data/memory/undefined_memory.json        │       │
│  └──────────────────────────────────────────────────┘       │
│                                                               │
│  ┌──────────────────────────────────────────────────┐       │
│  │         Conversation History (对话历史)            │       │
│  │         data/conversations/*.json                 │       │
│  └──────────────────────────────────────────────────┘       │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 记忆流转机制

1. **对话产生** → 临时存储在内存
2. **短期记忆 (Redis)** → 活跃对话,快速访问
3. **对话压缩** → 超过阈值后压缩为摘要
4. **长期记忆 (Milvus)** → 语义向量存储,支持智能检索
5. **关系记忆 (Neo4j)** → 实体关系网络,知识图谱
6. **手动记忆** → 重要信息人工标注

---

## 数据库介绍

### 1. Redis - 潮汐记忆

**作用**: 存储短期对话、会话状态、活跃记忆

**特点**:
- 极高的读写速度 (内存数据库)
- 支持过期时间 (TTL)
- 适合频繁访问的数据

**数据类型**:
- 对话历史 (最新 N 条消息)
- 会话状态
- 活跃记忆索引

**存储示例**:
```json
{
  "qq_1234567890": [
    {"role": "user", "content": "你好", "time": "2026-03-04 10:00:00"},
    {"role": "assistant", "content": "你好呀!", "time": "2026-03-04 10:00:01"}
  ]
}
```

---

### 2. Neo4j - 关系记忆

**作用**: 存储知识图谱、实体关系、社交网络

**特点**:
- 原生图数据库
- 强大的图查询语言 (Cypher)
- 自然表达复杂关系

**数据结构**:
- 节点 (Node): 人、地点、事件、概念等实体
- 关系 (Relationship): 喜欢认识、属于等连接
- 属性 (Property): 实体和关系的详细信息

**示例图**:
```
(佳:人) -[:喜欢]-> (MIYA:AI)
  |
  +--[:认识]-> (小明:人)
```

**Cypher 查询示例**:
```cypher
// 查找佳的所有朋友
MATCH (p:Person {name: "佳"})-[:认识]->(friend)
RETURN friend.name

// 查找 MIYA 喜欢的所有实体
MATCH (miya:AI {name: "MIYA"})-[:喜欢]->(entity)
RETURN entity
```

---

### 3. Milvus - 向量长期记忆

**作用**: 存储语义向量记忆、支持智能检索、梦境压缩

**特点**:
- 专门为向量检索设计
- 支持海量向量存储
- 基于 AI 的语义相似度搜索

**数据结构**:
- 向量 (Vector): 文本转为 768 维向量
- 元数据 (Metadata): 时间、情感、上下文等
- 集合 (Collection): 按类别分组存储

**检索示例**:
```python
# 语义搜索相似记忆
results = milvus_client.search(
    collection_name="miya_memory",
    data=[vector],  # 查询向量
    limit=10  # 返回最相似的 10 条
)
```

---

### 4. Undefined Memory - 手动轻量记忆

**作用**: 存储人工标注的重要信息、配置、静态数据

**特点**:
- JSON 文件存储
- 无需数据库服务
- 人工维护

**存储位置**: `data/memory/undefined_memory.json`

**数据结构**:
```json
{
  "memories": [
    {
      "id": "mem_001",
      "content": "创造者喜欢蓝色",
      "category": "preference",
      "importance": "high",
      "created_at": "2026-03-04"
    }
  ]
}
```

---

## 环境要求

### 硬件要求

| 组件     | 最低配置    | 推荐配置     |
|----------|-------------|--------------|
| CPU      | 4 核心      | 8+ 核心      |
| 内存     | 8 GB        | 16 GB+       |
| 磁盘空间 | 20 GB       | 50 GB+ (SSD) |
| 网络     | 稳定连接    | 稳定连接     |

### 软件要求

| 组件          | 版本要求     | 用途           |
|---------------|--------------|----------------|
| Python        | 3.9+        | 运行 MIYA      |
| Docker        | 20.10+      | 运行数据库容器 |
| Redis         | 6.0+        | 潮汐记忆       |
| Neo4j         | 4.4+        | 关系记忆       |
| Milvus        | 2.4+        | 向量记忆       |

---

## 安装部署

### 方式一: Docker Compose 一键部署 (推荐)

#### 1. 安装 Docker Desktop

下载并安装 Docker Desktop:
- Windows: https://www.docker.com/products/docker-desktop
- macOS: https://www.docker.com/products/docker-desktop
- Linux: 参考官方文档

**配置代理 (可选)**:
如果网络环境需要代理,在 Docker Desktop 中配置:
1. 打开 Docker Desktop
2. Settings → Resources → Proxies
3. 启用 Manual proxy configuration
4. 填入你的代理地址

#### 2. 拉取项目代码

```bash
git clone <repository-url>
cd Miya
```

#### 3. 安装 Python 依赖

```bash
# Windows
pip install -r requirements.txt

# Linux/macOS
pip3 install -r requirements.txt
```

**关键依赖**:
```txt
redis>=5.0.0
neo4j>=5.0.0
pymilvus==2.4.0
python-dotenv>=1.0.0
```

#### 4. 配置环境变量

复制示例配置文件:
```bash
# Windows
copy config\.env.example config\.env

# Linux/macOS
cp config/.env.example config/.env
```

编辑 `config/.env`,配置数据库连接:

```ini
# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# Neo4j 配置
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=Aa316316

# Milvus 配置
MILVUS_URI=http://localhost:19530
MILVUS_TOKEN=
MILVUS_USE_LITE=false

# 对话历史配置
MAX_MESSAGES_PER_SESSION=200
CONVERSATION_RETENTION_DAYS=30
```

#### 5. 启动所有数据库

```bash
# 启动 Redis 和 Neo4j
docker-compose up -d

# 启动 Milvus
docker-compose -f docker-compose.milvus.yml up -d
```

**验证启动状态**:
```bash
# 查看运行中的容器
docker ps

# 应该看到以下容器:
# - redis
# - neo4j
# - milvus-standalone
# - milvus-etcd
# - milvus-minio
```

#### 6. 运行数据库测试

```bash
python test_memory_system.py
```

**预期输出**:
```
============================================================
测试新的记忆系统功能
============================================================

[1/5] 测试 Redis 连接...
  [OK] Redis 已连接

[2/5] 测试 Neo4j 连接...
  [OK] Neo4j 已连接
        节点数: 4517
        关系数: 5368

[3/5] 测试 Milvus 连接...
  [OK] Milvus 已连接
        模式: remote
        集合: 0

[4/5] 测试 MemoryNet 功能...
  [OK] MemoryNet 初始化成功

[5/5] 测试知识图谱存储...
  [OK] 已存储测试知识图谱关系

============================================================
记忆系统测试完成！
============================================================
```

---

### 方式二: 手动安装各组件

#### Redis 安装

**Windows**:
1. 下载 Redis for Windows: https://github.com/microsoftarchive/redis/releases
2. 解压并运行 `redis-server.exe`
3. 默认端口: 6379

**Linux**:
```bash
sudo apt-get install redis-server
sudo systemctl start redis
sudo systemctl enable redis
```

**macOS**:
```bash
brew install redis
brew services start redis
```

#### Neo4j 安装

**Windows**:
1. 下载 Neo4j Desktop: https://neo4j.com/download/
2. 安装并启动 Neo4j Desktop
3. 创建新数据库,版本选择 4.4+
4. 设置密码 (默认: neo4j, 修改为 Aa316316)

**Linux**:
```bash
# 添加 Neo4j 仓库
wget -O - https://debian.neo4j.com/neotechnology.gpg.key | sudo apt-key add -
echo 'deb https://debian.neo4j.com stable latest' | sudo tee /etc/apt/sources.list.d/neo4j.list

# 安装
sudo apt-get update
sudo apt-get install neo4j

# 启动
sudo systemctl start neo4j
sudo systemctl enable neo4j
```

**访问 Neo4j Browser**:
- URL: http://localhost:7474
- 用户名: neo4j
- 密码: Aa316316

#### Milvus 安装

**使用 Docker Compose (推荐)**:

```bash
# 使用提供的配置文件
docker-compose -f docker-compose.milvus.yml up -d

# 等待 15-30 秒让服务启动
```

**Milvus Lite (单机无 Docker)**:
```bash
pip install pymilvus[milvus_lite]
```

配置文件中设置:
```ini
MILVUS_USE_LITE=true
```

---

### 方式三: 使用国内镜像源 (中国用户)

如果网络环境无法访问官方镜像,使用国内加速源:

#### 镜像源配置

**Docker 镜像加速**:
编辑 Docker Desktop 的 daemon.json:
```json
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://mirror.ccs.tencentyun.com"
  ]
}
```

**Python pip 镜像加速**:
```bash
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

#### 使用国内 Milvus 镜像

编辑 `docker-compose.milvus.yml`:
```yaml
services:
  milvus-standalone:
    image: registry.cn-hangzhou.aliyuncs.com/milvus/milvus:v2.4.15
    # ... 其他配置
```

---

## 配置说明

### 完整配置文件: `config/.env`

```ini
# ========================================
# Redis 配置 (潮汐记忆)
# ========================================
# Redis 主机地址
REDIS_HOST=localhost

# Redis 端口
REDIS_PORT=6379

# Redis 密码 (如果设置了密码)
REDIS_PASSWORD=

# Redis 数据库编号 (0-15)
REDIS_DB=0

# ========================================
# Neo4j 配置 (关系记忆)
# ========================================
# Neo4j 连接 URI
NEO4J_URI=bolt://localhost:7687

# Neo4j 用户名
NEO4J_USER=neo4j

# Neo4j 密码 (重要: 修改为你的密码)
NEO4J_PASSWORD=Aa316316

# ========================================
# Milvus 配置 (向量长期记忆)
# ========================================
# Milvus 连接 URI
MILVUS_URI=http://localhost:19530

# Milvus 认证 Token (如果启用)
MILVUS_TOKEN=

# 是否使用 Milvus Lite (本地文件模式)
# true: 使用 Milvus Lite (无需 Docker, 适合小规模)
# false: 使用远程 Milvus (Docker, 适合生产环境)
MILVUS_USE_LITE=false

# 向量维度 (根据 embedding 模型确定)
MILVUS_DIMENSION=768

# 索引类型: IVF_FLAT, HNSW, IVF_PQ
MILVUS_INDEX_TYPE=IVF_FLAT

# 索引参数 (根据索引类型)
MILVUS_INDEX_PARAMS={"nlist":128}

# 搜索参数
MILVUS_SEARCH_PARAMS={"nprobe":10}

# ========================================
# 对话历史配置
# ========================================
# 每个会话最大消息数
MAX_MESSAGES_PER_SESSION=200

# 对话历史保留天数
CONVERSATION_RETENTION_DAYS=30

# 对话历史存储目录
CONVERSATION_DATA_DIR=data\conversations

# ========================================
# 记忆系统配置
# ========================================
# 对话压缩阈值 (超过此值时触发压缩)
MEMORY_COMPRESSION_THRESHOLD=50

# 长期记忆检索数量
LONG_TERM_MEMORY_LIMIT=10

# 跨平台记忆整合数量
CROSS_PLATFORM_MEMORY_LIMIT=20

# Undefined 记忆存储路径
UNDEFINED_MEMORY_PATH=data\memory\undefined_memory.json

# ========================================
# 性能配置
# ========================================
# 批处理大小 (用于向量插入)
BATCH_SIZE=100

# 连接池大小
CONNECTION_POOL_SIZE=10

# 查询超时时间 (秒)
QUERY_TIMEOUT=30

# ========================================
# 日志配置
# ========================================
# 日志级别: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO

# 日志文件路径
LOG_FILE=logs\miya.log

# 是否输出到控制台
LOG_TO_CONSOLE=true
```

### 环境变量优先级

1. 系统环境变量 (最高优先级)
2. `.env` 文件
3. 代码默认值 (最低优先级)

---

## 启动停止

### 便捷脚本

#### Windows

**启动所有数据库**:
```bash
# 方式 1: 使用启动脚本
start.bat

# 方式 2: 手动启动
docker-compose up -d
docker-compose -f docker-compose.milvus.yml up -d
```

**停止所有数据库**:
```bash
# 方式 1: 使用停止脚本
stop.bat

# 方式 2: 手动停止
docker-compose down
docker-compose -f docker-compose.milvus.yml down
```

**单独管理 Milvus**:
```bash
# 启动 Milvus
start_milvus.bat

# 停止 Milvus
stop_milvus.bat
```

#### Linux/macOS

**启动所有数据库**:
```bash
#!/bin/bash
# 启动 Redis 和 Neo4j
docker-compose up -d

# 启动 Milvus
docker-compose -f docker-compose.milvus.yml up -d

# 检查状态
docker-compose ps
```

**停止所有数据库**:
```bash
#!/bin/bash
# 停止 Redis 和 Neo4j
docker-compose down

# 停止 Milvus
docker-compose -f docker-compose.milvus.yml down
```

### Docker 命令详解

#### 查看容器状态
```bash
docker ps                    # 运行中的容器
docker ps -a                 # 所有容器 (包括停止的)
```

#### 查看日志
```bash
# 查看所有容器日志
docker-compose logs

# 查看特定容器日志
docker logs redis
docker logs neo4j
docker logs milvus-standalone

# 实时跟踪日志
docker logs -f milvus-standalone

# 查看最后 50 行
docker logs --tail 50 milvus-standalone
```

#### 重启服务
```bash
# 重启单个服务
docker-compose restart redis

# 重启所有服务
docker-compose restart

# 重建并重启 (重新创建容器)
docker-compose up -d --force-recreate
```

#### 进入容器
```bash
# 进入 Redis 容器
docker exec -it redis redis-cli

# 进入 Neo4j 容器
docker exec -it neo4j cypher-shell

# 进入 Milvus 容器
docker exec -it milvus-standalone bash
```

---

## 使用方法

### 1. 验证数据库连接

#### 测试 Redis
```python
import redis
from config.settings import settings

# 连接 Redis
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    password=settings.REDIS_PASSWORD,
    db=settings.REDIS_DB,
    decode_responses=True
)

# 测试连接
try:
    redis_client.ping()
    print("[OK] Redis 连接成功")
except Exception as e:
    print(f"[ERROR] Redis 连接失败: {e}")
```

#### 测试 Neo4j
```python
from neo4j import GraphDatabase
from config.settings import settings

# 连接 Neo4j
driver = GraphDatabase.driver(
    settings.NEO4J_URI,
    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
)

# 测试连接
try:
    driver.verify_connectivity()
    print("[OK] Neo4j 连接成功")

    # 查询节点数量
    with driver.session() as session:
        result = session.run("MATCH (n) RETURN count(n) as count")
        count = result.single()["count"]
        print(f"  节点数: {count}")
except Exception as e:
    print(f"[ERROR] Neo4j 连接失败: {e}")
finally:
    driver.close()
```

#### 测试 Milvus
```python
from pymilvus import MilvusClient
from config.settings import settings

# 连接 Milvus
milvus_client = MilvusClient(
    uri=settings.MILVUS_URI,
    token=settings.MILVUS_TOKEN
)

# 测试连接
try:
    collections = milvus_client.list_collections()
    print("[OK] Milvus 连接成功")
    print(f"  集合数量: {len(collections)}")
except Exception as e:
    print(f"[ERROR] Milvus 连接失败: {e}")
```

---

### 2. 在 MIYA 中使用记忆系统

#### 存储记忆

```python
from webnet.memory import MemoryNet

# 初始化 MemoryNet
memory_net = MemoryNet()

# 存储对话记忆
memory_net.store_memory(
    user_id="user_123",
    content="用户说今天心情不好",
    memory_type="dialogue",
    emotion="sad",
    importance=0.8
)

# 存储知识图谱关系
memory_net.store_knowledge_relation(
    subject="佳",
    relation="喜欢",
    object="蓝色",
    context="创造者偏好的颜色"
)
```

#### 检索记忆

```python
# 检索对话记忆
memories = memory_net.retrieve_recent_memories(
    user_id="user_123",
    limit=10
)

# 语义搜索长期记忆
results = memory_net.semantic_search(
    query="用户提到心情不好的时候",
    limit=5
)

# 知识图谱查询
relations = memory_net.knowledge_search(
    entity="佳",
    relation_type="喜欢"
)
```

---

### 3. 直接操作数据库

#### Redis 操作示例

```python
import redis

redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

# 存储对话历史
redis_client.lpush('user_123:history', json.dumps({
    "role": "user",
    "content": "你好",
    "time": "2026-03-04 10:00:00"
}))

# 获取对话历史
history = redis_client.lrange('user_123:history', 0, -1)

# 设置过期时间 (24小时)
redis_client.expire('user_123:history', 86400)
```

#### Neo4j 操作示例

```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver(
    'bolt://localhost:7687',
    auth=('neo4j', 'Aa316316')
)

# 创建节点和关系
with driver.session() as session:
    # 创建节点
    session.run("""
        CREATE (p:Person {name: '佳', role: 'creator'})
    """)

    # 创建关系
    session.run("""
        MATCH (p:Person {name: '佳'})
        CREATE (ai:AI {name: 'MIYA'})
        CREATE (p)-[:创造]->(ai)
    """)

    # 查询
    result = session.run("""
        MATCH (p:Person {name: '佳'})-[:创造]->(ai)
        RETURN ai.name as ai_name
    """)
    print(result.single()["ai_name"])

driver.close()
```

#### Milvus 操作示例

```python
from pymilvus import MilvusClient

client = MilvusClient(uri='http://localhost:19530')

# 创建集合
client.create_collection(
    collection_name='test_collection',
    dimension=768
)

# 插入向量
client.insert(
    collection_name='test_collection',
    data=[
        {
            'id': 1,
            'vector': [0.1, 0.2, ..., 0.768],  # 768 维向量
            'text': '这是一条测试数据',
            'metadata': {'source': 'test'}
        }
    ]
)

# 搜索向量
results = client.search(
    collection_name='test_collection',
    data=[[0.1, 0.2, ..., 0.768]],
    limit=10
)

# 查询集合统计
stats = client.get_collection_stats('test_collection')
print(f"总数据量: {stats['row_count']}")
```

---

### 4. 监控和调试

#### 查看数据库状态

```bash
# Redis
redis-cli INFO

# Neo4j
curl http://localhost:7474/db/manage/server/ha/available

# Milvus
curl http://localhost:19530/healthz
```

#### 查看数据统计

```python
# Redis
redis_client.dbsize()  # 键的数量

# Neo4j
session.run("MATCH (n) RETURN count(n) as count")

# Milvus
client.get_collection_stats('miya_memory')
```

---

## 故障排除

### 常见问题

#### 1. Redis 连接失败

**症状**:
```
ERROR: Could not connect to Redis at localhost:6379: Connection refused
```

**解决方案**:
```bash
# 检查 Redis 是否运行
docker ps | grep redis

# 如果没有运行,启动它
docker-compose up -d redis

# 检查端口是否被占用
netstat -ano | findstr :6379  # Windows
lsof -i :6379                  # Linux/macOS
```

---

#### 2. Neo4j 认证失败

**症状**:
```
Neo4jError: The client is unauthorized due to authentication failure.
```

**解决方案**:
1. 检查密码是否正确
2. 重置密码:
```bash
docker exec -it neo4j neo4j-admin set-initial-password Aa316316
```
3. 重启 Neo4j:
```bash
docker-compose restart neo4j
```

---

#### 3. Milvus 集合不存在错误

**症状**:
```
MilvusException: collection not found[miya_memory]
```

**解决方案**:
这是正常情况!集合会在首次使用时自动创建。如果想预创建:
```python
from pymilvus import MilvusClient

client = MilvusClient(uri='http://localhost:19530')

# 创建集合
client.create_collection(
    collection_name='miya_memory',
    dimension=768,
    metric_type='IP'  # 内积,适合文本相似度
)

print("集合创建成功")
```

---

#### 4. Docker 镜像拉取失败

**症状**:
```
Error response from daemon: failed to pull image
```

**解决方案**:
1. 配置 Docker 代理 (如果需要)
2. 使用国内镜像源
3. 手动拉取镜像:
```bash
docker pull quay.io/coreos/etcd:v3.5.5
docker pull minio/minio:latest
docker pull milvusdb/milvus:v2.4.15
```

---

#### 5. 端口冲突

**症状**:
```
bind: address already in use
```

**解决方案**:
1. 查找占用端口的进程:
```bash
netstat -ano | findstr :6379   # Windows
lsof -i :6379                  # Linux/macOS
```

2. 停止冲突的进程或修改端口配置

---

### 日志分析

#### Redis 日志
```bash
docker logs redis --tail 100
```

#### Neo4j 日志
```bash
docker logs neo4j --tail 100
```

#### Milvus 日志
```bash
docker logs milvus-standalone --tail 100
docker logs milvus-etcd --tail 50
docker logs milvus-minio --tail 50
```

---

## 性能优化

### Redis 优化

```ini
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

### Neo4j 优化

```ini
# neo4j.conf
dbms.memory.heap.initial_size=512m
dbms.memory.heap.max_size=2G
dbms.memory.pagecache.size=2G
dbms.connector.bolt.thread_pool_max_size=400
```

### Milvus 优化

```python
# 使用合适的索引类型
client.create_index(
    collection_name='miya_memory',
    index_name='vector_index',
    field_name='vector',
    index_type='HNSW',  # 高性能索引
    index_params={
        'M': 16,
        'efConstruction': 256
    }
)

# 批量插入
batch_size = 100
for i in range(0, len(data), batch_size):
    batch = data[i:i+batch_size]
    client.insert(collection_name, data=batch)
```

---

## 备份恢复

### Redis 备份

```bash
# 手动备份
docker exec redis redis-cli BGSAVE

# 拷贝备份文件
docker cp redis:/data/dump.rdb ./redis_backup.rdb

# 恢复
docker cp ./redis_backup.rdb redis:/data/dump.rdb
docker restart redis
```

### Neo4j 备份

```bash
# 使用 Neo4j Admin 工具
docker exec neo4j neo4j-admin database backup \
    --from-path=data/databases \
    --backup-dir=/backups \
    neo4j

# 拷贝备份文件
docker cp neo4j:/backups ./neo4j_backup
```

### Milvus 备份

```bash
# 备份 Milvus 数据
docker exec milvus-standalone cp -r /var/lib/milvus /tmp/milvus_backup

# 拷贝到宿主机
docker cp milvus-standalone:/tmp/milvus_backup ./milvus_backup
```

---

## 总结

### 快速检查清单

部署完成后,使用以下清单验证:

- [ ] Docker 已安装并运行
- [ ] Redis 容器运行中 (端口 6379)
- [ ] Neo4j 容器运行中 (端口 7474, 7687)
- [ ] Milvus 容器运行中 (端口 19530)
- [ ] Python 依赖已安装
- [ ] `.env` 文件已配置
- [ ] `test_memory_system.py` 测试通过
- [ ] MIYA 能正常启动和对话

### 相关文件

- 配置文件: `config/.env`
- Docker Compose: `docker-compose.yml`, `docker-compose.milvus.yml`
- 启动脚本: `start.bat`, `stop.bat`
- 测试脚本: `test_memory_system.py`
- 核心代码: `core/memory_system_initializer.py`

### 支持资源

- Redis 文档: https://redis.io/docs/
- Neo4j 文档: https://neo4j.com/docs/
- Milvus 文档: https://milvus.io/docs/
- Docker 文档: https://docs.docker.com/

---

**最后更新**: 2026-03-04
**维护者**: MIYA Team
