"""
AI客户端模块
支持多种大模型API接入和工具调用
整合弥娅人设提示词
"""
import logging
import json
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass
from pathlib import Path

from .prompt_cache import get_global_prompt_cache
from core.constants import Encoding


logger = logging.getLogger(__name__)


@dataclass
class AIMessage:
    """AI消息类"""
    role: str  # system, user, assistant, tool
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None


class BaseAIClient:
    """AI客户端基类"""

    def __init__(self, api_key: str, model: str, **kwargs):
        self.api_key = api_key
        self.model = model
        self.config = kwargs
        self.tool_registry: Optional[Callable] = None
        self.tool_context: Optional[Dict[str, Any]] = None
        self.personality = kwargs.get('personality', None)  # 人格实例
        self._miya_prompt: Optional[str] = None  # 弥娅人设提示词缓存
        self._miya_prompt_full: Optional[str] = None  # 弥娅人设完整版提示词
        self.use_compact_prompt: bool = kwargs.get('use_compact_prompt', False)  # 是否使用紧凑版提示词
        self.enable_prompt_cache: bool = kwargs.get('enable_prompt_cache', True)  # 是否启用提示词缓存
        self.prompt_cache = get_global_prompt_cache() if self.enable_prompt_cache else None

        # 尝试加载弥娅人设提示词
        self._load_miya_prompt()

    def set_tool_registry(self, tool_registry: Callable):
        """设置工具注册表

        Args:
            tool_registry: 工具注册表函数，返回工具定义列表
        """
        self.tool_registry = tool_registry

    def set_tool_context(self, context: Dict[str, Any]):
        """设置工具执行上下文

        Args:
            context: 工具执行上下文（包含 send_like_callback 等）
        """
        self.tool_context = context

    def set_personality(self, personality):
        """设置人格实例

        Args:
            personality: 人格实例
        """
        self.personality = personality

    def _load_miya_prompt(self):
        """加载弥娅人设提示词"""
        try:
            prompt_path = Path(__file__).parent.parent / 'prompts' / 'miya_personality.json'
            compact_prompt_path = Path(__file__).parent.parent / 'prompts' / 'miya_personality_compact.json'
            
            # 优先尝试加载紧凑版本（用于需要工具调用的场景）
            if compact_prompt_path.exists():
                with open(compact_prompt_path, 'r', encoding=Encoding.UTF8) as f:
                    prompt_config = json.load(f)
                self._miya_prompt = prompt_config.get('system_prompt', '')
                self._miya_prompt_full = prompt_config.get('system_prompt_full', '')
                logger.info("成功加载弥娅人设提示词（紧凑版本）")
            elif prompt_path.exists():
                with open(prompt_path, 'r', encoding=Encoding.UTF8) as f:
                    prompt_config = json.load(f)
                self._miya_prompt = prompt_config.get('system_prompt', '')
                self._miya_prompt_full = self._miya_prompt
                logger.info("成功加载弥娅人设提示词（完整版本）")
            else:
                logger.warning(f"弥娅人设提示词文件不存在：{prompt_path}")
                self._miya_prompt = ""
                self._miya_prompt_full = ""
        except Exception as e:
            logger.warning(f"加载弥娅人设提示词失败：{e}")
            self._miya_prompt = ""
            self._miya_prompt_full = ""

    def get_miya_system_prompt(self, additional_context: Optional[Dict] = None, use_full: bool = False) -> str:
        """
        获取弥娅人设系统提示词（支持缓存）

        Args:
            additional_context: 额外上下文（如 user_id 等）
            use_full: 是否使用完整版提示词（False表示使用紧凑版）

        Returns:
            完整的系统提示词
        """
        # 构建缓存上下文
        cache_context = {
            "use_full": use_full,
            "has_personality": self.personality is not None,
            "additional_context": additional_context or {}
        }

        # 添加人格状态到缓存上下文
        if self.personality:
            cache_context["personality_state"] = self.personality.get_current_state()
            cache_context["current_title"] = self.personality.get_current_title()
            cache_context["address_phrase"] = self.personality.get_address_phrase()

        # 尝试从缓存获取
        if self.prompt_cache and self.enable_prompt_cache:
            cached_prompt = self.prompt_cache.get(cache_context)
            if cached_prompt is not None:
                logger.debug("[AIClient] 提示词缓存命中")
                return cached_prompt

        # 生成提示词
        prompt = self._generate_miya_prompt(base_only=False, use_full=use_full)

        # 添加动态人格信息
        if self.personality:
            personality_desc = self.personality.get_personality_description()
            prompt += "\n\n" + personality_desc

        # 添加当前称呼信息
        if self.personality:
            current_title = self.personality.get_current_title()
            address_phrase = self.personality.get_address_phrase()
            prompt += f"\n\n【当前称呼配置】\n- 当前称呼：{current_title}\n- 开场白：{address_phrase}"

        # 替换占位符
        if additional_context:
            for key, value in additional_context.items():
                placeholder = '{' + key + '}'
                if placeholder in prompt:
                    prompt = prompt.replace(placeholder, str(value))

        # 存入缓存
        if self.prompt_cache and self.enable_prompt_cache:
            self.prompt_cache.set(cache_context, prompt)
            logger.debug("[AIClient] 提示词已缓存")

        return prompt

    def _generate_miya_prompt(self, base_only: bool = True, use_full: bool = False) -> str:
        """
        生成弥娅基础提示词

        Args:
            base_only: 是否只返回基础提示词
            use_full: 是否使用完整版

        Returns:
            基础提示词
        """
        # 选择使用完整版还是紧凑版
        if use_full and self._miya_prompt_full:
            return self._miya_prompt_full
        elif self._miya_prompt:
            return self._miya_prompt
        else:
            return ""

    async def chat(
        self,
        messages: List[AIMessage],
        tools: Optional[List[Dict]] = None,
        max_iterations: int = 10,
        use_miya_prompt: bool = True
    ) -> str:
        """
        聊天接口（支持工具调用）

        Args:
            messages: 消息列表
            tools: 可用工具列表
            max_iterations: 最大工具调用迭代次数
            use_miya_prompt: 是否使用弥娅人设提示词

        Returns:
            AI回复
        """
        # 如果启用人设提示词且消息中包含系统提示词，则替换
        if use_miya_prompt and messages and messages[0].role == "system":
            miya_prompt = self.get_miya_system_prompt()
            if miya_prompt:
                # 从系统提示词中提取上下文信息
                system_prompt = messages[0].content
                additional_context = {}
                # 提取 user_id 等占位符
                import re
                placeholders = re.findall(r'\{(\w+)\}', system_prompt)
                for ph in placeholders:
                    match = re.search(rf'\{ph}\s*[:：]\s*(\S+)', system_prompt)
                    if match:
                        additional_context[ph] = match.group(1)

                messages[0].content = miya_prompt + "\n\n" + self._extract_tools_instruction(system_prompt)

        raise NotImplementedError

    def _extract_tools_instruction(self, system_prompt: str) -> str:
        """
        从原始系统提示词中提取工具使用指令

        Args:
            system_prompt: 原始系统提示词

        Returns:
            工具使用指令
        """
        # 提取工具使用规则部分
        if "工具使用规则" in system_prompt:
            start = system_prompt.find("工具使用规则")
            end = system_prompt.find("\n\n可用工具")
            if end == -1:
                end = system_prompt.find("\n\n【游戏模式识别与处理】")
                if end == -1:
                    end = len(system_prompt)
            return system_prompt[start:end]
        return ""

    async def chat_with_system_prompt(
        self,
        system_prompt: str,
        user_message: str,
        tools: Optional[List[Dict]] = None,
        use_miya_prompt: bool = True,
        conversation_history: Optional[List[Dict]] = None,
        tool_choice: str = "auto"
    ) -> str:
        """
        使用系统提示词聊天

        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            tools: 可用工具列表
            use_miya_prompt: 是否使用弥娅人设提示词
            conversation_history: 对话历史 [{'role': 'user', 'content': '...'}, ...]
            tool_choice: 工具选择策略 ("auto", "required", "none")

        Returns:
            AI回复
        """
        # 如果启用人设提示词，则使用弥娅人设
        if use_miya_prompt:
            # 如果有工具，使用紧凑版提示词以提高工具调用准确率
            use_full = not bool(tools) or self.use_compact_prompt
            miya_prompt = self.get_miya_system_prompt(use_full=use_full)
            if miya_prompt:
                extracted = self._extract_tools_instruction(system_prompt)
                logger.debug(f"[AIClient] 提取的工具指令长度: {len(extracted)}, 提示词类型: {'完整版' if use_full else '紧凑版'}")
                system_prompt = miya_prompt + "\n\n" + extracted

        # 构建消息列表
        messages = [AIMessage(role="system", content=system_prompt)]

        # 添加对话历史
        if conversation_history:
            for msg in conversation_history:
                messages.append(AIMessage(role=msg['role'], content=msg['content']))

        # 添加当前用户消息
        messages.append(AIMessage(role="user", content=user_message))

        return await self.chat(messages, tools, use_miya_prompt=False, tool_choice=tool_choice)  # 避免重复添加


