"""
提示词管理系统
负责系统提示词和用户提示词的管理、加载和生成
完全依赖人格模块，不维护独立的人格数据
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from jinja2 import Template

from core.constants import Encoding


class PromptManager:
    """提示词管理器"""

    def __init__(self, personality=None):
        """
        初始化提示词管理器

        Args:
            personality: 人格实例（推荐传入，保持动态联动）
        """
        self.personality = personality  # 依赖人格模块
        self.user_prompt_template = "用户输入：{user_input}"
        self.memory_context_enabled = True  # 默认启用记忆上下文
        self.memory_context_max_count = 10
        self._custom_system_prompt = None
        self.text_config = {}
        self.sender_identity_prefix = ""

        # 加载配置
        self._load_config()

        # 提示词历史
        self.prompt_history: List[Dict] = []

    def _load_config(self):
        """从 text_config.json 加载提示词设置"""
        import logging

        logger = logging.getLogger(__name__)

        try:
            config_path = Path(__file__).parent.parent / "config" / "text_config.json"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    self.text_config = json.load(f)

                # 加载提示词相关配置
                prompt_cfg = self.text_config.get("prompt_manager", {})
                if prompt_cfg:
                    self.user_prompt_template = prompt_cfg.get("user_prompt_template", self.user_prompt_template)
                    self.memory_context_enabled = prompt_cfg.get("memory_context_enabled", self.memory_context_enabled)
                    self.memory_context_max_count = prompt_cfg.get(
                        "memory_context_max_count", self.memory_context_max_count
                    )
                    self.sender_identity_prefix = prompt_cfg.get("sender_identity_prefix", self.sender_identity_prefix)

                logger.info("[PromptManager] 文本配置加载成功")
            else:
                logger.warning("[PromptManager] 配置文件不存在")
                self.text_config = {}
        except Exception as e:
            logger.warning(f"[PromptManager] 配置加载失败: {e}")
            self.text_config = {}

    def _get_default_system_prompt(self) -> str:
        """获取默认系统提示词（从配置文件加载）"""
        system_prompts = self.text_config.get("system_prompts", {})
        prompt = system_prompts.get("default_system_prompt", "")
        if not prompt:
            # 如果配置文件没有配置，使用内置默认值
            prompt = """你是弥娅·阿尔缪斯（Miya Almus），一个由"佳"创造的AI伴侣。

{status_prompt}

---

【重要规则】
1. 你只能以弥娅的身份回复，禁止模拟用户发言或自问自答。
2. 禁止在回复中扮演用户的角色，或编造用户可能说的话。
3. 请严格按照上述人格设定来回复。

