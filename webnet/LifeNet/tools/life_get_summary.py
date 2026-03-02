"""LifeNet 获取总结工具"""


async def execute(args, context):
    """获取总结
    
    参数:
        level: 层级（必填，可选：weekly/monthly/quarterly/yearly）
        period: 周期（必填，如：2025-W03, 2025-01, 2025-Q1, 2025）
    
    返回:
        总结内容
    """
    life_net = context.get("lifenet")
    if not life_net:
        return "❌ LifeNet 未初始化"
    
    level = args.get("level", "")
    if not level:
        return "❌ 请提供总结层级（weekly/monthly/quarterly/yearly）"
    
    period = args.get("period", "")
    if not period:
        return "❌ 请提供周期"
    
    result = await life_net.handle_tool_call(
        "life_get_summary",
        {"level": level, "period": period},
        context
    )
    
    return result
