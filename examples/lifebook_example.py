"""LifeBook 记忆管理系统 - 使用示例

演示如何使用整合进弥娅的 LifeBook 功能
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from webnet.LifeNet.subnet import LifeSubnet


async def main():
    """主函数 - LifeBook 使用示例"""

    print("=" * 60)
    print("LifeBook 记忆管理系统 - 使用示例")
    print("=" * 60)
    print()

    # 初始化 LifeNet
    life = LifeSubnet()
    context = {"lifenet": life}

    # 示例 1: 添加日记
    print("【示例 1】添加日记")
    print("-" * 60)
    result = await life.handle_tool_call(
        "life_add_diary",
        {
            "content": "今天是个好日子，天气晴朗，心情也很好。上午完成了项目代码，中午和同事一起吃了火锅，下午看了会书，晚上和朋友视频聊天。",
            "mood": "开心",
            "tags": ["#工作", "#生活", "#开心"]
        },
        context
    )
    print(result)
    print()

    # 示例 2: 创建角色节点
    print("【示例 2】创建角色节点")
    print("-" * 60)
    result = await life.handle_tool_call(
        "life_create_character_node",
        {
            "name": "张三",
            "description": "我的大学同学，现在在同一个公司工作，性格开朗，喜欢打篮球。",
            "tags": ["#朋友", "#同事", "#大学"]
        },
        context
    )
    print(result)
    print()

    # 示例 3: 创建阶段节点
    print("【示例 3】创建阶段节点")
    print("-" * 60)
    result = await life.handle_tool_call(
        "life_create_stage_node",
        {
            "name": "参加工作",
            "description": "2025年2月加入A公司，开始职业生涯。",
            "tags": ["#工作", "#人生阶段"]
        },
        context
    )
    print(result)
    print()

    # 示例 4: 列出所有节点
    print("【示例 4】列出所有节点")
    print("-" * 60)
    result = await life.handle_tool_call(
        "life_list_nodes",
        {},
        context
    )
    print(result)
    print()

    # 示例 5: 获取日记
    print("【示例 5】获取今天的日记")
    print("-" * 60)
    result = await life.handle_tool_call(
        "life_get_diary",
        {},
        context
    )
    print(result)
    print()

    # 示例 6: 添加周记
    print("【示例 6】添加周记")
    print("-" * 60)
    result = await life.handle_tool_call(
        "life_add_summary",
        {
            "level": "weekly",
            "title": "2025年第9周总结",
            "content": """## 本周回顾

这周工作很充实，完成了多个项目的开发。

### 工作方面
- 完成了项目A的核心功能
- 参与了代码审查，学习了新的设计模式
- 和团队配合默契，项目进展顺利

### 生活方面
- 周中和朋友一起吃了火锅
- 看了一本好书，收获很大
- 坚持了运动，身体状态不错

### 下周计划
- 继续推进项目B的开发
- 学习新的技术栈
- 多和朋友交流
""",
            "capsule": "充实的一周，工作生活平衡，收获满满"
        },
        context
    )
    print(result)
    print()

    # 示例 7: 搜索记忆
    print("【示例 7】搜索记忆")
    print("-" * 60)
    result = await life.handle_tool_call(
        "life_search_memory",
        {
            "keyword": "开心",
            "limit": 3
        },
        context
    )
    print(result)
    print()

    # 示例 8: 一键获取记忆上下文（核心功能）
    print("【示例 8】一键获取记忆上下文（核心功能）")
    print("-" * 60)
    result = await life.handle_tool_call(
        "life_get_memory_context",
        {
            "months_back": 1,
            "include_nodes": True
        },
        context
    )
    print(result)
    print()

    # 示例 9: 获取周记
    print("【示例 9】获取周记")
    print("-" * 60)
    result = await life.handle_tool_call(
        "life_get_summary",
        {
            "level": "weekly",
            "period": "2025-W09"
        },
        context
    )
    print(result)
    print()

    print("=" * 60)
    print("所有示例运行完成！")
    print("=" * 60)
    print()
    print("💡 提示：")
    print("  1. 所有数据保存在 data/lifebook/ 目录")
    print("  2. 你可以查看 data/lifebook/daily/ 等目录中的 Markdown 文件")
    print("  3. 参考 docs/LIFEBOOK_INTEGRATION.md 了解更多用法")
    print()


if __name__ == "__main__":
    asyncio.run(main())
