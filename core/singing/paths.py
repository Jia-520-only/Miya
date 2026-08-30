"""
唱歌模块外部路径统一解析

所有外部工具（RVC 整合包 / GPT-SoVITS / MDX 部件 / ffmpeg）的路径集中从
config/singing_config.json 的 paths 节读取；**留空时自动探测**常见安装位置，
换机器无需手改配置（除非整合包放在非常规位置）。
"""

import json
import logging
import os
import shutil
import string
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 自动探测结果缓存 (rvc / sovits → 根目录路径; 空串 = 未找到)
_detect_cache: Dict[str, str] = {}


def load_singing_paths() -> Dict[str, str]:
    """读取 singing_config.json 的 paths 节（相对项目根定位，不受 cwd 影响）"""
    candidates = [
        os.path.join(_PROJECT_ROOT, "config", "singing_config.json"),
        os.path.join(os.getcwd(), "config", "singing_config.json"),
    ]
    for cp in candidates:
        try:
            if not os.path.exists(cp):
                continue
            with open(cp, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            return cfg.get("paths", {}) or {}
        except Exception as e:
            logger.warning(f"[paths] 读取配置失败 {cp}: {e}")
    return {}


def _rvc_features(d: str) -> bool:
    """RVC 整合包特征: start_api.bat + assets/weights"""
    return os.path.exists(os.path.join(d, "start_api.bat")) and os.path.isdir(
        os.path.join(d, "assets", "weights")
    )


def _sovits_features(d: str) -> bool:
    """GPT-SoVITS 整合包特征: tools/uvr5/uvr5_weights (翻唱分离用) 或 go_api.bat + runtime"""
    return os.path.isdir(os.path.join(d, "tools", "uvr5", "uvr5_weights")) or (
        os.path.exists(os.path.join(d, "go_api.bat"))
        and os.path.exists(os.path.join(d, "runtime", "python.exe"))
    )


def _search_base_dirs() -> list:
    """构造探测搜索位置: 项目父目录/项目内 tools → 各盘符根 → 盘符下常见目录"""
    bases = [os.path.dirname(_PROJECT_ROOT)]
    tools = os.path.join(_PROJECT_ROOT, "tools")
    if os.path.isdir(tools):
        bases.append(tools)
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if not os.path.isdir(drive):
            continue
        bases.append(drive)
        for sub in ("AIvoice", "AIVoice", "AI语音", "AIVOICE", "soft", "tools"):
            p = os.path.join(drive, sub)
            if os.path.isdir(p):
                bases.append(p)
    return bases


def _detect_root(kind: str) -> str:
    """自动探测整合包根目录 (kind: 'rvc' | 'sovits')

    - 单层: 目录本身满足特征
    - 双层嵌套: 整合包常见 RVCxxx/RVCxxx 结构, 名字命中关键字时向内找一层
    结果缓存, 只扫描一次。
    """
    if kind in _detect_cache:
        return _detect_cache[kind]

    feature = _rvc_features if kind == "rvc" else _sovits_features
    keyword = "rvc" if kind == "rvc" else "sovits"
    found = ""
    for base in _search_base_dirs():
        try:
            entries = os.listdir(base)
        except OSError:
            continue
        for name in entries:
            if name.startswith("."):
                continue
            d = os.path.join(base, name)
            if not os.path.isdir(d):
                continue
            if feature(d):
                found = d
                break
            if keyword not in name.lower():
                continue
            # 双层嵌套结构
            try:
                for n2 in os.listdir(d):
                    d2 = os.path.join(d, n2)
                    if os.path.isdir(d2) and feature(d2):
                        found = d2
                        break
            except OSError:
                continue
            if found:
                break
        if found:
            break
    _detect_cache[kind] = found
    if found:
        logger.info(f"[paths] 自动探测到 {'RVC' if kind == 'rvc' else 'GPT-SoVITS'} 整合包: {found}")
    return found


def get_rvc_root() -> str:
    """RVC 整合包根目录 — 配置显式路径优先, 留空自动探测"""
    cfg = (load_singing_paths().get("rvc_root") or "").rstrip("/\\")
    if cfg and os.path.isdir(cfg):
        return cfg
    return _detect_root("rvc")


def get_gpt_sovits_root() -> str:
    """GPT-SoVITS 整合包根目录 — 配置显式路径优先, 留空自动探测"""
    cfg = (load_singing_paths().get("gpt_sovits_root") or "").rstrip("/\\")
    if cfg and os.path.isdir(cfg):
        return cfg
    return _detect_root("sovits")


def get_mdx_root() -> str:
    """MDX 分离部件根目录

    优先读配置 paths.mdx_root (支持 {rvc_root} 模板)；留空时自动探测 RVC 整合包内的
    mdx/ 子目录 (推荐布局: 把 MDX 分离 runtime + 模型放进 {rvc_root}/mdx/, 随 RVC 整合包一起分发)。
    """
    cfg_root = (load_singing_paths().get("mdx_root") or "").rstrip("/\\")
    if cfg_root:
        rvc = get_rvc_root()
        cfg_root = cfg_root.replace("{rvc_root}", rvc or "")
        return cfg_root
    rvc = get_rvc_root()
    if rvc:
        cand = os.path.join(rvc, "mdx")
        if os.path.isdir(os.path.join(cand, "runtime")) or os.path.isdir(os.path.join(cand, "models")):
            return cand
    return ""


def expand_path(path: str, extra: Optional[Dict[str, str]] = None) -> str:
    """路径模板展开：{rvc_root} / {gpt_sovits_root} / {mdx_root}

    两轮替换以支持嵌套模板 (如 mdx_root = "{rvc_root}/mdx")。
    """
    if not path:
        return ""
    mapping = {
        "{rvc_root}": get_rvc_root(),
        "{gpt_sovits_root}": get_gpt_sovits_root(),
        "{mdx_root}": get_mdx_root(),
    }
    if extra:
        mapping.update(extra)
    for _ in range(2):
        for k, v in mapping.items():
            path = path.replace(k, v or "")
    return path


def find_ffmpeg() -> str:
    """统一 ffmpeg 探测：配置 > RVC 根目录/ffmpeg 子目录 > 系统 PATH"""
    paths = load_singing_paths()
    cfg_ffmpeg = expand_path(paths.get("ffmpeg", ""))
    if cfg_ffmpeg and os.path.exists(cfg_ffmpeg):
        return cfg_ffmpeg

    rvc = get_rvc_root()
    if rvc:
        for c in (
            os.path.join(rvc, "ffmpeg.exe"),
            os.path.join(rvc, "ffmpeg", "ffmpeg.exe"),
        ):
            if os.path.exists(c):
                return c

    found = shutil.which("ffmpeg")
    return found or "ffmpeg"


def resolve_runtime_python(root: str, explicit: str, fallback: str = "") -> str:
    """解析整合包 runtime python：显式配置 > {root}/runtime/python.exe > 系统 python"""
    if explicit and os.path.exists(explicit):
        return explicit
    if root:
        cand = os.path.join(root, "runtime", "python.exe")
        if os.path.exists(cand):
            return cand
    return fallback or "python"


def env_report() -> Dict[str, object]:
    """环境自检报告：供 singing_env_check 脚本使用"""
    paths = load_singing_paths()
    rvc = get_rvc_root()
    sovits = get_gpt_sovits_root()
    ffmpeg = find_ffmpeg()
    return {
        "rvc_root": rvc,
        "rvc_exists": bool(rvc) and os.path.isdir(rvc),
        "rvc_launch_bat": os.path.join(rvc, "start_api.bat") if rvc else "",
        "rvc_weights_dir": os.path.join(rvc, "assets", "weights") if rvc else "",
        "gpt_sovits_root": sovits,
        "gpt_sovits_exists": bool(sovits) and os.path.isdir(sovits),
        "ffmpeg": ffmpeg,
        "ffmpeg_ok": os.path.exists(ffmpeg) or (ffmpeg != "ffmpeg"),
        "paths_cfg": paths,
    }


def _ensure_ffmpeg_in_path():
    """把探测到的 ffmpeg 所在目录注入 PATH（pydub 等依赖 PATH 找 ffmpeg）"""
    try:
        ffmpeg = find_ffmpeg()
        d = os.path.dirname(ffmpeg)
        if d and os.path.isdir(d):
            env_path = os.environ.get("PATH", "")
            if d not in env_path:
                os.environ["PATH"] = d + os.pathsep + env_path
    except Exception:
        pass


_ensure_ffmpeg_in_path()
