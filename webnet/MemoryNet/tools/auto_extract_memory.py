"""
自动提取重要信息并存储为长期记忆

此工具由弥娅自动调用，用于从对话中提取重要信息并存储为长期记忆
"""
from typing import Dict, Any
import logging
from webnet.tools.base import BaseTool, ToolContext
from datetime import datetime

logger = logging.getLogger(__name__)


class AutoExtractMemory(BaseTool):
    """自动提取记忆工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "auto_extract_memory",
            "description": """自动从对话中提取重要信息并存储为长期记忆。当用户分享个人信息（如喜好、生日、联系方式等）、重要事件、或明确要求弥娅记住某些事情时，必须调用此工具。

重要信息包括但不限于：
- 个人偏好：喜欢的颜色、食物、音乐、电影、游戏等
- 个人信息：生日、星座、年龄、姓名等
- 重要事件：重要日期、纪念日、计划事项等
- 明确的记忆请求：用户说"记住..."、"你记着..."等

注意事项：
- 只存储用户明确提供的重要信息，不要过度提取
- 标签应该简洁明了，便于后续检索
- 事实描述应该准确，不要添加AI的主观猜测""",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {
                        "type": "string",
                        "description": "需要记住的事实或信息，准确描述用户分享的内容。例如：'用户喜欢青色'、'用户生日是2000年1月1日'、'用户计划下周去旅游'"
                    },
                    "tags": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "标签列表，用于分类和检索。例如：['喜好', '颜色']、['个人信息', '生日']、['计划', '旅游']"
                    },
                    "importance": {
                        "type": "number",
                        "description": "重要性评分（0-1），默认0.7。个人信息和明确要求的记忆应设为0.9，一般喜好设为0.7，次要信息设为0.5",
                        "default": 0.7,
                        "minimum": 0,
                        "maximum": 1
                    }
                },
                "required": ["fact", "tags"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具 - 提取并存储记忆"""
        fact = args.get("fact", "")
        tags = args.get("tags", [])
        importance = args.get("importance", 0.7)

        if not fact:
            return "❌ 缺少必须的参数：fact（事实内容）"

        if not tags:
            return "⚠️ 建议提供标签以便后续检索，但已使用默认标签 ['通用']"
            tags = ['通用']

        try:
            # 优先使用 Undefined 轻量记忆系统
            try:
                from memory.undefined_memory import get_undefined_memory_adapter
                adapter = get_undefined_memory_adapter()

                await adapter.create(
                    fact=fact,
                    tags=tags,
                    importance=importance
                )

                result = f"✅ 已记住：{fact}\n"
                result += f"   标签: {', '.join(tags)}\n"
                result += f"   重要性: {importance:.1f}"
                return result

            except ImportError:
                logger.debug("Undefined 记忆系统不可用，尝试其他记忆系统")
            except Exception as e:
                logger.error(f"调用 Undefined 记忆系统失败: {e}", exc_info=True)

            # 回退到记忆引擎
            memory_engine = context.memory_engine
            if memory_engine and hasattr(memory_engine, 'store_dream'):
                memory_id = f"memory_{datetime.now().timestamp()}"
                memory_engine.store_dream(
                    memory_id,
                    {
                        'content': fact,
                        'tags': tags,
                        'importance': importance,
                        'type': 'long_term',
                        'timestamp': datetime.now().isoformat()
                    }
                )

                return f"✅ 已记住（记忆引擎）：{fact}\n标签: {', '.join(tags)}"

            # 都不可用
            return "⚠️ 记忆系统未初始化，无法保存长期记忆"

        except Exception as e:
            logger.error(f"存储记忆失败: {e}", exc_info=True)
            return f"❌ 存储记忆失败: {str(e)}"

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Any]:
        """验证参数"""
        fact = args.get("fact", "")
        tags = args.get("tags", [])
        importance = args.get("importance", 0.7)

        if not fact:
            return False, "缺少必填参数: fact（事实内容）"

        if not isinstance(tags, list):
            return False, "tags 参数必须是数组"

        if importance < 0 or importance > 1:
            return False, "importance 参数必须在 0 到 1 之间"

        return True, None
