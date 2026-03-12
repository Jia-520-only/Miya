# 数据库修复快速指南

## ✅ 已完成的修复

### 1. Redis客户端 (`storage/redis_client.py`)
- ✅ 支持真实Redis连接
- ✅ 自动回退到模拟模式（连接失败时）
- ✅ 完整的Redis API支持（string, hash, list等）
- ✅ TTL过期自动处理
- ✅ 连接健康检查

### 2. Milvus客户端 (`storage/milvus_client.py`)
- ✅ 支持真实Milvus连接
- ✅ 自动回退到模拟模式
- ✅ 向量插入、搜索、删除、更新
- ✅ 支持多种距离计算（L2, IP, COSINE）
- ✅ 集合管理（创建、删除、索引）

### 3. Neo4j客户端 (`storage/neo4j_client.py`)
- ✅ 支持真实Neo4j连接
- ✅ 自动回退到模拟模式
- ✅ 节点和关系管理
- ✅ Cypher查询支持
- ✅ 记忆五元组专门方法

### 4. 记忆引擎 (`hub/memory_engine.py`)
- ✅ 集成真实数据库客户端
- ✅ 潮汐记忆存储到Redis
- ✅ 长期记忆存储到Milvus
- ✅ 知识图谱存储到Neo4j
- ✅ 智能搜索（向量+关键词）
- ✅ 自动模式切换

### 5. Docker Compose配置 (`docker-compose.yml`)
- ✅ 一键启动所有数据库服务
- ✅ 包含Redis、Milvus、Neo4j
- ✅ 包含依赖服务（etcd, minio）
- ✅ 可选管理工具（Redis Commander）
- ✅ 健康检查和自动重启

---

## 🚀 快速开始

### 方式1：使用模拟模式（无需安装数据库）

```bash
# 直接运行系统
python run/main.py

# 或启动PC端
run/pc_start.bat
```

系统会自动使用模拟模式，所有数据存储在内存中。

### 方式2：使用真实数据库（推荐）

#### 步骤1：启动数据库服务

```bash
# Windows
docker-compose up -d

# Linux/Mac
chmod +x docker-compose.yml
docker-compose up -d
```

等待约30-60秒让所有服务启动完成。

#### 步骤2：验证连接

```bash
# 运行测试脚本
python test_database_connection.py
```

你会看到类似这样的输出：

```
============================================================
  测试 Redis 连接
============================================================
✅ Redis连接成功!
   模式: 真实
   SET/GET测试: ✅ 成功
   统计信息: {'mode': 'real', 'keys_count': 1, ...}
```

#### 步骤3：启动弥娅

```bash
# 命令行模式
python run/main.py

# 或PC端
run/pc_start.bat
```

系统会自动检测并使用真实数据库。

---

## 📊 数据库管理

### 访问Web管理界面

| 服务 | 地址 | 用途 |
|-----|------|------|
| Redis Commander | http://localhost:8081 | Redis可视化管理 |
| MinIO Console | http://localhost:9001 | Milvus对象存储管理 |
| Neo4j Browser | http://localhost:9001 | 知识图谱可视化 |

**启动管理工具**：
```bash
docker-compose --profile tools up -d redis-commander
```

### 查看日志

```bash
# 查看所有日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f redis
docker-compose logs -f milvus
docker-compose logs -f neo4j
```

---

## 🔧 配置说明

### 最小配置（使用默认值）

无需修改任何配置，系统会自动：
- 尝试连接localhost的数据库
- 连接失败时自动回退到模拟模式

### 完整配置

编辑 `config/.env` 文件：

```env
# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Milvus配置
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION=miya_memory
MILVUS_DIMENSION=1536
MILVUS_INDEX_TYPE=IVF_FLAT

# Neo4j配置
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=miya_password_2026
NEO4J_DATABASE=neo4j
```

---

## 💡 使用示例

### Python代码中使用