class OpenAIClient(BaseAIClient):
    """OpenAI API客户端"""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: Optional[str] = None,
        **kwargs
    ):
        super().__init__(api_key, model, **kwargs)
        self.base_url = base_url or "https://api.openai.com/v1"

        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
        except ImportError:
            logger.warning("OpenAI库未安装，请在虚拟环境中运行: pip install openai")
            self.client = None

    async def chat(
        self,
        messages: List[AIMessage],
        tools: Optional[List[Dict]] = None,
        max_iterations: int = 20,
        use_miya_prompt: bool = True,
        tool_choice: str = "auto"
    ) -> str:
        """调用OpenAI聊天接口（支持工具调用）
        
        Args:
            messages: 消息列表
            tools: 可用工具列表
            max_iterations: 最大工具调用迭代次数
            use_miya_prompt: 是否使用弥娅人设提示词
            tool_choice: 工具选择策略 ("auto", "required", "none")
        
        Returns:
            AI回复
        """
        if not self.client:
            raise RuntimeError("OpenAI客户端未初始化，请安装openai库")

        # 调用基类方法处理人设提示词
        if use_miya_prompt:
            # 复制消息列表以避免修改原始数据
            messages = [AIMessage(role=msg.role, content=msg.content,
                                 tool_calls=msg.tool_calls, tool_call_id=msg.tool_call_id)
                       for msg in messages]

        # 使用传入的工具或工具注册表
        if tools is None and self.tool_registry:
            tools = self.tool_registry()

        logger.info(f"[AIClient] 开始聊天 (模型: {self.model})，工具数量: {len(tools) if tools else 0}")
        if tools:
            logger.info(f"[AIClient] 可用工具: {[t.get('function', {}).get('name', 'unknown') for t in tools]}")
            # 打印start_trpg工具的schema
            for t in tools:
                if t.get('function', {}).get('name') == 'start_trpg':
                    logger.debug(f"[AIClient] start_trpg工具schema: {json.dumps(t.get('function', {}), ensure_ascii=False)[:500]}")

        iteration = 0
        current_messages = messages.copy()

        while iteration < max_iterations:
            try:
                # 转换为OpenAI格式
                openai_messages = []
                for msg in current_messages:
                    msg_dict = {"role": msg.role, "content": msg.content}
                    if msg.tool_calls:
                        msg_dict["tool_calls"] = msg.tool_calls
                    if msg.tool_call_id:
                        msg_dict["tool_call_id"] = msg.tool_call_id
                    openai_messages.append(msg_dict)

                # 构建请求参数
                request_params = {
                    "model": self.model,
                    "messages": openai_messages,
                    "temperature": self.config.get('temperature', 0.7),
                    "max_tokens": self.config.get('max_tokens', 2000)
                }

                # 添加工具相关参数
                if tools:
                    request_params["tools"] = tools
                    request_params["tool_choice"] = tool_choice

                response = await self.client.chat.completions.create(**request_params)

                choice = response.choices[0]
                message = choice.message

                # 增强调试日志
                logger.info(f"[AIClient] OpenAI响应 - 返回类型: {type(message).__name__}, 有工具调用: {bool(message.tool_calls)}, content长度: {len(message.content) if message.content else 0}, tool_choice={tool_choice}")

                # 如果没有工具调用，返回结果
                if not message.tool_calls:
                    logger.debug(f"[AIClient] OpenAI返回纯文本（无工具调用），tool_choice={tool_choice}")
                    logger.debug(f"[AIClient] 返回内容预览: {message.content[:200] if message.content else '(无内容)'}")
                    if tool_choice == "required":
                        logger.error(f"[AIClient] tool_choice='required'但模型未调用工具，可能是工具描述或系统提示词问题")
                    return message.content

                # 有工具调用，执行工具
                tool_calls = message.tool_calls
                logger.info(f"AI请求调用工具: {[tc.function.name for tc in tool_calls]}")

                # 添加助手消息（包含工具调用）
                current_messages.append(AIMessage(
                    role="assistant",
                    content=message.content or "",
                    tool_calls=[
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in tool_calls
                    ]
                ))

                # 执行工具
                for tool_call in tool_calls:
                    from .tool_adapter import get_tool_adapter
                    adapter = get_tool_adapter()

                    # 解析工具参数（使用 JSON 而不是 eval）
                    tool_args = json.loads(tool_call.function.arguments)
                    logger.info(f"[AIClient] 工具调用: {tool_call.function.name}, 参数: {tool_args}")

                    result = await adapter.execute_tool(
                        tool_call.function.name,
                        tool_args,
                        self.tool_context or {}
                    )

                    # 检查是否是直接返回工具（如运势、抽签、游戏存档等）
                    # 这些工具返回的结果已经是格式化的，直接返回给用户
                    direct_return_tools = [
                        'horoscope', 'wenchang_dijun',
                        'list_game_saves', 'create_game_save', 'load_game_save',
                        'roll_dice', 'roll_secret', 'skill_check',
                        'create_pc', 'show_pc', 'update_pc', 'delete_pc',
                        'start_combat', 'add_initiative', 'next_turn', 'show_initiative', 'end_combat',
                        'rest', 'attack', 'combat_log',
                        'kp_command',
                        'terminal_command'  # 终端命令工具直接返回结果
                    ]
                    if tool_call.function.name in direct_return_tools:
                        logger.info(f"[AIClient] 检测到直接返回工具: {tool_call.function.name}，直接返回结果")
                        return result

                    # 添加工具结果消息
                    tool_result_msg = AIMessage(
                        role="tool",
                        content=result,
                        tool_call_id=tool_call.id
                    )
                    current_messages.append(tool_result_msg)
                    logger.info(f"[AIClient] 工具结果已添加到对话历史: {result[:100] if result else '(无结果)'}")

                iteration += 1

            except Exception as e:
                logger.error(f"OpenAI API调用失败: {e}")
                raise

        # 达到最大迭代次数
        return "抱歉，工具调用次数过多，无法完成请求。"


