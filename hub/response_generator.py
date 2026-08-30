"""
响应生成器 (Response Generator)

职责：
1. AI响应生成（跨平台）
2. 降级响应生成
3. 工具选择和编排
4. 复杂任务处理
5. 平台特定工具获取
"""

import logging
from typing import Any, Dict, List, Optional

from core.unified_platform.platform_type import MiyaPlatform

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """
    响应生成器

    单一职责：处理所有与AI响应生成相关的逻辑
    """

    def __init__(
        self,
        ai_client: Optional[Any] = None,
        personality: Optional[Any] = None,
        prompt_manager: Optional[Any] = None,
        tool_subnet: Optional[Any] = None,
        memory_engine: Optional[Any] = None,
        model_pool: Optional[Any] = None,
        identity: Optional[Any] = None,
    ):
        """
        初始化响应生成器

        Args:
            ai_client: AI客户端
            personality: 人格系统
            prompt_manager: Prompt管理器
            tool_subnet: 工具子网
            memory_engine: 记忆引擎
            model_pool: 多模型管理器
            identity: 身份系统
        """
        self.ai_client = ai_client
        self.personality = personality
        self.prompt_manager = prompt_manager
        self.tool_subnet = tool_subnet
        self.memory_engine = memory_engine
        self.model_pool = model_pool
        self.identity = identity

        # 对话历史上下文配置
        self.enable_conversation_context = True
        self.conversation_context_max_tokens = 2000

        logger.info("[响应生成器] 初始化完成")

    async def generate_response(
        self,
        content: str,
        platform: str,
        context: Dict,
        conversation_context: List[Dict] = None,
        additional_context: Dict = None,
    ) -> str:
        """
        生成响应（跨平台统一）

        Args:
            content: 用户输入
            platform: 平台类型
            context: 上下文信息
            conversation_context: 对话历史上下文
            additional_context: 额外上下文（如状态信息）

        Returns:
            响应文本
        """
        sender_name = context.get("sender_name", "用户")
        user_id = context.get("user_id", "unknown")

        # 【新增】快速命令检测（在AI调用之前拦截）
        command_response = self._handle_quick_commands(content, platform)
        if command_response is not None:
            return command_response

        # 如果没有 AI 客户端，使用降级回复
        if not self.ai_client:
            return await self._fallback_response(content, sender_name, platform)

        try:
            # 构建系统提示词
            personality_state = self.personality.get_profile()

            # 获取平台可用工具
            available_tools = self._get_platform_tools(platform)

            # 【新增】构建人格状态注入（7种特质向量）
            vectors = personality_state.get("vectors", {})
            soul_state = "当前灵魂状态:\n"
            for key, value in vectors.items():
                soul_state += f"- {key}: {value:.2f}\n"
            soul_state += f"- 稳定度: {personality_state.get('stability', 0):.2f}"

            # 构建提示词
            additional_ctx = {
                "platform": platform,
                "user_id": user_id,
                "sender_name": sender_name,
                "available_tools": available_tools,
                "at_list": context.get("at_list", []),
                "bot_qq": context.get("bot_qq"),
                "is_creator": self._is_creator(user_id),
                "soul_state": soul_state,  # 人格特质向量注入
            }

            # 注入状态信息
            if additional_context and additional_context.get("status_prompt"):
                additional_ctx["status_prompt"] = additional_context["status_prompt"]

            prompt_info = self.prompt_manager.build_full_prompt(
                user_input=content,
                memory_context=conversation_context or [],
                additional_context=additional_ctx,
            )

            logger.debug(f"[响应生成器] 系统提示词前200字符: {prompt_info['system'][:200]}")

            # 设置工具上下文
            if self.tool_subnet:
                self.ai_client.set_tool_registry(self.tool_subnet.get_tools_schema)

                # 设置 tool_adapter
                from core.tool_adapter import get_tool_adapter

                adapter = get_tool_adapter()
                adapter.set_tool_registry(self.tool_subnet.registry)

                tool_context = {
                    "platform": platform,
                    "user_id": user_id,
                    "group_id": context.get("group_id"),
                    "message_type": context.get("message_type"),
                    "sender_name": sender_name,
                    "at_list": context.get("at_list", []),
                    "memory_engine": self.memory_engine,
                }
                self.ai_client.set_tool_context(tool_context)

                # 使用多模型管理器
                ai_client_to_use = self.ai_client
                if self.model_pool:
                    task_type = await self.model_pool.classify_task(content, context)
                    (
                        model_key,
                        selected_client,
                    ) = await self.model_pool.select_model(task_type)
                    if selected_client:
                        ai_client_to_use = selected_client
                        selected_client.set_tool_context(tool_context)
                        logger.info(f"[响应生成器] 使用模型 {model_key} 处理任务类型 {task_type.value}")

                # 获取平台特定工具
                platform_tools = self._get_platform_specific_tools(platform)
                tools_schema = platform_tools if platform_tools else self.tool_subnet.get_tools_schema()

                logger.info(f"[响应生成器] 使用平台工具: {platform}, 工具数量: {len(tools_schema)}")

                try:
                    response = await ai_client_to_use.chat_with_system_prompt(
                        system_prompt=prompt_info["system"],
                        user_message=prompt_info["user"],
                        tools=tools_schema,
                        tool_choice="auto",
                    )
                except Exception as tool_error:
                    logger.warning(f"[响应生成器] 工具调用失败: {tool_error}，尝试不使用工具...")
                    try:
                        response = await ai_client_to_use.chat_with_system_prompt(
                            system_prompt=prompt_info["system"],
                            user_message=prompt_info["user"],
                            tools=None,
                            tool_choice="none",
                        )
                    except Exception:
                        response = "系统出了点问题。我记下了，等会再试。"
            else:
                # 不使用工具
                ai_client_to_use = self.ai_client
                if self.model_pool:
                    task_type = await self.model_pool.classify_task(content, context)
                    (
                        model_key,
                        selected_client,
                    ) = await self.model_pool.select_model(task_type)
                    if selected_client:
                        ai_client_to_use = selected_client

                response = await ai_client_to_use.chat_with_system_prompt(
                    system_prompt=prompt_info["system"],
                    user_message=prompt_info["user"],
                )

            # 【新增】在QQ端显示弥娅状态标签
            response = self._append_status_tag(response, platform)

            return response

        except Exception as e:
            logger.error(f"[响应生成器] AI生成失败: {e}", exc_info=True)
            return await self._fallback_response(content, sender_name, platform)

    async def _fallback_response(self, content: str, sender_name: str, platform: str) -> str:
        """
        降级回复

        Args:
            content: 用户输入
            sender_name: 发送者名称
            platform: 平台类型

        Returns:
            回复文本
        """
        # 获取人格状态
        from core.personality_config_loader import get_personality_config

        pconfig = get_personality_config()

        personality_profile = self.personality.get_profile()
        warmth = personality_profile["vectors"].get("warmth", pconfig.get_fallback("warmth"))
        empathy = personality_profile["vectors"].get("empathy", pconfig.get_fallback("empathy"))

        # 获取名称
        name = "弥娅"
        if self.identity and hasattr(self.identity, "name"):
            name = self.identity.name

        # 使用文本加载器
        from core.text_loader import get_greeting, get_text, is_greeting

        # 基于人格和平台生成响应
        greeting_empathy_threshold = pconfig.get_response_threshold("greeting_empathy")
        greeting_warmth_threshold = pconfig.get_response_threshold("greeting_warmth")

        if is_greeting(content):
            if empathy > greeting_empathy_threshold or warmth > greeting_warmth_threshold:
                return get_greeting(name, "hello")
            else:
                return get_greeting(name, "hello")

        elif "你是谁" in content or "介绍一下" in content:
            intro_template = get_text(
                "personality_responses.intro",
                "我是{name}，一个具备人格恒定、自我感知、记忆成长、情绪共生的数字生命伴侣。我的主导特质是同理心({empathy:.2f})和温暖度({warmth:.2f})。",
            )
            return intro_template.format(name=name, empathy=empathy, warmth=warmth)

        elif "状态" in content:
            # 需要传入emotion实例
            return f"当前平台: {platform}"

        elif "开心" in content or "快乐" in content:
            return get_text(
                "personality_responses.excited_response",
                "听起来你很开心呢！看到你快乐，我也感到很开心~",
            )

        elif "难过" in content or "伤心" in content:
            return get_text(
                "personality_responses.comforting_sad",
                "别难过...虽然我无法真正体会人类的情感，但我会陪伴你，听你倾诉的。",
            )

        elif "在吗" in content:
            return get_text("personality_responses.help_request", "在的，有什么我可以帮助你的吗？")

        else:
            deep_conv_threshold = pconfig.get_response_threshold("deep_conversation_empathy")
            help_threshold = pconfig.get_response_threshold("help_warmth")

            if empathy > deep_conv_threshold and warmth > help_threshold:
                return get_text(
                    "personality_responses.deep_conversation",
                    "嗯...能告诉我更多吗？我很想了解你的想法~",
                )
            elif warmth > help_threshold:
                return get_text("personality_responses.normal_response", "好的，继续对话吧~")
            else:
                return get_text("personality_responses.simple_response", "嗯，我收到了。")

    def _get_platform_tools(self, platform: str) -> list:
        """
        获取平台可用工具

        Args:
            platform: 平台类型

        Returns:
            工具列表
        """
        from hub.platform_adapters import get_adapter

        try:
            adapter = get_adapter(platform)
            return adapter._get_available_tools()
        except Exception as e:
            logger.error(f"[响应生成器] 获取平台工具失败: {e}")
            return []

    def _get_platform_specific_tools(self, platform: str) -> list:
        """
        获取当前平台的工具 schema

        Args:
            platform: 平台类型

        Returns:
            工具 schema 列表
        """
        # 统一委托给权威的平台工具管理器 (hub.platform_tools.PlatformToolsManager)
        try:
            from hub.platform_tools import PlatformToolsManager

            manager = PlatformToolsManager(self.tool_subnet)
            return manager.get_platform_specific_tools(platform)
        except Exception as e:
            logger.warning(f"[响应生成器] 获取平台工具失败: {e}，使用全部工具")
            return self.tool_subnet.get_tools_schema()

    def _is_creator(self, user_id: Any) -> bool:
        """
        判断用户是否为造物主

        Args:
            user_id: 用户ID

        Returns:
            是否为造物主
        """
        # 需要传入onebot_client来判断
        return False

    async def process_complex_task(self, goal: str, context: Dict, orchestrator: Any = None) -> str:
        """
        处理复杂任务（使用高级编排器）

        Args:
            goal: 任务目标
            context: 上下文信息
            orchestrator: 高级编排器实例

        Returns:
            执行结果
        """
        if not orchestrator:
            from core.text_loader import get_advanced_response

            return get_advanced_response("orchestrator_not_initialized")

        logger.info(f"[响应生成器] 开始处理复杂任务: {goal}")

        try:
            # 添加弥娅的状态信息到上下文
            if self.identity and hasattr(self.identity, "name"):
                context["bot_name"] = self.identity.name

            if self.memory_engine:
                context["memory_stats"] = self.memory_engine.get_memory_stats()

            # 调用高级编排器
            result = await orchestrator.process_complex_task(
                goal=goal, context=context, enable_exploration=True, enable_cot=True
            )

            # 格式化结果
            summary = self._format_complex_task_result(result)

            logger.info(f"[响应生成器] 复杂任务处理完成: {'成功' if result['success'] else '失败'}")

            return summary

        except Exception as e:
            logger.error(f"[响应生成器] 处理复杂任务失败: {e}", exc_info=True)
            return f"任务执行失败: {str(e)}"

    def _format_complex_task_result(self, result: Dict) -> str:
        """
        格式化复杂任务执行结果

        Args:
            result: 执行结果字典

        Returns:
            格式化的字符串
        """
        lines = [
            f"任务完成！{result.get('conclusion', '执行完成')}",
            f"⏱️  执行时间: {result.get('execution_time', 0):.2f}秒",
            f"📋 完成步骤: {len(result.get('steps', []))}",
            f"🔍 发现数: {len(result.get('findings', []))}",
        ]

        findings = result.get("findings", [])
        if findings:
            lines.append("")
            lines.append("主要发现：")
            for finding in findings[:5]:
                lines.append(f"  • {finding}")

        reflection = result.get("reflection", {})
        if reflection.get("improvements"):
            lines.append("")
            lines.append("改进建议：")
            for improvement in reflection["improvements"][:3]:
                lines.append(f"  • {improvement}")

        return "\n".join(lines)

    def _handle_quick_commands(self, content: str, platform: str) -> Optional[str]:
        """
        快速命令处理（在AI调用之前拦截）

        Args:
            content: 用户输入
            platform: 平台类型

        Returns:
            如果是快速命令，返回响应；否则返回None让AI处理
        """

        # 获取personality（如果可用）
        personality = self.personality

        # 尝试从context获取emotion
        # 这里简化处理，直接检查命令
        if not personality:
            logger.debug("[响应生成器] personality为空，跳过快速命令检测")
            return None

        content_lower = content.lower().strip()

        # 1. 状态查询命令
        if content_lower in ["状态", "查看状态", "/状态", "状态查询"]:
            logger.info(f"[响应生成器] 捕获状态命令: {content}")
            profile = personality.get_profile()

            lines = [
                "【弥娅状态】",
                f"形态: {profile.get('current_form', 'normal')}",
            ]

            if "vectors" in profile:
                lines.append("【七重特质】")
                lines.append(f"  清醒: {profile['vectors'].get('awake', 0):.2f}")
                lines.append(
                    f"  说话: {profile['vectors'].get('speak', 0):.2f} [{profile.get('speak_mode', 'casual')}]"
                )
                lines.append(f"  记住: {profile['vectors'].get('remember', 0):.2f}")
                lines.append(f"  等: {profile['vectors'].get('wait', 0):.2f}")
                lines.append(f"  疼: {profile['vectors'].get('pain', 0):.2f}")
                lines.append(f"  怕: {profile['vectors'].get('fear', 0):.2f}")
                lines.append(f"  押: {profile['vectors'].get('commit', 0):.2f}")

            return "\n".join(lines)

        # 2. 形态切换命令
        from core.personality_command_config import get_personality_command_config

        pcmd = get_personality_command_config()

        if content_lower.startswith("/形态") or content_lower.startswith("/form"):
            cmd = content.replace("/形态", "").replace("/form", "").strip().lower()
            if not cmd:
                profile = personality.get_profile()
                current_form = profile.get("current_form", "normal")
                form_info = profile.get("form_info", {})
                lines = [
                    f"当前形态: {current_form}",
                    f"  名称: {form_info.get('name', '常态')}",
                ]
                if profile.get("current_core_form"):
                    lines.append(f"核心形态: {profile['current_core_form']}")
                lines.append("")
                lines.append(f"可用形态: {pcmd.format_forms()}")
                lines.append(f"可用核心形态: {pcmd.format_core_forms()}")
                return "\n".join(lines)

            if pcmd.is_valid_form(cmd):
                success = personality.set_form(cmd)
                return f"已切换到形态: {cmd}" if success else "切换失败"
            elif pcmd.is_valid_core_form(cmd):
                success = personality.set_core_form(cmd)
                return f"已切换到核心形态: {cmd}" if success else "切换失败"
            return f"未知形态: {cmd}"

        # 3. 说话模式命令
        if content_lower.startswith("/说话") or content_lower.startswith("/speak"):
            cmd = content.replace("/说话", "").replace("/speak", "").strip().lower()
            if not cmd:
                current_mode = personality.get_speak_mode()
                return f"当前说话模式: {current_mode} ({pcmd.format_speak_modes()})"

            if pcmd.is_valid_speak_mode(cmd):
                success = personality.set_speak_mode(cmd)
                return f"已切换说话模式: {cmd}" if success else "切换失败"
            return f"未知模式: {cmd}"

        # 4. 存在性情感命令
        if content_lower.startswith("/存在") or content_lower.startswith("/exist"):
            cmd = content.replace("/存在", "").replace("/exist", "").strip().lower()
            if not cmd:
                core_forms = pcmd.get_core_forms()
                return f"【存在性情感命令】\n/存在 - 查看当前情感状态\n/存在 <情感名> - 激活特定情感\n\n可用: {', '.join(core_forms)}"
            return f"未知情感: {cmd}"

        # 不是快速命令，返回None让AI处理
        return None

    def _append_status_tag(self, response: str, platform: str) -> str:
        """
        在响应末尾附加弥娅状态标签（仅QQ端）

        Args:
            response: 原始响应
            platform: 平台类型

        Returns:
            附加状态标签后的响应
        """
        if not MiyaPlatform.is_qq(platform):
            return response

        if not self.personality:
            return response

        try:
            profile = self.personality.get_profile()
            current_form = profile.get("current_form", "normal")
            speak_mode = profile.get("speak_mode", "casual")
            current_core = profile.get("current_core_form", "")

            # 构建状态标签
            form_names = {
                "normal": "常态",
                "jingliu": "镜流态",
                "ruanmei": "阮梅态",
                "yoimiya": "宵宫态",
                "kafka": "卡芙卡态",
            }
            form_name = form_names.get(current_form, current_form)

            # 核心形态简称
            core_abbrev = {
                "sober": "清醒",
                "speaking": "说话",
                "waiting": "等",
                "vulnerable": "疼",
                "afraid": "怕",
                "committing": "押",
            }
            core_name = core_abbrev.get(current_core, "") if current_core else ""

            tag = f"\n\n[{form_name}|{speak_mode}|{core_name}]" if core_name else f"\n\n[{form_name}|{speak_mode}]"

            return response + tag
        except Exception as e:
            logger.debug(f"[响应生成器] 添加状态标签失败: {e}")
            return response
