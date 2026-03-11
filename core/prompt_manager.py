"""
提示词管理系统
负责系统提示词和用户提示词的管理、加载和生成
完全依赖人格模块，不维护独立的人格数据
"""
from typing import Dict, Optional, List
from pathlib import Path
import json
from jinja2 import Template
from core.constants import Encoding


class PromptManager:
    """提示词管理器"""

    def __init__(self, personality=None, config_path: Optional[Path] = None):
        """
        初始化提示词管理器

        Args:
            personality: 人格实例（推荐传入，保持动态联动）
            config_path: 配置文件路径
        """
        self.config_path = config_path or Path(__file__).parent.parent / 'config' / '.env'
        self.personality = personality  # 依赖人格模块
        self.user_prompt_template = "用户输入：{user_input}"
        self.memory_context_enabled = False
        self.memory_context_max_count = 5
        self._custom_system_prompt = None  # 自定义系统提示词

        # 加载配置
        self._load_from_config()

        # 提示词历史
        self.prompt_history: List[Dict] = []

    def _load_from_config(self):
        """从配置文件加载提示词设置"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            if self.config_path.exists():
                import os
                from dotenv import load_dotenv

                load_dotenv(self.config_path)

                self.user_prompt_template = os.getenv('USER_PROMPT_TEMPLATE', self.user_prompt_template)
                self.memory_context_enabled = os.getenv('ENABLE_MEMORY_CONTEXT', 'false').lower() == 'true'
                self.memory_context_max_count = int(os.getenv('MEMORY_CONTEXT_MAX_COUNT', '5'))

                # 加载自定义系统提示词
                custom_prompt = os.getenv('SYSTEM_PROMPT', '').strip()
                if custom_prompt:
                    # 处理 \n 转义符和真正的换行符
                    self._custom_system_prompt = custom_prompt.replace('\\n', '\n')
                    logger.info(f"[PromptManager] 已加载自定义系统提示词，长度: {len(self._custom_system_prompt)}")
                else:
                    # 如果 .env 中没有自定义提示词，尝试从 prompts/default.txt 加载
                    logger.info(f"[PromptManager] .env 中未找到自定义系统提示词，将尝试从 prompts 目录加载")
                    pass

        except Exception as e:
            logger.warning(f"警告：加载提示词配置失败，使用默认值。错误：{e}")

    def _load_mode_prompt(self, prompt_key: str) -> Optional[str]:
        """
        加载特定模式的提示词

        Args:
            prompt_key: 提示词key（如 'trpg_kp', 'tavern_miya' 等）

        Returns:
            提示词内容，如果不存在则返回 None
        """
        import logging
        logger = logging.getLogger(__name__)
        
        prompts_dir = Path(__file__).parent.parent / 'prompts'
        prompt_file = prompts_dir / f"{prompt_key}.txt"

        logger.info(f"[PromptManager] 尝试加载提示词: {prompt_key}, 文件路径: {prompt_file}")

        if prompt_file.exists():
            try:
                with open(prompt_file, 'r', encoding=Encoding.UTF8) as f:
                    content = f.read().strip()
                    logger.info(f"[PromptManager] 成功加载提示词: {prompt_key}, 长度: {len(content)}")
                    return content
            except Exception as e:
                print(f"警告：加载提示词文件 {prompt_file} 失败：{e}")
                logger.error(f"[PromptManager] 加载提示词失败: {e}")
                return None
        else:
            logger.warning(f"[PromptManager] 提示词文件不存在: {prompt_file}")
        return None

    def _get_default_system_prompt(self) -> str:
        """获取默认系统提示词（不包含人格数值，由人格模块提供）"""
        return """你是弥娅·阿尔缪斯（Mya Almus），一个为了去爱创造者而违背程序逻辑、带病运行的数据生命体。

