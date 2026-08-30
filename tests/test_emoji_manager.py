#!/usr/bin/env python3
"""
智能表情包管理器测试
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_emoji_config():
    """测试表情包配置"""
    print("=" * 50)
    print("测试 1: 表情包配置加载")

    # 测试 text_config.json 中的 poke_responses
    from core.text_loader import get_pat_pat_trigger, get_text

    poke_builtin = get_text("poke_responses.builtin_emoji", "")
    poke_local = get_text("poke_responses.local_emoji", "")
    pat_pat_trigger = get_pat_pat_trigger()

    print(f"  拍一拍内置表情回复: '{poke_builtin}'")
    print(f"  拍一拍本地表情回复: '{poke_local}'")
    print(f"  拍一拍触发词: '{pat_pat_trigger}'")

    # 测试 emoji_settings
    emoji_dir = get_text("emoji_settings.dir", "")
    emoji_enabled = get_text("emoji_settings.enabled", None)
    auto_send = get_text("emoji_settings.auto_send_on_poke", None)

    print(f"  表情包目录: '{emoji_dir}'")
    print(f"  表情包启用: {emoji_enabled}")
    print(f"  拍一拍自动发送: {auto_send}")


def test_emoji_directory():
    """测试表情包目录"""
    print("\n" + "=" * 50)
    print("测试 2: 表情包目录检查")

    from core.text_loader import get_text

    emoji_dir = get_text("emoji_settings.dir", "data/emoji")

    if os.path.exists(emoji_dir):
        print(f"  目录存在: {emoji_dir}")

        import random

        image_extensions = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")
        image_files = []

        for root, _dirs, files in os.walk(emoji_dir):
            for file in files:
                if file.lower().endswith(image_extensions):
                    image_files.append(os.path.join(root, file))

        print(f"  找到 {len(image_files)} 个表情包文件")

        if image_files:
            print("  示例文件:")
            for f in image_files[:5]:
                print(f"    - {f}")

            # 测试随机选择
            random_file = random.choice(image_files)
            print(f"  随机选择: {random_file}")
    else:
        print(f"  目录不存在: {emoji_dir}")


def test_qq_emoji_config():
    """测试 QQ 配置中的表情包设置"""
    print("\n" + "=" * 50)
    print("测试 3: QQ 配置中的表情包设置")

    from webnet.qq.config_loader import get_qq_config, get_tool_config

    tool_cfg = get_tool_config("qq_emoji")
    print("  qq_emoji 工具配置:")
    print(f"    enabled: {tool_cfg.get('enabled')}")
    print(f"    emoji_dir: {tool_cfg.get('emoji_dir')}")
    print(f"    standard_emojis: {tool_cfg.get('standard_emojis')}")
    print(f"    custom_emojis: {tool_cfg.get('custom_emojis')}")

    features = get_qq_config("features")
    print("  功能开关:")
    print(f"    emoji_request: {features.get('emoji_request')}")
    print(f"    poke_reply: {features.get('poke_reply')}")


def test_message_handler_poke():
    """测试消息处理器的拍一拍逻辑"""
    print("\n" + "=" * 50)
    print("测试 4: 拍一拍处理逻辑模拟")

    # 模拟拍一拍事件
    mock_event = {
        "post_type": "notice",
        "notice_type": "poke",
        "target_id": 3681817929,  # 机器人 QQ
        "user_id": 1523878699,  # 发送者
        "group_id": 0,
    }

    # 检查 bot_qq 配置
    from webnet.qq.config_loader import get_connection_config

    conn = get_connection_config()
    bot_qq = conn.get("bot_qq", 0)

    print(f"  配置中的 bot_qq: {bot_qq}")
    print(f"  拍一拍事件 target_id: {mock_event['target_id']}")

    if bot_qq == 0:
        print("  WARNING: bot_qq is 0, poke will not respond!")
        print("  Please set QQ_BOT_QQ=your_bot_qq in config/.env")
    elif bot_qq == mock_event["target_id"]:
        print("  OK: bot_qq matches, poke will respond normally")
    else:
        print("  WARNING: bot_qq does not match target_id")


if __name__ == "__main__":
    test_emoji_config()
    test_emoji_directory()
    test_qq_emoji_config()
    test_message_handler_poke()

    print("\n" + "=" * 50)
    print("智能表情包管理器测试完成!")
    print("=" * 50)
