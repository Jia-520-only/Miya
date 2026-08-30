"""
强制修复 JWT 问题并重启后端
"""
import subprocess
import sys
import time
import os

print("=" * 60)
print("强制修复 JWT 并重启后端")
print("=" * 60)

# 1. 检查 pyjwt 是否安装
print("\n[1/4] 检查 PyJWT 安装状态...")
try:
    import jwt
    print(f"     ✓ PyJWT 已安装 (版本: {jwt.__version__})")
except ImportError:
    print("     ✗ PyJWT 未安装,正在安装...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyjwt>=2.8.0"])
    print("     ✓ PyJWT 安装完成")

# 2. 停止所有 Python 进程
print("\n[2/4] 停止所有 Python 进程...")
try:
    # Windows 命令
    subprocess.run("taskkill /F /IM python.exe", shell=True, check=False)
    subprocess.run("taskkill /F /IM pythonw.exe", shell=True, check=False)
    print("     ✓ Python 进程已停止")
except Exception as e:
    print(f"     ⚠ 停止进程时出错: {e}")

# 3. 等待进程完全结束
print("\n[3/4] 等待进程完全结束...")
time.sleep(3)
print("     ✓ 等待完成")

# 4. 启动后端服务器
print("\n[4/4] 启动后端服务器...")
print("     正在启动,请稍等...")
print()

try:
    os.chdir(r"d:\AI_MIYA_Facyory\MIYA\Miya")
    subprocess.run([sys.executable, "run/web_main.py"])
except KeyboardInterrupt:
    print("\n\n✓ 后端服务器已停止")
except Exception as e:
    print(f"\n✗ 启动失败: {e}")
    sys.exit(1)
