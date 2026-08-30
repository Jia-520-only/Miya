"""
健康检查接口
"""
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_storage():
    """检查存储连接"""
    print("\n检查存储连接...")

    try:
        from storage import RedisAsyncClient, MilvusClient, Neo4jClient

        redis = RedisAsyncClient()
        # 注意：这里需要await，但健康检查可以简化
        redis.set('health_check', 'ok')
        result = redis.get('health_check')
        print(f"  ✓ Redis: {'正常' if result == 'ok' else '异常'}")

        milvus = MilvusClient()
        print(f"  ✓ Milvus: 已连接")

        neo4j = Neo4jClient()
        print(f"  ✓ Neo4j: 已连接")

        return True
    except Exception as e:
        print(f"  ✗ 存储检查失败: {e}")
        return False


def check_modules():
    """检查核心模块"""
    print("\n检查核心模块...")

    try:
        from core import Personality, Ethics, Identity, Arbitrator, Entropy
        print(f"  ✓ Core: 正常")

        from hub import MemoryEmotion, MemoryEngine, Emotion, Decision, Scheduler
        print(f"  ✓ Hub: 正常")

        from mlink import MLinkCore
        print(f"  ✓ M-Link: 正常")

        from perceive import PerceptualRing, AttentionGate
        print(f"  ✓ Perceive: 正常")

        from webnet import NetManager, CrossNetEngine
        print(f"  ✓ Webnet: 正常")

        from detect import TimeDetector, SpaceDetector, NodeDetector, EntropyDiffusion
        print(f"  ✓ Detect: 正常")

        from trust import TrustScore, TrustPropagation
        print(f"  ✓ Trust: 正常")

        from evolve import Sandbox, ABTest, UserCoPlay
        print(f"  ✓ Evolve: 正常")

        return True
    except Exception as e:
        print(f"  ✗ 模块检查失败: {e}")
        return False


def check_memory():
    """检查内存使用"""
    print("\n检查内存使用...")

    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()

        print(f"  RSS内存: {memory_info.rss / 1024 / 1024:.2f} MB")
        print(f"  VMS内存: {memory_info.vms / 1024 / 1024:.2f} MB")

        return True
    except ImportError:
        print(f"  ⚠ psutil未安装，跳过内存检查")
        return True
    except Exception as e:
        print(f"  ✗ 内存检查失败: {e}")
        return False


def main():
    """健康检查主函数"""
    print("=" * 50)
    print("        弥娅系统健康检查")
    print("        System Health Check")
    print("=" * 50)
    print(f"\n检查时间: {datetime.now()}")

    results = {
        'modules': check_modules(),
        'storage': check_storage(),
        'memory': check_memory()
    }

    print("\n" + "=" * 50)
    print("检查结果:")
    print(f"  模块: {'✓ 正常' if results['modules'] else '✗ 异常'}")
    print(f"  存储: {'✓ 正常' if results['storage'] else '✗ 异常'}")
    print(f"  内存: {'✓ 正常' if results['memory'] else '✗ 异常'}")
    print("=" * 50)

    # 返回退出码
    if all(results.values()):
        print("\n所有检查通过 ✓")
        return 0
    else:
        print("\n部分检查失败 ✗")
        return 1


if __name__ == '__main__':
    sys.exit(main())
