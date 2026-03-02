"""LifeNet 获取日记工具"""


async def execute(args, context):
    """获取日记
    
    参数:
        date: 日期（可选，格式：YYYY-MM-DD，默认为今天）
    
    返回:
        日记内容
    """
    life_net = context.get("lifenet")
    if not life_net:
        return "❌ LifeNet 未初始化"
    
    date = args.get("date")
    
    result = await life_net.handle_tool_call(
        "life_get_diary",
        {"date": date},
        context
    )
    
    return result
