"""参考项目式 MDX 分离 CLI (audio_separator + onnx)

由 Live2D-Virtual-Girlfriend 整合包的 runtime python 运行。
复刻参考项目的两次分离配方:
  UVR-MDX-NET-Inst_HQ_3 → 伴奏分离
  UVR_MDXNET_KARA_2    → 和声提取

用法:
  mdx_sep_cli.py <input> <output_dir> --model-file <onnx绝对路径>
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


def _ensure_ffmpeg_in_path():
    """audio_separator 依赖 PATH 里的 ffmpeg (pydub 转码用)

    优先用弥娅探测到的 ffmpeg (RVC 整合包自带), 注入其目录到 PATH。
    """
    try:
        from paths import find_ffmpeg

        ffmpeg = find_ffmpeg()
        d = os.path.dirname(ffmpeg)
        if d and os.path.isdir(d):
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
            return
    except Exception:
        pass
    sys.stderr.write("警告: 未找到 ffmpeg, 分离可能失败\n")


if __name__ == "__main__":
    _ensure_ffmpeg_in_path()

    parser = argparse.ArgumentParser(description="MDX audio separator CLI (audio_separator)")
    parser.add_argument("input", help="Input audio file")
    parser.add_argument("output_dir", help="Output directory")
    parser.add_argument("--model-file", required=True, help="Absolute path to .onnx model")
    args = parser.parse_args()

    model_file = os.path.abspath(args.model_file)
    if not os.path.exists(model_file):
        sys.stderr.write(f"模型不存在: {model_file}\n")
        sys.exit(2)

    os.makedirs(args.output_dir, exist_ok=True)
    work = tempfile.mkdtemp(prefix="mdxsep_")
    try:
        # ASCII 工作目录 (避免中文路径兼容问题)
        src = os.path.join(work, "_input.wav")
        shutil.copy2(os.path.abspath(args.input), src)

        import logging

        logging.basicConfig(level=logging.WARNING)

        from audio_separator.separator import Separator

        separator = Separator(
            output_dir=work,
            model_file_dir=os.path.dirname(model_file),
            log_level=logging.WARNING,
        )
        separator.load_model(model_filename=os.path.basename(model_file))
        vocal_name, inst_name = separator.separate(src)

        vocal_src = os.path.join(work, vocal_name)
        inst_src = os.path.join(work, inst_name)
        if not os.path.exists(vocal_src):
            sys.stderr.write(f"分离无输出: {vocal_name}\n")
            sys.exit(3)

        vocal_out = os.path.join(args.output_dir, "Vocals.wav")
        inst_out = os.path.join(args.output_dir, "Instrumental.wav")
        shutil.move(vocal_src, vocal_out)
        if os.path.exists(inst_src):
            shutil.move(inst_src, inst_out)
        print(f"OK vocal={os.path.getsize(vocal_out)}B inst={os.path.getsize(inst_out) if os.path.exists(inst_out) else 0}B")
    finally:
        shutil.rmtree(work, ignore_errors=True)
