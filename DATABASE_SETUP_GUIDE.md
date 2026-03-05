# 弥娅数据库部署指南

> 版本：v5.2 更新
> 更新时间：2026-02-28

---

## 概述

弥娅的记忆系统现在支持真实数据库连接，并具备自动回退机制：

- ✅ **Redis** - 潮汐记忆（短期缓存）
- ✅ **Milvus** - 向量长期记忆（语义检索）
- ✅ **Neo4j** - 知识图谱（五元组关系）

所有客户端都支持：
- 自动连接真实数据库（如果可用）
- 连接失败时自动回退到模拟模式
- 透明的模式切换，无需修改代码

---

## 快速启动

### 1. 使用Docker Compose一键启动（推荐）

```bash
# 启动所有数据库服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down

# 停止服务并删除数据卷（慎用！）
docker-compose down -v
```

### 2. 分步启动服务

```bash
# 启动Redis
docker-compose up -d redis

# 启动Milvus（会自动启动etcd和minio）
docker-compose up -d milvus

# 启动Neo4j
docker-compose up -d neo4j

# 启动管理工具（可选）
docker-compose --profile tools up -d
```

---

## 配置说明

### 环境变量配置

编辑 `config/.env` 文件：

```env
# Redis配置（可选，默认自动回退到模拟模式）
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=  # 留空表示无密码

# Milvus配置（可选）
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION=miya_memory
MILVUS_DIMENSION=1536
MILVUS_INDEX_TYPE=IVF_FLAT

# Neo4j配置（可选）
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=miya_password_2026
NEO4J_DATABASE=neo4j
```

### 默认凭据

| 服务 | 用户名 | 密码 | 访问地址 |
|-----|--------|------|---------|
| Redis | - | - | localhost:6379 |
| Milvus | - | - | localhost:19530 |
| MinIO | minioadmin | minioadmin | http://localhost:9001 |
| Neo4j | neo4j | miya_password_2026 | http://localhost:7474 |
| Redis Commander | - | - | http://localhost:8081 |

---

## 使用示例

### Python代码中使用

```python
from storage.redis_client import RedisClient
from storage.milvus_client import MilvusClient
from storage.neo4j_client import Neo4jClient
from hub.memory_engine import MemoryEngine
import logging

logging.basicConfig(level=logging.INFO)

# 1. 创建客户端（自动尝试连接，失败则回退到模拟模式）
redis_client = RedisClient(host='localhost', port=6379)
milvus_client = MilvusClient(host='localhost', port=19530, dimension=1536)
neo4j_client = Neo4jClient(uri='bolt://localhost:7687',
                             user='neo4j',
                             password='miya_password_2026')

# 2. 检查连接模式
print(f"Redis模式: {'真实' if not redis_client.is_mock_mode() else '模拟'}")
print(f"Milvus模式: {'真实' if not milvus_client.is_mock_mode() else '模拟'}")
print(f"Neo4j模式: {'真实' if not neo4j_client.is_mock_mode() else '模拟'}")

# 3. 创建记忆引擎
memory_engine = MemoryEngine(
    redis_client=redis_client,
    milvus_client=milvus_client,
    neo4j_client=neo4j_client
)

# 4. 存储潮汐记忆
memory_engine.store_tide(
    memory_id="test_001",
    content={"text": "用户喜欢吃苹果", "emotion": "joy"},
    priority=0.8,
    ttl=3600
)

# 5. 压缩为长期记忆
memory_engine.compress_to_dream("test_001")

# 6. 搜索长期记忆
results = memory_engine.search_dream("喜欢什么食物", top_k=5)
print(f"搜索结果: {results}")

# 7. 获取统计信息
stats = memory_engine.get_memory_stats()
print(f"记忆统计: {stats}")
```

---

## 管理工具访问

### Redis Commander

访问地址：http://localhost:8081

功能：
- 可视化查看Redis键值
- 执行Redis命令
- 监控Redis状态

