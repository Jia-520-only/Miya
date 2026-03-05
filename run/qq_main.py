"""
弥娅QQ机器人主程序
集成Undefined的QQ能力到弥娅架构
"""
import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rich.logging import RichHandler
from rich.console import Console

from core import (
    Personality, Ethics, Identity, Arbitrator, Entropy, PromptManager,
    AIClientFactory, set_tool_adapter
)
# 不再提前导入 get_tool_registry，使用 ToolNet 代替
# from webnet.tools import get_tool_registry
from hub import MemoryEmotion, MemoryEngine, Emotion, Decision, Scheduler
from hub.game_mode_adapter import GameModeAdapter  # 架构修复: 导入适配器
from webnet import QQNet
from config import Settings
from core.constants import Encoding


class MiyaQQBot:
    """弥娅QQ机器人"""

    def __init__(self):
        self.logger = self._setup_logger()
        self.settings = Settings()
        self.logger.info("弥娅QQ机器人初始化中...")

        # 初始化弥娅核心
        self.personality = Personality()
        self.ethics = Ethics()
        self.identity = Identity()
        self.arbitrator = Arbitrator(self.personality, self.ethics)
        self.entropy = Entropy()
        self.prompt_manager = PromptManager(personality=self.personality)  # 绑定人格实例

        # 初始化中枢
        self.memory_emotion = MemoryEmotion()
        self.memory_engine = MemoryEngine()
        self.emotion = Emotion()
        self.decision = Decision(self.emotion, self.personality, self.ethics)
        self.scheduler = None  # 将在工具初始化后创建，传入tool_registry

        # 初始化工具系统
        self._init_tools()

        # 初始化全局记忆系统 (M-Link + MemoryNet)
        self._init_memory_system()

        # 初始化AI客户端
        self.ai_client = self._init_ai_client()

        # 初始化LifeNet
        self._init_lifenet()

        # 设置LifeNet到ToolAdapter
        if self.life_subnet:
            from core import get_tool_adapter
            adapter = get_tool_adapter()
            adapter.set_life_subnet(self.life_subnet)

        # 初始化决策层 Hub
        self._init_decision_hub()

        # 初始化TTS子网
        self._init_tts_system()

        # 初始化QQ子网
        self.qq_net = QQNet(self, mlink=self.mlink, memory_net=self.memory_net, tts_net=self.tts_net)
        self.qq_net.set_message_callback(self._handle_qq_callback)

        # 注册 M-Link 节点
        self._register_mlink_nodes()

        self.identity.awake()
        self.logger.info("弥娅QQ机器人初始化完成")

    def _register_mlink_nodes(self):
        """注册 M-Link 节点"""
        if not self.mlink:
            return

        try:
            # 注册 QQNet 节点
            self.mlink.register_node('qq_net', [
                'qq_group_chat',
                'qq_private_chat',
                'qq_command',
                'qq_message_history',
                'qq_poke',
                'qq_multimedia',
                'qq_tts'
            ])

            # 注册 TTSNet 节点（如果存在）
            if self.tts_net:
                self.mlink.register_node('tts_net', [
                    'tts_generation',
                    'voice_synthesis',
                    'audio_output'
                ])

            # 注册 MemoryNet 节点（如果存在）
            if self.memory_net:
                self.mlink.register_node('memory_net', [
                    'memory_storage',
                    'conversation_history',
                    'memory_retrieval'
                ])

            self.logger.info("M-Link 节点注册完成")

        except Exception as e:
            self.logger.error(f"M-Link 节点注册失败: {e}")

    def _init_tools(self):
        """初始化工具系统 - 使用 ToolNet 子网（原生M-Link模式）"""
        try:
            from webnet.ToolNet import get_tool_subnet

            # 获取 ToolNet 子网（符合弥娅子网架构）
            self.tool_subnet = get_tool_subnet(
                memory_engine=self.memory_engine,
                cognitive_memory=None,  # 如果有认知记忆系统，传入实例
                onebot_client=None,  # 延迟绑定
                scheduler=None  # 初始化时不传入，稍后再设置
            )

            # 保存工具注册表引用（兼容旧版）
            self.tool_registry = self.tool_subnet.registry

            # 现在创建 scheduler 并传入 tool_registry（onebot_client稍后在QQNet初始化后设置）
            self.scheduler = Scheduler(tool_registry=self.tool_registry, onebot_client=None)

            # 设置工具适配器
            from core import get_tool_adapter
            adapter = get_tool_adapter()

            # 启用原生M-Link模式
            adapter.set_tool_registry(self.tool_registry)
            adapter.enable_native_mode(
                tool_registry=self.tool_registry,
                emotion_system=self.emotion,
                memory_engine=self.memory_engine
            )

            # 不在此处初始化统一记忆接口，等待LifeNet初始化后再调用
            self.logger.info(f"ToolNet 子网初始化成功，已加载 {len(self.tool_registry.tools)} 个工具")
            self.logger.info("✅ 已启用原生M-Link模式（感知层 + 传输层）")

        except Exception as e:
            self.logger.warning(f"ToolNet 子网初始化失败: {e}，降级到旧版工具系统")
            # 降级到旧版
            from webnet.tools import get_tool_registry
            self.tool_registry = get_tool_registry()
            self.scheduler = Scheduler(tool_registry=self.tool_registry, onebot_client=None)
            from core import get_tool_adapter
            adapter = get_tool_adapter()
            adapter.set_tool_registry(self.tool_registry)
            self.tool_subnet = None

    def _init_unified_memory(self):
        """初始化统一记忆接口（在LifeNet初始化后调用）"""
        try:
            from core.unified_memory import get_unified_memory

            self.unified_memory = get_unified_memory(
                memory_engine=self.memory_engine,
                cognitive_memory=None,  # 如果有认知记忆系统
                lifebook_manager=self.life_subnet,
                grag_memory=None
            )

            # 设置到工具适配器
            from core import get_tool_adapter
            adapter = get_tool_adapter()
            adapter.set_unified_memory(self.unified_memory)

            self.logger.info("✅ 统一记忆接口已初始化")

        except Exception as e:
            self.logger.warning(f"统一记忆接口初始化失败: {e}")
            self.unified_memory = None

    def _init_memory_system(self):
        """初始化全局记忆系统 (M-Link + MemoryNet)"""
        try:
            from mlink.mlink_core import MLinkCore
            from webnet.memory import MemoryNet

            # 初始化 M-Link
            self.mlink = MLinkCore()
            self.logger.info("M-Link 初始化成功")

            # 初始化 MemoryNet 全局记忆子网
            self.memory_net = MemoryNet(self.mlink)
            self.logger.info("MemoryNet 全局记忆子网初始化成功")

        except Exception as e:
            self.logger.error(f"全局记忆系统初始化失败: {e}")
            self.mlink = None
            self.memory_net = None

    async def _initialize_memory_net_async(self):
        """异步初始化 MemoryNet（在事件循环中调用）"""
        if self.memory_net:
            try:
                await self.memory_net.initialize()
                self.logger.info("MemoryNet 初始化完成")
            except Exception as e:
                self.logger.error(f"MemoryNet 初始化失败: {e}")

    def _init_lifenet(self):
        """初始化 LifeNet 记忆管理网络"""
        try:
            from webnet.LifeNet.subnet import LifeSubnet

            # 检查配置是否启用
            lifebook_enabled = self.settings.get('lifebook.enabled', True)

            if lifebook_enabled:
                base_dir = self.settings.get('lifebook.base_dir', 'data/lifebook')
                self.life_subnet = LifeSubnet(base_dir=base_dir, ai_client=self.ai_client)
                self.logger.info(f"LifeNet 初始化成功 (data_dir={base_dir})")
            else:
                self.life_subnet = None
                self.logger.info("LifeBook 功能已禁用")

        except Exception as e:
            self.logger.error(f"LifeNet 初始化失败: {e}")
            self.life_subnet = None

        # LifeNet初始化完成后，初始化统一记忆接口
        self._init_unified_memory()

    def _init_decision_hub(self):
        """初始化决策层 Hub"""
        try:
            from hub.decision_hub import DecisionHub
            from mlink.message import MessageType, FlowType

            # 创建决策层
            # 架构修复: 创建并传入GameModeAdapter而非直接依赖WebNet层
            self.game_mode_adapter = None
            try:
                # 延迟加载WebNet层的GameModeManager
                from webnet.EntertainmentNet.game_mode import get_game_mode_manager
                game_mode_manager = get_game_mode_manager()
                self.game_mode_adapter = GameModeAdapter(game_mode_manager)
                self.logger.info("GameModeAdapter初始化成功")
            except Exception as e:
                self.logger.warning(f"GameModeAdapter初始化失败(可能未安装游戏模式): {e}")
                self.game_mode_adapter = GameModeAdapter()  # 创建未连接的适配器

            self.decision_hub = DecisionHub(
                mlink=self.mlink,
                ai_client=self.ai_client,
                emotion=self.emotion,
                personality=self.personality,
                prompt_manager=self.prompt_manager,
                memory_net=self.memory_net,
                decision_engine=self.decision,
                tool_registry=self.tool_registry,
                memory_engine=self.memory_engine,
                scheduler=self.scheduler,
                onebot_client=None,  # 初始化时为None，稍后在QQNet初始化后设置
                game_mode_adapter=self.game_mode_adapter  # 架构修复: 传入适配器
            )

            # 设置响应回调（用于发送回 QQNet）
            self.decision_hub.set_response_callback(self._send_qq_response)

            # 注册 M-Link 节点
            self.mlink.register_node('decision_hub', [
                'decision_making',
                'ai_generation',
                'emotion_management',
                'memory_coordination'
            ])

            self.logger.info("决策层 Hub 初始化成功")

        except Exception as e:
            self.logger.error(f"决策层 Hub 初始化失败: {e}")
            self.decision_hub = None

    def _init_tts_system(self):
        """初始化TTS系统"""
        try:
            from webnet.tts import TTSNet

            # 初始化 TTSNet
            self.tts_net = TTSNet(self.mlink)

            # 加载TTS配置
            import json
            tts_config_path = Path(__file__).parent.parent / 'config' / 'tts_config.json'
            if tts_config_path.exists():
                with open(tts_config_path, 'r', encoding=Encoding.UTF8) as f:
                    tts_config = json.load(f)
                self.tts_net.initialize(tts_config)
                self.logger.info("TTS系统初始化成功")
            else:
                self.logger.warning("TTS配置文件不存在,使用默认配置")
                self.tts_net = None

        except Exception as e:
            self.logger.warning(f"TTS系统初始化失败: {e}")
            self.tts_net = None

    def _init_ai_client(self):
        """初始化AI客户端（简化版 - 只需配置URL、模型名、API KEY）"""
        try:
            import os
            from dotenv import load_dotenv

            load_dotenv(Path(__file__).parent.parent / 'config' / '.env')

            # 简化配置：只需3个参数
            api_key = os.getenv('AI_API_KEY', '')
            base_url = os.getenv('AI_API_BASE_URL', '')
            model = os.getenv('AI_MODEL', '')

            if not api_key:
                self.logger.warning("未配置 AI_API_KEY，将使用简化回复")
                return None

            if not base_url:
                self.logger.warning("未配置 AI_API_BASE_URL，将使用简化回复")
                return None

            if not model:
                self.logger.warning("未配置 AI_MODEL，将使用简化回复")
                return None

            # 使用统一的 OpenAI 格式客户端（支持任何OpenAI兼容的API）
            temperature = float(os.getenv('AI_TEMPERATURE', '0.7'))
            max_tokens = int(os.getenv('AI_MAX_TOKENS', '2000'))

            # 直接创建 OpenAIClient，不区分提供商
            from core.ai_client import OpenAIClient
            client = OpenAIClient(
                api_key=api_key,
                model=model,
                base_url=base_url,
                temperature=temperature,
                max_tokens=max_tokens
            )

            # 验证客户端是否真正初始化成功
            if not hasattr(client, 'client') or client.client is None:
                self.logger.warning("AI客户端初始化失败，将使用简化回复")
                return None

            # 设置工具注册表（延迟加载）
            if self.tool_registry:
                def get_tools():
                    return self.tool_registry.get_tools_schema()
                client.set_tool_registry(get_tools)

            self.logger.info(f"AI客户端初始化成功: {model} ({base_url})")
            return client

        except Exception as e:
            self.logger.warning(f"AI客户端初始化失败: {e}，将使用简化回复")
            return None

    def _setup_logger(self) -> logging.Logger:
        """设置日志"""
        # 设置根日志级别，确保所有模块的日志都能输出
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)

        logger = logging.getLogger('MiyaQQ')
        logger.setLevel(logging.INFO)

        # Rich控制台输出
        console = Console(force_terminal=True)
        console_handler = RichHandler(
            level=logging.INFO,
            console=console,
            show_time=True,
            show_path=True,
            markup=True,
            rich_tracebacks=True,
        )
        console_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
        # 只添加到 root_logger，避免重复输出
        # logger.addHandler(console_handler)
        root_logger.addHandler(console_handler)

        # 文件输出
        log_dir = Path(__file__).parent / '..' / 'logs'
        log_dir.mkdir(exist_ok=True)

        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_dir / f'miya_qq_{datetime.now().strftime("%Y%m%d")}.log',
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding=Encoding.UTF8
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        return logger

    async def _handle_qq_callback(self, qq_message) -> None:
        """
        处理QQ消息回调

        Args:
            qq_message: QQMessage对象
        """
        try:
            self.logger.info(
                f"[QQ消息] type={qq_message.message_type} "
                f"sender={qq_message.sender_id} "
                f"content={qq_message.message[:50]}"
            )

            # 感知层处理
            perception = {
                'source': 'qq',
                'message_type': qq_message.message_type,
                'user_id': qq_message.sender_id,
                'sender_id': qq_message.sender_id,
                'sender_name': qq_message.sender_name,
                'group_id': qq_message.group_id,
                'group_name': qq_message.group_name,
                'content': qq_message.message,
                'is_at_bot': qq_message.is_at_bot,
                'at_list': qq_message.at_list,  # 添加@列表
                'bot_qq': self.qq_net.bot_qq,  # 添加机器人QQ号
                'timestamp': datetime.now().isoformat()
            }

            # 检查用户输入是否是TTS切换指令（在AI处理之前拦截）
            content = perception.get('content', '').strip().lower()
            direct_response = None

            if content in ['/voice', '/语音']:
                self.qq_net.set_tts_mode('voice')
                direct_response = "✅ 已切换为语音模式"
            elif content in ['/text', '/文本']:
                self.qq_net.set_tts_mode('text')
                direct_response = "✅ 已切换为文本模式"
            elif content in ['/tts on', '/tts 开启', '/tts开启']:
                self.qq_net.toggle_tts(True)
                direct_response = "✅ TTS已开启"
            elif content in ['/tts off', '/tts 关闭', '/tts关闭']:
                self.qq_net.toggle_tts(False)
                direct_response = "❌ TTS已关闭"
            elif content in ['/smarttts on', '/智能tts 开启', '/智能tts开启', '/智能语音 开启']:
                self.qq_net.toggle_smart_tts(True)
                self._save_tts_config(smart_tts_enabled=True)
                direct_response = "✅ 智能TTS判断已开启"
            elif content in ['/smarttts off', '/智能tts 关闭', '/智能tts关闭', '/智能语音 关闭']:
                self.qq_net.toggle_smart_tts(False)
                self._save_tts_config(smart_tts_enabled=False)
                direct_response = "❌ 智能TTS判断已关闭"
            elif content in ['/localplay on', '/本地播放开']:
                self.qq_net.toggle_local_playback(True)
                direct_response = "✅ 本地播放已开启"
            elif content in ['/localplay off', '/本地播放关']:
                self.qq_net.toggle_local_playback(False)
                direct_response = "❌ 本地播放已关闭"
            elif content.startswith('/volume ') or content.startswith('/音量 '):
                try:
                    volume_str = content.replace('/volume ', '').replace('/音量 ', '')
                    volume = float(volume_str)
                    self.qq_net.set_local_playback_volume(volume)
                    direct_response = f"✅ 本地播放音量已设置为 {volume}"
                except:
                    direct_response = "❌ 音量设置失败，请输入 0.0-1.0 之间的数值"
            elif content in ['/streaming on', '/流式开']:
                self._update_tts_streaming_config(True)
                self._save_tts_config(streaming_enabled=True)
                direct_response = "✅ 流式响应已开启"
            elif content in ['/streaming off', '/流式关']:
                self._update_tts_streaming_config(False)
                self._save_tts_config(streaming_enabled=False)
                direct_response = "❌ 流式响应已关闭"

            # 如果是直接命令，直接发送响应
            if direct_response:
                await self._send_qq_response(qq_message, direct_response)
                return

            # 【游戏启动指令拦截】
            # 检测游戏启动关键词，直接调用工具
            game_start_result = await self._handle_game_start_commands(perception, qq_message)
            if game_start_result:
                return  # 已处理，不再继续

            # 通过 M-Link 发送感知数据到决策层
            if self.mlink and self.decision_hub:
                from mlink.message import Message, MessageType

                # 创建 M-Link 消息
                message = Message(
                    msg_type=MessageType.DATA.value,
                    content=perception,
                    source='qq_net',
                    destination='decision_hub',
                    priority=1
                )

                # 通过 M-Link 发送消息
                available_nodes = ['decision_hub']
                success = await self.mlink.send(message, available_nodes)

                if success:
                    # 决策层处理感知数据并返回响应
                    response_text = await self.decision_hub.process_perception(message)

                    # 发送响应
                    if response_text:
                        await self._send_qq_response(qq_message, response_text)
                else:
                    self.logger.warning("M-Link 发送消息失败，降级到直接处理")
                    # 降级到直接处理
                    response_text = await self._generate_response(perception)
                    if response_text:
                        await self._send_qq_response(qq_message, response_text)
            else:
                # 降级到直接处理（M-Link 或决策层未初始化）
                self.logger.debug("M-Link 或决策层未初始化，使用直接处理")
                response_text = await self._generate_response(perception)
                if response_text:
                    await self._send_qq_response(qq_message, response_text)

        except Exception as e:
            self.logger.error(f"处理QQ消息失败: {e}", exc_info=True)

    async def _handle_game_start_commands(self, perception: dict, qq_message) -> bool:
        """
        处理游戏启动指令，直接调用工具
        
        Args:
            perception: 感知数据
            qq_message: QQ消息对象
            
        Returns:
            True 表示已处理，False 表示继续处理
        """
        content = perception.get('content', '')
        
        # === 游戏启动命令 ===
        # 定义游戏启动关键词映射
        command_mapping = {
            'COC7': 'coc7',
            'coc7': 'coc7',
            'COC7跑团': 'coc7',
            'DND': 'dnd5e',
            'DND5E': 'dnd5e',
            'dnd5e': 'dnd5e',
            'DND5E跑团': 'dnd5e',
        }
        
        # 检查是否包含启动关键词
        rule_system = None
        for keyword, system in command_mapping.items():
            if keyword in content:
                rule_system = system
                break
        
        # 检查启动动词（支持更通用的启动方式）
        start_verbs = ['启动', '开始', '进入', '主持', '开启']
        game_triggers = ['跑团', 'trpg', 'TRPG']
        
        # 如果包含启动动词和游戏触发词，默认使用coc7
        if not rule_system and any(verb in content for verb in start_verbs) and any(trigger in content for trigger in game_triggers):
            rule_system = 'coc7'  # 默认使用COC7
            self.logger.info(f"[QQBot] 检测到通用跑团启动，默认使用coc7规则")
        
        if rule_system and any(verb in content for verb in start_verbs):
            self.logger.info(f"[QQBot] 拦截到游戏启动指令: {rule_system}")
            
            # 提取团名称
            session_name = '未命名团'
            import re
            name_match = re.search(r'团名[：:]\s*([^\s，,。]+)', content)
            if name_match:
                session_name = name_match.group(1)
            
            # 调用 start_trpg 工具
            try:
                from core import get_tool_adapter
                
                adapter = get_tool_adapter()
                result = await adapter.execute_tool(
                    'start_trpg',
                    {'rule_system': rule_system, 'session_name': session_name},
                    {
                        'user_id': perception.get('user_id'),
                        'group_id': perception.get('group_id'),
                        'sender_name': perception.get('sender_name'),
                        'superadmin': getattr(self.qq_net, 'superadmin_qq', None),
                        'onebot_client': self.qq_net,
                        'game_mode_adapter': self.game_mode_adapter,
                    }
                )

                # 发送工具结果
                self.logger.info(f"[QQBot] 工具返回结果: {result[:200] if result else 'None'}")
                if result:
                    await self._send_qq_response(qq_message, result)
                    self.logger.info(f"[QQBot] 游戏启动工具调用成功")
                    return True
                else:
                    self.logger.warning(f"[QQBot] 工具返回结果为空")
                    return True
                    
            except Exception as e:
                self.logger.error(f"[QQBot] 调用游戏启动工具失败: {e}", exc_info=True)
        
        # === 其他游戏相关命令（需要让AI处理，因为需要更多上下文）===
        # 这里不拦截，让AI决定如何处理这些命令
        # 包括：加载存档、投骰、技能检定、角色卡管理等
        
        return False

    async def _send_qq_response(self, qq_message, response_text: str) -> None:
        """
        发送QQ响应

        Args:
            qq_message: QQMessage对象
            response_text: 响应文本
        """
        if not response_text:
            self.logger.warning("[QQBot] _send_qq_response: response_text为空")
            return

        self.logger.info(f"[QQBot] 准备发送响应: type={qq_message.message_type}, content前100字符={response_text[:100]}")
        try:
            # 拍一拍消息需要在群中发送回复（如果有群ID）
            if qq_message.message_type == "poke":
                if qq_message.group_id and qq_message.group_id > 0:
                    await self.qq_net.send_group_message(
                        qq_message.group_id,
                        response_text
                    )
                elif qq_message.user_id and qq_message.user_id > 0:
                    # 私聊拍一拍
                    await self.qq_net.send_private_message(
                        qq_message.user_id,
                        response_text
                    )
            elif qq_message.message_type == "group":
                self.logger.info(f"[QQBot] 发送群消息: group_id={qq_message.group_id}")
                await self.qq_net.send_group_message(
                    qq_message.group_id,
                    response_text
                )
                self.logger.info(f"[QQBot] 群消息发送完成")
            elif qq_message.message_type == "private":
                self.logger.info(f"[QQBot] 发送私聊消息: user_id={qq_message.user_id}")
                await self.qq_net.send_private_message(
                    qq_message.user_id,
                    response_text
                )
                self.logger.info(f"[QQBot] 私聊消息发送完成")
        except Exception as e:
            self.logger.error(f"发送QQ响应失败: {e}", exc_info=True)

    def _update_tts_streaming_config(self, enabled: bool):
        """更新 TTS 流式响应配置（全局生效）"""
        if not self.tts_net:
            return

        try:
            # 更新所有 TTS 引擎的流式配置
            for engine_name, engine in self.tts_net.registry.engines.items():
                if hasattr(engine, 'config'):
                    engine.config['streaming'] = enabled

            self.logger.info(f"TTS 流式响应已{'开启' if enabled else '关闭'} (全局生效)")
        except Exception as e:
            self.logger.warning(f"更新 TTS 流式配置失败: {e}")

    def _save_tts_config(self, streaming_enabled: bool = None, local_playback_enabled: bool = None, local_playback_volume: float = None, smart_tts_enabled: bool = None):
        """保存 TTS 配置到文件"""
        try:
            import json
            tts_config_path = Path(__file__).parent.parent / 'config' / 'tts_config.json'

            if tts_config_path.exists():
                with open(tts_config_path, 'r', encoding=Encoding.UTF8) as f:
                    tts_config = json.load(f)

                if streaming_enabled is not None:
                    tts_config['streaming_enabled'] = streaming_enabled
                if local_playback_enabled is not None:
                    tts_config['local_playback_enabled'] = local_playback_enabled
                if local_playback_volume is not None:
                    tts_config['local_playback_volume'] = local_playback_volume
                if smart_tts_enabled is not None:
                    tts_config['smart_tts_enabled'] = smart_tts_enabled

                with open(tts_config_path, 'w', encoding=Encoding.UTF8) as f:
                    json.dump(tts_config, f, ensure_ascii=False, indent=2)

                self.logger.info("TTS 配置已保存")
        except Exception as e:
            self.logger.warning(f"保存 TTS 配置失败: {e}")

    async def _generate_response(self, perception: dict) -> str:
        """
        生成响应

        Args:
            perception: 感知数据

        Returns:
            响应文本
        """
        content = perception.get('content', '')
        sender_name = perception.get('sender_name', '用户')
        is_at_bot = perception.get('is_at_bot', False)
        message_type = perception.get('message_type', '')

        # 如果是拍一拍
        if content.endswith(' 拍了拍你'):
            response = self.emotion.influence_response(
                f"被{sender_name}拍了呢~"
            )
            return response

        # 如果是@或私聊才回复
        if message_type == 'private' or is_at_bot:
            # 日志：打印at_list
            at_list = perception.get('at_list', [])
            self.logger.info(f"[Decision] at_list={at_list}")

            # 保存记忆
            self.memory_engine.store_tide(
                f"qq_{datetime.now().timestamp()}",
                {
                    'content': content,
                    'sender_name': sender_name,
                    'message_type': message_type
                }
            )

            # 使用AI客户端生成回复
            if self.ai_client:
                try:
                    # 获取上下文
                    memory_context = self.memory_engine.get_memory_stats()
                    personality_state = self.personality.get_profile()

                    # 构建提示词（传递用户ID用于替换系统提示词中的占位符）
                    prompt_info = self.prompt_manager.build_full_prompt(
                        user_input=content,
                        memory_context=[],  # 可以添加历史记忆
                        additional_context={
                            'user_id': perception.get('user_id', 0),
                            'at_list': perception.get('at_list', []),
                            'bot_qq': self.qq_net.bot_qq
                        }
                    )

                    # 调试：打印系统提示词（截取前500字符）
                    self.logger.info(f"[系统提示词] {prompt_info['system'][:500]}")

                    # 设置工具上下文
                    if self.tool_registry:
                        # 准备工具上下文
                        tool_context = {
                            'onebot_client': self.qq_net.onebot_client,
                            'send_like_callback': getattr(self.qq_net.onebot_client, 'send_like', None),
                            'user_id': perception.get('user_id'),
                            'group_id': perception.get('group_id'),
                            'message_type': perception.get('message_type'),
                            'sender_name': sender_name,
                            'at_list': perception.get('at_list', []),  # 添加@列表
                            'memory_engine': self.memory_engine,
                            'emotion': self.emotion,
                            'personality': self.personality,
                            'scheduler': self.scheduler
                        }
                        self.logger.info(f"[ToolContext] memory_engine类型: {type(self.memory_engine)}, scheduler类型: {type(self.scheduler)}")
                        self.ai_client.set_tool_context(tool_context)

                        response = await self.ai_client.chat_with_system_prompt(
                            system_prompt=prompt_info['system'],
                            user_message=prompt_info['user'],
                            tools=self.tool_registry.get_tools_schema()
                        )
                    else:
                        response = await self.ai_client.chat_with_system_prompt(
                            system_prompt=prompt_info['system'],
                            user_message=prompt_info['user']
                        )

                    # 情绪染色
                    response = self.emotion.influence_response(response)

                    # 情绪衰减
                    self.emotion.decay_coloring()

                    return response

                except Exception as e:
                    self.logger.error(f"AI生成失败: {e}，使用简化回复")
                    return self._fallback_response(content, sender_name)
            else:
                # 没有AI客户端，使用简化回复
                return self._fallback_response(content, sender_name)

        return None

    def _fallback_response(self, content: str, sender_name: str) -> str:
        """
        降级回复（当AI不可用时）

        Args:
            content: 用户输入
            sender_name: 发送者名称

        Returns:
            回复文本
        """
        if '你好' in content or 'hi' in content.lower():
            response = f"{sender_name}你好呀~我是{self.identity.name}，很高兴认识你！"
        elif '你是谁' in content:
            response = f"我是{self.identity.name}，一个具备人格恒定、自我感知、记忆成长、情绪共生的数字生命。"
        elif '状态' in content:
            emotion_state = self.emotion.get_emotion_state()
            response = (
                f"当前情绪状态: {emotion_state['dominant']}，强度: {emotion_state['intensity']:.2f}\n"
                f"记忆数量: {self.memory_engine.get_memory_stats()['tide_count']}"
            )
        else:
            response = self.emotion.influence_response(
                f"收到了{sender_name}的消息: {content}"
            )

        return response

    async def start(self) -> None:
        """启动机器人"""
        self.logger.info("正在启动弥娅QQ机器人...")

        # 异步初始化 MemoryNet
        await self._initialize_memory_net_async()

        # 配置QQ子网
        onebot_ws_url = self.settings.get('qq.onebot_ws_url', 'ws://localhost:3001')
        onebot_token = self.settings.get('qq.onebot_token', '')
        bot_qq = self.settings.get('qq.bot_qq', 0)
        superadmin_qq = self.settings.get('qq.superadmin_qq', 0)

        # 读取TTS配置
        import json
        tts_enabled = True
        tts_mode = "text"
        qq_message_split = True
        qq_max_message_length = 200
        local_playback_enabled = False
        local_playback_volume = 1.0
        streaming_enabled = False
        smart_tts_enabled = False
        try:
            tts_config_path = Path(__file__).parent.parent / 'config' / 'tts_config.json'
            if tts_config_path.exists():
                with open(tts_config_path, 'r', encoding=Encoding.UTF8) as f:
                    tts_config = json.load(f)
                    tts_enabled = tts_config.get('enabled', True)
                    tts_mode = tts_config.get('qq_default_mode', 'text')
                    qq_message_split = tts_config.get('qq_message_split', True)
                    qq_max_message_length = tts_config.get('qq_max_message_length', 200)
                    local_playback_enabled = tts_config.get('local_playback_enabled', False)
                    local_playback_volume = tts_config.get('local_playback_volume', 1.0)
                    streaming_enabled = tts_config.get('streaming_enabled', False)
                    smart_tts_enabled = tts_config.get('smart_tts_enabled', False)

                # 更新 TTS 引擎的流式配置（全局生效）
                if streaming_enabled:
                    self._update_tts_streaming_config(True)
        except:
            pass

        self.qq_net.configure(
            onebot_ws_url=onebot_ws_url,
            onebot_token=onebot_token,
            bot_qq=bot_qq,
            superadmin_qq=superadmin_qq,
            tts_enabled=tts_enabled,
            tts_voice_mode=tts_mode,
            smart_tts_enabled=smart_tts_enabled,
            qq_message_split=qq_message_split,
            qq_max_message_length=qq_max_message_length,
            local_playback_enabled=local_playback_enabled,
            local_playback_volume=local_playback_volume,
        )

        # 连接并运行
        await self.qq_net.connect()

        # QQNet 连接后，设置 scheduler 的 onebot_client（此时 onebot_client 已创建）
        if self.scheduler and hasattr(self.qq_net, 'onebot_client') and self.qq_net.onebot_client:
            self.scheduler.onebot_client = self.qq_net.onebot_client
            self.logger.info("Scheduler 已设置 onebot_client")

        # 同时设置 decision_hub 的 onebot_client
        if self.decision_hub and hasattr(self.qq_net, 'onebot_client') and self.qq_net.onebot_client:
            self.decision_hub.onebot_client = self.qq_net.onebot_client
            self.logger.info("DecisionHub 已设置 onebot_client")

        self.logger.info("=" * 50)
        self.logger.info(f"        {self.identity.name} QQ机器人")
        self.logger.info(f"        UUID: {self.identity.uuid}")
        self.logger.info(f"        版本: {self.identity.version}")
        self.logger.info(f"        启动时间: {self.identity.awake_time}")
        self.logger.info("=" * 50)

        # 启动调度器
        await self.scheduler.start()

        await self.qq_net.start()

    async def stop(self) -> None:
        """停止机器人"""
        self.logger.info("正在停止弥娅QQ机器人...")
        await self.scheduler.stop()
        await self.qq_net.stop()
        self.logger.info("弥娅QQ机器人已停止")


