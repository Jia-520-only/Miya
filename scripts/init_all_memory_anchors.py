#!/usr/bin/env python3
"""
弥娅记忆锚点统一初始化脚本
- 身份锚点：预加载到记忆系统（弥娅自我认知）
- 用户锚点：按需检索，不预加载（避免与人设规则冲突）

运行方式:
  python scripts/init_all_memory_anchors.py          # 初始化身份锚点
  python scripts/init_all_memory_anchors.py --identity  # 只初始化身份锚点
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def load_config() -> dict:
    """加载记忆配置"""
    config_path = Path(__file__).parent.parent / "config" / "memory_config.json"

    if not config_path.exists():
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_anchor_file_path(config_key: str) -> Path:
    """获取锚点文件路径"""
    config = load_config()
    anchors_config = config.get("anchors", {})

    file_path = anchors_config.get(config_key, "")

    if not file_path:
        defaults = {
            "identity_anchors": "data/memory_anchors_identity.json",
        }
        file_path = defaults.get(config_key, "")

    path = Path(file_path)
    if not path.is_absolute():
        path = Path(__file__).parent.parent / path

    return path


async def init_identity_anchors():
    """初始化身份记忆锚点"""
    print("\n" + "=" * 60)
    print("初始化身份记忆锚点")
    print("=" * 60)

    anchor_path = get_anchor_file_path("identity_anchors")
    print(f"\n加载配置文件: {anchor_path}\n")

    if not anchor_path.exists():
        print(f"[!] 配置文件不存在: {anchor_path}")
        return 0

    try:
        with open(anchor_path, "r", encoding="utf-8") as f:
            anchors = json.load(f)

        print(f"共 {len(anchors)} 条身份锚点\n")

        from memory import store_important

        success_count = 0
        for i, anchor in enumerate(anchors, 1):
            try:
                content = anchor.get("fact", anchor.get("content", ""))
                await store_important(
                    content=content,
                    user_id="system",
                    tags=anchor.get("tags", []),
                    priority=anchor.get("priority", 0.9),
                    metadata={"source": "identity_anchor", "type": "self_cognition"},
                )
                print(f"[{i}/{len(anchors)}] OK: {content[:40]}...")
                success_count += 1
            except Exception as e:
                content = anchor.get("fact", anchor.get("content", ""))
                print(f"[{i}/{len(anchors)}] FAIL: {content[:40]}... - {str(e)[:40]}")

        print(f"\n身份锚点初始化完成: {success_count}/{len(anchors)}")
        return success_count

    except ImportError as e:
        print(f"[!] 无法导入记忆模块: {e}")
        return 0
    except Exception as e:
        print(f"[!] 错误: {e}")
        return 0


async def main():
    parser = argparse.ArgumentParser(description="弥娅记忆锚点初始化")
    parser.add_argument("--identity", action="store_true", help="只初始化身份锚点")
    parser.parse_args()

    print("=" * 60)
    print("弥娅记忆锚点初始化")
    print("=" * 60)
    print("\n说明:")
    print("  - 身份锚点: 预加载（弥娅自我认知）")
    print("  - 用户锚点: 按需检索（不预加载，避免与人设冲突）")

    identity_count = await init_identity_anchors()

    print("\n" + "=" * 60)
    print("初始化完成")
    print(f"  身份锚点: {identity_count} 条")
    print("  用户锚点: 按需检索（已配置在 data/memory_anchors_user.json）")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
