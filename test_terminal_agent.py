"""
测试终端代理连接
用于验证弥娅Web API是否正常工作并可以被终端代理访问
"""
import asyncio
import aiohttp
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def test_api_connection():
    """测试API连接"""
    ports_to_try = [8000, 8080, 8001, 8888]
    host = "localhost"

    print("=" * 60)
    print("弥娅终端代理连接测试")
    print("=" * 60)

    for port in ports_to_try:
        print(f"\n测试端口 {port}...")

        # 测试 /status 端点
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://{host}:{port}/status"
                print(f"  - 尝试连接: {url}")

                async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        print(f"  ✅ 成功连接！")
                        print(f"     状态: {data.get('status')}")
                        print(f"     数据: {data}")

                        # 测试 /terminal/chat 端点
                        print(f"\n  - 测试聊天端点: http://{host}:{port}/terminal/chat")
                        chat_url = f"http://{host}:{port}/terminal/chat"
                        chat_payload = {
                            "message": "ping",
                            "session_id": "test",
                            "from_terminal": "test"
                        }

                        async with session.post(
                            chat_url,
                            json=chat_payload,
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as chat_resp:
                            if chat_resp.status == 200:
                                chat_data = await chat_resp.json()
                                print(f"  ✅ 聊天端点正常！")
                                print(f"     响应: {chat_data.get('response', 'N/A')}")
                                return port
                            else:
                                print(f"  ❌ 聊天端点返回错误: {chat_resp.status}")
                    else:
                        print(f"  ❌ 状态码: {resp.status}")
        except Exception as e:
            print(f"  ❌ 连接失败: {str(e)}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    print("\n提示:")
    print("1. 如果所有端口都连接失败，请确保弥娅主程序已启动")
    print("2. 检查弥娅主程序启动日志中的端口号")
    print("3. 确认防火墙允许本地连接")
    print("4. 查看 docs/TERMINAL_AGENT_SETUP.md 了解详细配置")

    return None


async def test_all_api_endpoints():
    """测试所有API端点"""
    port = 8000
    host = "localhost"

    print("\n" + "=" * 60)
    print(f"测试弥娅Web API (端口 {port})")
    print("=" * 60)

    endpoints = [
        ("/status", "GET", "系统状态"),
        ("/chat", "POST", "聊天接口"),
        ("/terminal/chat", "POST", "终端聊天"),
        ("/terminal/execute", "POST", "终端执行"),
        ("/desktop/terminal/execute", "POST", "桌面终端执行"),
    ]

    async with aiohttp.ClientSession() as session:
        for path, method, name in endpoints:
            url = f"http://{host}:{port}{path}"
            print(f"\n测试 {name} ({method} {path})...")

            try:
                if method == "GET":
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                        print(f"  状态码: {resp.status}")
                        if resp.status == 200:
                            print(f"  ✅ 端点正常")
                else:  # POST
                    async with session.post(url, json={}, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                        print(f"  状态码: {resp.status}")
                        if resp.status == 200:
                            print(f"  ✅ 端点正常")
            except Exception as e:
                print(f"  ❌ 错误: {str(e)}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    print("\n选择测试模式:")
    print("1. 测试终端代理连接")
    print("2. 测试所有API端点")
    print("0. 退出")

    choice = input("\n请选择 (0-2): ").strip()

    if choice == "1":
        asyncio.run(test_api_connection())
    elif choice == "2":
        asyncio.run(test_all_api_endpoints())
    else:
        print("退出")
