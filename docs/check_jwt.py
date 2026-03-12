"""
检查 JWT 库是否正确安装
"""
import sys

print("Python 路径:", sys.executable)
print()

# 检查 1: 直接导入
try:
    import jwt
    print("[OK] JWT 可以直接导入")
    print("  版本:", jwt.__version__ if hasattr(jwt, '__version__') else "未知")
except ImportError as e:
    print("[FAIL] JWT 导入失败:", e)
    sys.exit(1)

print()

# 检查 2: 测试编码和解码
try:
    import jwt
    from datetime import datetime, timedelta

    # 测试编码
    payload = {
        "sub": "test",
        "level": 5,
        "exp": (datetime.utcnow() + timedelta(hours=1)).timestamp()
    }
    token = jwt.encode(payload, "secret_key", algorithm="HS256")
    print("[OK] JWT 编码成功")
    print("  Token:", token[:50] + "...")

    # 测试解码（忽略过期验证）
    decoded = jwt.decode(token, "secret_key", algorithms=["HS256"], options={"verify_exp": False})
    print("[OK] JWT 解码成功")
    print("  解码结果:", decoded)

except Exception as e:
    print("[FAIL] JWT 操作失败:", e)
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("=" * 50)
print("所有 JWT 检查通过!")
print("=" * 50)
