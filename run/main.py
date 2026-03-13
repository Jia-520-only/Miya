"""
弥娅系统总入口（终端模式）- 使用统一跨平台架构
"""
import sys
import logging
import asyncio
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core import Personality, Ethics, Identity, Arbitrator, Entropy, PromptManager
from hub import MemoryEmotion, MemoryEngine, Emotion, Decision, Scheduler, DecisionHub
from mlink import MLinkCore, Message, Router
from perceive import PerceptualRing, AttentionGate
from webnet import NetManager, CrossNetEngine
from detect import TimeDetector, SpaceDetector, NodeDetector, EntropyDiffusion
from trust import TrustScore, TrustPropagation
from evolve import Sandbox, ABTest, UserCoPlay
from storage import RedisAsyncClient, initialize_redis, get_redis_client, MilvusClient, Neo4jClient
from config import Settings
from core.constants import Encoding
from hub.platform_adapters import get_adapter
from tools.terminal import TerminalTool
from core.system_detector import get_system_detector
from core.autonomy_with_personality import get_autonomy_with_personality

# 导入多终端管理器
from core.terminal_orchestrator import IntelligentTerminalOrchestrator
from core.terminal_types import TerminalType
from core.terminal_manager import (
    MasterTerminalController,
    ChildTerminalManager,
    ChildTerminalConfig,
    MiyaTakeoverMode
)
from core.ssh_terminal_manager import SSHTerminalManager


