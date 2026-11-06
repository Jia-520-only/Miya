"""从命令行调用与弥娅相同的本地 ComfyUI 工具。"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcpserver.art_service.service import ArtService


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("list_workflows", "describe_workflow", "assist_prompt", "upload_media", "generate", "get_task"),
    )
    parser.add_argument("--workflow", default="image", choices=("image", "video"))
    parser.add_argument("--prompt", default="")
    parser.add_argument("--parameters-json", default="{}")
    parser.add_argument("--file-path", default="")
    parser.add_argument("--prompt-id", default="")
    parser.add_argument("--wait-seconds", type=int, default=20)
    call = vars(parser.parse_args())
    call["tool_name"] = "comfyui"
    print(asyncio.run(ArtService().handle_handoff(call)))
