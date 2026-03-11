"""
验证 pyjwt 是否在虚拟环境中安装
"""
import sys
import os

print("=" * 60)
print("Python 环境信息")
print("=" * 60)
print("Python 路径:", sys.executable)
print("Python 版本:", sys.version)
print("当前工作目录:", os.getcwd())
print()

# 检查虚拟环境
if hasattr(sys, 'real_prefix'):
    print("[INFO] 检测到虚拟环境 (real_prefix)")
elif hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix:
    print("[INFO] 检测到虚拟环境 (venv)")
    print("       venv 路径:", sys.prefix)
else:
    print("[WARN] 未检测到虚拟环境,使用系统 Python")

print()

# 检查 pyjwt
try:
    import jwt
    print("[OK] PyJWT 已安装")
    print("     版本:", jwt.__version__)
    print("     路径:", jwt.__file__)
except ImportError as e:
    print("[FAIL] PyJWT 未安装或无法导入")
    print("       错误:", e)
    print()
    print("请运行: pip install pyjwt>=2.8.0")
    sys.exit(1)

print()
print("=" * 60)
print("所有检查通过!")
print("=" * 60)