class Miya:
    """弥娅系统主类（支持跨平台统一交互）"""

    def __init__(self):
        self.logger = self._setup_logger()
        self.settings = Settings()
        self.logger.info("弥娅系统初始化中...")

        # 【第一阶段】系统环境检测
        self.system_detector = get_system_detector()
        self.system_info = self.system_detector.detect()
        self.logger.info(f"✅ 系统检测完成:")
        self.logger.info(f"   操作系统: {self.system_info.os_name} {self.system_info.os_version}")
        if self.system_info.distro != "unknown":
            self.logger.info(f"   发行版: {self.system_info.distro} {self.system_info.distro_version}")
        self.logger.info(f"   架构: {self.system_info.arch}")
        self.logger.info(f"   Shell: {self.system_info.shell}")
        self.logger.info(f"   Python: {self.system_info.python_version}")
        if self.system_info.node_version != "not_installed":
            self.logger.info(f"   Node.js: {self.system_info.node_version}")
        self.logger.info(f"   包管理器: {', '.join(self.system_info.package_managers)}")
        self.logger.info(f"   当前路径: {self.system_info.current_path}")

        # 初始化核心层
        self.personality = Personality()
        self.ethics = Ethics()
        self.identity = Identity()
        self.arbitrator = Arbitrator(self.personality, self.ethics)
        self.entropy = Entropy()
        self.prompt_manager = PromptManager(personality=self.personality)

        # 初始化中枢层
        self.memory_emotion = MemoryEmotion()
        self.memory_engine = MemoryEngine()
        self.emotion = Emotion()
        self.decision = Decision(self.emotion, self.personality, self.ethics)
        self.scheduler = Scheduler()

        # 初始化M-Link
        self.mlink = MLinkCore()

        # 初始化感知层
        self.perceptual_ring = PerceptualRing()
        self.attention_gate = AttentionGate()

        # 初始化子网
        self.net_manager = NetManager()
        self.cross_net_engine = CrossNetEngine(self.net_manager)

        # 初始化检测层
        self.time_detector = TimeDetector()
        self.space_detector = SpaceDetector()
        self.node_detector = NodeDetector()
        self.entropy_diffusion = EntropyDiffusion()

        # 初始化信任系统
        self.trust_score = TrustScore()
        self.trust_propagation = TrustPropagation(self.trust_score)

        # 初始化演化层
        self.sandbox = Sandbox()
        self.ab_test = ABTest()
        self.user_co_play = UserCoPlay()

        # 初始化存储（使用统一Redis客户端）
        self.logger.info(f"  [数据库] Redis 初始化中...")
        self.redis = RedisAsyncClient()
        redis_status = "已连接" if not self.redis.is_mock else "模拟模式"
        self.logger.info(f"  [数据库] Redis {redis_status}")

        self.logger.info(f"  [数据库] Milvus 初始化中...")
        self.milvus = MilvusClient()
        milvus_status = f"Milvus Lite (本地)" if self.milvus._is_lite else "远程Milvus"
        if self.milvus.is_mock_mode():
            milvus_status = "模拟模式"
        self.logger.info(f"  [数据库] Milvus {milvus_status}")

        self.neo4j = self._init_neo4j()

        # 初始化全局记忆系统 (M-Link + MemoryNet)
        self._init_memory_system()

        # 【框架一致性】初始化 ToolNet 子网（符合 MIYA 蛛网式分布式架构）
        self.tool_subnet = None
        self._init_tool_subnet()

        # 【框架一致性】终端工具由 DecisionHub 管理,不在这里初始化

        # 【WebNet】初始化 Web 子网
        self.web_net = None
        self._init_web_net()

        # 初始化 AI 客户端
        self.ai_client = self._init_ai_client()

        # 初始化向量系统
        self._init_vector_system()

        # 初始化 DecisionHub（跨平台统一决策）
        self.decision_hub = DecisionHub(
            mlink=self.mlink,
            ai_client=self.ai_client,
            emotion=self.emotion,
            personality=self.personality,
            prompt_manager=self.prompt_manager,
            memory_net=self.memory_net,  # 传入MemoryNet，实现统一记忆
            decision_engine=self.decision,
            tool_subnet=self.tool_subnet,  # 传入 ToolNet 子网（符合 MIYA 框架）
            memory_engine=self.memory_engine,
            scheduler=self.scheduler,
            onebot_client=None,
            game_mode_adapter=None,
            identity=self.identity,
            multi_model_manager=getattr(self, 'multi_model_manager', None),  # 传递多模型管理器
            miya_instance=self  # 传递miya实例，用于获取系统状态
        )

        # 初始化平台适配器
        self.terminal_adapter = get_adapter('terminal')

        # 【多终端】初始化多终端编排器
        self.terminal_orchestrator = IntelligentTerminalOrchestrator()
        self.logger.info("[多终端] 终端编排器初始化成功")

        # 【主终端控制器】初始化主终端控制器（主-子终端协作架构）
        self.ssh_manager = SSHTerminalManager()
        self.master_terminal_controller = MasterTerminalController(
            local_manager=self.terminal_orchestrator.terminal_manager,
            ssh_manager=self.ssh_manager,
            show_thinking=True,
            auto_monitor=True,
            monitor_interval=1.0
        )
        self.child_terminal_manager = ChildTerminalManager(
            local_manager=self.terminal_orchestrator.terminal_manager,
            ssh_manager=self.ssh_manager
        )
        self.miya_takeover_mode = MiyaTakeoverMode(
            master_controller=self.master_terminal_controller,
            child_manager=self.child_terminal_manager
        )
        self.logger.info("[多终端] 主-子终端协作架构初始化完成")

        # 【弥娅回调】设置弥娅AI回调
        self.miya_takeover_mode.set_miya_callback(self._miya_ai_callback)
        self.logger.info("[多终端] 弥娅AI回调已设置")

        # 【自主能力】初始化带人设的自主能力
        self.autonomy_with_personality = get_autonomy_with_personality(
            personality=self.personality,
            emotion=self.emotion,
            memory_engine=self.memory_engine,
            memory_emotion=self.memory_emotion
        )
        self.autonomy_with_personality.initialize()
        self.logger.info("✅ 自主能力已初始化（含人设集成）")

        # 【WebNet】初始化 Web API 路由器
        self.web_api = None
        self._init_web_api()

        self.logger.info("弥娅系统初始化完成（含跨平台支持）")
        self.identity.awake()

    def _setup_logger(self) -> logging.Logger:
        """设置日志"""
        logger = logging.getLogger('Miya')
        logger.setLevel(logging.INFO)

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # 文件处理器
        log_dir = Path(__file__).parent / '..' / 'logs'
        log_dir.mkdir(exist_ok=True)

        file_handler = logging.FileHandler(
            log_dir / f'miya_{datetime.now().strftime("%Y%m%d")}.log',
            encoding=Encoding.UTF8
        )
        file_handler.setLevel(logging.DEBUG)

        # 格式化
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

        return logger

    def _init_neo4j(self):
        """初始化 Neo4j 客户端"""
        import os
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).parent.parent / 'config' / '.env')

        neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
        neo4j_password = os.getenv('NEO4J_PASSWORD')
        neo4j_database = os.getenv('NEO4J_DATABASE', 'neo4j')

        self.logger.info(f"  [数据库] Neo4j 配置: {neo4j_uri} (用户: {neo4j_user})")

        if neo4j_password:
            neo4j = Neo4jClient(
                uri=neo4j_uri,
                user=neo4j_user,
                password=neo4j_password,
                database=neo4j_database
            )
            if neo4j.is_mock_mode():
                self.logger.warning(f"  [数据库] Neo4j 连接失败，使用模拟模式")
            else:
                self.logger.info(f"  [数据库] Neo4j 连接成功")
        else:
            self.logger.warning(f"  [数据库] 未配置 Neo4j 密码，使用模拟模式")
            neo4j = None

        return neo4j

    def _init_terminal_tool(self):
        """初始化终端工具"""
        try:
            terminal_tool = TerminalTool()
            self.logger.info(f"  [工具] 终端工具初始化成功")
            return terminal_tool
        except Exception as e:
            self.logger.warning(f"  [工具] 终端工具初始化失败: {e}")
            return None

    def _init_tool_subnet(self):
        """
        初始化 ToolNet 子网（符合 MIYA 蛛网式分布式架构）

        ToolNet 是 MIYA 框架的工具子网，包含：
        - 基础工具（时间、用户信息、Python 解释器）
        - 终端命令工具（弥娅完全掌控命令行）
        - 消息工具、群工具、记忆工具等
        """
        try:
            from webnet.ToolNet import get_tool_subnet

            self.tool_subnet = get_tool_subnet(
                memory_engine=self.memory_engine,
                cognitive_memory=self.memory_net,  # MemoryNet 即为认知记忆
                onebot_client=None,  # 终端模式不需要 OneBot
                scheduler=self.scheduler
            )
            self.logger.info("ToolNet 子网初始化成功")
            self.logger.info(f"  已注册 {len(self.tool_subnet.registry.tools)} 个工具")
        except Exception as e:
            self.logger.warning(f"ToolNet 子网初始化失败: {e}", exc_info=True)
            self.tool_subnet = None

    def _init_web_net(self):
        """初始化 WebNet 子网"""
        try:
            from webnet.webnet import WebNet

            self.web_net = WebNet(
                memory_engine=self.memory_engine,
                emotion_manager=self.emotion
            )
            self.logger.info("WebNet 子网初始化成功")
        except Exception as e:
            self.logger.warning(f"WebNet 初始化失败（可选模块）: {e}")
            self.web_net = None

    def _init_memory_system(self):
        """初始化全局记忆系统 (M-Link + MemoryNet)"""
        try:
            from webnet.memory import MemoryNet

            # 初始化 M-Link
            self.mlink = MLinkCore()
            self.logger.info("M-Link 初始化成功")

            # 初始化 MemoryNet 全局记忆子网
            self.memory_net = MemoryNet(self.mlink)
            self.logger.info("MemoryNet 全局记忆子网初始化成功")
            
            # 清除对话历史移到异步初始化之后，此处不再处理

            # 初始化Neo4j知识图谱（使用已连接的neo4j客户端）
            self._init_neo4j_system()

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
                
                # 清除之前的终端对话历史，确保新会话是干净的
                try:
                    if self.memory_net.conversation_history:
                        session_to_clear = "terminal_default"
                        await self.memory_net.conversation_history.clear_session(session_to_clear)
                        self.logger.info("已清除之前的终端对话历史（新会话开始）")
                except Exception as e:
                    self.logger.warning(f"清除对话历史失败: {e}")
                    
            except Exception as e:
                self.logger.error(f"MemoryNet 初始化失败: {e}")

    def _init_ai_client(self):
        """初始化AI客户端（支持多模型）"""
        try:
            import os
            from dotenv import load_dotenv

            load_dotenv(Path(__file__).parent.parent / 'config' / '.env')

            # 尝试初始化多模型管理器
            try:
                from core.multi_model_manager import MultiModelManager
                from core.ai_client import AIClientFactory

                # 加载多模型配置
                config_path = Path(__file__).parent.parent / 'config' / 'multi_model_config.json'

                if config_path.exists():
                    import json
                    with open(config_path, 'r', encoding='utf-8') as f:
                        multi_model_config = json.load(f)

                    # 创建模型客户端
                    model_clients = {}
                    models_config = multi_model_config.get('models', {})

                    for model_key, model_info in models_config.items():
                        provider = model_info.get('provider', 'openai')
                        api_key = model_info.get('api_key', '')
                        model_name = model_info.get('name', '')
                        base_url = model_info.get('base_url', '')

                        # 跳过未配置API密钥的模型
                        if not api_key or not model_name:
                            continue

                        try:
                            client = AIClientFactory.create_client(
                                provider=provider,
                                api_key=api_key,
                                model=model_name,
                                base_url=base_url,
                                temperature=float(os.getenv('AI_TEMPERATURE', '0.7')),
                                max_tokens=int(os.getenv('AI_MAX_TOKENS', '2000'))
                            )

                            if client and hasattr(client, 'client') and client.client is not None:
                                model_clients[model_key] = client
                                self.logger.info(f"  [多模型] {model_key}: {model_name} ({base_url})")
                        except Exception as e:
                            self.logger.warning(f"  [多模型] {model_key} 初始化失败: {e}")

                    # 如果成功创建了多个模型，使用多模型管理器
                    if model_clients:
                        self.multi_model_manager = MultiModelManager(
                            model_clients=model_clients,
                            config_path=str(config_path)
                        )
                        self.logger.info(f"多模型管理器初始化成功，已加载 {len(model_clients)} 个模型")

                        # 使用 qwen_72b 作为默认模型（工具调用和任务规划的首选）
                        default_client = model_clients.get('qwen_72b') or model_clients.get('deepseek_v3_official')
                        if default_client:
                            self.logger.info(f"默认模型: {default_client.model}")
                            return default_client

            except Exception as e:
                self.logger.warning(f"多模型管理器初始化失败，使用单一模型: {e}")

            # 降级到单一模型模式
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

            # 使用统一的 OpenAI 格式客户端
            temperature = float(os.getenv('AI_TEMPERATURE', '0.7'))
            max_tokens = int(os.getenv('AI_MAX_TOKENS', '2000'))

            from core.ai_client import OpenAIClient
            client = OpenAIClient(
                api_key=api_key,
                model=model,
                base_url=base_url,
                temperature=temperature,
                max_tokens=max_tokens
            )

            # 验证客户端是否初始化成功
            if not hasattr(client, 'client') or client.client is None:
                self.logger.warning("AI客户端初始化失败，将使用简化回复")
                return None

            self.logger.info(f"AI客户端初始化成功: {model} ({base_url})")
            return client

        except Exception as e:
            self.logger.warning(f"AI客户端初始化失败: {e}，将使用简化回复")
            return None

    def _init_vector_system(self):
        """初始化向量系统"""
        try:
            from core.embedding_client import EmbeddingClient, EmbeddingProvider
            from memory.real_vector_cache import RealVectorCache

            # 使用本地模型（无需API）
            self.embedding_client = EmbeddingClient(
                provider=EmbeddingProvider.SENTENCE_TRANSFORMERS,
                model='paraphrase-multilingual-MiniLM-L12-v2'
            )

            # 初始化向量缓存
            import os
            data_dir = Path(__file__).parent.parent / 'data'
            data_dir.mkdir(exist_ok=True)

            self.vector_cache = RealVectorCache(
                embedding_client=self.embedding_client,
                milvus_db_path=str(data_dir / 'milvus_lite.db'),
                collection_name='miya_vectors'
            )

            # 初始化语义动力学引擎
            from memory.semantic_dynamics_engine import get_semantic_dynamics_engine
            self.semantic_engine = get_semantic_dynamics_engine(
                config={'top_k': 10, 'fuzzy_threshold': 0.85},
                vector_cache=self.vector_cache
            )
            self.semantic_engine.set_embedding_client(self.embedding_client)

            self.logger.info("向量系统初始化成功（使用Sentence Transformers本地模型）")

        except Exception as e:
            self.logger.warning(f"向量系统初始化失败: {e}，将不使用向量功能")
            self.embedding_client = None
            self.vector_cache = None
            self.semantic_engine = None

    def _init_web_api(self):
        """初始化 Web API 路由器"""
        try:
            from core.web_api import create_web_api

            self.web_api = create_web_api(
                web_net=self.web_net,
                decision_hub=self.decision_hub
            )
            
            if self.web_api:
                self.logger.info("Web API 路由器初始化成功")
                # 尝试启动 API 服务器（后台运行）
                self._start_api_server()
            else:
                self.logger.warning("FastAPI 不可用，Web API 功能将被禁用")
        except Exception as e:
            self.logger.warning(f"Web API 初始化失败（可选模块）: {e}")
            self.web_api = None

    def _start_api_server(self):
        """启动 API 服务器（后台线程）"""
        try:
            import threading
            import uvicorn

            def run_server():
                if self.web_api and self.web_api.router:
                    from fastapi import FastAPI
                    from fastapi.middleware.cors import CORSMiddleware

                    app = FastAPI(title="弥娅终端API")
                    app.add_middleware(
                        CORSMiddleware,
                        allow_origins=["*"],
                        allow_credentials=True,
                        allow_methods=["*"],
                        allow_headers=["*"],
                    )
                    app.include_router(self.web_api.router)

                    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")

            server_thread = threading.Thread(target=run_server, daemon=False)
            server_thread.start()

            import time
            time.sleep(2)

            self.logger.info("Web API 服务器已在后台启动 (http://0.0.0.0:8000)")
        except Exception as e:
            self.logger.warning(f"API 服务器启动失败: {e}")


    def _init_neo4j_system(self):
        """初始化Neo4j知识图谱系统"""
        try:
            from memory.grag_memory import GRAGMemoryManager

            # 使用已初始化的neo4j客户端（在第81行已初始化）
            self.neo4j_client = self.neo4j

            # 检查是否为模拟模式
            if self.neo4j_client and not self.neo4j_client.is_mock_mode():
                self.logger.info("Neo4j知识图谱连接成功")

                # 初始化GRAG记忆管理器
                self.grag_memory = GRAGMemoryManager(
                    config={'enabled': True, 'auto_extract': True},
                    neo4j_client=self.neo4j_client
                )
                self.logger.info("GRAG知识图谱记忆管理器初始化成功")
            else:
                self.logger.warning("Neo4j连接失败或为模拟模式，将不使用知识图谱功能")
                self.grag_memory = None

        except Exception as e:
            self.logger.warning(f"Neo4j知识图谱初始化失败: {e}，将不使用知识图谱功能")
            self.grag_memory = None
            self.neo4j_client = None

    async def process_input_async(self, user_input: str, user_id: str = 'default') -> str:
        """
        处理用户输入（使用统一跨平台架构）

        Args:
            user_input: 用户输入
            user_id: 用户ID

        Returns:
            系统响应
        """
        # self.logger.info(f"用户输入: {user_input}")  # 注释掉，避免终端输出冗余日志


        # 【框架一致性】检查是否是带前缀的终端命令
        if self.decision_hub and self.decision_hub.terminal_tool:
            # 只处理带前缀的直接命令（! 或 >>）
            # 自然语言由 AI 理解，AI 决定是否调用终端工具
            if user_input.startswith(('!', '>>')):
                # 去掉前缀，提取实际命令
                prefix = '!' if user_input.startswith('!') else '>>'
                command = user_input[len(prefix):].strip()

                # 执行命令
                result = self.decision_hub.terminal_tool.execute(command)
                formatted_result = self.decision_hub.terminal_tool.format_result(result)
                self.logger.info(f"终端工具响应: {formatted_result[:100]}")
                return formatted_result


        # 使用平台适配器转换为M-Link Message
        message = self.terminal_adapter.to_message(
            user_input=user_input,
            context={
                'user_id': user_id,
                'sender_name': user_id,
                'timestamp': datetime.now()
            }
        )

        # 使用DecisionHub处理（跨平台统一流程）
        response = await self.decision_hub.process_perception_cross_platform(message)

        # DecisionHub 已经将响应设置到 message.content 中
        # 直接返回响应，如果是 None 则返回空字符串
        self.logger.debug(f"系统响应: {response}")
        return response or ""

    def process_input(self, user_input: str, user_id: str = 'default') -> str:
        """
        处理用户输入（同步接口）

        Args:
            user_input: 用户输入
            user_id: 用户ID

        Returns:
            系统响应
        """
        # 使用事件循环运行异步方法
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(self.process_input_async(user_input, user_id))
            return response
        finally:
            loop.close()

    async def _miya_ai_callback(self, input_text: str, from_terminal: str = "master") -> str:
        """
        弥娅AI回调 - 用于主终端控制器和弥娅接管模式

        Args:
            input_text: 用户输入
            from_terminal: 来源终端（"master" 或 child_id）

        Returns:
            弥娅AI响应
        """
        # 使用M-Link Message格式
        # 注意：content 需要是字典格式，包含 platform、content、user_id、sender_name 等
        from mlink import Message

        perception_data = {
            'platform': 'terminal',
            'content': input_text,
            'user_id': 'default',
            'sender_name': from_terminal
        }

        message = Message(
            msg_type="text",
            content=perception_data,
            source=from_terminal
        )

        # 使用DecisionHub处理
        response = await self.decision_hub.process_perception_cross_platform(message)

        return response or ""

    def get_system_status(self) -> dict:
        """获取系统状态"""
        status = {
            'identity': self.identity.get_identity(),
            'personality': self.personality.get_profile(),
            'emotion': self.emotion.get_emotion_state(),
            'memory_stats': self.memory_engine.get_memory_stats(),
            'perception': self.perceptual_ring.get_global_state(),
            'trust_stats': self.trust_score.get_trust_stats(),
            'entropy_health': self.entropy.get_health_report(),
            'platform': 'terminal',
            'platform_info': self.terminal_adapter.get_platform_info()
        }

        # M-Link 和 MemoryNet 可能为 None
        if self.mlink:
            status['mlink_stats'] = self.mlink.get_system_stats()
        else:
            status['mlink_stats'] = {}

        if self.memory_net:
            status['memory_net_stats'] = {'initialized': True}
        else:
            status['memory_net_stats'] = {'initialized': False}

        return status

    def shutdown(self) -> None:
        """关闭系统"""
        self.logger.info("弥娅系统正在关闭...")

        # 清理资源
        self.redis.flushdb()

        self.logger.info("弥娅系统已关闭")