class DeepSeekClient(BaseAIClient):
    """DeepSeek API客户端"""

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-chat",
        base_url: Optional[str] = None,
        **kwargs
    ):
        super().__init__(api_key, model, **kwargs)
        self.base_url = base_url or "https://api.deepseek.com/v1"

        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
        except ImportError:
            logger.warning("OpenAI库未安装，请运行: pip install openai")
            self.client = None

    async def chat(
        self,
        messages: List[AIMessage],
        tools: Optional[List[Dict]] = None,
        max_iterations: int = 20,
        use_miya_prompt: bool = True,
        tool_choice: str = "auto"
    ) -> str:
        """调用DeepSeek聊天接口（支持工具调用）
        
        Args:
            messages: 消息列表
            tools: 可用工具列表
            max_iterations: 最大工具调用迭代次数
            use_miya_prompt: 是否使用弥娅人设提示词
            tool_choice: 工具选择策略 ("auto", "required", "none")
        
        Returns:
            AI回复
        """
        if not self.client:
            raise RuntimeError("DeepSeek客户端未初始化，请安装openai库")

        # 调用基类方法处理人设提示词
        if use_miya_prompt:
            # 复制消息列表以避免修改原始数据
            messages = [AIMessage(role=msg.role, content=msg.content,
                                 tool_calls=msg.tool_calls, tool_call_id=msg.tool_call_id)
                       for msg in messages]

        # 使用传入的工具或工具注册表
        if tools is None and self.tool_registry:
            tools = self.tool_registry()

        logger.info(f"[AIClient] 开始聊天 (模型: {self.model})，工具数量: {len(tools) if tools else 0}, has_tool_context={self.tool_context is not None}, tool_choice={tool_choice}")
        if tools:
            logger.info(f"[AIClient] 可用工具: {[t.get('function', {}).get('name', 'unknown') for t in tools]}")

        iteration = 0
        current_messages = messages.copy()

        while iteration < max_iterations:
            try:
                # 转换为OpenAI格式
                openai_messages = []
                for msg in current_messages:
                    msg_dict = {"role": msg.role, "content": msg.content}
                    if msg.tool_calls:
                        msg_dict["tool_calls"] = msg.tool_calls
                    if msg.tool_call_id:
                        msg_dict["tool_call_id"] = msg.tool_call_id
                    openai_messages.append(msg_dict)

                # 构建请求参数
                request_params = {
                    "model": self.model,
                    "messages": openai_messages,
                    "temperature": self.config.get('temperature', 0.7),
                    "max_tokens": self.config.get('max_tokens', 2000)
                }

                # 添加工具相关参数
                if tools:
                    request_params["tools"] = tools
                    request_params["tool_choice"] = tool_choice

                response = await self.client.chat.completions.create(**request_params)

                # 增强调试日志
                choice = response.choices[0]
                message = choice.message

                logger.info(f"[AIClient] DeepSeek响应 - 返回类型: {type(message).__name__}, 有工具调用: {bool(message.tool_calls)}, content长度: {len(message.content) if message.content else 0}")

                # 如果没有工具调用，返回结果
                if not message.tool_calls:
                    logger.debug(f"[AIClient] DeepSeek返回纯文本（无工具调用），tool_choice={tool_choice}")
                    logger.debug(f"[AIClient] 返回内容预览: {message.content[:200] if message.content else '(无内容)'}")
                    # 如果使用了required但没调用工具，记录详细错误
                    if tool_choice == "required":
                        logger.error(f"[AIClient] tool_choice='required'但模型未调用工具，可能是工具描述或系统提示词问题")
                    return message.content

                # 有工具调用，执行工具
                tool_calls = message.tool_calls
                logger.info(f"DeepSeek AI请求调用工具: {[tc.function.name for tc in tool_calls]}")

                # 添加助手消息（包含工具调用）
                current_messages.append(AIMessage(
                    role="assistant",
                    content=message.content or "",
                    tool_calls=[
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in tool_calls
                    ]
                ))

                # 执行工具
                for tool_call in tool_calls:
                    from .tool_adapter import get_tool_adapter
                    adapter = get_tool_adapter()

                    # 解析工具参数（使用 JSON 而不是 eval）
                    arguments_str = tool_call.function.arguments

                    # 尝试解析 JSON，如果失败则尝试修复
                    try:
                        tool_args = json.loads(arguments_str)
                    except json.JSONDecodeError as e:
                        logger.error(f"[AIClient] JSON解析失败: {arguments_str}")
                        logger.error(f"[AIClient] 错误详情: {e}")

                        fixed_str = arguments_str

                        # 修复常见的 JSON 格式问题
                        try:
                            # 1. 移除末尾多余的逗号
                            fixed_str = fixed_str.rstrip(', ')
                        except Exception:
                            pass

                        try:
                            tool_args = json.loads(fixed_str)
                            logger.info(f"[AIClient] JSON修复成功（移除逗号）")
                        except Exception as e2:
                            # 2. 尝试修复中文值没有引号的问题（如 "target_id": 用户 -> "target_id": "用户"）
                            import re
                            try:
                                # 匹配 "key": 值（值是中文或英文但没有引号）
                                def add_quotes(match):
                                    key_part = match.group(1)
                                    value_part = match.group(2)
                                    # 如果值不包含引号，则添加引号
                                    if '"' not in value_part:
                                        value_part = '"' + value_part + '"'
                                    return key_part + value_part

                                fixed_str2 = re.sub(
                                    r'("[\w\u4e00-\u9fa5]+":\s*)([\w\u4e00-\u9fa5]+)',
                                    add_quotes,
                                    fixed_str
                                )
                                tool_args = json.loads(fixed_str2)
                                logger.info(f"[AIClient] JSON修复成功（修复中文值）: {fixed_str2}")
                            except Exception as e3:
                                logger.error(f"[AIClient] JSON修复也失败: {e2}, {e3}")
                                # 即使JSON解析失败，也要添加工具响应消息，避免API报错
                                error_result = json.dumps({
                                    "success": False,
                                    "error": f"JSON解析失败: {e}",
                                    "raw_arguments": arguments_str
                                }, ensure_ascii=False)
                                current_messages.append(AIMessage(
                                    role="tool",
                                    content=error_result,
                                    tool_call_id=tool_call.id
                                ))
                                continue

                    logger.info(f"[AIClient] 工具调用: {tool_call.function.name}, 参数: {tool_args}")

                    result = await adapter.execute_tool(
                        tool_call.function.name,
                        tool_args,
                        self.tool_context or {}
                    )

                    logger.info(f"[AIClient] 工具执行结果: {result[:200] if result else '(无结果)'}")

                    # 检查是否是直接返回工具（如运势、抽签等）
                    # 这些工具返回的结果已经是格式化的，直接返回给用户
                    direct_return_tools = ['horoscope', 'wenchang_dijun', 'terminal_command', 'multi_terminal']
                    if tool_call.function.name in direct_return_tools:
                        logger.info(f"[AIClient] 检测到直接返回工具: {tool_call.function.name}，直接返回结果")
                        return result

                    # 添加工具结果消息
                    current_messages.append(AIMessage(
                        role="tool",
                        content=result,
                        tool_call_id=tool_call.id
                    ))

                iteration += 1

            except Exception as e:
                logger.error(f"DeepSeek API调用失败: {e}")
                raise

        # 达到最大迭代次数
        return "抱歉，工具调用次数过多，无法完成请求。"


