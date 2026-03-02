"""LifeNet 列出节点工具"""


async def execute(args, context):
    """列出节点
    
    参数:
        node_type: 节点类型（可选，character 或 stage）
    
    返回:
        节点列表
    """
    life_net = context.get("lifenet")
    if not life_net:
        return "❌ LifeNet 未初始化"
    
    node_type = args.get("node_type")
    
    result = await life_net.handle_tool_call(
        "life_list_nodes",
        {"node_type": node_type},
        context
    )
    
    return result
