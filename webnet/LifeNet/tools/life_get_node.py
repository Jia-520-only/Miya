"""LifeNet 获取节点详情工具"""


async def execute(args, context):
    """获取节点详情
    
    参数:
        name: 节点名称（必填）
    
    返回:
        节点详情
    """
    life_net = context.get("lifenet")
    if not life_net:
        return "❌ LifeNet 未初始化"
    
    name = args.get("name", "")
    if not name:
        return "❌ 请提供节点名称"
    
    result = await life_net.handle_tool_call(
        "life_get_node",
        {"name": name},
        context
    )
    
    return result