def main():
    """主函数"""
    print("=" * 50)
    print("        弥娅 AI 系统")
    print("        Miya AI System")
    print("=" * 50)
    print()

    try:
        print("[系统] 正在初始化弥娅系统...")
        # 创建弥娅实例
        miya = Miya()

        # 异步初始化 MemoryNet
        print("[系统] 初始化全局记忆网络...")
        if miya.memory_net:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(miya._initialize_memory_net_async())
            finally:
                loop.close()
        else:
            print("[警告] 全局记忆网络未初始化，记忆功能将受限")

        print(f"\n{miya.identity.name} 已启动 (v{miya.identity.version})")
        print(f"UUID: {miya.identity.uuid}")
        print(f"启动时间: {miya.identity.awake_time}")
        print()

        # 显示系统配置摘要
        print("=" * 50)
        print("【系统配置摘要】")
        print(f"  平台: 终端模式 (Terminal)")
        print(f"  记忆系统: {'已启用 (MemoryNet)' if miya.memory_net else '未启用'}")
        print(f"  AI客户端: {'已启用 (' + miya.ai_client.model + ')' if miya.ai_client else '未启用'}")

        # 检查数据库连接状态
        neo4j_status = "已连接" if miya.neo4j and not miya.neo4j.is_mock_mode() else "模拟模式/未连接"
        milvus_status = "已连接" if miya.milvus and not miya.milvus.is_mock_mode() else "模拟模式/未连接"
        redis_status = "已连接" if miya.redis and hasattr(miya.redis, 'is_mock') and not miya.redis.is_mock else "模拟模式/未连接"

        print(f"  Neo4j: {neo4j_status}")
        print(f"  Milvus: {milvus_status}")
        print(f"  Redis: {redis_status}")
        print(f"  终端工具: {'已启用' if miya.decision_hub and miya.decision_hub.terminal_tool else '未启用'}")
        print("=" * 50)
        print("\n提示: 使用 '!' 或 '>>' 前缀执行终端命令")
        print("      如: !ls, >>pwd, !查看当前目录")
        print("\n输入 'status' 查看系统状态")
        print("输入 'exit' 或 '退出' 退出程序")
        print()

        # 启动定时任务调度器
        if miya.scheduler:
            try:
                # 设置终端回调，用于在终端模式下输出提醒
                async def terminal_callback(message: str):
                    print(f"\n【定时提醒】 {message}\n佳: ")

                miya.scheduler.terminal_callback = terminal_callback

                # 在后台线程中启动调度器
                miya.scheduler.start_background()
                print("[系统] 定时任务调度器已启动（后台运行）")
            except Exception as e:
                print(f"[警告] 定时任务调度器启动失败: {e}")

        # 交互循环 - 使用异步主循环
        async def main_loop():
            while True:
                try:
                    # 同步获取用户输入
                    user_input = input("佳: ").strip()

                    if user_input.lower() in ['exit', 'quit', '退出', '再见']:
                        print(f"{miya.identity.name}: 再见！")
                        # 保存对话历史到 Lifebook
                        if miya.decision_hub:
                            try:
                                import asyncio
                                loop = asyncio.get_event_loop()
                                if loop.is_running():
                                    asyncio.create_task(
                                        miya.decision_hub.handle_session_end("default", platform="terminal")
                                    )
                                else:
                                    loop.run_until_complete(
                                        miya.decision_hub.handle_session_end("default", platform="terminal")
                                    )
                                print("对话历史已保存")
                            except Exception as e:
                                print(f"保存对话历史失败: {e}")
                        break

                    if user_input.lower() in ['status', '状态']:
                        status = miya.get_system_status()
                        print(f"\n=== {miya.identity.name} 系统状态 ===")
                        print(f"版本: {miya.identity.version}")
                        print(f"UUID: {miya.identity.uuid}")
                        print(f"\n【人格状态】")
                        print(f"  形态: {status['personality']['state']}")
                        print(f"  主导特质: {status['personality']['dominant_trait']}")
                        print(f"  人格向量:")
                        for trait, value in status['personality']['vectors'].items():
                            print(f"    {trait}: {value:.2f}")
                        print(f"\n【情绪状态】")
                        print(f"  主导情绪: {status['emotion']['dominant']}")
                        print(f"  情绪强度: {status['emotion']['intensity']:.2f}")
                        print(f"  当前情绪:")
                        for emotion, intensity in status['emotion']['current'].items():
                            print(f"    {emotion}: {intensity:.2f}")
                        print(f"\n【记忆统计】")
                        print(f"  潮汐记忆: {status['memory_stats'].get('tide_count', 0)}条")
                        print(f"  长期记忆: {status['memory_stats'].get('longterm_count', 0)}条")
                        print(f"\n【感知状态】")
                        print(f"  全局激活: {status['perception']['global_active']}")
                        print(f"  外部感知: {status['perception']['external_active']}")
                        print(f"  内部感知: {status['perception']['internal_active']}")
                        print(f"\n【信任统计】")
                        print(f"  平均信任: {status['trust_stats']['avg_score']:.2f}")
                        print(f"  总交互: {status['trust_stats']['total_interactions']}")
                        print(f"\n【系统健康】")
                        print(f"  熵值: {status['entropy_health']['current_entropy']:.3f}")
                        print(f"  健康状态: {status['entropy_health']['status']}")
                        print()
                        continue

                    # 【自主能力】触发自主改进
                    if user_input.lower() in ['auto', '自动改进', 'improve', '自主']:
                        print(f"\n{miya.identity.name}: 正在进行自主改进...")
                        result = await miya.autonomy_with_personality.personalized_improvement(
                            max_fixes=5,
                            consider_personality=True
                        )
                        print(f"\n{miya.identity.name}: 改进完成！")
                        print(f"  发现问题: {result['problems_found']}")
                        print(f"  做出决策: {result['decisions_made']}")
                        print(f"  尝试修复: {result['fixes_attempted']}")
                        print(f"  成功修复: {result['fixes_successful']}")
                        if result.get('personality_influenced'):
                            print(f"  人设影响: 是")
                        if result.get('current_emotion'):
                            print(f"  当前情绪: {result['current_emotion']}")
                        print()
                        continue

                    # 【自主能力】查看学习报告
                    if user_input.lower() in ['learn', '学习报告', '报告']:
                        print(f"\n{miya.identity.name}: 正在生成学习报告...")
                        report = miya.autonomy_with_personality.generate_personalized_report()
                        print(f"\n=== {miya.identity.name} 学习报告 ===")
                        if report.get('personality'):
                            personality = report['personality']
                            print(f"\n【人格状态】")
                            vectors = personality.get('vectors', {})
                            print(f"  形态: {personality.get('current_form', {}).get('name', '未知')}")
                            print(f"  专属称呼: {personality.get('current_title', '佳')}")
                            print(f"  状态: {personality.get('state', '未知')}")
                            print(f"  人格向量:")
                            if vectors:
                                vector_names = {
                                    'warmth': '温暖度',
                                    'logic': '逻辑性',
                                    'creativity': '创造力',
                                    'empathy': '同理心',
                                    'resilience': '韧性'
                                }
                                for key, value in vectors.items():
                                    cn_name = vector_names.get(key, key)
                                    print(f"    {cn_name}: {value:.2f}")
                            print()
                        if report.get('emotion'):
                            emotion = report['emotion']
                            print(f"\n【情绪状态】")
                            current_emotion = emotion.get('current_emotion', {})
                            if current_emotion:
                                print(f"  主导情绪: {current_emotion.get('dominant', '未知')}")
                                print(f"  情绪强度: {current_emotion.get('intensity', 0):.2f}")
                                print(f"  当前情绪:")
                                for emotion_name, intensity in current_emotion.get('current', {}).items():
                                    print(f"    {emotion_name}: {intensity:.2f}")
                            print()
                        if report.get('memory'):
                            print(f"\n【记忆统计】")
                            stats = report.get('memory', {})
                            print(f"  长期记忆: {stats.get('longterm_count', 0)}条")
                            print(f"  潮汐记忆: {stats.get('tide_count', 0)}条")
                            print(f"  语义记忆: {stats.get('semantic_count', 0)}条")
                            print(f"  知识图谱: {stats.get('graph_count', 0)}条")
                            print()
                        if report.get('learning'):
                            learning = report.get('learning', {})
                            print(f"\n【学习统计】")
                            print(f"  学习次数: {learning.get('total_learnings', 0)}次")
                            print(f"  改进次数: {learning.get('total_improvements', 0)}次")
                            if learning.get('learning_history'):
                                print(f"  最近学习:")
                                for item in learning.get('learning_history', [])[:5]:
                                    print(f"    - {item.get('type', '未知')}: {item.get('description', '无描述')}")
                            print()
                        continue

                    if user_input.lower() in ['yes', 'y', '是', '确认']:
                        if miya.decision_hub and miya.decision_hub.terminal_tool and miya.decision_hub.terminal_tool.pending_command:
                            # 确认执行待确认的命令
                            command = miya.decision_hub.terminal_tool.pending_command
                            result = miya.decision_hub.terminal_tool.execute(command, user_confirm=True)
                            response = miya.decision_hub.terminal_tool.format_result(result)
                            print(f"{miya.identity.name}: {response}\n")
                            continue
                        else:
                            # 没有待确认的命令
                            print(f"{miya.identity.name}: 当前没有待确认的命令。\n")
                            continue

                    if user_input.lower() in ['取消', 'cancel', 'no', 'n']:
                        if miya.decision_hub and miya.decision_hub.terminal_tool and miya.decision_hub.terminal_tool.pending_command:
                            # 取消待确认的命令
                            command = miya.decision_hub.terminal_tool.pending_command
                            result = miya.decision_hub.terminal_tool.execute(command, user_confirm=False)
                            response = miya.decision_hub.terminal_tool.format_result(result)
                            print(f"{miya.identity.name}: {response}\n")
                            continue
                        else:
                            # 没有待确认的命令
                            print(f"{miya.identity.name}: 当前没有待确认的命令。\n")
                            continue

                    # 检查是否是主终端的特殊命令
                    if user_input.lower().startswith('switch '):
                        # 切换终端
                        terminal_name = user_input[7:].strip()
                        print(f"\n[主终端] 切换到终端: {terminal_name}")
                        continue

                    if user_input.lower() == 'list terminals':
                        # 列出所有终端
                        status = miya.miya_takeover_mode.get_all_terminals_status()
                        print(f"\n=== 所有终端状态 ===")
                        for tid, tstatus in status.items():
                            print(f"  {tid}: {tstatus['name']} ({tstatus['type']}) - {tstatus.get('status', 'unknown')}")
                        print()
                        continue

                    # 使用弥娅接管模式处理输入
                    await miya.miya_takeover_mode.handle_input(user_input, from_terminal="master")

                except KeyboardInterrupt:
                    print("\n\n检测到中断信号...")
                    break

        # 运行异步主循环
        asyncio.run(main_loop())

    except Exception as e:
        logging.error(f"系统错误: {e}", exc_info=True)
        return 1

    finally:
        if 'miya' in locals():
            # 关闭对话历史管理器（等待所有保存任务完成）
            try:
                if miya.memory_net and hasattr(miya.memory_net, 'conversation_history'):
                    async def cleanup_conversation_history():
                        await miya.memory_net.conversation_history.close()
                        print("对话历史已保存")
                    asyncio.run(cleanup_conversation_history())
            except Exception as e:
                logging.error(f"关闭对话历史管理器失败: {e}", exc_info=True)

            miya.shutdown()

    return 0


if __name__ == '__main__':
    sys.exit(main())
