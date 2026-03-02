"""LifeNet 创建角色节点工具"""


async def execute(args, context):
    """创建角色节点
    
    参数:
        name: 角色名称（必填）
        description: 描述（可选）
        tags: 标签列表（可选，如 ["#家人", "#重要"]）
    
    返回:
        结果消息
    """
    life_net = context.get("lifenet")
    if not life_net:
        return "❌ LifeNet 未初始化"
    
    name = args.get("name", "")
    if not name:
        return "❌ 请提供角色名称"
    
    description = args.get("description", "")
    tags = args.get("tags")
    
    result = await life_net.handle_tool_call(
        "life_create_character_node",
        {"name": name, "description": description, "tags": tags},
        context
    )
    
    return result
