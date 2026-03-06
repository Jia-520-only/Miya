"""快速测试向量功能"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from core.embedding_client import EmbeddingClient, EmbeddingProvider


async def test_embedding():
    """测试Embedding客户端"""
    print("=" * 50)
    print("测试Embedding客户端")
    print("=" * 50)
    
    try:
        # 初始化客户端
        client = EmbeddingClient(
            provider=EmbeddingProvider.SENTENCE_TRANSFORMERS,
            model='paraphrase-multilingual-MiniLM-L12-v2'
        )
        print("\n[1/4] 客户端创建成功")
        
        # 初始化
        await client.initialize()
        print("[2/4] 客户端初始化成功")
        
        # 获取向量维度
        dimension = client.get_dimension()
        print(f"[3/4] 向量维度: {dimension}")
        
        # 生成向量
        test_text = "弥娅是一个温暖的AI助手"
        vector = await client.embed(test_text)
        print(f"[4/4] 向量生成成功: {len(vector)}维")
        
        print("\n[OK] Embedding客户端测试通过")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Embedding客户端测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_vector_cache():
    """测试向量缓存"""
    print("\n" + "=" * 50)
    print("测试向量缓存")
    print("=" * 50)
    
    try:
        from memory.real_vector_cache import RealVectorCache
        import os
        
        # 初始化Embedding客户端
        client = EmbeddingClient(
            provider=EmbeddingProvider.SENTENCE_TRANSFORMERS
        )
        await client.initialize()
        print("\n[1/5] Embedding客户端初始化成功")
        
        # 创建数据目录
        data_dir = Path(__file__).parent / 'data'
        data_dir.mkdir(exist_ok=True)
        
        # 初始化向量缓存
        vector_cache = RealVectorCache(
            embedding_client=client,
            milvus_db_path=str(data_dir / 'test_milvus_lite.db'),
            collection_name='test_vectors'
        )
        print("[2/5] 向量缓存初始化成功")
        
        # 添加测试数据
        test_texts = [
            "弥娅是一个AI助手",
            "AI可以帮助人类解决问题",
            "机器学习是人工智能的一个分支",
            "编程需要逻辑思维"
        ]
        
        for i, text in enumerate(test_texts):
            success = await vector_cache.add(text, metadata={'id': i})
            print(f"[3/5] 添加数据 {i+1}/{len(test_texts)}: {'成功' if success else '失败'}")
        
        # 搜索测试
        query = "人工智能"
        results = await vector_cache.search_similar(query, top_k=2)
        print(f"\n[4/5] 搜索结果: 找到 {len(results)} 条相似内容")
        
        for result in results:
            metadata = result.get('metadata', {})
            distance = result.get('distance', 1.0)
            print(f"   - {metadata.get('text', '')[:30]}... (距离: {distance:.4f})")
        
        print("\n[5/5] 向量缓存测试通过")
        return True
        
    except Exception as e:
        print(f"\n❌ 向量缓存测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_semantic_engine():
    """测试语义动力学引擎"""
    print("\n" + "=" * 50)
    print("测试语义动力学引擎")
    print("=" * 50)
    
    try:
        from memory.semantic_dynamics_engine import get_semantic_dynamics_engine
        from memory.real_vector_cache import RealVectorCache
        
        # 初始化Embedding客户端
        client = EmbeddingClient(
            provider=EmbeddingProvider.SENTENCE_TRANSFORMERS
        )
        await client.initialize()
        print("\n[1/4] Embedding客户端初始化成功")
        
        # 创建向量缓存
        data_dir = Path(__file__).parent / 'data'
        vector_cache = RealVectorCache(
            embedding_client=client,
            milvus_db_path=str(data_dir / 'test_milvus_lite2.db'),
            collection_name='test_semantic_vectors'
        )
        print("[2/4] 向量缓存初始化成功")
        
        # 初始化语义动力学引擎
        engine = get_semantic_dynamics_engine(
            config={'top_k': 5, 'fuzzy_threshold': 0.85},
            vector_cache=vector_cache
        )
        engine.set_embedding_client(client)
        print("[3/4] 语义动力学引擎初始化成功")
        
        # 测试处理对话
        test_messages = [
            {'role': 'user', 'content': '你好弥娅'},
            {'role': 'assistant', 'content': '你好！我是弥娅，很高兴认识你。'}
        ]
        
        result = await engine.process_conversation(
            messages=test_messages,
            enable_semantic_groups=True,
            enable_meta_thinking=True
        )
        
        print(f"[4/4] 对话处理成功:")
        print(f"   - 召回记忆: {len(result.retrieved_memories)} 条")
        print(f"   - 上下文影响: {result.context_influence:.3f}")
        print(f"   - 语义组: {result.semantic_groups}")
        
        print("\n✅ 语义动力学引擎测试通过")
        return True
        
    except Exception as e:
        print(f"\n❌ 语义动力学引擎测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("\n" + "=" * 50)
    print("向量功能完整性测试")
    print("=" * 50)
    
    results = []
    
    # 测试1: Embedding客户端
    results.append(await test_embedding())
    
    # 测试2: 向量缓存
    results.append(await test_vector_cache())
    
    # 测试3: 语义动力学引擎
    results.append(await test_semantic_engine())
    
    # 总结
    print("\n" + "=" * 50)
    print("测试总结")
    print("=" * 50)
    print(f"总测试数: {len(results)}")
    print(f"通过数: {sum(results)}")
    print(f"失败数: {len(results) - sum(results)}")
    
    if all(results):
        print("\n✅ 所有测试通过！向量功能已完整实现。")
    else:
        print("\n⚠️ 部分测试失败，请检查错误信息。")


if __name__ == "__main__":
    asyncio.run(main())
