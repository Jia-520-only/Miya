"""
测试核心模块导入
用于验证依赖是否正确安装
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("[Test] Testing core module imports...")

try:
    # 测试核心模块
    from core import Personality, Ethics, Identity, Arbitrator, Entropy
    print("[OK] Core module imports successful")
except Exception as e:
    print(f"[ERROR] Failed to import core modules: {e}")
    sys.exit(1)

try:
    # 测试中枢模块
    from hub import MemoryEmotion, MemoryEngine, Emotion, Decision, Scheduler
    print("[OK] Hub module imports successful")
except Exception as e:
    print(f"[ERROR] Failed to import hub modules: {e}")
    sys.exit(1)

try:
    # 测试存储模块
    from storage import RedisAsyncClient, MilvusClient, Neo4jClient
    print("[OK] Storage module imports successful")
except Exception as e:
    print(f"[ERROR] Failed to import storage modules: {e}")
    sys.exit(1)

try:
    # 测试网络模块
    from webnet import NetManager, CrossNetEngine
    print("[OK] Webnet module imports successful")
except Exception as e:
    print(f"[ERROR] Failed to import webnet modules: {e}")
    sys.exit(1)

try:
    # 测试M-Link模块
    from mlink import MLinkCore, Message, Router
    print("[OK] M-Link module imports successful")
except Exception as e:
    print(f"[ERROR] Failed to import mlink modules: {e}")
    sys.exit(1)

try:
    # 测试感知模块
    from perceive import PerceptualRing, AttentionGate
    print("[OK] Perceive module imports successful")
except Exception as e:
    print(f"[ERROR] Failed to import perceive modules: {e}")
    sys.exit(1)

print("\n[SUCCESS] All imports passed!")
print("[Info] Ready to start main program...")
sys.exit(0)
