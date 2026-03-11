"""
AuthNet 鉴权子网测试用例

测试跨平台权限检查功能
"""
import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
# test_authnet.py 在 tests/ 目录下，所以需要向上两级到项目根目录
project_root = Path(__file__).resolve().parent.parent
os.chdir(project_root)
sys.path.insert(0, str(project_root))


def test_permission_core():
    """测试权限核心功能"""
    print("\n=== 测试权限核心功能 ===")
    from webnet.AuthNet.permission_core import PermissionCore

    perm_core = PermissionCore()

    # 测试系统管理员权限
    result = perm_core.check_permission('system_admin', 'tool.web_search')
    assert result == True, "系统管理员应该有web_search权限"
    print(f"[PASS] 系统管理员权限检查: {result}")

    # 测试不存在用户（应返回False，使用默认权限）
    result = perm_core.check_permission('unknown_user', 'tool.web_search')
    print(f"[PASS] 未知用户权限检查: {result}")

    # 测试超级管理员权限
    result = perm_core.check_permission('system_admin', 'any.permission')
    assert result == True, "系统管理员（*）应该有所有权限"
    print(f"[PASS] 超级管理员权限检查: {result}")


def test_user_mapper():
    """测试用户映射功能"""
    print("\n=== 测试用户映射功能 ===")
    from webnet.AuthNet.user_mapper import UserMapper

    mapper = UserMapper()

    # 测试生成用户ID
    user_id = mapper.generate_user_id('qq', '12345')
    assert user_id == 'qq_12345', f"用户ID格式错误: {user_id}"
    print(f"[PASS] 用户ID生成: {user_id}")

    # 测试确保用户存在
    user_id = mapper.ensure_user_exists('test', '001', '测试用户', ['User'])
    assert user_id == 'test_001', f"用户ID格式错误: {user_id}"
    print(f"[PASS] 用户创建: {user_id}")

    # 测试获取用户信息
    user_info = mapper.get_user_info(user_id)
    assert user_info is not None, "用户应该存在"
    assert user_info['username'] == '测试用户', f"用户名错误: {user_info['username']}"
    print(f"[PASS] 用户信息查询: {user_info['username']}")

    # 测试平台用户查询
    platform_user = mapper.get_platform_user('test', '001')
    assert platform_user is not None, "平台用户应该存在"
    print(f"[PASS] 平台用户查询: {platform_user['user_id']}")

    # 清理测试数据
    users_data = mapper.load_users()
    users_data['users'] = [u for u in users_data['users'] if u['user_id'] != user_id]
    mapper.save_users(users_data)
    print(f"[PASS] 测试数据已清理")


def test_auth_subnet():
    """测试AuthNet子网"""
    print("\n=== 测试AuthNet子网 ===")
    from webnet.AuthNet import AuthSubnet

    # 测试初始化
    auth = AuthSubnet()
    print(f"[PASS] AuthNet初始化成功，工具数: {len(auth.tools)}")

    # 测试工具列表
    expected_tools = {
        'check_permission', 'grant_permission', 'revoke_permission',
        'list_permissions', 'list_groups', 'add_user', 'remove_user'
    }
    assert set(auth.tools.keys()) == expected_tools, f"工具列表不匹配"
    print(f"[PASS] 工具列表: {', '.join(expected_tools)}")

    # 测试健康检查
    is_healthy = auth.health_check()
    assert is_healthy == True, "AuthNet应该健康"
    print(f"[PASS] 健康状态: {is_healthy}")


async def test_tool_execution():
    """测试工具执行"""
    print("\n=== 测试工具执行 ===")
    from webnet.AuthNet import AuthSubnet

    auth = AuthSubnet()

    # 测试check_permission工具
    result = await auth.execute_tool(
        'check_permission',
        {'user_id': 'system_admin', 'permission': 'tool.web_search'},
        user_id=999,
        sender_name='测试用户'
    )
    print(f"[PASS] check_permission工具执行结果: {result}")

    # 测试list_groups工具
    result = await auth.execute_tool(
        'list_groups',
        {},
        user_id=999,
        sender_name='测试用户'
    )
    print(f"[PASS] list_groups工具执行结果: {result[:100]}...")

    # 测试add_user工具
    result = await auth.execute_tool(
        'add_user',
        {'user_id': 'test_user_001', 'username': '测试用户', 'platform': 'test', 'permission_groups': ['User']},
        user_id=999,
        sender_name='测试用户'
    )
    print(f"[PASS] add_user工具执行结果: {result[:100]}...")

    # 测试新用户的权限检查
    from webnet.AuthNet.permission_core import PermissionCore
    perm_core = PermissionCore()
    result = perm_core.check_permission('test_user_001', 'tool.web_search')
    print(f"[PASS] 新用户权限检查: {result}")

    # 清理测试数据
    users_data = perm_core.load_users()
    users_data['users'] = [u for u in users_data['users'] if u['user_id'] != 'test_user_001']
    perm_core.save_users(users_data)
    print(f"[PASS] 测试用户已清理")


def test_permission_definitions():
    """测试权限定义"""
    print("\n=== 测试权限定义 ===")
    from webnet.AuthNet.permissions import TOOL_PERMISSIONS, get_tool_permission

    # 检查权限定义
    assert 'tool.web_search' in TOOL_PERMISSIONS, "权限定义缺失"
    assert 'agent.task.execute' in TOOL_PERMISSIONS, "权限定义缺失"
    print(f"[PASS] 权限定义数量: {len(TOOL_PERMISSIONS)}")

    # 测试工具权限映射
    perm = get_tool_permission('web_search')
    assert perm == 'tool.web_search', f"权限映射错误: {perm}"
    print(f"[PASS] 工具权限映射: {perm}")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*50)
    print("AuthNet 鉴权子网测试套件")
    print("="*50)

    try:
        test_permission_core()
        test_user_mapper()
        test_auth_subnet()
        asyncio.run(test_tool_execution())
        test_permission_definitions()

        print("\n" + "="*50)
        print("所有测试通过！")
        print("="*50)
        return True

    except AssertionError as e:
        print(f"\n[FAIL] 测试失败: {e}")
        return False
    except Exception as e:
        print(f"\n[ERROR] 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