启动：
```bash
docker-compose --profile tools up -d redis-commander
```

### MinIO Console

访问地址：http://localhost:9001

凭据：
- 用户名：minioadmin
- 密码：minioadmin

功能：
- 查看Milvus对象存储
- 管理存储桶

### Neo4j Browser

访问地址：http://localhost:7474

凭据：
- 用户名：neo4j
- 密码：miya_password_2026

功能：
- 执行Cypher查询
- 可视化知识图谱
- 监控Neo4j状态

示例Cypher查询：
```cypher
// 查看所有记忆节点
MATCH (n:Memory) RETURN n LIMIT 25

// 查看特定情绪的记忆
MATCH (s)-[r]->(o) WHERE r.emotion = 'joy' RETURN s, r, o

// 查看记忆关系图
MATCH (a)-[r]->(b) RETURN a, r, b LIMIT 100
```

---

## 健康检查

### 检查所有服务状态

```bash
# Redis
redis-cli ping
# 应该返回 PONG

# Milvus
curl http://localhost:9091/healthz
# 应该返回 OK

# Neo4j
curl http://localhost:7474
# 应该返回Neo4j页面
```

### 在Python中检查

```python
# Redis健康检查
if redis_client.connect():
    print("✅ Redis连接正常")

# Milvus健康检查
if milvus_client.connect():
    print("✅ Milvus连接正常")

# Neo4j健康检查
if neo4j_client.connect():
    print("✅ Neo4j连接正常")
```

---

## 性能调优

### Redis性能优化

```env
# 增加最大内存（在docker-compose.yml中配置）
REDIS_MAX_MEMORY=2gb

# 使用持久化
REDIS_APPENDONLY=yes

# 内存淘汰策略
REDIS_MAXMEMORY_POLICY=allkeys-lru
```

### Milvus性能优化

```env
# 索引类型选择
MILVUS_INDEX_TYPE=HNSW  # 更快的搜索速度

# HNSW参数
MILVUS_INDEX_PARAMS={"M":16,"efConstruction":200}

# 搜索参数
MILVUS_SEARCH_PARAMS={"ef":64}
```

### Neo4j性能优化

```env
# 增加堆内存（在docker-compose.yml中配置）
NEO4J_dbms_memory_heap_max__size=2g

# 增加页缓存
NEO4J_dbms_memory_pagecache_size=2g

# 并发查询数
NEO4J_dbms.cypher.max_query_cache_size=1000
```

---

## 数据备份

### Redis备份

```bash
# 触发快照
redis-cli BGSAVE

# 复制RDB文件
docker cp miya-redis:/data/dump.rdb ./backup/redis/
```

### Milvus备份

```bash
# 备份Milvus数据卷
docker run --rm -v miya_milvus_data:/data -v $(pwd)/backup:/backup \
  alpine tar czf /backup/milvus_backup_$(date +%Y%m%d).tar.gz -C /data .
```

### Neo4j备份

```bash
# 使用Neo4j备份命令
docker exec miya-neo4j neo4j-admin backup \
  --from=/data \
  --to=/backup \
  --backup-dir=/data/backups

# 复制备份文件
docker cp miya-neo4j:/data/backups ./backup/neo4j/
```

### 导出记忆数据

```python
# 导出所有记忆数据
data = memory_engine.export_memories()

# 保存到文件
import json
with open('memory_backup.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
```

---

## 故障排查

### 问题1：Redis连接失败

**症状**：日志显示"Redis连接失败，使用模拟模式"

**解决方案**：
1. 检查Redis是否运行：`docker-compose ps redis`
2. 检查端口是否被占用：`netstat -ano | findstr :6379`
3. 检查防火墙设置
4. 查看Redis日志：`docker-compose logs redis`

### 问题2：Milvus启动失败

**症状**：Milvus容器不断重启

