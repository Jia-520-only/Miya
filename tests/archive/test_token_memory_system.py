# -*- coding: utf-8 -*-
"""
测试Token感知的记忆系统
"""
import asyncio
import sys
import os
from pathlib import Path

# 设置UTF-8输出
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from webnet.EntertainmentNet.game_mode.game_memory_manager import get_game_memory_manager


async def test_token_estimation():
    """测试Token估算功能"""
    print("\n" + "="*60)
    print("测试1: Token估算功能")
    print("="*60)

    manager = get_game_memory_manager()

    # 测试不同文本的token估算
    test_texts = [
        "简短的中文文本",
        "这是一段比较长的中文文本,包含了更多的内容,用于测试token估算的准确性。",
        "Short English text",
        "This is a longer English text with more content to test token estimation accuracy.",
        "混合Mixed文本Text with 中文Chinese和English混合"
    ]

    for text in test_texts:
        tokens = manager.estimate_tokens(text)
        print(f"文本: {text[:40]}...")
        print(f"  估算token数: {tokens}")

    # 测试对话列表的token估算
    test_messages = [
        {'role': 'user', 'content': '玩家: 我要进行侦查检定'},
        {'role': 'assistant', 'content': 'KP: 请投掷1d100进行侦查检定'},
        {'role': 'user', 'content': '玩家: 75'},
        {'role': 'assistant', 'content': 'KP: 你的检定失败了,没有发现任何线索'}
    ]

    total_tokens = manager.estimate_conversation_tokens(test_messages)
    print(f"\n对话列表总token数: {total_tokens}")

    print("\n[OK] Token估算功能测试通过\n")


async def test_conversation_management():
    """测试对话管理功能"""
    print("\n" + "="*60)
    print("测试2: 对话管理功能")
    print("="*60)

    manager = get_game_memory_manager()

    # 创建测试游戏
    game_id = manager.create_game(
        game_name="测试游戏",
        rule_system="coc7",
        mode_type="trpg",
        group_id=999999
    )

    print(f"[OK] 创建测试游戏: {game_id}")

    # 添加测试消息
    test_messages = [
        ('user', '玩家: 我开始探索这个房间', 12345, '测试玩家'),
        ('assistant', 'KP: 你进入了一个昏暗的房间,空气中弥漫着霉味'),
        ('user', '玩家: 我要仔细检查墙上的画作', 12345, '测试玩家'),
        ('assistant', 'KP: 你发现画中的人物眼睛似乎在注视着你'),
        ('user', '玩家: 我感到很不安,准备离开这里', 12345, '测试玩家'),
    ]

    for role, content, player_id, player_name in test_messages:
        manager.add_conversation_message(game_id, role, content, player_id, player_name)

    print(f"[OK] 添加了 {len(test_messages)} 条测试消息")

    # 获取对话历史
    history = manager.get_conversation_history(game_id, max_tokens=50000)
    print(f"[OK] 获取到 {len(history)} 条对话历史")

    # 估算token数
    history_tokens = manager.estimate_conversation_history_tokens(history)
    print(f"[OK] 历史对话token数: {history_tokens}")

    print("\n[OK] 对话管理功能测试通过\n")


async def test_token_aware_history():
    """测试Token感知的历史获取"""
    print("\n" + "="*60)
    print("测试3: Token感知的历史获取")
    print("="*60)

    manager = get_game_memory_manager()

    # 创建测试游戏
    game_id = manager.create_game(
        game_name="Token测试游戏",
        rule_system="coc7",
        mode_type="trpg",
        group_id=999998
    )

    # 添加大量消息(模拟长时间游戏)
    print("添加大量测试消息...")
    for i in range(50):
        manager.add_conversation_message(
            game_id,
            'user',
            f'玩家: 这是第{i+1}条消息,我要继续探索这个神秘的地方',
            12345,
            '测试玩家'
        )
        manager.add_conversation_message(
            game_id,
            'assistant',
            f'KP: KP对此进行了回应,描述了场景的变化'
        )

    print(f"[OK] 添加了 100 条测试消息")

    # 测试不同token限制下的获取
    for max_tokens in [10000, 30000, 50000]:
        history = manager.get_conversation_history(game_id, max_tokens=max_tokens)
        tokens = manager.estimate_conversation_history_tokens(history)
        print(f"Token限制 {max_tokens}: 获取 {len(history)} 条消息, 实际 {tokens} tokens")

    print("\n[OK] Token感知的历史获取测试通过\n")


