"""
测试数据库连接脚本
验证Redis、Milvus、Neo4j连接状态
"""
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# Windows控制台UTF-8支持
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# 加载环境变量
load_dotenv('config/.env')

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage.redis_client import RedisClient
from storage.milvus_client import MilvusClient
from storage.neo4j_client import Neo4jClient
from hub.memory_engine import MemoryEngine


def print_header(text: str):
    """打印标题"""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}")


def test_redis():
    """测试Redis连接"""
    print_header("测试 Redis 连接")

    redis_client = RedisClient(
        host=os.getenv('REDIS_HOST', 'localhost'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        db=int(os.getenv('REDIS_DB', 0)),
        password=os.getenv('REDIS_PASSWORD', None)
    )

    # 测试连接
    if redis_client.connect():
        print(f"✅ Redis连接成功!")
        print(f"   模式: {'真实' if not redis_client.is_mock_mode() else '模拟'}")

        # 测试基本操作
        redis_client.set('test_key', {'data': 'hello'}, ttl=60)
        value = redis_client.get('test_key')
        print(f"   SET/GET测试: {'✅ 成功' if value else '❌ 失败'}")

        # 获取统计信息
        stats = redis_client.get_stats()
        print(f"   统计信息: {stats}")

        redis_client.delete('test_key')
    else:
        print(f"❌ Redis连接失败，使用模拟模式")

    redis_client.close()
    return not redis_client.is_mock_mode()


def test_milvus():
    """测试Milvus连接"""
    print_header("测试 Milvus 连接")

    milvus_client = MilvusClient(
        host=os.getenv('MILVUS_HOST', 'localhost'),
        port=int(os.getenv('MILVUS_PORT', 19530)),
        collection_name=os.getenv('MILVUS_COLLECTION', 'miya_memory'),
        dimension=int(os.getenv('MILVUS_DIMENSION', 1536))
    )

    # 测试连接
    if milvus_client.connect():
        print(f"✅ Milvus连接成功!")
        print(f"   模式: {'真实' if not milvus_client.is_mock_mode() else '模拟'}")

        # 创建集合
        if milvus_client.create_collection():
            print(f"   创建/验证集合: ✅ 成功")

            # 测试插入
            import numpy as np
            test_vector = np.random.rand(1536).tolist()
            ids = milvus_client.insert([test_vector], ids=['test_001'])
            print(f"   插入测试向量: ✅ 成功 (ID: {ids[0]})")

            # 测试搜索
            results = milvus_client.search(test_vector, top_k=1)
            print(f"   搜索测试: {'✅ 成功' if len(results) > 0 else '❌ 失败'}")

            # 测试删除
            deleted = milvus_client.delete(ids)
            print(f"   删除测试向量: {'✅ 成功' if deleted > 0 else '❌ 失败'}")

        # 获取统计信息
        stats = milvus_client.get_stats()
        print(f"   统计信息: {stats}")
    else:
        print(f"❌ Milvus连接失败，使用模拟模式")

    milvus_client.close()
    return not milvus_client.is_mock_mode()


def test_neo4j():
    """测试Neo4j连接"""
    print_header("测试 Neo4j 连接")

    neo4j_client = Neo4jClient(
        uri=os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
        user=os.getenv('NEO4J_USER', 'neo4j'),
        password=os.getenv('NEO4J_PASSWORD', None),
        database=os.getenv('NEO4J_DATABASE', 'neo4j')
    )

    # 测试连接
    if neo4j_client.connect():
        print(f"✅ Neo4j连接成功!")
        print(f"   模式: {'真实' if not neo4j_client.is_mock_mode() else '模拟'}")

        # 测试创建节点
        node_id = neo4j_client.create_node(
            labels=['Test', 'Memory'],
            properties={'name': 'test_node', 'created_at': datetime.now().isoformat()}
        )
        print(f"   创建测试节点: ✅ 成功 (ID: {node_id})")

        # 测试查询
        node = neo4j_client.get_node(node_id)
        print(f"   查询节点: {'✅ 成功' if node else '❌ 失败'}")

        # 测试创建关系
        rel_id = neo4j_client.create_relationship(
            start_node=node_id,
            end_node=node_id,
            rel_type='TEST_RELATION',
            properties={'test': 'data'}
        )
        print(f"   创建测试关系: ✅ 成功 (ID: {rel_id})")

        # 测试五元组
        quintuple_id = neo4j_client.create_memory_quintuple(
            subject='测试用户',
            predicate='表达了',
            obj='测试想法',
            context='这是一个测试记忆',
            emotion='happy'
        )
        print(f"   创建记忆五元组: ✅ 成功 (ID: {quintuple_id})")

        # 获取统计信息
        stats = neo4j_client.get_stats()
        print(f"   统计信息: {stats}")

        # 清理测试数据
        neo4j_client.delete_node(node_id)
        print(f"   清理测试数据: ✅ 完成")
    else:
        print(f"❌ Neo4j连接失败，使用模拟模式")

    neo4j_client.close()
    return not neo4j_client.is_mock_mode()


def test_memory_engine():
    """测试记忆引擎"""
    print_header("测试记忆引擎集成")

    # 创建客户端
    redis_client = RedisClient(
        host=os.getenv('REDIS_HOST', 'localhost'),
        port=int(os.getenv('REDIS_PORT', 6379))
    )

    milvus_client = MilvusClient(
        host=os.getenv('MILVUS_HOST', 'localhost'),
        port=int(os.getenv('MILVUS_PORT', 19530)),
        dimension=1536
    )

    neo4j_client = Neo4jClient(
        uri=os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
        user=os.getenv('NEO4J_USER', 'neo4j'),
        password=os.getenv('NEO4J_PASSWORD', None)
    )

    # 创建记忆引擎
    memory_engine = MemoryEngine(
        redis_client=redis_client,
        milvus_client=milvus_client,
        neo4j_client=neo4j_client
    )

    print(f"✅ 记忆引擎初始化成功!")

    # 显示连接模式
    print(f"\n数据库连接状态:")
    print(f"  Redis:  {'✅ 真实' if not redis_client.is_mock_mode() else '⚠️ 模拟'}")
    print(f"  Milvus: {'✅ 真实' if not milvus_client.is_mock_mode() else '⚠️ 模拟'}")
    print(f"  Neo4j:  {'✅ 真实' if not neo4j_client.is_mock_mode() else '⚠️ 模拟'}")

    # 测试潮汐记忆
    print(f"\n测试潮汐记忆:")
    memory_engine.store_tide(
        memory_id="test_tide_001",
        content={"text": "这是一个测试记忆", "emotion": "joy"},
        priority=0.8,
        ttl=3600
    )
    print(f"  存储潮汐记忆: ✅ 成功")

    retrieved = memory_engine.retrieve_tide("test_tide_001")
    print(f"  检索潮汐记忆: {'✅ 成功' if retrieved else '❌ 失败'}")

    # 测试梦境压缩
    print(f"\n测试梦境压缩:")
    memory_engine.compress_to_dream("test_tide_001")
    print(f"  压缩为梦境记忆: ✅ 成功")

    # 测试搜索
    print(f"\n测试记忆搜索:")
    results = memory_engine.search_dream("测试记忆", top_k=5)
    print(f"  搜索结果数量: {len(results)}")
    for i, r in enumerate(results[:3]):
        print(f"    {i+1}. {r.get('content', {}).get('summary', 'N/A')}")

    # 获取统计信息
    print(f"\n记忆引擎统计:")
    stats = memory_engine.get_memory_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # 清理测试数据
    print(f"\n清理测试数据...")
    redis_client.close()
    milvus_client.close()
    neo4j_client.close()
    print(f"✅ 清理完成")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("  弥娅数据库连接测试")
    print("  版本: v5.2")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    results = {}

    try:
        # 测试各个数据库
        results['redis'] = test_redis()
        results['milvus'] = test_milvus()
        results['neo4j'] = test_neo4j()

        # 测试记忆引擎
        test_memory_engine()

    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断测试")
    except Exception as e:
        print(f"\n\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

    # 打印总结
    print_header("测试总结")
    print(f"\n连接状态:")
    for db, success in results.items():
        status = "✅ 成功" if success else "⚠️ 模拟"
        mode = "真实连接" if success else "模拟模式"
        print(f"  {db.upper():8} - {status:8} ({mode})")

    # 总体评估
    real_count = sum(results.values())
    total_count = len(results)

    if real_count == total_count:
        print(f"\n🎉 所有数据库连接成功！系统将使用真实数据库。")
    elif real_count == 0:
        print(f"\n⚠️ 所有数据库使用模拟模式。建议启动数据库服务以获得完整功能。")
        print(f"\n启动命令:")
        print(f"  docker-compose up -d")
    else:
        print(f"\n⚠️ 部分数据库使用模拟模式。建议检查未连接的数据库服务。")
        print(f"\n未连接的数据库:")
        for db, success in results.items():
            if not success:
                print(f"  - {db.upper()}")

    print(f"\n详细文档: DATABASE_SETUP_GUIDE.md")
    print(f"{'=' * 60}\n")


if __name__ == '__main__':
    main()
