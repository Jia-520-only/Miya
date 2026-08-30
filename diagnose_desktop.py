"""
诊断和修复弥娅桌面端启动问题
"""
import subprocess
import sys
import time
import os

def check_port(port):
    """检查端口是否被占用"""
    try:
        result = subprocess.run(
            ['netstat', '-ano'],
            capture_output=True,
            text=True,
            timeout=5
        )
        for line in result.stdout.split('\n'):
            if f':{port}' in line and 'LISTENING' in line:
                parts = line.split()
                if len(parts) >= 5:
                    return parts[-1]  # PID
        return None
    except Exception as e:
        print(f"检查端口 {port} 失败: {e}")
        return None

def kill_process(pid):
    """终止进程"""
    try:
        subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                      capture_output=True, timeout=5)
        print(f"✅ 已终止进程 {pid}")
        return True
    except Exception as e:
        print(f"❌ 终止进程 {pid} 失败: {e}")
        return False

def check_ports():
    """检查关键端口"""
    print("\n=== 检查端口占用 ===")
    ports = [8000, 5173, 3000, 7687, 6379]

    for port in ports:
        pid = check_port(port)
        if pid:
            print(f"⚠️  端口 {port} 被进程 {pid} 占用")
        else:
            print(f"✅ 端口 {port} 可用")

def cleanup_ports():
    """清理占用的端口"""
    print("\n=== 清理端口占用 ===")
    ports = [8000, 5173]

    for port in ports:
        pid = check_port(port)
        if pid:
            print(f"\n清理端口 {port} (进程 {pid})")
            kill_process(pid)
            time.sleep(1)

def test_api():
    """测试 API 端点"""
    print("\n=== 测试 API 端点 ===")

    import requests

    endpoints = [
        "http://127.0.0.1:8000/health",
        "http://127.0.0.1:8000/api/status",
        "http://127.0.0.1:8000/api/emotion",
        "http://127.0.0.1:8000/api/chat"
    ]

    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, timeout=2)
            print(f"✅ {endpoint} - {response.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"❌ {endpoint} - 连接失败")
        except Exception as e:
            print(f"⚠️  {endpoint} - {e}")

def main():
    print("=" * 60)
    print("弥娅桌面端诊断工具")
    print("=" * 60)

    # 1. 检查端口
    check_ports()

    # 2. 清理端口
    print("\n是否要清理占用的端口 (8000, 5173)?")
    choice = input("输入 'y' 继续，其他键跳过: ").strip().lower()

    if choice == 'y':
        cleanup_ports()

    # 3. 测试 API
    print("\n是否要测试 API 端点 (需要服务已启动)?")
    choice = input("输入 'y' 继续，其他键跳过: ").strip().lower()

    if choice == 'y':
        test_api()

    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)
    print("\n提示:")
    print("1. 如果端口被占用，请运行清理选项")
    print("2. 如果 API 无法连接，请检查后端是否启动")
    print("3. 启动命令: python run/desktop_main.py")
    print("4. 或使用启动菜单: start.bat → 选择 4")

if __name__ == '__main__':
    main()