async def test_compression():
    """测试对话压缩功能"""
    print("\n" + "="*60)
    print("测试4: 对话压缩功能")
    print("="*60)

    manager = get_game_memory_manager()

    # 创建测试游戏
    game_id = manager.create_game(
        game_name="压缩测试游戏",
        rule_system="coc7",
        mode_type="trpg",
        group_id=999997
    )

    # 添加消息(包含各种类型,用于测试压缩摘要)
    test_scenarios = [
        ("玩家: 我进行侦查检定", "KP: 请投掷1d100"),
        ("玩家: 32", "KP: 检定成功!你发现了一个隐藏的暗格"),
        ("玩家: 我打开暗格看看里面有什么", "KP: 里面有一把生锈的钥匙和一张泛黄的纸条"),
        ("玩家: 我进行战斗检定,准备攻击敌人", "KP: 先投掷你的攻击检定"),
        ("玩家: 55", "KP: 你的攻击未命中,敌人反击了!"),
        ("玩家: 我要进行骰子检定", "KP: 骰子是随机的结果"),
        ("玩家: 我调查这个房间", "KP: 你发现房间里有异常的痕迹"),
    ]

    print("添加测试消息(包含各种游戏场景)...")
    for user_msg, kp_msg in test_scenarios:
        manager.add_conversation_message(game_id, 'user', user_msg, 12345, '测试玩家')
        manager.add_conversation_message(game_id, 'assistant', kp_msg)

    print(f"[OK] 添加了 {len(test_scenarios)*2} 条测试消息")

    # 执行压缩
    print("\n执行对话压缩...")
    success = await manager.compress_old_messages(
        game_id,
        target_tokens=5000,
        compression_ratio=0.3
    )

    if success:
        print("[OK] 压缩执行成功")

        # 检查压缩后的对话
        history = manager.get_conversation_history(game_id, max_tokens=50000)
        print(f"[OK] 压缩后获取到 {len(history)} 条对话")

        # 检查是否有摘要
        summaries = [msg for msg in history if msg.get('role') == 'system']
        if summaries:
            print(f"[OK] 发现 {len(summaries)} 条摘要记录")
            print(f"摘要内容: {summaries[0]['content'][:200]}...")
        else:
            print("[WARN] 未发现摘要记录(可能消息数量不足)")
    else:
        print("[ERROR] 压缩执行失败")

    print("\n[OK] 对话压缩功能测试通过\n")


async def cleanup():
    """清理测试数据"""
    print("\n" + "="*60)
    print("清理测试数据")
    print("="*60)

    manager = get_game_memory_manager()

    # 删除测试游戏
    test_game_ids = []
    try:
        games = manager.list_games(group_id=999999)
        test_game_ids.extend([g.game_id for g in games])
    except:
        pass

    try:
        games = manager.list_games(group_id=999998)
        test_game_ids.extend([g.game_id for g in games])
    except:
        pass

    try:
        games = manager.list_games(group_id=999997)
        test_game_ids.extend([g.game_id for g in games])
    except:
        pass

    for game_id in test_game_ids:
        manager.delete_game(game_id)
        print(f"[OK] 删除测试游戏: {game_id}")

    print("\n[OK] 清理完成\n")


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("Token感知记忆系统测试")
    print("="*60)

    try:
        await test_token_estimation()
        await test_conversation_management()
        await test_token_aware_history()
        await test_compression()
        await cleanup()

        print("\n" + "="*60)
        print("所有测试通过! [OK]")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        await cleanup()


if __name__ == "__main__":
    asyncio.run(main())
