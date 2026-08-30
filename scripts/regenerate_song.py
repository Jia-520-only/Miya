"""重生成指定歌曲 (临时脚本): python scripts/regenerate_song.py <歌名目录>"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

logging.basicConfig(level=logging.INFO, format="%(name)s %(message)s")

from core.singing.manager import SingingWorkflow, SingingRegistry
from core.singing.provider_builtin import BuiltinSingingEngine


async def main():
    song_dir_name = sys.argv[1]
    cfg = json.load(open("config/singing_config.json", encoding="utf-8"))
    eng_cfg = cfg["engines"]["builtin"]

    e = BuiltinSingingEngine()
    e.initialize(eng_cfg)

    out_dir = os.path.join(e.output_base_dir, song_dir_name)
    result = await e.process_full_pipeline(song_dir_name, out_dir)
    print("PIPELINE:", "OK" if result else "FAIL")
    if not result:
        sys.exit(2)

    w = SingingWorkflow(SingingRegistry())
    vocal = result["vocal_path"]
    accomp = result["accompany_path"]
    mix = os.path.join(out_dir, f"{song_dir_name}_mix.wav")
    r = await w._mix_wav_files(vocal, accomp, 70, 70, mix)
    print("MIX:", r)
    assert r and os.path.exists(r)
    import numpy as np
    import soundfile as sf

    d, sr = sf.read(r, dtype="float32", always_2d=True)
    print(f"done: {len(d)/sr:.1f}s peak={np.abs(d).max():.3f}")


if __name__ == "__main__":
    asyncio.run(main())
