"""弥娅唱歌模块环境自检

在任意电脑上运行，检查 RVC 翻唱所需的外部环境是否齐全：
  python scripts/singing_env_check.py

检查项：
  1. config paths 配置解析
  2. RVC 整合包 (根目录/启动脚本/配置的声线模型/index/rmvpe/yutto)
  3. 人声分离引擎 (GPT-SoVITS BS-Roformer / MDX 多轮分离 / RVC 自带 UVR5 回退)
  4. ffmpeg
  5. Python 依赖 (requests/pydub/soundfile/scipy/numpy/pedalboard)
  6. RVC 服务连通性
  7. 本地音乐库
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:  # Windows 控制台默认 GBK, 强制 UTF-8 输出 (避免 ✓/✗ 乱码)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

OK, WARN, FAIL = "✓", "△", "✗"

_fail_count = 0


def check(ok: bool, name: str, detail: str = "", optional: bool = False):
    global _fail_count
    if ok:
        mark = OK
    elif optional:
        mark = WARN
    else:
        mark = FAIL
        _fail_count += 1
    print(f"  {mark} {name}" + (f"  — {detail}" if detail else ""))
    return ok


def _config():
    cfg_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", "singing_config.json",
    )
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    from core.singing.paths import (
        env_report, expand_path, find_ffmpeg, get_gpt_sovits_root,
        get_mdx_root, get_rvc_root,
    )

    print("=== 弥娅唱歌模块环境自检 ===")
    report = env_report()
    cfg = _config()
    builtin = cfg.get("engines", {}).get("builtin", {})

    # 1. 路径配置
    print("\n[1] 路径解析 (config/singing_config.json → paths, 留空自动探测)")
    rvc = report["rvc_root"]
    sovits = report["gpt_sovits_root"]
    mdx = get_mdx_root()
    ffmpeg = report["ffmpeg"]
    print(f"  rvc_root       = {rvc or '(未配置且未探测到)'}")
    print(f"  gpt_sovits_root= {sovits or '(未配置且未探测到)'}")
    print(f"  mdx_root       = {mdx or '(未配置且未探测到)'}")
    print(f"  ffmpeg         = {ffmpeg}")

    # 2. RVC 整合包
    print("\n[2] RVC 整合包 (声线换声)")
    ok_rvc_root = check(report["rvc_exists"], "rvc_root 目录存在", rvc)
    launch_bat = report["rvc_launch_bat"]
    check(ok_rvc_root and os.path.exists(launch_bat), "start_api.bat 存在", launch_bat)
    wdir = report["rvc_weights_dir"]
    ok_weights = ok_rvc_root and os.path.isdir(wdir)
    check(ok_weights, "assets/weights 模型目录存在", wdir)

    model_name = builtin.get("rvc_model", "")
    if ok_weights:
        models = [f for f in os.listdir(wdir) if f.endswith(".pth")]
        check(bool(models), f"声线模型目录 ({len(models)} 个 .pth)")
        if model_name:
            has_model = os.path.exists(os.path.join(wdir, model_name + ".pth")) or os.path.exists(
                os.path.join(wdir, model_name)
            )
            check(has_model, f"配置的模型 {model_name} 存在",
                  "未找到! 请放入 assets/weights/ 或改 rvc_model" if not has_model else "")

    index_cfg = expand_path(builtin.get("rvc_index_path", ""))
    if index_cfg:
        check(os.path.exists(index_cfg), f"音色索引 {os.path.basename(index_cfg)} 存在", index_cfg)
    else:
        check(True, "未配置音色索引 (可选, 音色还原度略降)")

    rmvpe_dir = os.path.join(rvc, "assets", "rmvpe") if rvc else ""
    check(ok_rvc_root and os.path.exists(os.path.join(rmvpe_dir, "rmvpe.pt")),
          "rmvpe 音高模型存在 (f0_method=rmvpe 必需)")

    # yutto (B站音源下载, 可选)
    if ok_rvc_root:
        yutto_dir = os.path.join(rvc, "runtime", "Lib", "site-packages", "yutto")
        check(os.path.isdir(yutto_dir), "yutto 已安装 (B站音源下载)",
              "(无 B 站音源需求可忽略, 安装: runtime\\python.exe -m pip install yutto)" if not os.path.isdir(yutto_dir) else "",
              optional=True)

    # 3. 人声分离引擎
    print("\n[3] 人声分离引擎")
    stages_enabled = builtin.get("separation_stages_enabled", False)
    stages = builtin.get("separation_stages") or []
    use_mdx = stages_enabled and any(s.get("model_type") == "mdx" for s in stages)

    if use_mdx:
        print("  当前配置: MDX 多轮分离 (必需)")
        ok_mdx = bool(mdx) and os.path.isdir(mdx)
        check(ok_mdx, "MDX 分离部件目录存在 (mdx_root)", mdx or "(未配置, 推荐放 {rvc_root}/mdx/)")
        if ok_mdx:
            py = os.path.join(mdx, "runtime", "python.exe")
            check(os.path.exists(py), "runtime python 存在", py)
            asep = os.path.join(mdx, "runtime", "Lib", "site-packages", "audio_separator")
            check(os.path.isdir(asep), "audio_separator 已安装")
            for s in stages:
                if s.get("model_type") != "mdx":
                    continue
                mp = expand_path(s.get("model_path", ""))
                check(os.path.exists(mp), f"MDX 模型 {os.path.basename(mp)} 存在", mp)
    else:
        print("  当前配置: 传统 UVR5 分离")

    sovits_ok = report["gpt_sovits_exists"]
    if use_mdx:
        check(sovits_ok, "GPT-SoVITS 整合包 (BS-Roformer 备选分离)",
              sovits or "(未配置, MDX 模式非必需)")
    else:
        check(sovits_ok, "GPT-SoVITS 整合包 (BS-Roformer 主分离)",
              sovits or "(未配置, 将回退到 RVC UVR5/demucs)")
    if sovits_ok:
        py = os.path.join(sovits, "runtime", "python.exe")
        check(os.path.exists(py), "runtime python 存在", py)
        w = os.path.join(sovits, "tools", "uvr5", "uvr5_weights")
        check(os.path.isdir(w), "uvr5_weights 目录存在", w)
        if os.path.isdir(w):
            have = any(f.startswith("model_bs_roformer") for f in os.listdir(w))
            check(have, "BS-Roformer 模型存在 (SDR 12.97)")

    if not sovits_ok and not use_mdx:
        rvc_w = os.path.join(rvc, "assets", "uvr5_weights") if rvc else ""
        rvc_ok = bool(rvc_w) and os.path.isdir(rvc_w)
        check(rvc_ok, "RVC 自带 UVR5 权重 (回退方案)", rvc_w)
        if rvc_ok:
            hp5 = any(f == "HP5_only_main_vocal.pth" for f in os.listdir(rvc_w))
            check(hp5, "HP5_only_main_vocal 模型存在")

    # 4. ffmpeg
    print("\n[4] ffmpeg")
    check(report["ffmpeg_ok"], "ffmpeg 可用", ffmpeg)

    # 5. Python 依赖
    print("\n[5] Python 依赖 (弥娅运行环境)")
    for mod in ("requests", "pydub", "soundfile", "numpy", "scipy", "pedalboard"):
        try:
            __import__(mod)
            check(True, mod)
        except ImportError:
            check(False, mod, "pip install " + mod)

    # 6. RVC 服务
    print("\n[6] RVC 服务 (http://127.0.0.1:7897)")
    try:
        import requests

        r = requests.get("http://127.0.0.1:7897/", timeout=5)
        check(r.status_code == 200, "RVC WebUI 服务在线")
    except Exception:
        check(False, "RVC 服务未运行", "弥娅点歌时会自动拉起, 或手动运行 start_api.bat")

    # 7. 本地音乐库
    print("\n[7] 本地音乐库 (本地音源)")
    dirs = builtin.get("source_config", {}).get("input_dirs", [])
    total = 0
    for d in dirs:
        exists = os.path.isdir(d)
        n = len(os.listdir(d)) if exists else 0
        total += n
        check(exists, d, f"{n} 个文件" if exists else "不存在 (自动创建)")
    if total == 0:
        print("  (提示: 无本地歌曲, 可放入 mp3 或依赖网易云/B站音源)")

    print("\n=== 自检完成 ===")
    if _fail_count:
        print(f"共 {_fail_count} 项未通过 — 按上面 ✗ 提示补齐即可。")
    else:
        print("全部通过! 唱歌模块可以正常点歌了。")
    print("提示: paths 节默认留空自动探测 (项目父目录/各盘符/AIvoice 等常见位置); 仅当整合包在非常规位置时才需填写。")
    return 1 if _fail_count else 0


if __name__ == "__main__":
    sys.exit(main())
