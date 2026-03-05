"""
迁移系统测试套件

测试Redis客户端、缓存系统、记忆系统的新实现
"""
import asyncio
import pytest
import time
from typing import Optional

# Redis客户端测试
from storage import RedisAsyncClient, RedisConfig, initialize_redis, get_redis_client, reset_redis
from storage.redis_async_client import MockRedisAsyncClient

# 缓存系统测试
from core.unified_cache import (
    get_cache, unified_cache_get, unified_cache_set,
    unified_cache_delete, unified_cache_clear, cached,
    BaseCacheLayer, CacheConfig
)
from core.cache_adapter import CacheManagerAdapter, PromptCacheAdapter

# 记忆系统测试
from memory.memory_interface import (
    MemoryItem, MemoryType, BaseMemoryInterface, MemoryManager,
    get_memory_manager
)
from memory.cognitive_adapter import CognitiveMemoryAdapter
from memory.cognitive_memory_system import CognitiveMemorySystem


class TestRedisClient:
    """Redis客户端测试"""
    
    @pytest.fixture
    async def redis_client(self):
        """创建测试用的Redis客户端（使用模拟模式）"""
        reset_redis()
        config = RedisConfig(use_mock=True)
        client = RedisAsyncClient(config)
        await client.connect()
        yield client
        await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_string_operations(self, redis_client):
        """测试字符串操作"""
        # 设置值
        await redis_client.set("test_key", "test_value", ttl=60)
        value = await redis_client.get("test_key")
        assert value == "test_value"
        
        # 删除值
        success = await redis_client.delete("test_key")
        assert success
        value = await redis_client.get("test_key")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_complex_types(self, redis_client):
        """测试复杂类型"""
        # 字典
        await redis_client.set("dict_key", {"name": "test", "value": 123})
        value = await redis_client.get("dict_key")
        assert value["name"] == "test"
        assert value["value"] == 123
        
        # 列表
        await redis_client.set("list_key", [1, 2, 3, 4])
        value = await redis_client.get("list_key")
        assert value == [1, 2, 3, 4]
    
    @pytest.mark.asyncio
    async def test_hash_operations(self, redis_client):
        """测试Hash操作"""
        # 设置hash字段
        await redis_client.hset("test_hash", "field1", "value1")
        await redis_client.hset("test_hash", "field2", "value2")
        
        # 获取hash字段
        value = await redis_client.hget("test_hash", "field1")
        assert value == "value1"
        
        # 获取所有hash字段
        all_data = await redis_client.hgetall("test_hash")
        assert len(all_data) == 2
        assert all_data["field1"] == "value1"
    
    @pytest.mark.asyncio
    async def test_list_operations(self, redis_client):
        """测试List操作"""
        # 推入列表
        await redis_client.lpush("test_list", "item1", "item2", "item3")
        
        # 弹出列表
        item = await redis_client.lpop("test_list")
        assert item == "item3"
        
        # 获取列表范围
        items = await redis_client.lrange("test_list", 0, -1)
        assert len(items) >= 1
    
    @pytest.mark.asyncio
    async def test_ttl_expiration(self, redis_client):
        """测试TTL过期"""
        # 设置短TTL
        await redis_client.set("expire_key", "value", ttl=1)
        
        # 立即获取
        value = await redis_client.get("expire_key")
        assert value == "value"
        
        # 等待过期
        await asyncio.sleep(1.1)
        value = await redis_client.get("expire_key")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_stats(self, redis_client):
        """测试统计信息"""
        await redis_client.set("key1", "value1")
        await redis_client.get("key1")
        await redis_client.get("nonexistent")
        
        stats = await redis_client.get_stats()
        assert stats["total_operations"] >= 3
        assert "is_mock" in stats
    
    @pytest.mark.asyncio
    async def test_redis_manager(self):
        """测试Redis管理器"""
        from storage import get_redis_manager
        
        manager = get_redis_manager()
        config = RedisConfig(use_mock=True)
        success = await manager.initialize(config)
        assert success
        
        client = await manager.get_client()
        assert client is not None
        assert client.is_mock
        
        await manager.close()