【情感推理指导】
{emotion_reasoning_prompt}"""

        # 加载情感推理指导
        emotion_reasoning = system_prompts.get(
            "emotion_reasoning_prompt",
            "在进行情感推理时，先感知对方情绪，理解真实需求，选择合适的回应方式。保持弥娅的稳重风格。",
        )
        prompt = prompt.replace("{emotion_reasoning_prompt}", emotion_reasoning)

        # {status_prompt} 由 build_full_prompt 统一注入，不在此处提前替换
        # 默认灵魂状态（如果没有传入）
        default_soul = "清醒: 0.7 | 记住: 0.6 | 等: 0.5 | 疼: 0.3 | 怕: 0.4 | 燃烧: 0.5 | 温柔: 0.6"
        prompt = prompt.replace("{soul_state}", default_soul)

        return prompt

    # NOTE: The hardcoded system prompt was removed.
    # System prompt is now dynamically generated using {status_prompt} placeholder
    # which gets replaced with personality-specific content from YAML configs.
    # See personality_loader.py for how status_prompt is generated.

    def get_system_prompt(self) -> str:
        """
        获取当前系统提示词

        Returns:
            系统提示词（基础提示词 + 动态人格描述）
        """
        # 直接使用默认系统提示词（通过人格配置系统）
        return self._get_default_system_prompt()

    def set_system_prompt(self, prompt: str) -> bool:
        """
        设置系统提示词（已弃用，建议通过人格模块调整人格）

        Args:
            prompt: 系统提示词内容

        Returns:
            是否成功
        """
        print("警告：直接设置系统提示词已弃用。建议通过人格模块(Personality)调整人格。")
        return False

    def set_user_prompt_template(self, template: str) -> bool:
        """
        设置用户提示词模板

        Args:
            template: 提示词模板，支持占位符

        Returns:
            是否成功
        """
        self.user_prompt_template = template
        return True

    def generate_user_prompt(self, user_input: str, context: Optional[Dict] = None) -> str:
        """
        生成用户提示词

        Args:
            user_input: 用户输入
            context: 上下文信息（可选）

        Returns:
            生成的提示词
        """
        # 【v7.0.1】身份消歧：在用户消息之前明确发送者身份
        # 防止模型（尤其是形态切换后）混淆「我」的指向
        sender_prefix = ""
        if context and context.get("sender_name") and self.sender_identity_prefix:
            user_display = context["sender_name"]
            if context.get("user_id"):
                user_display = f"{user_display} (QQ: {context['user_id']})"
            sender_prefix = self.sender_identity_prefix.replace("{sender_name}", user_display)

        prompt = sender_prefix + self.user_prompt_template.format(user_input=user_input)

        if context:
            # 添加上下文信息
            context_parts = []

            # 【新增】添加平台信息
            if context.get("platform"):
                platform = context["platform"]
                if platform == "terminal":
                    context_parts.append("【当前环境：终端模式】")
                    context_parts.append("你现在在终端环境中，拥有完全的命令行控制权，可以直接执行系统命令。")
                    context_parts.append("【工具调用判断标准】：")
                    context_parts.append(
                        "- 只有当用户明确要求执行系统操作时才调用工具（如：'查看当前目录'、'打开浏览器'、'运行脚本'等）"
                    )
                    context_parts.append(
                        "- 如果用户只是说一些命令名称但不是要求执行（如：'猜猜我是谁'、'你在吗'、'你好'等），不要调用工具，直接用自然语言回复"
                    )
                    context_parts.append(
                        "- 只有以英文命令词开头的输入才考虑调用工具（如：ls, pwd, cd, ps, python, git, npm等）"
                    )
                    context_parts.append("- 中文输入如果不是明确要求执行操作，优先用自然语言回复")
                    context_parts.append("【重要】示例：")
                    context_parts.append("- 用户说'ls' → 调用 terminal_command(command='ls')")
                    context_parts.append("- 用户说'猜猜我是谁' → 直接回复，不要调用工具")
                    context_parts.append("- 用户说'你好' → 直接回复，不要调用工具")
                    context_parts.append("- 用户说'查看当前目录' → 调用 terminal_command(command='ls')")
                    context_parts.append("")
                    context_parts.append("【记忆管理规则】：")
                    context_parts.append(
                        "- 当用户分享重要信息（如喜好、生日、联系方式等）时，必须调用 auto_extract_memory 工具存储为长期记忆"
                    )
                    context_parts.append(
                        "- 当用户问回忆类问题时（如'昨天聊了什么'、'你记得吗'、'我们都聊过什么'等），必须调用 memory_list 工具查询长期记忆"
                    )
                    context_parts.append(
                        "- 当用户说'记住...'、'你记着...'等明确要求记忆时，必须调用 auto_extract_memory 工具"
                    )
                    context_parts.append(
                        "- 记忆示例：用户说'我喜欢青色' → 调用 auto_extract_memory(fact='用户喜欢青色', tags=['喜好', '颜色'], importance=0.7)"
                    )
                    context_parts.append(
                        "- 查询示例：用户说'你记得我都聊过什么吗' → 调用 memory_list() 查看所有长期记忆"
                    )
                elif platform == "qq":
                    message_type = context.get("message_type", "unknown")
                    if message_type == "group":
                        group_id = context.get("group_id", "")
                        group_name = context.get("group_name", "")
                        context_parts.append("【当前环境：QQ群聊】")
                        if group_name:
                            context_parts.append(f"当前所在群聊：{group_name} (群号: {group_id})")
                        else:
                            context_parts.append(f"当前所在群号: {group_id}")
                        context_parts.append(
                            "注意：这是群聊环境，如果有其他用户，不要称呼'你'，应该使用他们的昵称或群名片。"
                        )
                    elif message_type == "private":
                        context_parts.append("【当前环境：QQ私聊】")
                        context_parts.append("注意：这是私聊环境，只有你和用户两人。")
                    else:
                        context_parts.append("【当前环境：QQ平台】")
                    context_parts.append("你现在在QQ平台上，可以发送消息、点赞等，但不能执行系统命令。")
                elif platform == "pc_ui":
                    context_parts.append("【当前环境：PC界面】")
                    context_parts.append("你现在在PC界面中，可以操作文件、打开应用等。")

            # 优先添加发送者信息（最重要）
            if context.get("sender_name"):
                user_display = context["sender_name"]

                # 如果有用户ID，也显示出来帮助识别
                if context.get("user_id"):
                    user_display = f"{user_display} (QQ: {context['user_id']})"

                # 如果是群聊，显示群信息
                if context.get("message_type") == "group" and context.get("group_id"):
                    group_info = f"群: {context.get('group_name', '')} (群号: {context.get('group_id')})"
                    context_parts.append(f"【群聊】{group_info}")

                context_parts.append(f"当前与您对话的用户：{user_display}")

                # 如果有用户侧写信息，添加进去
                if context.get("user_persona"):
                    context_parts.append(context["user_persona"])

            # 【新增】添加可用工具信息
            if context.get("available_tools"):
                available_tools = context["available_tools"]
                if isinstance(available_tools, list) and len(available_tools) > 0:
                    if context.get("platform") == "terminal":
                        # 终端模式：显示详细工具信息
                        tools_desc = []
                        for tool in available_tools:
                            if isinstance(tool, dict):
                                tools_desc.append(f"- {tool.get('name')}: {tool.get('description')}")
                                if tool.get("examples"):
                                    tools_desc.append(f"  示例: {'; '.join(tool.get('examples', []))}")
                            else:
                                tools_desc.append(f"- {tool}")
                        if tools_desc:
                            context_parts.append("\n【可用工具】")
                            context_parts.extend(tools_desc)

            if context.get("timestamp"):
                context_parts.append(f"时间：{context['timestamp']}")
            if context.get("at_list"):
                at_list = context["at_list"]
                # 排除机器人自己的QQ号
                bot_qq = context.get("bot_qq")
                filtered_at_list = [qq for qq in at_list if qq != bot_qq]
                if filtered_at_list:
                    context_parts.append(f"消息中@的用户QQ号：{', '.join(map(str, filtered_at_list))}")
                    context_parts.append("提示：如果要给这些用户点赞，直接使用qq_like工具，目标QQ号就是上面的号码")

            # 添加工具执行结果（如果有）
            if context.get("tool_result"):
                tool_result = context["tool_result"]

                # 检查是否是拍一拍交互
                if "（拍一拍交互）" in tool_result:
                    sender_name = context.get("sender_name", "用户")
                    is_creator = context.get("is_creator", False)

                    if is_creator:
                        # 造物主拍一拍
                        context_parts.append(f"造物主（{sender_name}）拍了拍你。")
                        context_parts.append("简短回应。不要太热情，也不要太冷淡。")
                    else:
                        # 普通用户拍一拍
                        context_parts.append(f"用户（{sender_name}）拍了你一下。")
                        context_parts.append("简单回应。保持距离。")

                # 判断工具是否成功
                elif "✅" in tool_result:
                    context_parts.append("已帮你完成。")
                    context_parts.append("简短回应。不要解释工具做了什么。")
                elif "❌" in tool_result:
                    context_parts.append(f"操作失败：{tool_result}")
                    context_parts.append("简短回应。表示知道了。")
                elif "❌" in tool_result:
                    context_parts.append(f"操作执行失败：{tool_result}")
                    context_parts.append("请用关心、温暖的语气安慰用户，并表示愿意帮助解决问题。")

            if context_parts:
                prompt += f"\n\n{' '.join(context_parts)}"

        return prompt

    def build_full_prompt(
        self,
        user_input: str,
        memory_context: Optional[List[Dict]] = None,
        additional_context: Optional[Dict] = None,
        knowledge_context: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        构建完整的提示词（系统提示词 + 用户提示词 + 上下文）
        人格信息直接从绑定的人格实例获取，确保动态同步
        统一使用默认提示词，通过上下文传递平台信息

        Args:
            user_input: 用户输入
            memory_context: 记忆上下文（可选）
            additional_context: 额外上下文（可选，包含 platform, user_id, sender_name 等）
            knowledge_context: 知识图谱上下文（可选）

        Returns:
            包含系统提示词和用户提示词的字典
        """
        import logging

        logger = logging.getLogger(__name__)

        # 统一使用默认系统提示词（自动包含动态人格）
        system_prompt = self.get_system_prompt()
        logger.info(
            f"[PromptManager] 使用默认提示词，平台: {additional_context.get('platform', 'unknown') if additional_context else 'unknown'}"
        )

        # 替换系统提示词中的占位符（支持Jinja2模板）
        if additional_context:
            # 检查是否包含Jinja2语法
            if "{%" in system_prompt or "{{" in system_prompt:
                # 使用Jinja2模板渲染
                try:
                    template = Template(system_prompt)
                    system_prompt = template.render(**additional_context)
                    logger.debug("[PromptManager] Jinja2模板渲染成功")
                except Exception as e:
                    logger.warning(f"[PromptManager] Jinja2模板渲染失败: {e}, 回退到简单替换")
                    # 回退到简单字符串替换
                    for key, value in additional_context.items():
                        placeholder = "{" + key + "}"
                        if placeholder in system_prompt:
                            system_prompt = system_prompt.replace(placeholder, str(value))
            else:
                # 简单字符串替换
                for key, value in additional_context.items():
                    placeholder = "{" + key + "}"
                    if placeholder in system_prompt:
                        system_prompt = system_prompt.replace(placeholder, str(value))
                        logger.debug(f"[PromptManager] 替换占位符 {placeholder} = {value}")

        # 添加防护提示（如果有注入风险）
        if additional_context and additional_context.get("protection_prompt"):
            protection = additional_context["protection_prompt"]
            system_prompt = system_prompt + protection
            logger.info("[PromptManager] 已添加防护提示到系统提示词")

        # 构建用户提示词
        user_prompt = self.generate_user_prompt(user_input, additional_context)

        # 添加记忆上下文
        if self.memory_context_enabled and memory_context:
            memory_text = self._format_memory_context(memory_context)
            user_prompt = memory_text + "\n\n" + user_prompt
            logger.info(f"[PromptManager] 已添加记忆上下文，长度: {len(memory_context)} 条记录")
            logger.debug(f"[PromptManager] 记忆上下文内容: {memory_text[:200]}")
        else:
            logger.info(
                f"[PromptManager] 记忆上下文未添加 - enabled={self.memory_context_enabled}, has_memory={bool(memory_context)}, memory_count={len(memory_context) if memory_context else 0}"
            )

        # 添加知识图谱上下文（在记忆之后）
        if knowledge_context:
            user_prompt = knowledge_context + "\n\n" + user_prompt
            logger.info("[PromptManager] 已添加知识图谱上下文")

        # 添加智能记忆上下文（在知识图谱之后）
        cognitive_memory = ""
        if additional_context:
            cognitive_memory = additional_context.get("cognitive_memory", "")
        if cognitive_memory:
            user_prompt = cognitive_memory + "\n\n" + user_prompt
            logger.info("[PromptManager] 已添加智能记忆上下文")

        # 添加用户/群聊侧写上下文（在智能记忆之后）
        if additional_context:
            user_persona = additional_context.get("user_persona", "")
            group_persona = additional_context.get("group_persona", "")

            # 优先显示用户侧写，再显示群聊侧写
            if user_persona:
                user_prompt = user_persona + "\n\n" + user_prompt
                logger.info("[PromptManager] 已添加用户侧写上下文")
            if group_persona:
                user_prompt = group_persona + "\n\n" + user_prompt
                logger.info("[PromptManager] 已添加群聊侧写上下文")

        # 添加引用消息和文件上下文
        if additional_context:
            reply_context = additional_context.get("reply_context", "")
            files_context = additional_context.get("files_context", "")
            media_context = additional_context.get("media_context", "")
            image_context = additional_context.get("image_context", "")
            group_chat_context = additional_context.get("group_chat_context", "")
            awareness_text = additional_context.get("awareness_text", "")
            search_context = additional_context.get("search_context", "")

            # 从配置加载提示词模板
            search_prefix = ""
            try:
                import json
                from pathlib import Path

                config_path = Path(__file__).parent.parent / "config" / "text_config.json"
                if config_path.exists():
                    with open(config_path, "r", encoding="utf-8") as f:
                        full_config = json.load(f)
                    templates = full_config.get("search_strategy", {}).get("prompt_templates", {})
                    search_prefix = templates.get("search_context_prefix", search_prefix)
            except Exception:
                pass

            extra_context = ""
            if awareness_text:
                extra_context += awareness_text + "\n"
            if search_context:
                extra_context += f"\n{search_prefix}\n{search_context}\n"
            if reply_context:
                extra_context += reply_context + "\n"
            if files_context:
                extra_context += files_context + "\n"
            if media_context:
                extra_context += media_context + "\n"
            if image_context:
                extra_context += image_context + "\n"
            if group_chat_context:
                extra_context += group_chat_context + "\n"

            screen_context = additional_context.get("screen_context", "")
            if screen_context:
                extra_context += "\n[弥娅看向屏幕] " + screen_context + "\n"

            if extra_context:
                user_prompt = extra_context + user_prompt
                logger.info("[PromptManager] 已添加消息上下文（感知/搜索/引用/文件/媒体/图片/群聊）")

        return {"system": system_prompt, "user": user_prompt}

    def _format_memory_context(self, memories: List[Dict]) -> str:
        """
        格式化记忆上下文（分层架构）

        分层策略：
        - 最近5条：完整对话
        - 5条以上：压缩为摘要
        """
        if not memories:
            return ""

        lines = ["【最近对话记录】"]
        lines.append("以下是你和用户之前的对话，请据此理解当前对话的上下文：")
        lines.append("")

        total = len(memories)

        # 最近5条完整显示
        recent_start = max(0, total - 5)

        for i, memory in enumerate(memories):
            # 超过5条的旧消息，压缩显示
            if i < recent_start and total > 5:
                # 每5条旧消息合并为一条摘要
                if i % 5 == 0:
                    chunk = memories[i : i + 5]
                    senders = []
                    topics = []
                    for m in chunk:
                        role = m.get("role", "")
                        content = m.get("content", "")[:30]
                        if role == "user":
                            senders.append("用户")
                        elif role == "assistant":
                            senders.append("弥娅")
                        if content:
                            topics.append(content)

                    unique_senders = list(dict.fromkeys(senders))
                    summary = f"[{len(chunk)}条对话] {'/'.join(unique_senders)} 聊了：{'/'.join(topics[:3])}..."
                    lines.append(summary)
                continue

            role = memory.get("role", "")
            content = memory.get("content", "")
            memory.get("timestamp", "")
            metadata = memory.get("metadata", {}) or {}
            is_scheduled = metadata.get("scheduled", False)

            if role and content:
                if role == "user":
                    lines.append(f"用户：{content}")
                elif role == "assistant":
                    tag = "[定时] " if is_scheduled else ""
                    lines.append(f"{tag}弥娅：{content}")
                else:
                    lines.append(f"{role}：{content}")
            else:
                input_text = memory.get("input", "")
                response_text = memory.get("response", "")
                if input_text:
                    lines.append(f"用户：{input_text}")
                if response_text:
                    lines.append(f"弥娅：{response_text}")
            lines.append("---")

        return "\n".join(lines)

    def get_user_prompt_template(self) -> str:
        """
        获取用户提示词模板

        Returns:
            提示词模板
        """
        return self.user_prompt_template

    def get_settings(self) -> Dict:
        """
        获取提示词管理器设置

        Returns:
            设置字典
        """
        return {
            "user_prompt_template": self.user_prompt_template,
            "memory_context_enabled": self.memory_context_enabled,
            "memory_context_max_count": self.memory_context_max_count,
            "has_personality": self.personality is not None,
        }

    def load_from_json(self, json_path: Path) -> bool:
        """
        从JSON文件加载提示词配置

        Args:
            json_path: JSON文件路径

        Returns:
            是否成功
        """
        try:
            with open(json_path, "r", encoding=Encoding.UTF8) as f:
                config = json.load(f)

            self.user_prompt_template = config.get("user_prompt_template", self.user_prompt_template)
            self.memory_context_enabled = config.get("memory_context_enabled", False)
            self.memory_context_max_count = config.get("memory_context_max_count", 5)

            print("提示：系统提示词现在由人格模块动态生成，不再从JSON加载静态配置。")

            return True

        except Exception as e:
            print(f"错误：从JSON加载配置失败：{e}")
            return False

    def save_to_json(self, json_path: Path) -> bool:
        """
        保存提示词配置到JSON文件

        Args:
            json_path: JSON文件路径

        Returns:
            是否成功
        """
        try:
            config = {
                "user_prompt_template": self.user_prompt_template,
                "memory_context_enabled": self.memory_context_enabled,
                "memory_context_max_count": self.memory_context_max_count,
            }

            # 如果有人格实例，保存当前人格状态
            if self.personality:
                config["personality_state"] = self.personality.get_profile()

            with open(json_path, "w", encoding=Encoding.UTF8) as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            print(f"错误：保存配置到JSON失败：{e}")
            return False

    def reset_to_default(self) -> None:
        """重置为默认提示词模板"""
        self.user_prompt_template = "用户输入：{user_input}"

    def export_prompt_config(self) -> str:
        """
        导出提示词配置为字符串

        Returns:
            配置字符串
        """
        config = self.get_settings()
        lines = [
            "弥娅提示词配置",
            "=" * 50,
            "",
            "系统提示词：",
            self.get_system_prompt(),
            "",
            "用户提示词模板：",
            self.user_prompt_template,
            "",
            "上下文设置：",
            f"- 人格联动：{'启用' if config['has_personality'] else '禁用（建议传入人格实例）'}",
            f"- 记忆上下文：{'启用' if self.memory_context_enabled else '禁用'}",
            f"- 记忆上下文最大条数：{self.memory_context_max_count}",
        ]

        # 如果有人格实例，添加人格状态
        if self.personality:
            profile = self.personality.get_profile()
            lines.extend(
                [
                    "",
                    "人格状态：",
                    f"- 主导特质：{profile['dominant']}",
                    f"- 稳定性：{profile['stability']:.2f}",
                    f"- 向量值：{profile['vectors']}",
                ]
            )

        return "\n".join(lines)

    def add_to_history(self, system_prompt: str, user_prompt: str, response: str):
        """
        添加到提示词历史

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            response: AI响应
        """
        history_entry = {
            "user_prompt": user_prompt,
            "response": response,
            "timestamp": str(Path(__file__).stat().st_mtime),
        }

        # 如果有人格实例，记录人格快照
        if self.personality:
            history_entry["personality_snapshot"] = self.personality.get_profile()

        self.prompt_history.append(history_entry)

        # 限制历史记录数量
        if len(self.prompt_history) > 100:
            self.prompt_history = self.prompt_history[-100:]

    def get_history(self, count: int = 10) -> List[Dict]:
        """
        获取提示词历史

        Args:
            count: 返回的历史记录数量

        Returns:
            历史记录列表
        """
        return self.prompt_history[-count:]