**解决方案**：
1. 检查依赖服务：`docker-compose ps etcd minio`
2. 查看Milvus日志：`docker-compose logs milvus`
3. 确保内存充足（至少4GB）
4. 重启Milvus：`docker-compose restart milvus`

### 问题3：Neo4j密码错误

**症状**：认证失败

**解决方案**：
1. 重置Neo4j密码：
```bash
docker exec miya-neo4j neo4j-admin set-initial-password miya_password_2026
docker-compose restart neo4j
```

2. 更新配置文件中的密码

### 问题4：内存不足

**症状**：容器被OOM Killer杀死

**解决方案**：
1. 增加Docker内存限制
2. 调整数据库内存配置
3. 使用swap空间
4. 减少并发查询数

### 问题5：向量搜索速度慢

**症状**：搜索响应时间长

**解决方案**：
1. 创建索引：
```python
milvus_client.create_index(index_type='HNSW')
```

2. 调整搜索参数：
```python
results = milvus_client.search(
    query_vector=vector,
    top_k=10,
    metric_type='IP'
)
```

---

## 监控和日志

### 查看日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f redis
docker-compose logs -f milvus
docker-compose logs -f neo4j

# 查看最近100行日志
docker-compose logs --tail=100
```

### 性能监控

```bash
# Docker资源使用
docker stats

# Redis性能
redis-cli INFO stats

# Milvus性能
curl http://localhost:9091/metrics

# Neo4j性能
curl http://localhost:7474/db/manage/server/jmx/domain/org.neo4j/instance=kernel#name=Primitive.count
```

---

## 升级和维护

### 升级数据库版本

```bash
# 1. 备份数据
./scripts/backup_all.sh

# 2. 停止服务
docker-compose down

# 3. 修改docker-compose.yml中的镜像版本

# 4. 启动服务
docker-compose up -d

# 5. 验证数据
./scripts/verify_data.sh
```

### 清理过期数据

```python
# 清理Redis过期键
redis_client.flushdb()

# 清理Milvus旧向量
old_vectors = milvus_client.search([0]*1536, top_k=10000)
old_ids = [v['id'] for v in old_vectors if is_old(v)]
milvus_client.delete(old_ids)

# 清理Neo4j旧关系
neo4j_client.query("MATCH (n)-[r]->() WHERE r.created_at < '2024-01-01' DELETE r")
```

---

## 安全建议

1. **修改默认密码**：不要使用示例中的密码
2. **使用TLS加密**：生产环境建议启用TLS
3. **网络隔离**：使用Docker网络限制访问
4. **定期备份**：设置自动备份脚本
5. **访问控制**：配置防火墙规则
6. **日志审计**：启用访问日志和审计日志

---

## 常见问题

### Q: 必须使用真实数据库吗？

A: 不是必需的。系统会自动检测，如果连接失败会回退到模拟模式，保证系统正常运行。

### Q: 模拟模式和真实模式有什么区别？

A:
- **模拟模式**：数据存储在内存中，重启后丢失，适合测试和开发
- **真实模式**：数据持久化，支持大规模数据，适合生产环境

### Q: 如何从模拟模式迁移到真实模式？

A: 修改配置文件中的数据库连接信息，重启系统即可。系统会自动使用真实数据库。

### Q: 数据库的最低配置要求是什么？

A:
- Redis: 512MB内存
- Milvus: 4GB内存（standalone模式）
- Neo4j: 2GB内存

推荐配置：
- Redis: 2GB内存
- Milvus: 8GB内存
- Neo4j: 4GB内存

### Q: 如何扩展到分布式部署？

A:
- Redis: 使用Redis Cluster
- Milvus: 使用Milvus Cluster模式
- Neo4j: 使用Neo4j Causal Cluster

---

## 技术支持

如有问题，请：
1. 查看本文档的故障排查部分
2. 查看日志文件
3. 提交Issue到项目仓库
4. 加入用户社区讨论

---

**祝使用愉快！** 🚀
