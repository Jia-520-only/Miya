# MIYA 数据库部署检查清单

> 使用此清单确保数据库系统正确部署

---

## 📋 部署前检查

### 环境检查
- [ ] 操作系统: Windows 10+ / macOS 10.15+ / Linux (Ubuntu 20.04+)
- [ ] Python 版本: 3.9+
- [ ] Docker 已安装并运行
- [ ] 网络连接正常 (或已配置代理)
- [ ] 至少 8GB 可用内存
- [ ] 至少 20GB 可用磁盘空间

### 依赖软件检查
```bash
# 检查 Python 版本
python --version  # 应该显示 Python 3.9+

# 检查 Docker 版本
docker --version  # 应该显示 Docker 20.10+

# 检查 Docker Compose
docker-compose --version
```

---

## 🔧 安装步骤

### 1. 拉取代码
- [ ] 已克隆或下载项目代码
- [ ] 进入项目根目录

### 2. 安装 Python 依赖
```bash
# Windows
pip install -r requirements.txt

# Linux/macOS
pip3 install -r requirements.txt
```

检查项:
- [ ] 所有依赖安装成功
- [ ] 没有报错或警告

### 3. 配置环境变量
- [ ] 已复制 `.env.example` 为 `.env`
- [ ] 已编辑 `config/.env` 文件

关键配置检查:
- [ ] `REDIS_HOST=localhost`
- [ ] `REDIS_PORT=6379`
- [ ] `NEO4J_URI=bolt://localhost:7687`
- [ ] `NEO4J_USER=neo4j`
- [ ] `NEO4J_PASSWORD=Aa316316` (或你的密码)
- [ ] `MILVUS_URI=http://localhost:19530`
- [ ] `MILVUS_USE_LITE=false` (使用远程 Milvus)

### 4. 启动数据库容器
```bash
# 启动 Redis 和 Neo4j
docker-compose up -d

# 启动 Milvus
docker-compose -f docker-compose.milvus.yml up -d
```

容器状态检查:
- [ ] `redis` 容器运行中
- [ ] `neo4j` 容器运行中
- [ ] `milvus-standalone` 容器运行中
- [ ] `milvus-etcd` 容器运行中
- [ ] `milvus-minio` 容器运行中

验证命令:
```bash
docker ps
# 应该看到上述 5 个容器
```

---

## ✅ 连接测试

### Redis 连接测试
- [ ] 运行测试: `redis-cli ping` (如果已安装)
- [ ] 或运行 Python 测试:
```python
import redis
r = redis.Redis(host='localhost', port=6379)
print(r.ping())  # 应该输出 True
```

### Neo4j 连接测试
- [ ] 访问 http://localhost:7474
- [ ] 使用用户名 `neo4j` 和密码 `Aa316316` 登录
- [ ] 执行测试查询:
```cypher
MATCH (n) RETURN count(n)
```
- [ ] 显示查询结果,无错误

### Milvus 连接测试
- [ ] 运行 Python 测试:
```python
from pymilvus import MilvusClient
c = MilvusClient('http://localhost:19530')
print(len(c.list_collections()))  # 应该输出集合数量
```

### 综合测试
- [ ] 运行 `python test_memory_system.py`
- [ ] 所有测试项显示 `[OK]`
- [ ] 没有错误或异常

---

## 🎯 功能验证

### 启动 MIYA
- [ ] 运行启动命令: `start.bat` 或 `python run/qq_main.py`
- [ ] 系统正常初始化
- [ ] 所有子系统加载成功

### 日志验证
检查启动日志中是否有以下关键信息:
- [ ] `已连接到 Redis`
- [ ] `已连接到 Neo4j`
- [ ] `已连接到 Milvus (远程模式)`
- [ ] `弥娅记忆系统初始化完成`

### 对话测试
- [ ] 发送测试消息
- [ ] MIYA 正常回复
- [ ] 对话历史保存到 Redis
- [ ] 长期记忆存储到 Milvus
- [ ] 知识图谱更新到 Neo4j

---

## 📊 性能检查

### 响应时间
- [ ] 普通对话响应时间 < 3 秒
- [ ] 记忆检索时间 < 1 秒
- [ ] 知识图谱查询时间 < 2 秒

### 资源使用
```bash
# 检查容器资源使用
docker stats

# 正常范围:
# - Redis: < 500MB 内存
# - Neo4j: < 2GB 内存
# - Milvus: < 4GB 内存
```

---

## 🔍 故障排查检查

### 如果 Redis 连接失败
- [ ] 检查 Redis 容器是否运行: `docker ps | grep redis`
- [ ] 检查端口是否被占用: `netstat -ano | findstr :6379`
- [ ] 查看 Redis 日志: `docker logs redis`
- [ ] 重启 Redis: `docker-compose restart redis`

### 如果 Neo4j 连接失败
- [ ] 检查密码是否正确
- [ ] 重置密码: `docker exec -it neo4j neo4j-admin set-initial-password Aa316316`
- [ ] 查看 Neo4j 日志: `docker logs neo4j`
- [ ] 重启 Neo4j: `docker-compose restart neo4j`

### 如果 Milvus 连接失败
- [ ] 等待 Milvus 启动 (15-30 秒)
- [ ] 检查所有 Milvus 容器是否运行
- [ ] 查看 Milvus 日志: `docker logs milvus-standalone`
- [ ] 集合不存在是正常的,会自动创建

### 如果 MIYA 启动失败
- [ ] 检查 Python 依赖是否完整
- [ ] 检查 `.env` 文件配置
- [ ] 运行 `python test_memory_system.py` 诊断问题
- [ ] 查看启动日志中的错误信息

---

## 📝 部署完成确认

### 必要文件
- [ ] `config/.env` 配置文件
- [ ] `docker-compose.yml` (Redis + Neo4j)
- [ ] `docker-compose.milvus.yml` (Milvus)
- [ ] `start.bat` / `start.sh` 启动脚本
- [ ] `stop.bat` / `stop.sh` 停止脚本

### 运行服务
- [ ] Redis 运行中 (端口 6379)
- [ ] Neo4j 运行中 (端口 7474, 7687)
- [ ] Milvus 运行中 (端口 19530)
- [ ] 所有容器健康状态正常

### 功能就绪
- [ ] MIYA 能正常启动
- [ ] 对话功能正常
- [ ] 记忆系统正常工作
- [ ] 所有测试通过

---

## 🚀 部署后建议

### 安全配置
- [ ] 修改 Redis 密码 (生产环境)
- [ ] 修改 Neo4j 密码 (生产环境)
- [ ] 配置防火墙规则
- [ ] 限制数据库访问 IP

### 备份策略
- [ ] 设置定期备份计划
- [ ] 测试备份恢复流程
- [ ] 备份文件存储在安全位置

### 监控配置
- [ ] 配置日志监控
- [ ] 设置资源使用告警
- [ ] 配置性能监控工具

---

## 📚 参考文档

- [完整指南](./DATABASE_COMPLETE_GUIDE.md) - 详细的部署和使用文档
- [快速参考](./DATABASE_QUICK_REFERENCE.md) - 常用命令和配置速查
- [项目 README](../README.md) - 项目总体介绍

---

## ✨ 部署成功!

如果以上所有项目都已检查完成,恭喜你!MIYA 数据库系统已经成功部署。

**下一步**:
1. 启动 MIYA 开始使用
2. 阅读[快速参考](./DATABASE_QUICK_REFERENCE.md)了解常用命令
3. 参考[完整指南](./DATABASE_COMPLETE_GUIDE.md)深入了解系统

---

**部署日期**: ___________
**部署人员**: ___________
**备注**: ___________