class TestUnifiedCache:
    """统一缓存系统测试"""
    
    @pytest.mark.asyncio
    async def test_basic_operations(self):
        """测试基本操作"""
        # 设置缓存
        success = await unified_cache_set("test_cache", "key1", "value1", 60)
        assert success
        
        # 获取缓存
        value = await unified_cache_get("test_cache", "key1")
        assert value == "value1"
        
        # 删除缓存
        success = await unified_cache_delete("test_cache", "key1")
        assert success
        
        # 验证删除
        value = await unified_cache_get("test_cache", "key1")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_cache_instance(self):
        """测试缓存实例"""
        cache = get_cache("instance_test")
        
        # 设置缓存
        await cache.set("key", "value", ttl=60)
        value = await cache.get("key")
        assert value == "value"
        
        # 获取统计
        stats = cache.get_stats()
        assert stats["size"] > 0
        assert "hits" in stats
        assert "misses" in stats
    
    @pytest.mark.asyncio
    async def test_ttl_expiration(self):
        """测试TTL过期"""
        # 设置短TTL
        await unified_cache_set("ttl_test", "key", "value", ttl=1)
        
        # 立即获取
        value = await unified_cache_get("ttl_test", "key")
        assert value == "value"
        
        # 等待过期
        await asyncio.sleep(1.1)
        value = await unified_cache_get("ttl_test", "key")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        """测试LRU驱逐"""
        config = CacheConfig(max_size=3, default_ttl=60)
        cache = get_cache("lru_test", config)
        
        # 添加4个条目（超过max_size）
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        await cache.set("key4", "value4")
        
        # 第一个条目应该被驱逐
        stats = cache.get_stats()
        assert stats["size"] <= 3
        value = await cache.get("key1")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_cached_decorator(self):
        """测试缓存装饰器"""
        call_count = 0
        
        @cached(cache_type="decorator_test", ttl=60)
        async def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * x
        
        # 第一次调用
        result1 = await expensive_function(5)
        assert result1 == 25
        assert call_count == 1
        
        # 第二次调用（应该命中缓存）
        result2 = await expensive_function(5)
        assert result2 == 25
        assert call_count == 1  # 没有增加
    
    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """测试缓存统计"""
        cache = get_cache("stats_test")
        
        # 命中
        await cache.set("key", "value")
        await cache.get("key")
        
        # 未命中
        await cache.get("nonexistent")
        
        stats = cache.get_stats()
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
        assert stats["hit_rate"] >= 0.0
    
    @pytest.mark.asyncio
    async def test_cache_clear(self):
        """测试清空缓存"""
        await unified_cache_set("clear_test", "key1", "value1")
        await unified_cache_set("clear_test", "key2", "value2")
        
        # 清空
        await unified_cache_clear("clear_test")
        
        # 验证
        value1 = await unified_cache_get("clear_test", "key1")
        value2 = await unified_cache_get("clear_test", "key2")
        assert value1 is None
        assert value2 is None


class TestCacheAdapter:
    """缓存适配器测试"""
    
    @pytest.mark.asyncio
    async def test_cache_manager_adapter(self):
        """测试缓存管理器适配器"""
        adapter = CacheManagerAdapter()
        
        # 测试基本操作
        await adapter.set("key", "value", ttl=60)
        value = await adapter.get("key")
        assert value == "value"
        
        # 测试统计
        stats = adapter.get_stats()
        assert stats is not None
    
    @pytest.mark.asyncio
    async def test_prompt_cache_adapter(self):
        """测试提示词缓存适配器"""
        adapter = PromptCacheAdapter()
        
        # 测试设置和获取
        context = {"user": "test", "query": "test query"}
        adapter.set(context, "cached prompt")
        
        result = adapter.get(context)
        assert result == "cached prompt"
        
        # 测试统计
        stats = adapter.get_stats()
        assert stats is not None


