"""
QQ图片分析工具 handler
"""

import logging
from typing import Any, Dict, Union

from webnet.ToolNet.tools.qq.qq_image_analyzer import QQImageAnalyzerTool

logger = logging.getLogger(__name__)


async def execute(args: Union[Dict[str, Any], Any], context: Any = None) -> str:
    """分析QQ图片 - 兼容两种调用方式

    Args:
        args: 可以是 kwargs dict 或 context (当作为第一参数时)
        context: 上下文对象

    调用方式1 (registry): execute(kwargs_dict, context)
    调用方式2 (直接): execute(context, image_url=...)
    """
    try:
        tool = QQImageAnalyzerTool()

        # 兼容处理：根据参数类型判断调用方式
        if isinstance(args, dict) and context is not None:
            # 方式1: execute(args, context) - registry 风格
            # args 是 kwargs，context 是 context
            actual_args = args
            actual_context = context
        elif isinstance(args, dict) and context is None:
            # 只有 argsdict，没有 context
            actual_args = args
            actual_context = None
        else:
            # args 本身就是 context
            actual_context = args
            actual_args = context if isinstance(context, dict) else {}

        logger.info(f"[qq_image_analyzer handler] args: {actual_args}, context type: {type(actual_context)}")

        # 调用工具
        result = await tool.execute(actual_context, **actual_args)
        return result
    except Exception as e:
        logger.error(f"图片分析失败: {e}")
        return f"图片分析失败: {str(e)}"
