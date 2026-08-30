"""RVC 整合包自带 UVR5 分离 CLI

由 RVC 整合包的 runtime python 运行（无 GPT-SoVITS 时的替代分离方案）。
使用 RVC 自带的 infer/modules/uvr5 模块 + assets/uvr5_weights 模型 (HP5 等)。

用法:
  rvc_uvr5_cli.py <input> <output_dir> [--model HP5_only_main_vocal] [--device cuda] [--rvc-root PATH]
输出:
  <output_dir>/Vocals.wav / Instrumental.wav
"""
import argparse
import os
import shutil
import sys
import tempfile

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)


def _resolve_rvc_root(cli_value: str) -> str:
    if cli_value:
        return cli_value
    try:
        from paths import get_rvc_root

        root = get_rvc_root()
        if root and os.path.isdir(root):
            return root
    except Exception:
        pass
    sys.stderr.write("缺少 RVC 根目录：请用 --rvc-root 指定，或在 singing_config.json paths.rvc_root 配置\n")
    sys.exit(2)


def _collect_biggest_wav(directory: str) -> str:
    """取目录中最大的 wav 文件路径"""
    best, best_size = "", 0
    for f in os.listdir(directory):
        if not f.lower().endswith(".wav"):
            continue
        fp = os.path.join(directory, f)
        sz = os.path.getsize(fp)
        if sz > best_size:
            best, best_size = fp, sz
    return best


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RVC builtin UVR5 separation CLI")
    parser.add_argument("input", help="Input audio file")
    parser.add_argument("output_dir", help="Output directory")
    parser.add_argument("--model", default="HP5_only_main_vocal", help="UVR5 model name in assets/uvr5_weights")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--agg", type=int, default=10)
    parser.add_argument("--rvc-root", default="", help="RVC 整合包根目录")
    args = parser.parse_args()

    rvc_root = _resolve_rvc_root(args.rvc_root)
    os.environ.setdefault("weight_uvr5_root", os.path.join(rvc_root, "assets", "uvr5_weights"))
    os.environ["PATH"] = rvc_root + os.pathsep + os.environ.get("PATH", "")
    sys.path.insert(0, rvc_root)
    sys.path.insert(0, os.path.join(rvc_root, "infer"))
    os.chdir(rvc_root)

    os.makedirs(args.output_dir, exist_ok=True)
    tmp_in = tempfile.mkdtemp(prefix="rvcuvr5_")
    voc_dir = os.path.join(args.output_dir, "_voc")
    ins_dir = os.path.join(args.output_dir, "_ins")
    shutil.rmtree(voc_dir, ignore_errors=True)
    shutil.rmtree(ins_dir, ignore_errors=True)
    os.makedirs(voc_dir, exist_ok=True)
    os.makedirs(ins_dir, exist_ok=True)

    try:
        # 临时目录内用 ASCII 文件名 (RVC 嵌入式 python 传中文路径给 ffmpeg 会乱码)
        _ext = os.path.splitext(args.input)[1].lower() or ".wav"
        shutil.copy2(os.path.abspath(args.input), os.path.join(tmp_in, f"_input{_ext}"))

        # RVC 的 configs.config 在 import 时解析 sys.argv (为 infer-web.py 设计)，
        # 注入兼容参数后再 import，避免劫持本 CLI 的参数
        _real_argv = sys.argv
        sys.argv = [
            "rvc_uvr5_cli.py",
            "--pycmd",
            sys.executable,
            "--port",
            "7865",
            "--noautoopen",
        ]
        try:
            from infer.modules.uvr5.modules import uvr
        finally:
            sys.argv = _real_argv

        gen = uvr(args.model, tmp_in, voc_dir, [], ins_dir, args.agg, "wav")
        last_msg = ""
        for msg in gen:
            if msg:
                last_msg = msg
        print(last_msg or "done")

        vocal_src = _collect_biggest_wav(voc_dir)
        inst_src = _collect_biggest_wav(ins_dir)
        vocal_out = os.path.join(args.output_dir, "Vocals.wav")
        inst_out = os.path.join(args.output_dir, "Instrumental.wav")

        ok = False
        if vocal_src and os.path.getsize(vocal_src) > 1024:
            shutil.move(vocal_src, vocal_out)
            ok = True
        if inst_src and os.path.getsize(inst_src) > 1024:
            shutil.move(inst_src, inst_out)

        if ok:
            print(f"OK vocal={os.path.getsize(vocal_out)}B inst={os.path.getsize(inst_out) if os.path.exists(inst_out) else 0}B")
        else:
            print("FAIL no vocal output", file=sys.stderr)
            sys.exit(1)
    finally:
        shutil.rmtree(tmp_in, ignore_errors=True)
        shutil.rmtree(voc_dir, ignore_errors=True)
        shutil.rmtree(ins_dir, ignore_errors=True)
