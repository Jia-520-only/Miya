"""
测试查询系统
"""
import asyncio
import sys
import logging

# 添加项目根目录到路径
sys.path.insert(0, 'd:/AI_MIYA_Facyory/MIYA/Miya')

logging.basicConfig(level=logging.DEBUG)


async def test_query_systems():
    """测试查询系统"""
    print("=" * 60)
    print("测试查询系统")
    print("=" * 60)

    # 测试酒馆查询系统
    print("\n1. 测试酒馆查询系统...")
    try:
        from webnet.EntertainmentNet.query.tavern_query_system import TavernQuerySystem
        tavern_system = TavernQuerySystem()
        print(f"   ✓ 酒馆查询系统初始化成功")
        print(f"   - 角色数量: {len(tavern_system.characters)}")
        print(f"   - 会话数量: {len(tavern_system.memory_data.get('sessions', {}))}")

        # 测试搜索
        results = await tavern_system.search_characters("温柔", limit=3)
        print(f"   ✓ 搜索'温柔'找到 {len(results)} 个角色")
        for r in results[:2]:
            print(f"     - {r['character_data']['name']} (分数: {r['score']:.2f})")
    except Exception as e:
        print(f"   ✗ 酒馆查询系统失败: {e}")
        import traceback
        traceback.print_exc()

    # 测试跑团查询系统
    print("\n2. 测试跑团查询系统...")
    try:
        from webnet.EntertainmentNet.query.trpg_query_system import TRPGQuerySystem
        trpg_system = TRPGQuerySystem()
        print(f"   ✓ 跑团查询系统初始化成功")
        print(f"   - 角色卡数量: {len(trpg_system.characters)}")
        print(f"   - 会话数量: {len(trpg_system.sessions_data.get('sessions', {}))}")

        # 测试搜索
        results = await trpg_system.search_characters("亚瑟", limit=3)
        print(f"   ✓ 搜索'亚瑟'找到 {len(results)} 个角色卡")
        for r in results[:2]:
            print(f"     - {r['character_data']['character_name']} (分数: {r['score']:.2f})")
    except Exception as e:
        print(f"   ✗ 跑团查询系统失败: {e}")
        import traceback
        traceback.print_exc()

    # 测试工具注册
    print("\n3. 测试工具注册...")
    try:
        from webnet.EntertainmentNet.query.tools.search_tavern_stories import (
            SearchTavernStories,
            SearchTavernCharacters,
            SearchTavernPreferences
        )
        from webnet.EntertainmentNet.query.tools.search_trpg_characters import (
            SearchTRPGCharacters,
            SearchTRPGByAttribute,
            SearchTRPGBySkill
        )

        print(f"   ✓ 成功导入酒馆工具类")
        print(f"   ✓ 成功导入跑团工具类")

        # 测试创建工具实例
        tools = []
        tools.append(SearchTavernStories())
        print(f"   ✓ SearchTavernStories 初始化成功")

        tools.append(SearchTavernCharacters())
        print(f"   ✓ SearchTavernCharacters 初始化成功")

        tools.append(SearchTavernPreferences())
        print(f"   ✓ SearchTavernPreferences 初始化成功")

        tools.append(SearchTRPGCharacters())
        print(f"   ✓ SearchTRPGCharacters 初始化成功")

        tools.append(SearchTRPGByAttribute())
        print(f"   ✓ SearchTRPGByAttribute 初始化成功")

        tools.append(SearchTRPGBySkill())
        print(f"   ✓ SearchTRPGBySkill 初始化成功")

        print(f"\n   总共 {len(tools)} 个工具全部初始化成功！")

    except Exception as e:
        print(f"   ✗ 工具注册失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_query_systems())
