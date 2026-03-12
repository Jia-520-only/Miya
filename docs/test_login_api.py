"""
测试登录 API
"""
import requests
import json

print("=" * 60)
print("测试登录 API")
print("=" * 60)

url = "http://localhost:8000/api/auth/login"
payload = {
    "username": "admin",
    "password": "admin123"
}

print(f"\n请求 URL: {url}")
print(f"请求数据: {json.dumps(payload, indent=2)}")

try:
    response = requests.post(url, json=payload, timeout=5)
    print(f"\n响应状态码: {response.status_code}")

    result = response.json()
    print(f"\n响应数据:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if result.get("success"):
        print("\n✓ 登录成功!")
        print(f"  用户名: {result['user']['username']}")
        print(f"  权限等级: {result['user']['level']}")
        print(f"  Token (前50字符): {result['token'][:50]}...")
    else:
        print(f"\n✗ 登录失败: {result.get('message')}")

except requests.exceptions.ConnectionError:
    print("\n✗ 无法连接到后端服务器")
    print("  请确保后端服务器正在运行 (http://localhost:8000)")
except Exception as e:
    print(f"\n✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
