#!/usr/bin/env python3
"""
弥娅系统级身份记忆锚点初始化脚本
从配置文件加载弥娅自我认知并初始化到记忆系统

运行方式: python scripts/init_miya_identity_anchors.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def get_anchor_config_path(config_name: str) -> str:
    """获取锚点配置文件路径"""
    config_path = Path(__file__).parent.parent / "config" / "memory_config.json"

    if not config_path.exists():
        return ""

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        anchors_config = config.get("anchors", {})
        return anchors_config.get(config_name, "")
    except Exception:
        return ""


def get_default_anchor_path(config_name: str) -> Path:
    """获取默认锚点文件路径"""
    data_dir = Path(__file__).parent.parent / "data"
    defaults = {
        "identity_anchors": "memory_anchors_identity.json",
    }
    return data_dir / defaults.get(config_name, "")


async def init_miya_identity_anchors():
    print("=" * 60)
    print("弥娅系统级身份记忆锚点初始化")
    print("=" * 60)

    # 从配置获取文件路径
    anchor_file = get_anchor_config_path("identity_anchors")
    if not anchor_file:
        anchor_file = get_default_anchor_path("identity_anchors")

    anchor_path = Path(anchor_file)
    if not anchor_path.is_absolute():
        anchor_path = Path(__file__).parent.parent / anchor_path

    print(f"\n正在从配置文件加载身份锚点: {anchor_path}\n")

    if not anchor_path.exists():
        print(f"[!] 配置文件不存在: {anchor_path}")
        return

    try:
        with open(anchor_path, "r", encoding="utf-8") as f:
            identity_anchors = json.load(f)

        print(f"Total: {len(identity_anchors)} identity anchors\n")

        from memory import get_memory_core, store_important

        success_count = 0
        for i, anchor in enumerate(identity_anchors, 1):
            try:
                await store_important(
                    content=anchor.get("fact", anchor.get("content", "")),
                    user_id="system",
                    tags=anchor.get("tags", []),
                    priority=anchor.get("priority", 0.9),
                    metadata={"source": "identity_anchor", "type": "self_cognition"},
                )
                fact_text = anchor.get("fact", anchor.get("content", ""))
                print(f"[{i}/{len(identity_anchors)}] OK: {fact_text[:40]}...")
                success_count += 1
            except Exception as e:
                fact_text = anchor.get("fact", anchor.get("content", ""))
                print(f"[{i}/{len(identity_anchors)}] FAIL: {fact_text[:40]}... - {str(e)[:50]}")

        print("\n" + "=" * 60)
        print(f"Identity anchors initialized: {success_count}/{len(identity_anchors)}")
        print("=" * 60)

    except ImportError as e:
        print(f"\n[!] Cannot import memory module: {e}")

    except Exception as e:
        print(f"\n[!] Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(init_miya_identity_anchors())