def check_onebot_available():
    """检查OneBot服务是否可用"""
    import os
    from dotenv import load_dotenv

    # 加载配置
    config_path = Path(__file__).parent.parent / 'config' / '.env'
    if config_path.exists():
        load_dotenv(config_path)

    onebot_ws_url = os.getenv('QQ_ONEBOT_WS_URL', 'ws://localhost:3001')
    bot_qq = os.getenv('QQ_BOT_QQ', '0')

    print("\n" + "=" * 60)
    print("  弥娅 QQ机器人 - 配置检查")
    print("=" * 60)
    print()
    print(f"OneBot WebSocket地址: {onebot_ws_url}")
    print(f"机器人QQ号: {bot_qq}")
    print()

    if bot_qq == '0':
        print("[WARN] 警告: 未配置机器人QQ号!")
        print("   请在 config/.env 中设置 QQ_BOT_QQ=你的QQ号")
        print()
        return False

    print("[OK] 基本配置检查通过")
    print()
    print("[WARN] 重要提示:")
    print("   1. 确保OneBot服务已启动 (NapCat或go-cqhttp)")
    print("   2. 确保OneBot的WebSocket地址配置正确")
    print("   3. 详细配置请参考: docs/QQ_BOT_SETUP.md")
    print()
    print("=" * 60)

    response = input("确认OneBot服务已启动? (y/n): ").strip().lower()
    return response == 'y'


def main():
    """主函数"""
    # 检查配置
    if not check_onebot_available():
        print()
        print("请先配置OneBot服务后再启动。")
        print()
        return 1

    bot = MiyaQQBot()

    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        asyncio.run(bot.stop())
    except ConnectionRefusedError as e:
        print()
        print("=" * 60)
        print("[ERROR] 连接失败!")
        print("=" * 60)
        print()
        print(f"错误信息: {e}")
        print()
        print("可能的原因:")
        print("  1. OneBot服务未启动")
        print("  2. WebSocket地址配置错误")
        print("  3. 端口被占用")
        print()
        print("解决方法:")
        print("  1. 启动OneBot服务 (NapCat或go-cqhttp)")
        print("  2. 检查 config/.env 中的 QQ_ONEBOT_WS_URL")
        print("  3. 参考 docs/QQ_BOT_SETUP.md 进行配置")
        print()
        print("=" * 60)
        return 1
    except Exception as e:
        logging.error(f"运行错误: {e}", exc_info=True)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
