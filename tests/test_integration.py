#!/usr/bin/env python3
"""
弥娅整合测试脚本
验证所有模块是否正常工作
"""

import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

print("=" * 60)
print("     弥娅整合测试")
print("=" * 60)
print()

# 测试结果
results = {}

async def test_imports():
    """测试核心模块导入"""
    print("[1/7] 测试核心模块导入...")
    
    try:
        # 核心层
        from core.personality import Personality
        from core.identity import Identity
        from core.ethics import Ethics
        from core.arbitrator import Arbitrator
        from core.entropy import EntropyMonitor
        print("  ✓ 核心层导入成功")
        
        # 中枢层
        from hub.memory_engine import MemoryEngine
        from hub.emotion import EmotionManager
        from hub.decision import DecisionEngine
        from hub.scheduler import TaskScheduler
        print("  ✓ 中枢层导入成功")
        
        # 传输层
        from mlink.mlink_core import MLinkCore
        from mlink.message import Message, MessageType
        from mlink.router import Router
        print("  ✓ 传输层导入成功")
        
        # 子网层
        from webnet.qq import QQNet
        from webnet.pc_ui import PCUINet
        print("  ✓ 子网层导入成功")
        
        # 感知层
        from perceive.perceptual_ring import PerceptualRing
        from perceive.attention_gate import AttentionGate
        print("  ✓ 感知层导入成功")
        
        # 检测层
        from detect.time_detector import TimeDetector
        from detect.space_detector import SpaceDetector
        from detect.node_detector import NodeDetector
        from detect.entropy_diffusion import EntropyDiffusion
        print("  ✓ 检测层导入成功")
        
        # 信任系统
        from trust.trust_score import TrustScoreManager
        from trust.trust_propagation import TrustPropagation
        print("  ✓ 信任系统导入成功")
        
        # 存储层
        from storage.redis_client import RedisClient
        from storage.milvus_client import MilvusClient
        from storage.neo4j_client import Neo4jClient
        print("  ✓ 存储层导入成功")
        
        results['imports'] = True
        return True
        
    except Exception as e:
        print(f"  ✗ 导入失败: {e}")
        results['imports'] = False
        return False

async def test_pc_ui():
    """测试PC端模块"""
    print("\n[2/7] 测试PC端模块...")
    
    try:
        from webnet.pc_ui import PCUINet
        from hub.memory_engine import MemoryEngine
        from hub.emotion import EmotionManager
        from mlink.mlink_core import MLinkCore
        
        # 创建实例（不初始化，仅测试导入）
        print("  ✓ PCUINet导入成功")
        print("  ✓ PC端模块测试通过")
        
        results['pc_ui'] = True
        return True
        
    except Exception as e:
        print(f"  ✗ PC端模块测试失败: {e}")
        results['pc_ui'] = False
        return False

def test_files():
    """测试关键文件是否存在"""
    print("\n[3/7] 测试关键文件...")
    
    files_to_check = [
        "config/.env",
        "config/settings.py",
        "core/personality.py",
        "core/identity.py",
        "hub/memory_engine.py",
        "hub/emotion.py",
        "mlink/mlink_core.py",
        "mlink/message.py",
        "webnet/pc_ui.py",
        "webnet/qq.py",
        "pc_ui/main.py",
        "pc_ui/frontend/index.html",
        "pc_ui/frontend/app.js",
        "run/pc_start.bat",
        "run/pc_start.sh",
        "requirements.txt",
        "README.md",
        "ALL_PROJECTS_INTEGRATION.md",
    ]
    
    missing_files = []
    for file_path in files_to_check:
        if not (PROJECT_ROOT / file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"  ✗ 缺少文件: {len(missing_files)}个")
        for file in missing_files:
            print(f"    - {file}")
        results['files'] = False
        return False
    else:
        print(f"  ✓ 所有关键文件存在 ({len(files_to_check)}个)")
        results['files'] = True
        return True

def test_configuration():
    """测试配置文件"""
    print("\n[4/7] 测试配置文件...")
    
    try:
        from config.settings import settings
        print("  ✓ 配置加载成功")
        
        # 检查关键配置项
        required_keys = [
            'DEBUG', 'LOG_LEVEL',
            'REDIS_HOST', 'REDIS_PORT',
            'MILVUS_HOST', 'MILVUS_PORT',
            'NEO4J_URI',
            'PERSONALITY_WARMTH',
        ]
        
        missing_keys = []
        for key in required_keys:
            if not hasattr(settings, key):
                missing_keys.append(key)
        
        if missing_keys:
            print(f"  ✗ 缺少配置项: {missing_keys}")
            results['config'] = False
            return False
        else:
            print(f"  ✓ 所有关键配置项存在")
            results['config'] = True
            return True
            
    except Exception as e:
        print(f"  ✗ 配置测试失败: {e}")
        results['config'] = False
        return False

async def test_message_flow():
    """测试消息流"""
    print("\n[5/7] 测试消息流...")
    
    try:
        from mlink.message import Message, MessageType, FlowType
        
        # 创建测试消息
        message = Message(
            type=MessageType.CONTROL,
            source="test",
            target="hub",
            content={"action": "test"},
            flow_type=FlowType.CONTROL
        )
        
        print("  ✓ 消息创建成功")
        print(f"    - 类型: {message.type}")
        print(f"    - 来源: {message.source}")
        print(f"    - 目标: {message.target}")
        
        results['message_flow'] = True
        return True
        
    except Exception as e:
        print(f"  ✗ 消息流测试失败: {e}")
        results['message_flow'] = False
        return False

def test_dependencies():
    """测试依赖包"""
    print("\n[6/7] 测试关键依赖包...")
    
    required_packages = [
        'fastapi',
        'uvicorn',
        'websockets',
        'redis',
        'numpy',
        'httpx',
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"  ✗ 缺少依赖包: {missing_packages}")
        results['dependencies'] = False
        return False
    else:
        print(f"  ✓ 所有关键依赖包已安装")
        results['dependencies'] = True
        return True

async def test_pc_ui_api():
    """测试PC端API结构"""
    print("\n[7/7] 测试PC端API结构...")
    
    try:
        from pc_ui.main import MiyaPCApp
        
        print("  ✓ MiyaPCApp导入成功")
        print("  ✓ PC端API结构正常")
        
        results['pc_api'] = True
        return True
        
    except Exception as e:
        print(f"  ✗ PC端API测试失败: {e}")
        results['pc_api'] = False
        return False

async def main():
    """运行所有测试"""
    print()
    print("开始整合测试...\n")
    
    # 运行测试
    await test_imports()
    await test_pc_ui()
    test_files()
    test_configuration()
    await test_message_flow()
    test_dependencies()
    await test_pc_ui_api()
    
    # 统计结果
    print("\n" + "=" * 60)
    print("     测试结果")
    print("=" * 60)
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed
    
    for test, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {test.ljust(20)} {status}")
    
    print()
    print(f"总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！弥娅整合成功！")
        return 0
    else:
        print(f"\n⚠️  {failed}个测试失败，请检查错误信息")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
