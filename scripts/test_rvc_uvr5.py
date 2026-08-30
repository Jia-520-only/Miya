"""RVC 自带 UVR5 (HP5) 分离回归测试 (临时脚本) — 模拟无 GPT-SoVITS 场景"""
import asyncio
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

logging.basicConfig(level=logging.INFO, format="%(name)s %(message)s")

from core.singing.paths import get_rvc_root
from core.singing.separator import UVR5Separator


async def main():
    rvc = get_rvc_root()
    sep = UVR5Separator(provider="rvc")
    sep.initialize(
        {
            "provider": "rvc",
            "uvr5_python": os.path.join(rvc, "runtime", "python.exe"),
            "uvr5_models": [{"type": "rvc_hp5", "name": "HP5_only_main_vocal", "path": ""}],
        }
    )

    src = os.path.join("data", "singing_input", "白挺 - 你从未离去.mp3")
    out_dir = os.path.join("data", "singing_sep_rvc_test")
    shutil.rmtree(out_dir, ignore_errors=True)
    v, i = await sep.separate(src, out_dir)
    print("VOCAL:", v, os.path.getsize(v) if v else None)
    print("INST :", i, os.path.getsize(i) if i else None)
    assert v and os.path.getsize(v) > 1000000, "RVC UVR5 separation failed"
    print("RVC UVR5 SEPARATION PASSED")
    shutil.rmtree(out_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
