"""检测当前 faiss 安装是否带 AVX2 加速模块。

用法:
    python setup/scripts/check_faiss_avx2.py
"""

from __future__ import annotations

import importlib


def main() -> int:
    try:
        import faiss
    except ImportError:
        print("[MISS] 未安装 faiss-cpu。请执行: pip install faiss-cpu")
        return 1

    print(f"[OK] faiss 基础模块已安装，版本: {getattr(faiss, '__version__', 'unknown')}")

    try:
        importlib.import_module("faiss.swigfaiss_avx2")
    except ImportError:
        print("[WARN] 当前 wheel 不包含 faiss.swigfaiss_avx2，将使用基础实现。")
        print("       建议: pip install --upgrade faiss-cpu")
        print("       若仍不支持，请改用 conda 安装 faiss-cpu 的 AVX2 构建。")
        return 2

    print("[OK] faiss AVX2 加速模块可用。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
