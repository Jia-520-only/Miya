"""LifeNet 获取记忆上下文工具"""


async def execute(args, context):
    """一键获取记忆上下文
    
    这是 LifeBook 的核心功能，根据时间滚动获取记忆：
    - 年度总结（长期记忆）
    - 季度总结
    - 月度总结（中期记忆）
    - 周度总结
    - 最近日记（短期记忆）
    - 关键人物与阶段节点
    
    参数:
        months_back: 回溯月数（可选，默认 1）
        include_nodes: 是否包含节点信息（可选，默认 True）
    
    返回:
        记忆上下文文本
    """
    life_net = context.get("lifenet")
    if not life_net:
        return "❌ LifeNet 未初始化"
    
    months_back = args.get("months_back", 1)
    include_nodes = args.get("include_nodes", True)
    
    result = await life_net.handle_tool_call(
        "life_get_memory_context",
        {"months_back": months_back, "include_nodes": include_nodes},
        context
    )
    
    return result
