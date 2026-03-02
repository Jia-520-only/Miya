"""LifeNet 添加日记工具"""


async def execute(args, context):
    """添加日记
    
    参数:
        content: 日记内容（必填）
        mood: 心情（可选）
        tags: 标签列表（可选，如 ["#工作", "#开心"]）
    
    返回:
        结果消息
    """
    # 获取 LifeNet 子网
    life_net = context.get("lifenet")
    if not life_net:
        return "❌ LifeNet 未初始化"
    
    content = args.get("content", "")
    if not content:
        return "❌ 请提供日记内容"
    
    mood = args.get("mood")
    tags = args.get("tags")
    
    result = await life_net.handle_tool_call(
        "life_add_diary",
        {"content": content, "mood": mood, "tags": tags},
        context
    )
    
    return result
