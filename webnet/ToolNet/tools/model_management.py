"""
模型管理工具 - 让弥娅自主调用和配置模型池

功能：
1. 查看可用模型列表
2. 查看模型配置
3. 动态选择模型
4. 修改模型路由策略

符合 MIYA 框架：
- 稳定：职责单一，错误处理完善
- 独立：依赖明确，模块解耦
- 可维修：代码清晰，易于扩展
- 故障隔离：执行失败不影响系统
"""
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from webnet.tools.base import BaseTool, ToolContext


class ModelManagementTool(BaseTool):
    """
    模型管理工具

    让弥娅可以自主调用和配置模型池中的模型
    """

    def __init__(self):
        super().__init__()
        self.name = "model_management"
        self.logger = logging.getLogger("Tool.ModelManagement")
        
        # 加载配置文件
        self._model_config = self._load_config()
        
        # 工具配置（OpenAI Function Calling 格式）
        self._tool_config = {
            "name": "model_management",
            "description": """管理AI模型池的查看和配置。弥娅可以自主查看可用模型、修改路由策略、查看使用统计。

可用操作：
- list_models: 列出所有可用模型及其能力
- get_model_info: 获取指定模型的详细信息（需要参数：model_key）
- list_strategies: 列出所有任务类型的路由策略
- get_strategy: 获取指定任务类型的路由策略（需要参数：task_type）

任务类型：
- simple_chat: 简单对话
- complex_reasoning: 复杂推理
- code_analysis: 代码分析
- code_generation: 代码生成
- tool_calling: 工具调用
- creative_writing: 创意写作
- chinese_understanding: 中文理解
- summarization: 摘要总结
- multimodal: 多模态
- task_planning: 任务规划

示例用法：
- 查看所有模型：model_management(action='list_models')
- 查看模型信息：model_management(action='get_model_info', model_key='qwen_72b')
- 查看路由策略：model_management(action='list_strategies')
- 查看策略详情：model_management(action='get_strategy', task_type='tool_calling')""",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "list_models",
                            "get_model_info",
                            "list_strategies",
                            "get_strategy"
                        ],
                        "description": "要执行的操作类型"
                    },
                    "model_key": {
                        "type": "string",
                        "description": "模型键名（get_model_info时必填，例如：qwen_72b, deepseek_v3_official）"
                    },
                    "task_type": {
                        "type": "string",
                        "description": "任务类型（get_strategy时必填，例如：tool_calling, code_generation）"
                    }
                },
                "required": ["action"]
            }
        }

    def _load_config(self) -> Dict:
        """加载配置文件"""
        try:
            # 计算正确的配置路径
            project_root = Path(__file__).parent.parent.parent.parent
            config_path = project_root / 'config' / 'multi_model_config.json'
            if config_path.exists():
                import json
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                self.logger.warning(f"配置文件不存在: {config_path}")
                return {}
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {e}")
            return {}

    @property
    def config(self) -> Dict[str, Any]:
        """工具配置（OpenAI Function Calling 格式）"""
        return self._tool_config

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """
        执行模型管理操作

        Args:
            args: 工具参数
            context: 执行上下文

        Returns:
            执行结果字符串
        """
        action = args.get("action", "")

        if not action:
            return "❌ 缺少action参数"

        try:
            if action == "list_models":
                return await self._list_models()
            elif action == "get_model_info":
                return await self._get_model_info(args)
            elif action == "list_strategies":
                return await self._list_strategies()
            elif action == "get_strategy":
                return await self._get_strategy(args)
            else:
                return f"❌ 未知的操作: {action}"

        except Exception as e:
            self.logger.error(f"执行操作失败: {e}", exc_info=True)
            return f"❌ 操作执行失败: {str(e)}"

    async def _list_models(self) -> str:
        """列出所有可用模型"""
        try:
            models_config = self._model_config.get('models', {})

            if not models_config:
                return "📊 当前没有配置的模型"

            result = "📊 可用模型列表\n\n"

            for model_key, model_info in models_config.items():
                result += f"【{model_key}】\n"
                result += f"  模型名称: {model_info.get('name', 'N/A')}\n"
                result += f"  提供商: {model_info.get('provider', 'N/A')}\n"
                result += f"  API地址: {model_info.get('base_url', 'N/A')}\n"
                result += f"  描述: {model_info.get('description', 'N/A')}\n"
                result += f"  能力: {', '.join(model_info.get('capabilities', []))}\n"
                result += f"  延迟: {model_info.get('latency', 'N/A')}\n"
                result += f"  质量: {model_info.get('quality', 'N/A')}\n"
                cost = model_info.get('cost_per_1k_tokens', {})
                result += f"  成本: 输入 ${cost.get('input', 0)}/1k tokens, 输出 ${cost.get('output', 0)}/1k tokens\n\n"

            result += f"总计: {len(models_config)} 个模型"
            return result

        except Exception as e:
            return f"❌ 获取模型列表失败: {str(e)}"

    async def _get_model_info(self, args: Dict[str, Any]) -> str:
        """获取模型详细信息"""
        model_key = args.get("model_key")

        if not model_key:
            return "❌ 缺少model_key参数"

        models_config = self._model_config.get('models', {})
        model_info = models_config.get(model_key)

        if not model_info:
            return f"❌ 未找到模型: {model_key}\n\n可用模型: {', '.join(models_config.keys())}"

        result = f"📊 模型详细信息\n\n"
        result += f"【{model_key}】\n"
        result += f"  模型名称: {model_info.get('name', 'N/A')}\n"
        result += f"  提供商: {model_info.get('provider', 'N/A')}\n"
        result += f"  API地址: {model_info.get('base_url', 'N/A')}\n"
        result += f"  描述: {model_info.get('description', 'N/A')}\n"
        result += f"  能力: {', '.join(model_info.get('capabilities', []))}\n"
        result += f"  延迟: {model_info.get('latency', 'N/A')}\n"
        result += f"  质量: {model_info.get('quality', 'N/A')}\n"
        cost = model_info.get('cost_per_1k_tokens', {})
        result += f"  成本: 输入 ${cost.get('input', 0)}/1k tokens, 输出 ${cost.get('output', 0)}/1k tokens"

        return result

    async def _list_strategies(self) -> str:
        """列出所有路由策略"""
        try:
            strategies = self._model_config.get('routing_strategy', {})

            if not strategies:
                return "🗺 当前没有配置的路由策略"

            result = "🗺 路由策略列表\n\n"

            for task_type, strategy in strategies.items():
                result += f"【{task_type}】\n"
                result += f"  首选: {strategy.get('primary', 'N/A')}\n"
                result += f"  次选: {strategy.get('secondary', 'N/A')}\n"
                result += f"  回退: {strategy.get('fallback', 'N/A')}\n"
                result += f"  成本优先级: {strategy.get('cost_priority', 'N/A')}\n"
                result += f"  速度优先级: {strategy.get('speed_priority', 'N/A')}\n"
                result += f"  质量优先级: {strategy.get('quality_priority', 'N/A')}\n\n"

            result += f"总计: {len(strategies)} 种任务类型"
            return result

        except Exception as e:
            return f"❌ 获取路由策略失败: {str(e)}"

    async def _get_strategy(self, args: Dict[str, Any]) -> str:
        """获取指定任务类型的路由策略"""
        task_type = args.get("task_type")

        if not task_type:
            return "❌ 缺少task_type参数"

        strategies = self._model_config.get('routing_strategy', {})
        strategy = strategies.get(task_type)

        if not strategy:
            return f"❌ 未找到任务类型: {task_type}\n\n可用任务类型: {', '.join(strategies.keys())}"

        result = f"🎯 任务类型: {task_type}\n\n"
        result += f"  首选模型: {strategy.get('primary', 'N/A')}\n"
        result += f"  次选模型: {strategy.get('secondary', 'N/A')}\n"
        result += f"  回退模型: {strategy.get('fallback', 'N/A')}\n"
        result += f"  成本优先级: {strategy.get('cost_priority', 'N/A')}\n"
        result += f"  速度优先级: {strategy.get('speed_priority', 'N/A')}\n"
        result += f"  质量优先级: {strategy.get('quality_priority', 'N/A')}"

        return result

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """验证参数"""
        action = args.get("action")

        if not action:
            return False, "缺少必填参数: action"

        if action == "get_model_info" and not args.get("model_key"):
            return False, "get_model_info 需要 model_key 参数"

        if action == "get_strategy" and not args.get("task_type"):
            return False, "get_strategy 需要 task_type 参数"

        return True, None
