"""
验证弥娅工具注册
检查wsl_manager等工具是否正确注册
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from webnet.ToolNet import get_tool_registry


def main():
    print("=" * 60)
    print("弥娅工具注册验证")
    print("=" * 60)

    # 获取工具注册表
    subnet = get_tool_registry()
    registry = subnet

    # 列出所有工具
    all_tools = list(registry.tools.keys())
    all_tools.sort()

    print(f"\n总共注册了 {len(all_tools)} 个工具\n")

    # 查找WSL相关工具
    wsl_tools = [t for t in all_tools if 'wsl' in t.lower()]

    if wsl_tools:
        print("[OK] Found WSL tools:")
        for tool in wsl_tools:
            print(f"  - {tool}")
    else:
        print("[ERROR] WSL tools not found")

    # 查找终端相关工具
    terminal_tools = [t for t in all_tools if 'terminal' in t.lower()]

    if terminal_tools:
        print(f"\n[OK] Found terminal tools ({len(terminal_tools)}):")
        for tool in terminal_tools:
            print(f"  - {tool}")
    else:
        print("[ERROR] Terminal tools not found")

    # 显示所有工具
    print("\n所有已注册的工具:")
    for i, tool in enumerate(all_tools, 1):
        if i % 5 == 0:
            print()
        print(f"  {i:2d}. {tool}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