class AnthropicClient(BaseAIClient):
    """Anthropic (Claude) API客户端"""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-sonnet-20240229",
        **kwargs
    ):
        super().__init__(api_key, model, **kwargs)

        try:
            from anthropic import AsyncAnthropic
            self.client = AsyncAnthropic(api_key=api_key)
        except ImportError:
            logger.warning("Anthropic库未安装，请运行: pip install anthropic")
            self.client = None

    async def chat(self, messages: List[AIMessage]) -> str:
        """调用Anthropic聊天接口"""
        if not self.client:
            raise RuntimeError("Anthropic客户端未初始化，请安装anthropic库")

        try:
            # 提取system prompt
            system_prompt = None
            user_messages = []

            for msg in messages:
                if msg.role == "system":
                    system_prompt = msg.content
                else:
                    user_messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })

            response = await self.client.messages.create(
                model=self.model,
                system=system_prompt,
                messages=user_messages,
                max_tokens=self.config.get('max_tokens', 2000)
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Anthropic API调用失败: {e}")
            raise


class ZhipuAIClient(BaseAIClient):
    """智谱AI API客户端"""

    def __init__(
        self,
        api_key: str,
        model: str = "glm-4",
        **kwargs
    ):
        super().__init__(api_key, model, **kwargs)

        try:
            from zhipuai import ZhipuAI
            self.client = ZhipuAI(api_key=api_key)
        except ImportError:
            logger.warning("智谱AI库未安装，请运行: pip install zhipuai")
            self.client = None

    async def chat(self, messages: List[AIMessage]) -> str:
        """调用智谱AI聊天接口"""
        if not self.client:
            raise RuntimeError("智谱AI客户端未初始化，请安装zhipuai库")

        try:
            # 同步调用（智谱AI暂不支持async）
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": msg.role, "content": msg.content}
                    for msg in messages
                ],
                temperature=self.config.get('temperature', 0.7)
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"智谱AI API调用失败: {e}")
            raise


class AIClientFactory:
    """AI客户端工厂"""

    _clients = {
        "openai": OpenAIClient,
        "deepseek": DeepSeekClient,
        "anthropic": AnthropicClient,
        "zhipu": ZhipuAIClient,
    }

    @classmethod
    def create_client(
        cls,
        provider: str,
        api_key: str,
        model: str,
        **kwargs
    ) -> BaseAIClient:
        """
        创建AI客户端

        Args:
            provider: 提供商名称 (openai, deepseek, anthropic, zhipu)
            api_key: API密钥
            model: 模型名称
            **kwargs: 其他配置

        Returns:
            AI客户端实例
        """
        provider = provider.lower()
        client_class = cls._clients.get(provider)

        if not client_class:
            raise ValueError(f"不支持的AI提供商: {provider}，支持的提供商: {list(cls._clients.keys())}")

        logger.info(f"创建{provider}客户端，模型: {model}")
        return client_class(api_key=api_key, model=model, **kwargs)

    @classmethod
    def list_providers(cls) -> List[str]:
        """列出所有支持的提供商"""
        return list(cls._clients.keys())
