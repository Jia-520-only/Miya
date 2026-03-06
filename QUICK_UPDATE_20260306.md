# MIYA 快速更新指南 (2026-03-06)

## 本次更新内容

### 1. 真正的向量功能 ✨

**之前**：
- ❌ 声称有"向量缓存"，但实际是假的
- ❌ 没有真正调用Embedding API
- ❌ 没有向量相似度搜索

**现在**：
- ✅ 实现真正的Embedding API集成
- ✅ 使用Milvus Lite向量数据库
- ✅ 支持向量相似度搜索
- ✅ 集成到SemanticDynamicsEngine

**支持的提供商**：
- OpenAI (text-embedding-3-small/large)
- DeepSeek (deepseek-embedding)
- SiliconFlow (BAAI/bge-large-zh-v1.5)
- Sentence Transformers (本地模型，无需API Key)

**快速开始**：
```bash
# 运行演示脚本（无需API Key，使用本地模型）
python demo_vector.py
```

### 2. 文件清理 🗑️

**删除的文件**：
- 39+ 个无用文件
- 释放 61.7 MB 空间

**清理内容**：
- 备份和临时文件 (~61.1 MB)
- 未使用配置文件 (~16 KB)
- 过时文档 (~560 KB)
- 示例和归档 (~40 KB)

**效果**：
- 项目更清爽
- Git操作更快
- 消除混淆

### 3. 架构澄清 📐

**之前**：
- ❌ 错误地描述为"蛛网式分布式架构"

**现在**：
- ✅ 明确为"模块化单体架构"
- ✅ 所有模块在同一Python进程中运行
- ✅ 模块间通过函数调用通信（延迟 < 1ms）

### 4. 多模型功能 (已完成) 🤖

**功能**：
- ✅ 6个模型全部使用
- ✅ 根据任务类型动态选择模型
- ✅ 测试通过 (9/10)

---

## 使用指南

### 向量功能（无需API Key）

```python
import asyncio
from core.embedding_client import EmbeddingClient, EmbeddingProvider
from memory.real_vector_cache import VectorCacheManager

async def main():
    # 使用本地模型
    client = EmbeddingClient(
        provider=EmbeddingProvider.SENTENCE_TRANSFORMERS,
        model="paraphrase-multilingual-MiniLM-L12-v2"
    )
    await client.initialize()

    # 创建向量缓存
    vector_cache = VectorCacheManager(
        embedding_client=client,
        milvus_db_path="data/milvus_lite.db"
    )

    # 添加对话
    await vector_cache.add_conversation(
        user_input="你好",
        ai_response="你好！我是弥娅"
    )

    # 搜索相似内容
    results = await vector_cache.search_similar(
        query="问候",
        top_k=5
    )

    print(f"找到 {len(results)} 条相似内容")

if __name__ == "__main__":
    asyncio.run(main())
```

### 向量功能（使用API）

```python
# 配置API Key在 config/.env
# OPENAI_API_KEY=sk-xxx
# 或
# DEEPSEEK_API_KEY=sk-xxx

from core.embedding_client import EmbeddingClient, EmbeddingProvider

client = EmbeddingClient(
    provider=EmbeddingProvider.OPENAI,  # 或 DEEPSEEK
    api_key="your_api_key"
)
await client.initialize()
```

---

## 新增文件

### 核心功能
- `core/embedding_client.py` - Embedding API客户端
- `memory/real_vector_cache.py` - 真正的向量缓存系统

### 文档
- `VECTOR_SYSTEM_COMPLETE.md` - 向量系统实现完成
- `CLEANUP_REPORT.md` - 文件清理报告
- `INTEGRATION_REPORT_20260306.md` - 本次优化总结
- `VECTOR_CACHE_ANALYSIS.md` - 向量缓存真实性分析

### 演示和测试
- `demo_vector.py` - 向量系统演示脚本
- `tests/test_vector_functionality.py` - 向量功能测试

---

## 修改的文件

### 内存模块
- `memory/__init__.py` - 导出新的向量模块

### 语义引擎
- `memory/semantic_dynamics_engine.py` - 集成向量缓存

---

## 演示

### 运行向量演示

```bash
python demo_vector.py
```

**演示内容**：
1. 初始化本地Sentence Transformers模型
2. 创建向量缓存（Milvus Lite）
3. 添加示例对话
4. 测试向量相似度搜索

**注意**：
- 首次运行会下载模型文件（~400MB）
- 之后会使用缓存的模型

### 运行测试

```bash
python tests/test_vector_functionality.py
```

**测试内容**：
1. Embedding客户端测试
2. 向量缓存测试
3. 向量缓存管理器测试

---

## 常见问题

### Q1: 向量功能需要API Key吗？

**A**: 不一定。可以使用本地Sentence Transformers模型，无需API Key。首次使用会下载模型文件。

### Q2: Milvus Lite需要Docker吗？

**A**: 不需要。Milvus Lite是本地文件模式，直接在Python中运行。

### Q3: 向量数据存储在哪里？

**A**: 存储在`data/milvus_lite.db`文件中。

### Q4: 向量维度是多少？

**A**: 取决于模型：
- OpenAI text-embedding-3-small: 1536
- OpenAI text-embedding-3-large: 3072
- DeepSeek deepseek-embedding: 1536
- Sentence Transformers: 384

### Q5: 如何切换到API提供商？

**A**:
```python
# 在 config/.env 中配置
OPENAI_API_KEY=sk-xxx
# 或
DEEPSEEK_API_KEY=sk-xxx

# 代码中使用
from core.embedding_client import EmbeddingClient, EmbeddingProvider

client = EmbeddingClient(
    provider=EmbeddingProvider.OPENAI,  # 或 DEEPSEEK
    api_key="your_api_key"
)
```

---

## 相关链接

- `VECTOR_SYSTEM_COMPLETE.md` - 向量系统详细文档
- `CLEANUP_REPORT.md` - 文件清理详细报告
- `README.md` - 项目主文档

---

**更新时间**: 2026-03-06
