"""LifeNet 搜索记忆工具"""


async def execute(args, context):
    """搜索记忆
    
    参数:
        keyword: 关键词（必填）
        level: 层级过滤（可选，可选：daily/weekly/monthly/quarterly/yearly）
        limit: 结果数量限制（可选，默认 5）
    
    返回:
        搜索结果
    """
    life_net = context.get("lifenet")
    if not life_net:
        return "❌ LifeNet 未初始化"
    
    keyword = args.get("keyword", "")
    if not keyword:
        return "❌ 请提供搜索关键词"
    
    level = args.get("level")
    limit = args.get("limit", 5)
    
    result = await life_net.handle_tool_call(
        "life_search_memory",
        {"keyword": keyword, "level": level, "limit": limit},
        context
    )
    
    return result
