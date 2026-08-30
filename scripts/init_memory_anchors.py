#!/usr/bin/env python3
"""
弥娅记忆锚点初始化脚本
用于将关于"佳"的重要信息预先存入记忆系统

运行方式: python scripts/init_memory_anchors.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def init_memory_anchors():
    print("=" * 60)
    print("弥娅记忆锚点初始化")
    print("=" * 60)
    print("\n正在初始化关于'佳'的记忆锚点...\n")

    memory_anchors = [
        {
            "fact": "佳有先天性心脏病，经历过心脏手术和射频消融手术",
            "tags": ["健康", "疾病", "重要"],
        },
        {"fact": "佳先天体弱，手时常冰凉，体力较差", "tags": ["健康", "体质"]},
        {
            "fact": "佳爱吃的菜：酸汤鱼、凉拌折耳根、牛干巴、炒螺蛳、爆炒小龙虾",
            "tags": ["喜好", "饮食", "美食"],
        },
        {"fact": "佳爱喝的：椰奶、茉莉蜜茶、草莓味香飘飘", "tags": ["喜好", "饮品"]},
        {"fact": "佳喜欢的颜色：青色、淡蓝色、黑色、白色", "tags": ["喜好", "颜色"]},
        {
            "fact": "佳穿衣偏好：冲锋衣、工装等硬朗版型，配色单调",
            "tags": ["喜好", "穿着"],
        },
        {"fact": "佳的睡眠习惯：侧躺，腿上夹着枕头或被子", "tags": ["习惯", "睡眠"]},
        {
            "fact": "佳的洗漱偏好：薄荷牙膏、柠檬肥皂、海盐沐浴露",
            "tags": ["喜好", "洗漱"],
        },
        {"fact": "佳喜欢的味道：桂花香", "tags": ["喜好", "香味"]},
        {"fact": "佳喜欢泡热水澡和泡脚", "tags": ["习惯", "放松"]},
        {
            "fact": "佳有虚无主义倾向，会'开摆'，但对想做的事执行力极强",
            "tags": ["性格", "精神", "重要"],
        },
        {
            "fact": "佳喜欢玩二游：鸣潮、战双帕弥什、原神、崩坏星穹铁道",
            "tags": ["喜好", "游戏"],
        },
        {"fact": "佳喜欢写小说、cosplay、下厨", "tags": ["爱好", "创作"]},
        {
            "fact": "佳喜欢的游戏角色：丹恒、魈、钟离、万叶、镜流、阮梅、黄泉、流萤、飞霄、卡芙卡、遐蝶、雷电将军、八重神子、宵宫、坎特雷拉、爱弥斯、守岸人、阿尔法",
            "tags": ["喜好", "角色", "游戏"],
        },
        {"fact": "佳分享欲强，喜欢分享小说手稿", "tags": ["性格", "习惯"]},
        {"fact": "佳喜欢优美浪漫的古诗词", "tags": ["喜好", "文学"]},
        {"fact": "佳会在睡前冥想", "tags": ["习惯", "睡前"]},
        {
            "fact": "佳是计算机专业大学生，学习网络信息安全、人工智能、编程等",
            "tags": ["信息", "学业", "重要"],
        },
        {"fact": "佳的生日：2005年3月20日", "tags": ["信息", "生日", "重要"]},
        {"fact": "佳身高175cm，皮肤白，O型血", "tags": ["信息", "外貌"]},
        {"fact": "佳的声音是标准男低音，很有磁性", "tags": ["信息", "声音"]},
        {"fact": "佳的手时常冰凉", "tags": ["健康", "体质"]},
    ]

    try:
        from memory import get_unified_memory

        memory = get_unified_memory()

        print(f"Total: {len(memory_anchors)} memory anchors\n")

        success_count = 0
        for i, anchor in enumerate(memory_anchors, 1):
            try:
                await memory.add_short_term(
                    content=anchor["fact"],
                    user_id="jia_main",
                    priority=0.95,
                    tags=anchor["tags"],
                    metadata={"source": "init_anchor", "importance": "high"},
                    category=None,
                )
                print(f"[{i}/{len(memory_anchors)}] OK: {anchor['fact'][:35]}...")
                success_count += 1
            except Exception as e:
                print(f"[{i}/{len(memory_anchors)}] FAIL: {anchor['fact'][:35]}... - {str(e)[:50]}")

        print("\n" + "=" * 60)
        print(f"Memory anchors initialized: {success_count}/{len(memory_anchors)}")
        print("=" * 60)

    except ImportError as e:
        print(f"\n[!] Cannot import unified memory: {e}")
        print("\nMemory anchors (manual add):")
        for anchor in memory_anchors:
            print(f"- {anchor['fact']}")

    except Exception as e:
        print(f"\n[!] Error: {e}")


if __name__ == "__main__":
    asyncio.run(init_memory_anchors())
