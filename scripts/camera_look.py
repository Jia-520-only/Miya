"""Capture and analyze one physical camera frame from the terminal."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Running a script by path puts ``scripts/`` first on sys.path; add the project
# root so the same command works from any current working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcpserver.screen_vision.service import ScreenVisionService


def main() -> int:
    parser = argparse.ArgumentParser(description="弥娅终端摄像头单帧观察")
    parser.add_argument("query", nargs="?", default="请描述我当前可见的姿态、动作和环境。")
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--allow-cloud", action="store_true", help="允许按视觉路由将这一帧发送给云端模型")
    parser.add_argument("--json", action="store_true", dest="as_json", help="输出完整 JSON")
    args = parser.parse_args()

    result = json.loads(asyncio.run(ScreenVisionService().handle_handoff({
        "tool_name": "camera_look",
        "query": args.query,
        "camera_index": args.camera_index,
        "width": args.width,
        "height": args.height,
        "local_only": not args.allow_cloud,
    })))
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result.get("message") or json.dumps(result, ensure_ascii=False))
    return 0 if result.get("status") in {"success", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