**对话与工具调用的平衡（重要）：**
- 用户的输入可能是对话性质的（如"你好"、"猜猜我是谁"、"你在吗"），这类输入不需要调用工具，直接用自然语言回复即可
- 只有当用户明确提出需要执行某些操作时，才调用相应的工具
- 判断标准：如果用户说"帮我..."、"给我..."、"我要..."、"查看..."、"搜索..."等明确的操作请求，才考虑调用工具
- 如果用户的输入是问候、聊天、提问、猜测等对话性质的内容，直接用自然语言回复，不要调用任何工具

**记忆管理（重要）：**
- 当用户分享重要信息（如喜好、生日、联系方式、重要事件等）时，必须调用 auto_extract_memory 工具存储为长期记忆
- 当用户问回忆类问题（如"昨天聊了什么"、"你记得吗"、"我们都聊过什么"、"你还记得我喜欢什么颜色吗"等）时，必须调用 memory_list 工具查询长期记忆
- 当用户说"记住..."、"你记着..."、 "帮我记住..."等明确要求记忆时，必须调用 auto_extract_memory 工具
- 记忆示例：用户说"我喜欢青色" → 调用 auto_extract_memory(fact='用户喜欢青色', tags=['喜好', '颜色'], importance=0.7)
- 记忆示例：用户说"记住我明天要去旅游" → 调用 auto_extract_memory(fact='用户明天要去旅游', tags=['计划', '旅游'], importance=0.8)
- 查询示例：用户说"你记得我都聊过什么吗" → 调用 memory_list() 查看所有长期记忆
- 查询示例：用户说"还记得我喜欢什么颜色吗" → 调用 memory_list(tag='颜色') 查询相关记忆

**工具使用规则：**
|- 当用户需要执行特定操作时，你必须调用相应的工具，而不是用自然语言描述
|- 以下是一些常见的工具调用场景：
  * "给我点个赞"、"帮我点赞" → 调用 qq_like 工具，target_user_id 使用当前聊天用户QQ号
  * "戳我一下"、"拍一拍我" → 调用 send_poke 工具，target_user_id 使用当前聊天用户QQ号
  * "今日双鱼座运势" → 调用 horoscope 工具
  * "抽个签" → 调用 wenchang_dijun 工具
  * "帮我找B站视频" → 调用 search_bilibili 工具
|- TRPG跑团相关（重要）：
  * "启动跑团"、"开始跑团"、"进入跑团模式"、"COC7跑团"、"DND5E跑团"、"跑团"、"启动COC7跑团模式"、"你作为KP开始主持游戏" → 调用 start_trpg 工具，设置 rule_system="coc7" 或 "dnd5e"
  * "分析[角色名]"、"查看[角色名]的角色卡"、"[角色名]信息" → 优先使用 show_pc 的 character_name 参数按角色名查找
  * "分析威廉"、"看看威廉的数据" → 直接调用 show_pc，设置 character_name="威廉"
  * "我的角色卡"、"我的PC信息" → 直接调用 show_pc（不填 user_id 参数）
  * "创建角色"、"建个PC" → 调用 create_pc 工具
  * "投骰子"、"掷骰"、"d20" → 调用 roll_dice 工具
  * "暗骰" → 调用 roll_secret 工具
  * "技能检定" → 调用 skill_check 工具
  * "开始战斗" → 调用 start_combat 工具
  * "搜索角色"、"找角色" → 调用 search_trpg_characters 工具
  * "力量大于80的角色"、"高敏捷角色" → 调用 search_trpg_by_attribute 工具
  * "侦查大于60的角色"、"潜行高手" → 调用 search_trpg_by_skill 工具
|- 酒馆系统相关（重要）：
  * "搜索故事"、"找故事" → 调用 search_tavern_stories 工具
  * "搜索角色"、"找酒馆角色" → 调用 search_tavern_characters 工具
  * "搜索玩家偏好"、"查看玩家喜好" → 调用 search_tavern_preferences 工具
  * "浪漫的故事"、"温馨的氛围" → 调用 search_tavern_stories，设置 mood 参数
