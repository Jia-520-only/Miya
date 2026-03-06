"""
测试 datetime 序列化修复
"""
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_datetime_serialization():
    """测试 datetime 序列化"""
    print("测试 datetime 序列化...")
    
    from core.task_planner import CustomJSONEncoder
    import json
    
    # 测试 datetime 对象
    data = {
        'now': datetime.now(),
        'string': 'test',
        'number': 42
    }
    
    try:
        result = json.dumps(data, cls=CustomJSONEncoder, ensure_ascii=False)
        print(f"  [OK] datetime 序列化成功")
        print(f"  结果: {result}")
        return True
    except Exception as e:
        print(f"  [FAIL] datetime 序列化失败: {e}")
        return False


def test_task_to_dict():
    """测试 Task.to_dict() 方法"""
    print("\n测试 Task.to_dict()...")
    
    from core.task_planner import Task, TaskStatus
    
    try:
        task = Task(
            id="test-001",
            name="测试任务",
            description="这是一个测试任务",
            priority=5
        )
        
        task_dict = task.to_dict()
        
        # 检查 datetime 字段是否被正确转换为字符串
        assert 'created_at' in task_dict
        assert isinstance(task_dict['created_at'], str)
        
        print(f"  [OK] Task.to_dict() 成功")
        print(f"  created_at: {task_dict['created_at']}")
        return True
    except Exception as e:
        print(f"  [FAIL] Task.to_dict() 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_context_with_datetime():
    """测试包含 datetime 的上下文"""
    print("\n测试包含 datetime 的上下文...")
    
    from core.task_planner import CustomJSONEncoder, TaskPlanner
    import json
    
    try:
        # 创建包含 datetime 的上下文
        context = {
            'timestamp': datetime.now(),
            'user_id': 'test-user',
            'session_id': 'test-session'
        }
        
        # 模拟 _build_decomposition_prompt 的行为
        result = json.dumps(context, ensure_ascii=False, cls=CustomJSONEncoder)
        
        print(f"  [OK] 包含 datetime 的上下文序列化成功")
        print(f"  结果: {result}")
        return True
    except Exception as e:
        print(f"  [FAIL] 包含 datetime 的上下文序列化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("datetime 序列化修复测试")
    print("=" * 60)
    
    results = []
    
    # 运行测试
    results.append(test_datetime_serialization())
    results.append(test_task_to_dict())
    results.append(test_context_with_datetime())
    
    # 总结
    print("\n" + "=" * 60)
    print("测试结果:")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"通过: {passed}/{total}")
    
    if passed == total:
        print("\n[SUCCESS] 所有测试通过！datetime 序列化修复成功！")
    else:
        print(f"\n[WARNING] {total - passed} 个测试失败")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
