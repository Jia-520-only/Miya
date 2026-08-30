import argparse
import os
import sys
import time

# GPT-SoVITS runtime 是嵌入式 Python (python39.zip)，sys.path 不含脚本目录，
# 显式插入以便 import 同目录的 paths.py
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)


def _resolve_sovits_root(cli_value: str) -> str:
    """GPT-SoVITS 根目录：命令行参数 > 弥娅配置 paths.gpt_sovits_root"""
    if cli_value:
        return cli_value
    try:
        from paths import get_gpt_sovits_root

        root = get_gpt_sovits_root()
        if root and os.path.isdir(root):
            return root
    except Exception:
        pass
    sys.stderr.write(
        "缺少 GPT-SoVITS 根目录：请用 --sovits-root 指定，或在 singing_config.json paths.gpt_sovits_root 配置\n"
    )
    sys.exit(2)


def _rename_vr_output(input_audio, output_vocal, output_inst):
    vocal_dir = os.path.dirname(output_vocal)
    inst_dir = os.path.dirname(output_inst)

    for root in [vocal_dir, inst_dir]:
        for f in os.listdir(root):
            fp = os.path.join(root, f)
            if not f.endswith(".wav") or f in ("Vocals.wav", "Instrumental.wav"):
                continue
            fl = f.lower()
            sz = os.path.getsize(fp)
            if sz < 1024:
                continue
            if "vocal" in fl and "instrument" not in fl:
                if os.path.exists(output_vocal):
                    os.remove(output_vocal)
                os.rename(fp, output_vocal)
            elif "instrument" in fl or "no_vocal" in fl or "other" in fl:
                if os.path.exists(output_inst):
                    os.remove(output_inst)
                os.rename(fp, output_inst)


def run_vr(input_audio, output_vocal, output_inst, model_path, device="cuda", agg=10):
    from tools.uvr5.vr import AudioPre

    ap = AudioPre(agg=agg, model_path=model_path, device=device, is_half=True)
    ap._path_audio_(
        input_audio,
        ins_root=os.path.dirname(output_inst),
        vocal_root=os.path.dirname(output_vocal),
        format="wav",
    )
    _rename_vr_output(input_audio, output_vocal, output_inst)
    return os.path.exists(output_vocal), os.path.exists(output_inst)


def run_bs_roformer(input_audio, output_vocal, output_inst, model_path, device="cuda"):
    from tools.uvr5.bsroformer import Roformer_Loader

    rl = Roformer_Loader(model_path=model_path, config_path="", device=device, is_half=True)
    rl._path_audio_(
        input_audio,
        others_root=os.path.dirname(output_inst),
        vocal_root=os.path.dirname(output_vocal),
        format="wav",
    )
    _rename_vr_output(input_audio, output_vocal, output_inst)
    return os.path.exists(output_vocal), os.path.exists(output_inst)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UVR5 Vocal Separation CLI")
    parser.add_argument("input", help="Input audio file")
    parser.add_argument("output_dir", help="Output directory")
    parser.add_argument("--model-type", default="vr", choices=["vr", "bs_roformer"])
    parser.add_argument("--model-path", required=True, help="Path to .pth or .ckpt model")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--agg", type=int, default=10)
    parser.add_argument("--sovits-root", default="", help="GPT-SoVITS 整合包根目录")
    args = parser.parse_args()

    base = _resolve_sovits_root(args.sovits_root)
    sys.path.insert(0, base)
    sys.path.insert(0, os.path.join(base, "tools", "uvr5"))
    os.chdir(base)

    os.makedirs(args.output_dir, exist_ok=True)
    vocal_out = os.path.join(args.output_dir, "Vocals.wav")
    inst_out = os.path.join(args.output_dir, "Instrumental.wav")

    t0 = time.time()
    if args.model_type == "vr":
        v_ok, i_ok = run_vr(args.input, vocal_out, inst_out, args.model_path, args.device, args.agg)
    else:
        v_ok, i_ok = run_bs_roformer(args.input, vocal_out, inst_out, args.model_path, args.device)
    elapsed = time.time() - t0

    if v_ok:
        print(f"OK {elapsed:.1f}s vocal={os.path.getsize(vocal_out)}B inst={os.path.getsize(inst_out) if i_ok else 0}B")
    else:
        print(f"FAIL {elapsed:.1f}s", file=sys.stderr)
        sys.exit(1)