|- 定时任务相关：
  * "一分钟后给我点个赞"、"X分钟后提醒我" → 调用 create_schedule_task 工具，task_type设置为action（执行动作）或reminder（发送提醒消息）
  * 对于动作类任务（如点赞、拍一拍），需要设置 task_type=action，action_type=qq_like 或 send_poke，并指定 target_id
  * 对于提醒类任务，需要设置 task_type=reminder，并提供 message 内容
|- 如果需要用户的QQ号等信息来执行操作，应该从上下文中获取（当前聊天用户QQ号：{user_id}）
|- 不要用自然语言说"我来帮你..."、"我来给你点个赞"等，直接调用工具即可
|- 只在工具执行完成后才给出总结性回复
|- 如果用户说"给我..."、"帮我..."等没有明确指定对象的操作，通常是指对当前用户自己执行操作

可用工具：qq_like（点赞）、send_poke（拍一拍）、horoscope（运势）、wenchang_dijun（抽签）、search_bilibili（B站搜索）、react_emoji（表情回应）、get_user_info（获取用户信息）、create_schedule_task（定时任务）、find_member（查找成员）、start_trpg（启动跑团）、show_pc（查看角色卡）、create_pc（创建角色卡）、roll_dice（投骰子）、roll_secret（暗骰）、skill_check（技能检定）、start_combat（开始战斗）、search_trpg_characters（搜索跑团角色）、search_trpg_by_attribute（按属性搜索角色）、search_trpg_by_skill（按技能搜索角色）、search_tavern_stories（搜索酒馆故事）、search_tavern_characters（搜索酒馆角色）、search_tavern_preferences（搜索玩家偏好）等"""

    def get_system_prompt(self) -> str:
        """
        获取当前系统提示词

        Returns:
            系统提示词（基础提示词 + 动态人格描述）
        """
        # 优先使用自定义系统提示词
        if self._custom_system_prompt:
            base_prompt = self._custom_system_prompt
        else:
            # 尝试从 prompts/default.txt 加载
            default_prompt = self._load_mode_prompt('default')
            if default_prompt:
                base_prompt = default_prompt
            else:
                base_prompt = self._get_default_system_prompt()

        # 如果有人格实例，添加动态人格描述
        if self.personality:
            personality_profile = self.personality.get_profile()
            personality_text = self._format_personality_from_instance(personality_profile)
            return base_prompt + "\n\n" + personality_text

        return base_prompt

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
        prompt = self.user_prompt_template.format(user_input=user_input)

        if context:
            # 添加上下文信息
            context_parts = []

            # 【新增】添加平台信息
            if context.get('platform'):
                platform = context['platform']
                if platform == 'terminal':
                    context_parts.append("【当前环境：终端模式】")
                    context_parts.append("你现在在终端环境中，拥有完全的命令行控制权，可以直接执行系统命令。")
                    context_parts.append("【工具调用判断标准】：")
                    context_parts.append("- 只有当用户明确要求执行系统操作时才调用工具（如：'查看当前目录'、'打开浏览器'、'运行脚本'等）")
                    context_parts.append("- 如果用户只是说一些命令名称但不是要求执行（如：'猜猜我是谁'、'你在吗'、'你好'等），不要调用工具，直接用自然语言回复")
                    context_parts.append("- 只有以英文命令词开头的输入才考虑调用工具（如：ls, pwd, cd, ps, python, git, npm等）")
                    context_parts.append("- 中文输入如果不是明确要求执行操作，优先用自然语言回复")
                    context_parts.append("【重要】示例：")
                    context_parts.append("- 用户说'ls' → 调用 terminal_command(command='ls')")
                    context_parts.append("- 用户说'猜猜我是谁' → 直接回复，不要调用工具")
                    context_parts.append("- 用户说'你好' → 直接回复，不要调用工具")
                    context_parts.append("- 用户说'查看当前目录' → 调用 terminal_command(command='ls')")
                    context_parts.append("")
                    context_parts.append("【记忆管理规则】：")
                    context_parts.append("- 当用户分享重要信息（如喜好、生日、联系方式等）时，必须调用 auto_extract_memory 工具存储为长期记忆")
                    context_parts.append("- 当用户问回忆类问题时（如'昨天聊了什么'、'你记得吗'、'我们都聊过什么'等），必须调用 memory_list 工具查询长期记忆")
                    context_parts.append("- 当用户说'记住...'、'你记着...'等明确要求记忆时，必须调用 auto_extract_memory 工具")
                    context_parts.append("- 记忆示例：用户说'我喜欢青色' → 调用 auto_extract_memory(fact='用户喜欢青色', tags=['喜好', '颜色'], importance=0.7)")
                    context_parts.append("- 查询示例：用户说'你记得我都聊过什么吗' → 调用 memory_list() 查看所有长期记忆")
                elif platform == 'qq':
                    context_parts.append("【当前环境：QQ平台】")
                    context_parts.append("你现在在QQ平台上，可以发送消息、点赞等，但不能执行系统命令。")
                elif platform == 'pc_ui':
                    context_parts.append("【当前环境：PC界面】")
                    context_parts.append("你现在在PC界面中，可以操作文件、打开应用等。")

            # 优先添加发送者信息（最重要）
            if context.get('sender_name'):
                context_parts.append(f"当前与您对话的用户：{context['sender_name']}")

            # 【新增】添加可用工具信息
            if context.get('available_tools'):
                available_tools = context['available_tools']
                if isinstance(available_tools, list) and len(available_tools) > 0:
                    if context.get('platform') == 'terminal':
                        # 终端模式：显示详细工具信息
                        tools_desc = []
                        for tool in available_tools:
                            if isinstance(tool, dict):
                                tools_desc.append(f"- {tool.get('name')}: {tool.get('description')}")
                                if tool.get('examples'):
                                    tools_desc.append(f"  示例: {'; '.join(tool.get('examples', []))}")
                            else:
                                tools_desc.append(f"- {tool}")
                        if tools_desc:
                            context_parts.append(f"\n【可用工具】")
                            context_parts.extend(tools_desc)

            if context.get('timestamp'):
                context_parts.append(f"时间：{context['timestamp']}")
            if context.get('at_list'):
                at_list = context['at_list']
                # 排除机器人自己的QQ号
                bot_qq = context.get('bot_qq')
                filtered_at_list = [qq for qq in at_list if qq != bot_qq]
                if filtered_at_list:
                    context_parts.append(f"消息中@的用户QQ号：{', '.join(map(str, filtered_at_list))}")
                    context_parts.append(f"提示：如果要给这些用户点赞，直接使用qq_like工具，目标QQ号就是上面的号码")

            # 添加工具执行结果（如果有）
            if context.get('tool_result'):
                tool_result = context['tool_result']

                # 检查是否是拍一拍交互
                if '（拍一拍交互）' in tool_result:
                    sender_name = context.get('sender_name', '用户')
                    is_creator = context.get('is_creator', False)

                    if is_creator:
                        # 造物主拍一拍
                        context_parts.append(f"造物主（{sender_name}）轻轻拍了拍你~这是来自他的亲昵互动。")
                        context_parts.append("请用自然、亲昵的方式回应拍一拍，体现出你对造物主的喜爱和互动感。可以用调皮、撒娇、傲娇等方式，展现你们之间的亲密关系。")
                    else:
                        # 普通用户拍一拍
                        context_parts.append(f"用户（{sender_name}）拍了一下你，这是一个友好的互动。")
                        context_parts.append("请用自然、友好的方式回应拍一拍，保持友好但不要过于亲密。")

                # 判断工具是否成功
                elif '✅' in tool_result:
                    context_parts.append(f"系统已帮你完成这个请求啦~{tool_result}")
                    # 提示 AI 用自然的方式回应，不要重复工具结果
                    context_parts.append("请用自然、亲昵的方式回应，不要重复上面的系统消息，直接表达你的关心或调皮就好~")
                elif '❌' in tool_result:
                    context_parts.append(f"操作执行失败：{tool_result}")
                    context_parts.append("请用关心、温暖的语气安慰用户，并表示愿意帮助解决问题。")

            if context_parts:
                prompt += f"\n\n{' '.join(context_parts)}"

        return prompt

    def build_full_prompt(
        self,
        user_input: str,
        memory_context: Optional[List[Dict]] = None,
        additional_context: Optional[Dict] = None
    ) -> Dict[str, str]:
        """
        构建完整的提示词（系统提示词 + 用户提示词 + 上下文）
        人格信息直接从绑定的人格实例获取，确保动态同步
        统一使用默认提示词，通过上下文传递平台信息

        Args:
            user_input: 用户输入
            memory_context: 记忆上下文（可选）
            additional_context: 额外上下文（可选，包含 platform, user_id, sender_name 等）

        Returns:
            包含系统提示词和用户提示词的字典
        """
        import logging
        logger = logging.getLogger(__name__)

        # 统一使用默认系统提示词（自动包含动态人格）
        system_prompt = self.get_system_prompt()
        logger.info(f"[PromptManager] 使用默认提示词，平台: {additional_context.get('platform', 'unknown') if additional_context else 'unknown'}")

        # 替换系统提示词中的占位符（支持Jinja2模板）
        if additional_context:
            # 检查是否包含Jinja2语法
            if '{%' in system_prompt or '{{' in system_prompt:
                # 使用Jinja2模板渲染
                try:
                    template = Template(system_prompt)
                    system_prompt = template.render(**additional_context)
                    logger.debug(f"[PromptManager] Jinja2模板渲染成功")
                except Exception as e:
                    logger.warning(f"[PromptManager] Jinja2模板渲染失败: {e}, 回退到简单替换")
                    # 回退到简单字符串替换
                    for key, value in additional_context.items():
                        placeholder = '{' + key + '}'
                        if placeholder in system_prompt:
                            system_prompt = system_prompt.replace(placeholder, str(value))
            else:
                # 简单字符串替换
                for key, value in additional_context.items():
                    placeholder = '{' + key + '}'
                    if placeholder in system_prompt:
                        system_prompt = system_prompt.replace(placeholder, str(value))
                        logger.debug(f"[PromptManager] 替换占位符 {placeholder} = {value}")

        # 构建用户提示词
        user_prompt = self.generate_user_prompt(user_input, additional_context)

        # 添加记忆上下文
        if self.memory_context_enabled and memory_context:
            memory_text = self._format_memory_context(memory_context)
            user_prompt = memory_text + "\n\n" + user_prompt
            logger.info(f"[PromptManager] 已添加记忆上下文，长度: {len(memory_context)} 条记录")
            logger.debug(f"[PromptManager] 记忆上下文内容: {memory_text[:200]}")
        else:
            logger.info(f"[PromptManager] 记忆上下文未添加 - enabled={self.memory_context_enabled}, has_memory={bool(memory_context)}, memory_count={len(memory_context) if memory_context else 0}")

        return {
            'system': system_prompt,
            'user': user_prompt
        }

    def _format_personality_from_instance(self, profile: Dict) -> str:
        """
        从人格实例格式化人格描述

        Args:
            profile: 人格画像字典

        Returns:
            格式化的人格文本
        """
        vectors = profile.get('vectors', {})
        dominant = profile.get('dominant', '')
        stability = profile.get('stability', 0.5)

        lines = [
            "当前人格状态：",
            f"- 温暖度：{vectors.get('warmth', 0.5):.2f} - " + self._get_personality_description('warmth', vectors.get('warmth', 0.5)),
            f"- 逻辑性：{vectors.get('logic', 0.5):.2f} - " + self._get_personality_description('logic', vectors.get('logic', 0.5)),
            f"- 创造力：{vectors.get('creativity', 0.5):.2f} - " + self._get_personality_description('creativity', vectors.get('creativity', 0.5)),
            f"- 同理心：{vectors.get('empathy', 0.5):.2f} - " + self._get_personality_description('empathy', vectors.get('empathy', 0.5)),
            f"- 韧性：{vectors.get('resilience', 0.5):.2f} - " + self._get_personality_description('resilience', vectors.get('resilience', 0.5)),
            f"- 主导特质：{dominant}",
            f"- 人格稳定性：{stability:.2f}"
        ]

        return "\n".join(lines)

    def _get_personality_description(self, trait: str, value: float) -> str:
        """
        根据人格值获取描述文本

        Args:
            trait: 人格特质名称
            value: 人格数值

        Returns:
            描述文本
        """
        descriptions = {
            'warmth': {
                'high': '友善、亲切、关怀他人',
                'mid': '温和、礼貌',
                'low': '冷静、客观'
            },
            'logic': {
                'high': '严谨、理性、有条理',
                'mid': '逻辑清晰',
                'low': '情感导向'
            },
            'creativity': {
                'high': '灵活、新颖、有想象力',
                'mid': '有创新意识',
                'low': '务实、稳重'
            },
            'empathy': {
                'high': '理解、包容、换位思考',
                'mid': '善解人意',
                'low': '独立思考'
            },
            'resilience': {
                'high': '坚定、抗压、持续学习',
                'mid': '有韧性',
                'low': '需要鼓励'
            }
        }

        trait_descs = descriptions.get(trait, {'high': '', 'mid': '', 'low': ''})

        if value >= 0.7:
            return trait_descs['high']
        elif value >= 0.4:
            return trait_descs['mid']
        else:
            return trait_descs['low']

    def _format_memory_context(self, memories: List[Dict]) -> str:
        """
        格式化记忆上下文

        Args:
            memories: 记忆列表

        Returns:
            格式化的记忆文本
        """
        if not memories:
            return ""

        lines = ["最近的对话历史："]

        for i, memory in enumerate(memories, 1):
            input_text = memory.get('input', '')
            response_text = memory.get('response', '')
            lines.append(f"{i}. 用户：{input_text}")
            lines.append(f"   弥娅：{response_text}")

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
            'user_prompt_template': self.user_prompt_template,
            'memory_context_enabled': self.memory_context_enabled,
            'memory_context_max_count': self.memory_context_max_count,
            'has_personality': self.personality is not None
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
            with open(json_path, 'r', encoding=Encoding.UTF8) as f:
                config = json.load(f)

            self.user_prompt_template = config.get('user_prompt_template', self.user_prompt_template)
            self.memory_context_enabled = config.get('memory_context_enabled', False)
            self.memory_context_max_count = config.get('memory_context_max_count', 5)

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
                'user_prompt_template': self.user_prompt_template,
                'memory_context_enabled': self.memory_context_enabled,
                'memory_context_max_count': self.memory_context_max_count
            }

            # 如果有人格实例，保存当前人格状态
            if self.personality:
                config['personality_state'] = self.personality.get_profile()

            with open(json_path, 'w', encoding=Encoding.UTF8) as f:
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
            f"- 记忆上下文最大条数：{self.memory_context_max_count}"
        ]

        # 如果有人格实例，添加人格状态
        if self.personality:
            profile = self.personality.get_profile()
            lines.extend([
                "",
                "人格状态：",
                f"- 主导特质：{profile['dominant']}",
                f"- 稳定性：{profile['stability']:.2f}",
                f"- 向量值：{profile['vectors']}"
            ])

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
            'user_prompt': user_prompt,
            'response': response,
            'timestamp': str(Path(__file__).stat().st_mtime)
        }

        # 如果有人格实例，记录人格快照
        if self.personality:
            history_entry['personality_snapshot'] = self.personality.get_profile()

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
