# MIYA 数据库系统 - 快速参考

> 用于快速查询常用命令和配置

---

## 🚀 快速启动

### 一键启动所有服务
```bash
# Windows
start.bat

# Linux/macOS
bash start.sh
```

### 单独启动 Milvus
```bash
# Windows
start_milvus.bat

# Linux/macOS
docker-compose -f docker-compose.milvus.yml up -d
```

---

## 🔧 常用命令

### Docker 容器管理
```bash
# 查看运行状态
docker ps

# 查看所有容器
docker ps -a

# 查看日志
docker-compose logs
docker logs milvus-standalone -f

# 重启服务
docker-compose restart
docker-compose restart milvus-standalone

# 停止服务
docker-compose down
docker-compose -f docker-compose.milvus.yml down
```

### 数据库连接测试
```bash
# 测试所有数据库
python test_memory_system.py

# 测试 Redis
python -c "import redis; r = redis.Redis(); print(r.ping())"

# 测试 Neo4j
python -c "from neo4j import GraphDatabase; d = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j','Aa316316')); print(d.verify_connectivity())"

# 测试 Milvus
python -c "from pymilvus import MilvusClient; c = MilvusClient('http://localhost:19530'); print(len(c.list_collections()))"
```

---

## 📊 数据库信息

### Redis
- **端口**: 6379
- **默认密码**: 无
- **数据类型**: 对话历史、会话状态
- **存储位置**: 内存 (持久化到 `dump.rdb`)

### Neo4j
- **Bolt 端口**: 7687
- **HTTP 端口**: 7474
- **用户名**: neo4j
- **密码**: Aa316316
- **访问地址**: http://localhost:7474
- **存储位置**: 容器内 `/data`

### Milvus
- **端口**: 19530
- **Web UI**: 9091
- **访问地址**: http://localhost:9091
- **存储位置**: 容器内 `/var/lib/milvus`

---

## ⚙️ 配置文件

### .env 关键配置
```ini
# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=Aa316316

# Milvus
MILVUS_URI=http://localhost:19530
MILVUSE_LITE=false  # false=远程Milvus, true=Milvus Lite
```

---

## 🐛 常见问题解决

### Redis 连接失败
```bash
# 检查 Redis 是否运行
docker ps | grep redis

# 重启 Redis
docker-compose restart redis

# 查看 Redis 日志
docker logs redis
```

### Neo4j 认证失败
```bash
# 重置密码
docker exec -it neo4j neo4j-admin set-initial-password Aa316316

# 重启 Neo4j
docker-compose restart neo4j
```

### Milvus 集合不存在
```python
# 这是正常的,集合会自动创建
# 手动创建集合:
from pymilvus import MilvusClient
client = MilvusClient('http://localhost:19530')
client.create_collection('miya_memory', 768)
```

### 端口冲突
```bash
# Windows 查看端口占用
netstat -ano | findstr :6379

# Linux/macOS 查看端口占用
lsof -i :6379
```

---

## 💾 备份恢复

### Redis 备份
```bash
# 备份
docker exec redis redis-cli BGSAVE
docker cp redis:/data/dump.rdb ./redis_backup.rdb

# 恢复
docker cp ./redis_backup.rdb redis:/data/dump.rdb
docker restart redis
```

### Neo4j 备份
```bash
# 备份
docker exec neo4j neo4j-admin database backup neo4j /backups
docker cp neo4j:/backups ./neo4j_backup

# 访问 Neo4j Browser 备份
http://localhost:7474 → System → Backup
```

### Milvus 备份
```bash
# 备份数据卷
docker run --rm -v miya_milvus:/data -v $(pwd):/backup alpine tar czf /backup/milvus_backup.tar.gz /data
```

---

## 📈 性能监控

### 查看数据库状态
```bash
# Redis
redis-cli INFO

# Neo4j
curl http://localhost:7474/db/manage/server/ha/available

# Milvus
curl http://localhost:19530/healthz
```

### 查看数据统计
```python
# Redis
redis_client.dbsize()

# Neo4j
MATCH (n) RETURN count(n)  # 在 Neo4j Browser 中执行

# Milvus
client.get_collection_stats('miya_memory')
```

---

## 🔗 相关链接

- **Redis 文档**: https://redis.io/docs/
- **Neo4j 文档**: https://neo4j.com/docs/
- **Milvus 文档**: https://milvus.io/docs/
- **Docker 文档**: https://docs.docker.com/
- **完整指南**: [DATABASE_COMPLETE_GUIDE.md](./DATABASE_COMPLETE_GUIDE.md)

---

## 📞 故障排查流程

1. 检查 Docker 容器是否运行: `docker ps`
2. 查看日志找出错误: `docker-compose logs`
3. 检查端口是否冲突: `netstat` / `lsof`
4. 检查配置文件: `config/.env`
5. 运行测试脚本: `python test_memory_system.py`
6. 查看详细文档: `docs/DATABASE_COMPLETE_GUIDE.md`

---

**快速提示**: 遇到问题时,先查看日志!日志是最好的故障排查工具。