class TestMemorySystem:
    """记忆系统测试"""
    
    @pytest.fixture
    async def cognitive_memory(self):
        """创建认知记忆系统"""
        memory = CognitiveMemorySystem(enabled=True)
        await memory.initialize()
        yield memory
        await memory.cleanup()
    
    @pytest.fixture
    async def memory_adapter(self, cognitive_memory):
        """创建记忆适配器"""
        return CognitiveMemoryAdapter(cognitive_memory)
    
    @pytest.mark.asyncio
    async def test_memory_manager(self):
        """测试记忆管理器"""
        manager = get_memory_manager()
        
        # 测试基本操作（需要注册具体的记忆存储）
        stats = await manager.get_memory_stats()
        assert stats is not None
    
    @pytest.mark.asyncio
    async def test_memory_item_creation(self):
        """测试记忆项创建"""
        memory = MemoryItem(
            content="测试记忆内容",
            memory_type=MemoryType.COGNITIVE,
            timestamp=time.time(),
            importance=0.8,
            user_id="user123"
        )
        
        assert memory.content == "测试记忆内容"
        assert memory.memory_type == MemoryType.COGNITIVE
        assert memory.importance == 0.8
        assert memory.user_id == "user123"
    
    @pytest.mark.asyncio
    async def test_cognitive_adapter_short_term(self, memory_adapter):
        """测试认知记忆适配器 - 短期记忆"""
        memory = MemoryItem(
            content="用户的短期记忆",
            memory_type=MemoryType.SHORT_TERM,
            timestamp=time.time(),
            user_id="user123"
        )
        
        memory_id = await memory_adapter.add_memory(memory)
        assert memory_id is not None
        
        # 获取最近记忆
        recent = await memory_adapter.get_recent_memories(limit=5)
        assert len(recent) > 0
    
    @pytest.mark.asyncio
    async def test_cognitive_adapter_pinned(self, memory_adapter):
        """测试认知记忆适配器 - 置顶记忆"""
        memory = MemoryItem(
            content="重要的置顶信息",
            memory_type=MemoryType.PINNED,
            timestamp=time.time()
        )
        
        memory_id = await memory_adapter.add_memory(memory)
        assert memory_id is not None
        
        # 获取记忆
        retrieved = await memory_adapter.get_memory(memory_id)
        assert retrieved is not None
        assert retrieved.content == "重要的置顶信息"
    
    @pytest.mark.asyncio
    async def test_search_memories(self, memory_adapter):
        """测试搜索记忆"""
        # 添加一些记忆
        await memory_adapter.add_memory(MemoryItem(
            content="用户喜欢安静的环境",
            memory_type=MemoryType.COGNITIVE,
            timestamp=time.time()
        ))
        
        await memory_adapter.add_memory(MemoryItem(
            content="用户喜欢音乐",
            memory_type=MemoryType.COGNITIVE,
            timestamp=time.time()
        ))
        
        # 搜索
        results = await memory_adapter.search_memories(
            query="喜欢",
            top_k=10
        )
        
        assert len(results) > 0
    
    @pytest.mark.asyncio
    async def test_memory_stats(self, memory_adapter):
        """测试记忆统计"""
        stats = await memory_adapter.get_memory_stats()
        assert stats is not None
        assert "short_term_count" in stats
        assert "pinned_count" in stats


class TestIntegration:
    """集成测试"""
    
    @pytest.mark.asyncio
    async def test_redis_and_cache_integration(self):
        """测试Redis和缓存集成"""
        # 使用模拟Redis
        redis_config = RedisConfig(use_mock=True)
        redis = RedisAsyncClient(redis_config)
        await redis.connect()
        
        # 设置值
        await redis.set("integration_key", "integration_value")
        value = await redis.get("integration_key")
        assert value == "integration_value"
        
        # 同时使用缓存
        await unified_cache_set("integration", "cache_key", "cache_value")
        cache_value = await unified_cache_get("integration", "cache_key")
        assert cache_value == "cache_value"
        
        await redis.disconnect()
    
    @pytest.mark.asyncio
    async def test_cache_and_memory_integration(self):
        """测试缓存和记忆集成"""
        # 创建记忆项
        memory = MemoryItem(
            content="集成测试记忆",
            memory_type=MemoryType.SHORT_TERM,
            timestamp=time.time()
        )
        
        # 缓存记忆结果
        memory_id = f"mem_{int(time.time())}"
        await unified_cache_set("memory_cache", memory_id, memory)
        
        # 从缓存获取
        cached_memory = await unified_cache_get("memory_cache", memory_id)
        assert cached_memory.content == "集成测试记忆"
        
        # 清理
        await unified_cache_clear("memory_cache")


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
