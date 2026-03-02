"""
TRPG 跑团系统测试脚本
"""

import asyncio
import sys
import io

# 设置输出编码为 UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from webnet.tools.base import ToolContext
from webnet.ToolNet.registry import ToolRegistry


class MockOneBotClient:
    """模拟 OneBot 客户端"""

    async def send_group_message(self, group_id: int, message: str):
        print(f"[群消息] 群 {group_id}: {message}")

    async def send_private_message(self, user_id: int, message: str):
        print(f"[私聊] 用户 {user_id}: {message}")


def create_context(user_id: int = 123456, group_id: int = 987654321):
    """创建测试上下文"""
    context = ToolContext(
        onebot_client=MockOneBotClient(),
        user_id=user_id,
        group_id=group_id,
        message_type="group",
        sender_name="测试用户"
    )
    return context


async def test_trpg_system():
    """测试 TRPG 系统"""

    print("=" * 60)
    print("弥娅 TRPG 跑团系统测试")
    print("=" * 60)
    print()

    # 初始化工具注册表
    registry = ToolRegistry()
    registry.load_all_tools()

    # 获取 TRPG 工具
    start_trpg = registry.get_tool('start_trpg')
    roll_dice = registry.get_tool('roll_dice')
    roll_secret = registry.get_tool('roll_secret')
    create_pc = registry.get_tool('create_pc')
    show_pc = registry.get_tool('show_pc')

    context = create_context()

    # 测试 1: 启动跑团模式
    print("=" * 60)
    print("测试 1: 启动跑团模式")
    print("=" * 60)
    result = await registry.execute_tool(
        'start_trpg',
        {'rule_system': 'coc7', 'session_name': '迷雾图书馆'},
        context
    )
    print(result)
    print()

    # 测试 2: 创建角色卡
    print("=" * 60)
    print("测试 2: 创建角色卡")
    print("=" * 60)
    result = await registry.execute_tool(
        'create_pc',
        {'name': '亚瑟', 'rule_system': 'coc7', 'use_random': True},
        context
    )
    print(result)
    print()

    # 测试 3: 查看角色卡
    print("=" * 60)
    print("测试 3: 查看角色卡")
    print("=" * 60)
    result = await registry.execute_tool(
        'show_pc',
        {},
        context
    )
    print(result)
    print()

    # 测试 4: 投骰
    print("=" * 60)
    print("测试 4: 投骰")
    print("=" * 60)
    result = await registry.execute_tool(
        'roll_dice',
        {'expression': '3d6', 'reason': '力量检定'},
        context
    )
    print(result)
    print()

    result = await registry.execute_tool(
        'roll_dice',
        {'expression': '1d100', 'reason': '侦查检定'},
        context
    )
    print(result)
    print()

    # 测试 5: 暗骰
    print("=" * 60)
    print("测试 5: 暗骰")
    print("=" * 60)
    result = await registry.execute_tool(
        'roll_secret',
        {'expression': '1d100', 'reason': '潜行检定'},
        context
    )
    print(result)
    print()

    # 测试 6: D&D 5E 规则
    print("=" * 60)
    print("测试 6: D&D 5E 规则系统")
    print("=" * 60)
    from webnet.EntertainmentNet.trpg.rules.dnd5e import DND5ERules

    # 测试属性修正
    modifier = DND5ERules.get_modifier(18)
    print(f"力量 18 的修正值: {modifier}")

    # 测试属性检定
    result = DND5ERules.ability_check(18, advantage=1)
    print(f"力量检定（优势）: {result}")

    # 测试伤害检定
    damage = DND5ERules.damage_roll('2d6', 4, critical=False)
    print(f"伤害检定 2d6+4: {damage}")
    print()

    # 测试 7: COC 7 规则
    print("=" * 60)
    print("测试 7: COC 7 规则系统")
    print("=" * 60)
    from webnet.EntertainmentNet.trpg.rules.coc7 import COC7Rules

    # 测试检定
    result = COC7Rules.check(42, 70)
    print(f"投骰 42 / 技能值 70: {result}")

    # 测试衍生属性
    derived = COC7Rules.calculate_derived_attrs(60, 65, 50, 70)
    print(f"衍生属性计算: {derived}")
    print()

    # 测试 8: 骰子系统
    print("=" * 60)
    print("测试 8: 骰子系统")
    print("=" * 60)
    from webnet.EntertainmentNet.trpg.dice import DiceEngine

    dice = DiceEngine()
    tests = ['d100', '3d6', '2d10+5', '4d6-2', '1d20', '2d8+3']

    for expr in tests:
        result = dice.roll(expr)
        print(f"{expr:12s}: {result.detail:20s} = {result.total}")
    print()

    print("=" * 60)
    print("测试完成！")
    print("=" * 60)


async def test_dice_only():
    """仅测试骰子系统（快速测试）"""

    print("=" * 60)
    print("骰子系统快速测试")
    print("=" * 60)

    from webnet.EntertainmentNet.trpg.dice import DiceEngine

    dice = DiceEngine()

    # 常用骰子表达式
    tests = [
        ('d100', '百面骰'),
        ('d20', '二十面骰'),
        ('3d6', '三个六面骰'),
        ('2d10+5', '两个十面骰加5'),
        ('4d6-2', '四个六面骰减2'),
        ('1d8+3', '一个八面骰加3'),
    ]

    for expr, desc in tests:
        result = dice.roll(expr)
        print(f"{desc:15s}: {expr:12s} → {result.detail:20s} = **{result.total}**")

    print()
    print("骰子系统测试完成！")


if __name__ == "__main__":
    import sys

    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] == '--dice-only':
        asyncio.run(test_dice_only())
    else:
        asyncio.run(test_trpg_system())
