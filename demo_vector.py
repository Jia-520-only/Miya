"""
向量系统演示脚本
无需API Key，使用本地Sentence Transformers模型
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))


async def main():
    print("\n" + "=" * 60)
    print("弥娅 - 向量系统演示")
    print("=" * 60)

    try:
        from core.embedding_client import EmbeddingClient, EmbeddingProvider
        from memory.real_vector_cache import VectorCacheManager

        # 使用本地模型（无需API Key）
        print("\n初始化本地Sentence Transformers模型...")
        print("(首次运行会下载模型文件，约400MB)")

        client = EmbeddingClient(
            provider=EmbeddingProvider.SENTENCE_TRANSFORMERS,
            model="paraphrase-multilingual-MiniLM-L12-v2"
        )
        await client.initialize()

        print(f"模型加载完成！")
        print(f"向量维度: {client.get_dimension()}")

        # 创建向量缓存
        print("\n创建向量缓存（Milvus Lite）...")
        vector_cache = VectorCacheManager(
            embedding_client=client,
            milvus_db_path="data/demo_milvus_lite.db"
        )

        # 添加示例对话
        print("\n添加示例对话...")
        conversations = [
            ("你好，我是用户", "你好！我是弥娅，很高兴认识你。"),
            ("你会做什么？", "我可以聊天、记忆对话、回答问题等。"),
            ("今天天气怎么样？", "抱歉，我没有联网功能，无法查询天气。"),
            ("我喜欢编程", "编程很有趣！你喜欢哪种编程语言？"),
            ("Python很棒", "确实！Python是一种简洁而强大的语言。")
        ]

        for user_input, ai_response in conversations:
            await vector_cache.add_conversation(user_input, ai_response)
            print(f"  已添加: {user_input[:30]}...")

        # 获取统计信息
        stats = vector_cache.get_stats()
        print(f"\n向量缓存统计:")
        print(f"  总向量数: {stats['total_vectors']}")
        print(f"  Embedding缓存: {stats['embedding_cache']['total_vectors']} 条")
        print(f"  Query缓存: {stats['query_cache']['total_vectors']} 条")
        print(f"  Memo缓存: {stats['memo_cache']['total_vectors']} 条")

        # 测试向量相似度搜索
        print("\n" + "-" * 60)
        print("测试向量相似度搜索")
        print("-" * 60)

        queries = [
            "你好",
            "编程",
            "Python",
            "我不知道",
            "天气"
        ]

        for query in queries:
            print(f"\n查询: '{query}'")
            results = await vector_cache.search_similar(
                query=query,
                cache_type="embedding",
                top_k=3
            )

            if results:
                print(f"  找到 {len(results)} 条相似内容:")
                for i, result in enumerate(results):
                    distance = result.get('distance', 1.0)
                    similarity = 1.0 - distance
                    metadata = result.get('metadata', {})
                    text = metadata.get('text', '')[:50]
                    role = metadata.get('role', 'unknown')

                    print(f"    {i+1}. [{role}] {text}... (相似度: {similarity:.2f})")
            else:
                print("  未找到相似内容")

        # 关闭
        vector_cache.close()

        print("\n" + "=" * 60)
        print("演示完成！")
        print("=" * 60)
        print("\n向量数据已保存到: data/demo_milvus_lite.db")
        print("下次运行将自动加载已有的向量数据。")

    except Exception as e:
        print(f"\n演示失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
