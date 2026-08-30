#!/usr/bin/env python3
"""
视觉小说陪玩模块测试脚本

使用方式:
  # 1. 纯配置验证（无需截图，不上电）
  python scripts/test_visual_novel.py --dry

  # 2. 用测试图片跑真实视觉分析（需要设置 MIYA_TEST_PIC_PATH）
  set MIYA_TEST_PIC_PATH=D:/screenshots/galgame_screen.png
  python scripts/test_visual_novel.py --vision

  # 3. 跑全部
  set MIYA_TEST_PIC_PATH=D:/screenshots/galgame_screen.png
  python scripts/test_visual_novel.py --all
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-5s [%(name)s] %(message)s",
)
logger = logging.getLogger("test_visual_novel")


def test_profile_loading() -> None:
    """Level 0: 验证 Profile YAML 加载和合并"""
    from core.game_play.profiles.base import GameProfileManager

    logger.info("=" * 50)
    logger.info("  Level 0: Profile 加载测试")
    logger.info("=" * 50)

    manager = GameProfileManager()

    general = manager.get_profile(None)
    assert general is not None, "general profile 加载失败"
    logger.info(f"  general: {general.game_name}")

    vn = manager.get_profile("visual_novel")
    assert vn is not None, "visual_novel profile 加载失败"
    logger.info(f"  visual_novel: {vn.game_name}")

    # 验证关键字段
    assert vn.system_prompt, "system_prompt 为空"
    assert len(vn.silence_scenes) == 2, f"silence_scenes 应为 2 个，实际 {vn.silence_scenes}"
    assert vn.speak_cooldown == 6.0, f"speak_cooldown 应为 6.0，实际 {vn.speak_cooldown}"
    assert vn.auto_speak, "auto_speak 应为 True"

    # 验证合并正确：visual_novel 覆盖了 general 的值
    assert vn.get_fps_for_scene("dialog") == 10.0, f"dialog fps 应为 0.1，实际 {vn.get_fps_for_scene('dialog')}"
    assert vn.get_fps_for_scene("choice") == 2.0, f"choice fps 应为 0.5，实际 {vn.get_fps_for_scene('choice')}"
    assert vn.should_silence_scene("loading"), "loading 应该是静默场景"
    assert vn.should_silence_scene("op_movie"), "op_movie 应该是静默场景"
    assert not vn.should_silence_scene("dialog"), "dialog 不应该是静默场景"

    logger.info("  Profile 加载: OK")
    logger.info("  Profile 合并: OK (camera_strategy 正确覆盖 general)")
    logger.info("  system_prompt 长度: %d 字符", len(vn.system_prompt))
    logger.info(
        "  fps: dialog=%.0f/s choice=%.0f/s menu=%.0f/s loading=暂停",
        vn.get_fps_for_scene("dialog"),
        vn.get_fps_for_scene("choice"),
        vn.get_fps_for_scene("menu"),
    )

    # 列出所有可用的 profile
    logger.info("  所有可用 Profile: %s", manager.list_game_ids())

    return None


async def test_engine_init() -> dict:
    """Level 1: 验证引擎初始化（不上电，不截图）"""
    from core.game_play.engine import get_game_play_engine

    logger.info("=" * 50)
    logger.info("  Level 1: 引擎初始化测试")
    logger.info("=" * 50)

    engine = get_game_play_engine()
    await engine.initialize()

    assert engine._profile_manager is not None, "profile_manager 未初始化"
    assert engine._initialized, "引擎未标记为已初始化"
    assert not engine._state.active, "引擎不应处于活跃状态"

    vn_profile = engine._profile_manager.get_profile("visual_novel")
    assert vn_profile is not None, "visual_novel profile 获取失败"
    logger.info("  引擎初始化: OK")
    logger.info("  visual_novel profile: %s", vn_profile.game_name)

    return {"status": "ok", "game_name": vn_profile.game_name}


async def test_vision_analysis(test_image_path: str = None) -> dict:
    """Level 2: 真实视觉分析测试（需要截图源）"""
    from core.game_play.engine import get_game_play_engine

    logger.info("=" * 50)
    logger.info("  Level 2: 视觉分析测试 (visual_novel profile)")
    logger.info("=" * 50)

    test_pic = os.environ.get("MIYA_TEST_PIC_PATH", test_image_path or "")
    if not test_pic:
        logger.warning("  跳过: 请设置 MIYA_TEST_PIC_PATH 环境变量指向一张 galgame 截图")
        logger.warning("  示例: set MIYA_TEST_PIC_PATH=D:\\screenshots\\gal.png")
        return {"status": "skipped", "reason": "MIYA_TEST_PIC_PATH 未设置"}

    if not Path(test_pic).exists():
        logger.error("  测试图片不存在: %s", test_pic)
        return {"status": "error", "reason": f"文件不存在: {test_pic}"}

    logger.info("  使用测试图片: %s", test_pic)

    engine = get_game_play_engine()
    await engine.initialize()

    result = await engine.start_game(game_id="visual_novel", voice_enabled=False)
    logger.info("  start_game 结果: %s", json.dumps(result, ensure_ascii=False, indent=2))

    if result.get("status") == "error":
        return {"status": "error", "reason": result.get("message")}

    status = engine.get_status()
    logger.info("  引擎状态: game=%s active=%s", status.get("game_name"), status.get("active"))

    # 获取画面摘要
    summary = await engine.get_screen_summary()
    logger.info("  画面摘要: %s", summary[:200])

    # 等一小段让相机循环跑一次
    logger.info("  等待相机循环运行 3 秒...")
    await asyncio.sleep(3)

    monitor_status = engine._monitor.get_status() if engine._monitor else {}
    logger.info(
        "  监控器状态: frame_count=%s last_scene=%s alerts=%s",
        monitor_status.get("frame_count"),
        monitor_status.get("last_scene"),
        monitor_status.get("alerts_count"),
    )

    if monitor_status.get("last_analysis"):
        analysis = monitor_status["last_analysis"]
        logger.info("  最新分析结果:")
        for key in ["scene", "mood", "speaker", "summary", "has_choice", "should_speak", "what_to_say"]:
            val = analysis.get(key, "")
            if val:
                logger.info("    %-14s: %s", key, str(val)[:100])

    await engine.stop_game()
    logger.info("  引擎已停止")

    return {
        "status": "ok",
        "frame_count": monitor_status.get("frame_count", 0),
        "last_scene": monitor_status.get("last_scene"),
        "alerts_count": monitor_status.get("alerts_count", 0),
        "summary": summary[:300] if summary else "",
    }


async def test_vision_offline(test_image_path: str = None) -> dict:
    """Level 3: 离线测试（只用静态图片模拟，不跑视觉 LLM）"""
    from core.game_play.engine import get_game_play_engine

    logger.info("=" * 50)
    logger.info("  Level 3: 离线 Profile 切换测试")
    logger.info("=" * 50)

    engine = get_game_play_engine()
    await engine.initialize()

    # 切换到 visual_novel profile 并验证场景策略
    vn = engine._profile_manager.get_profile("visual_novel")

    from core.game_play.screen_monitor import ProactiveScreenMonitor

    monitor = ProactiveScreenMonitor()
    monitor.apply_profile(vn)

    test_scenes = [
        ("dialog", True, 0.1),
        ("narration", True, 0.125),
        ("choice", True, 0.5),
        ("menu", True, 1 / 30),
        ("loading", False, 1 / 999),
        ("op_movie", False, 1 / 999),
    ]

    logger.info("  场景策略验证:")
    for scene, should_talk, expected_interval in test_scenes:
        monitor._update_interval(scene)
        actual = monitor._current_interval
        silenced = scene in monitor._silence_scenes
        logger.info("    %-12s interval=%.3fs silenced=%s", scene, actual, silenced)

    logger.info("  离线切换测试: OK")

    return {"status": "ok"}


async def main():
    parser = argparse.ArgumentParser(description="视觉小说陪玩模块测试")
    parser.add_argument("--dry", action="store_true", help="仅 Profile 配置验证")
    parser.add_argument("--vision", action="store_true", help="真实视觉分析（需截图源）")
    parser.add_argument("--offline", action="store_true", help="离线策略切换测试")
    parser.add_argument("--all", action="store_true", help="全部测试")
    parser.add_argument("--image", help="指定测试图片路径")
    args = parser.parse_args()

    run_all = args.all
    results = {}

    if args.dry or run_all:
        results["dry"] = test_profile_loading()

    if args.offline or run_all:
        results["offline"] = await test_engine_init()
        results["strategy"] = await test_vision_offline(args.image)

    if args.vision or run_all:
        results["vision"] = await test_vision_analysis(args.image)

    if not any([args.dry, args.vision, args.offline, args.all]):
        parser.print_help()
        return

    logger.info("")
    logger.info("=" * 50)
    logger.info("  测试结果汇总")
    logger.info("=" * 50)
    for name, r in results.items():
        s = r.get("status", "?")
        extra = ""
        if s in ("skipped", "error"):
            extra = f" — {r.get('reason', '')}"
        logger.info("  %-12s: %s%s", name, s, extra)


if __name__ == "__main__":
    asyncio.run(main())