```python
from storage.redis_client import RedisClient
from storage.milvus_client import MilvusClient
from storage.neo4j_client import Neo4jClient
from hub.memory_engine import MemoryEngine

# 创建客户端（自动检测，失败则回退）
redis = RedisClient()
milvus = MilvusClient(dimension=1536)
neo4j = Neo4jClient(password='miya_password_2026')

# 检查连接模式
print(f"Redis: {redis.is_mock_mode()}")  # False=真实, True=模拟
print(f"Milvus: {milvus.is_mock_mode()}")
print(f"Neo4j: {neo4j.is_mock_mode()}")

# 使用记忆引擎
memory = MemoryEngine(redis, milvus, neo4j)

# 存储记忆
memory.store_tide("mem_001", {"text": "我喜欢苹果"}, priority=0.8)

# 压缩为长期记忆
memory.compress_to_dream("mem_001")

# 搜索记忆
results = memory.search_dream("喜欢什么")

# 获取统计
stats = memory.get_memory_stats()
print(stats)
```

---

## 🐛 常见问题

### Q1: 启动数据库失败？

**错误**：`Cannot connect to Redis/Milvus/Neo4j`

**解决**：
1. 确保Docker已安装并运行
2. 检查端口是否被占用：`netstat -ano | findstr :6379`
3. 查看服务日志：`docker-compose logs -f`

### Q2: 内存不足？

**错误**：容器被OOM Killer杀死

**解决**：
1. 增加Docker内存限制到至少8GB
2. 或只启动部分服务：
```bash
# 只启动Redis
docker-compose up -d redis

# 只启动Milvus（不启动Neo4j）
docker-compose up -d redis milvus
```

### Q3: 必须使用真实数据库吗？

**不必须**。系统会自动检测，如果连接失败会回退到模拟模式，保证系统正常运行。

### Q4: 模拟模式和真实模式有什么区别？

| 特性 | 模拟模式 | 真实模式 |
|-----|---------|---------|
| 数据持久化 | ❌ 重启丢失 | ✅ 持久化存储 |
| 搜索性能 | ⚠️ 内存计算 | ✅ 索引加速 |
| 数据容量 | ⚠️ 受限内存 | ✅ 可扩展 |
| 并发支持 | ⚠️ 单线程 | ✅ 高并发 |

---

## 📈 性能建议

### 开发/测试
- 使用模拟模式或轻量级配置
- 只启动Redis
- 内存要求：2GB+

### 生产环境
- 使用真实数据库
- 启动所有服务
- 调整配置参数优化性能
- 内存要求：8GB+
- 磁盘：SSD推荐

### 优化配置

```env
# Redis：增加最大内存
REDIS_MAX_MEMORY=2gb

# Milvus：使用HNSW索引（更快）
MILVUS_INDEX_TYPE=HNSW

# Neo4j：增加堆内存
NEO4J_dbms_memory_heap_max__size=2g
```

---

## 📚 更多文档

- **详细部署指南**: `DATABASE_SETUP_GUIDE.md`
- **系统架构**: `ARCHITECTURE_ALIGNMENT_REPORT.md`
- **完整文档**: `README.md`

---

## ✨ 关键特性

### 自动回退机制

```python
# 尝试连接真实数据库
if not redis_client.connect():
    # 失败则自动使用模拟模式
    logger.warning("使用模拟模式")
    # 系统继续正常运行
```

### 透明切换

```python
# 代码完全相同，无需修改
client = RedisClient()
client.set('key', 'value')
value = client.get('key')
# 自动使用真实Redis或模拟实现
```

### 健康检查

```python
# 检查连接状态
if not client.is_mock_mode():
    # 真实模式
    stats = client.get_stats()
else:
    # 模拟模式
    stats = client.get_stats()
```

---

## 🎯 下一步

1. ✅ 修复完成！测试数据库连接：
   ```bash
   python test_database_connection.py
   ```

2. 🚀 启动弥娅系统：
   ```bash
   python run/main.py
   ```

3. 📊 查看管理界面：
   - Redis Commander: http://localhost:8081
   - Neo4j Browser: http://localhost:7474

4. 📖 阅读详细文档：
   - `DATABASE_SETUP_GUIDE.md`

---

**祝使用愉快！** 🎉
