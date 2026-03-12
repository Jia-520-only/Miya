"""检查工具注册"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from webnet.ToolNet.registry import ToolRegistry

print("=== 检查工具注册 ===")

registry = ToolRegistry()
registry.load_all_tools()

print(f"\n总共注册了 {len(registry.tools)} 个工具\n")

# 查找终端相关工具
print("=== 终端相关工具 ===")
terminal_tools = [name for name in registry.tools if 'terminal' in name.lower()]
for tool_name in terminal_tools:
    tool = registry.get_tool(tool_name)
    print(f"工具名称: {tool_name}")
    if tool:
        print(f"  配置名称: {tool.config.get('name', 'N/A')}")
        print(f"  描述: {tool.config.get('description', 'N/A')[:80]}...")
    print()

# 如果没有找到终端工具，列出所有工具
if not terminal_tools:
    print("未找到终端工具，列出所有工具：")
    for i, name in enumerate(registry.tools.keys(), 1):
        print(f"{i}. {name}")
