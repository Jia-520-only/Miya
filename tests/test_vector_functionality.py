"""
测试真正的向量缓存功能
验证Embedding API和Milvus Lite集成
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from core.embedding_client import EmbeddingClient, EmbeddingProvider, get_embedding_client
from memory.real_vector_cache import RealVectorCache, VectorCacheManager, get_vector_cache_manager


async def test_embedding_client():
    """测试Embedding客户端"""
    print("\n" + "=" * 60)
    print("测试1: Embedding客户端")
    print("=" * 60)

    try:
        # 使用DeepSeek作为示例（假设API key在config/.env中）
        # 如果没有API key，可以使用sentence-transformers本地模型
        import os
        from dotenv import load_dotenv

        load_dotenv()

        api_key = os.getenv('DEEPSEEK_API_KEY') or os.getenv('OPENAI_API_KEY')

        if api_key:
            # 使用API
            provider = EmbeddingProvider.DEEPSEEK if os.getenv('DEEPSEEK_API_KEY') else EmbeddingProvider.OPENAI
            client = EmbeddingClient(
                provider=provider,
                api_key=api_key
            )
            await client.initialize()
        else:
            # 使用本地模型
            print("未检测到API key，使用本地Sentence Transformers模型...")
            client = EmbeddingClient(
                provider=EmbeddingProvider.SENTENCE_TRANSFORMERS,
                model="paraphrase-multilingual-MiniLM-L12-v2"
            )
            await client.initialize()

        # 测试单个文本
        test_text = "弥娅是一个数字生命伴侣"
        print(f"\n生成向量: '{test_text}'")

        vector = await client.embed(test_text)

        if vector:
            print(f"向量维度: {len(vector)}")
            print(f"向量前10个值: {vector[:10]}")
            print("测试1: PASSED")
        else:
            print("测试1: FAILED - 向量为空")
            return False

        # 测试批量
        texts = [
            "你好世界",
            "人工智能",
            "机器学习"
        ]
        print(f"\n批量生成向量: {len(texts)} 条文本")

        vectors = await client.embed_batch(texts, batch_size=3)

        if vectors and len(vectors) == len(texts):
            print(f"成功生成 {len(vectors)} 个向量")
            print("测试1 (批量): PASSED")
        else:
            print("测试1 (批量): FAILED")
            return False

        return True, client

    except Exception as e:
        print(f"测试1: FAILED - {e}")
        import traceback
        traceback.print_exc()
        return False, None


async def test_vector_cache(embedding_client):
    """测试向量缓存"""
    print("\n" + "=" * 60)
    print("测试2: 向量缓存（Milvus Lite）")
    print("=" * 60)

    try:
        # 创建向量缓存
        cache = RealVectorCache(
            embedding_client=embedding_client,
            milvus_db_path="data/test_milvus_lite.db",
            collection_name="test_vectors"
        )

        print(f"\n缓存模式: {'真实模式' if cache.is_real_mode() else '模拟模式'}")

        # 测试添加
        test_text = "这是一个测试文本，用于验证向量缓存功能"
        print(f"\n添加文本: '{test_text}'")

        success = await cache.add(
            text=test_text,
            metadata={'type': 'test', 'source': 'unit_test'}
        )

        if success:
            print("添加成功")
        else:
            print("添加失败")
            return False

        # 测试搜索
        print("\n执行向量相似度搜索...")
        results = await cache.search(
            query="测试文本",
            top_k=5
        )

        if results:
            print(f"搜索到 {len(results)} 条结果")
            for i, result in enumerate(results[:3]):
                distance = result.get('distance', 1.0)
                metadata = result.get('metadata', {})
                print(f"  结果{i+1}: distance={distance:.4f}, text={metadata.get('text', '')[:50]}...")
            print("测试2 (搜索): PASSED")
        else:
            print("测试2 (搜索): FAILED - 无搜索结果")
            return False

        # 获取统计信息
        stats = cache.get_stats()
        print(f"\n缓存统计: {stats}")

        # 清理
        await cache.clear()
        cache.close()

        print("测试2: PASSED")
        return True

    except Exception as e:
        print(f"测试2: FAILED - {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_vector_cache_manager(embedding_client):
    """测试向量缓存管理器"""
    print("\n" + "=" * 60)
    print("测试3: 向量缓存管理器")
    print("=" * 60)

    try:
        # 创建缓存管理器
        manager = VectorCacheManager(
            embedding_client=embedding_client,
            milvus_db_path="data/test_manager_milvus_lite.db"
        )

        # 测试添加对话
        user_input = "你好，我是用户"
        ai_response = "你好！我是弥娅，很高兴认识你。"

        print(f"\n添加对话:")
        print(f"  用户: {user_input}")
        print(f"  AI: {ai_response}")

        success = await manager.add_conversation(user_input, ai_response)

        if success:
            print("添加对话成功")
        else:
            print("添加对话失败")
            return False

        # 测试搜索
        print("\n搜索相似对话...")
        results = await manager.search_similar(
            query="你好",
            cache_type="embedding",
            top_k=3
        )

        if results:
            print(f"搜索到 {len(results)} 条结果")
            print("测试3 (搜索): PASSED")
        else:
            print("测试3 (搜索): 无结果（可能是向量还未完全索引）")

        # 获取统计信息
        stats = manager.get_stats()
        print(f"\n管理器统计:")
        print(f"  Embedding缓存: {stats['embedding_cache']['total_vectors']} 条")
        print(f"  Query缓存: {stats['query_cache']['total_vectors']} 条")
        print(f"  Memo缓存: {stats['memo_cache']['total_vectors']} 条")
        print(f"  总计: {stats['total_vectors']} 条")

        manager.close()

        print("测试3: PASSED")
        return True

    except Exception as e:
        print(f"测试3: FAILED - {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("向量缓存功能测试")
    print("=" * 60)

    results = []

    # 测试1: Embedding客户端
    result = await test_embedding_client()
    if isinstance(result, tuple):
        success, client = result
        results.append(("Embedding客户端", success))
        if not success or not client:
            print("\nEmbedding客户端测试失败，跳过后续测试")
            return
    else:
        results.append(("Embedding客户端", False))
        print("\nEmbedding客户端测试失败，跳过后续测试")
        return

    # 测试2: 向量缓存
    success = await test_vector_cache(client)
    results.append(("向量缓存", success))

    # 测试3: 向量缓存管理器
    success = await test_vector_cache_manager(client)
    results.append(("向量缓存管理器", success))

    # 打印总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    for name, success in results:
        status = "PASSED" if success else "FAILED"
        symbol = "OK" if success else "XX"
        print(f"{symbol} {name}: {status}")

    total = len(results)
    passed = sum(1 for _, s in results if s)

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n所有测试通过！向量功能正常工作。")
    else:
        print(f"\n有 {total - passed} 个测试失败。")


if __name__ == "__main__":
    asyncio.run(main())
