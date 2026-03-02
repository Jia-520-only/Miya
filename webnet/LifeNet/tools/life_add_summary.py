"""LifeNet 添加总结工具"""


async def execute(args, context):
    """添加总结（周/月/季/年）
    
    参数:
        level: 层级（必填，可选：weekly/monthly/quarterly/yearly）
        title: 标题（必填）
        content: 内容（必填）
        capsule: 胶囊摘要（可选，一句话概括）
    
    返回:
        结果消息
    """
    life_net = context.get("lifenet")
    if not life_net:
        return "❌ LifeNet 未初始化"
    
    level = args.get("level", "")
    if not level:
        return "❌ 请提供总结层级（weekly/monthly/quarterly/yearly）"
    
    title = args.get("title", "")
    if not title:
        return "❌ 请提供标题"
    
    content = args.get("content", "")
    if not content:
        return "❌ 请提供内容"
    
    capsule = args.get("capsule")
    
    result = await life_net.handle_tool_call(
        "life_add_summary",
        {"level": level, "title": title, "content": content, "capsule": capsule},
        context
    )
    
    return result
