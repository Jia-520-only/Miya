"""内置唱歌引擎全流程端到端验证 (临时脚本)

用 data/singing_input/白挺 - 你从未离去.mp3 走完整管线:
下载 → UVR5 分离 → RVC 自动拉起+换声 → 验证成品
"""
import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[
        logging.FileHandler("logs/e2e_sing_test.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

from core.singing.provider_builtin import BuiltinSingingEngine


async def main():
    cfg = json.load(open("config/singing_config.json", encoding="utf-8"))
    eng_cfg = cfg["engines"]["builtin"]

    e = BuiltinSingingEngine()
    ok = e.initialize(eng_cfg)
    print("INIT:", ok)
    if not ok:
        sys.exit(2)

    out_dir = "data/singing/白挺 - 你从未离去"
    result = await e.process_full_pipeline("白挺 - 你从未离去", out_dir)
    print("RESULT:", result)

    if not result:
        sys.exit(3)

    vocal = result["vocal_path"]
    import numpy as np
    import soundfile as sf

    data, sr = sf.read(vocal, dtype="float32", always_2d=True)
    peak = float(np.max(np.abs(data))) if len(data) else 0.0
    print(f"VOCAL: sr={sr} dur={len(data)/sr:.1f}s peak={peak:.4f} size={os.path.getsize(vocal)}B")
    print("E2E OK" if peak > 0.01 and len(data) / sr > 30 else "E2E SUSPICIOUS")
    e.cleanup()
    sys.exit(0 if peak > 0.01 and len(data) / sr > 30 else 4)


if __name__ == "__main__":
    asyncio.run(main())
