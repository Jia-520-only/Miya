"""
弥娅系统总入口（终端模式）- 使用统一跨平台架构
"""

import asyncio
import builtins
import contextlib
import logging

# 跨平台控制台编码设置 - 支持中文输入
import os
import sys
from datetime import datetime
from pathlib import Path

os.environ["PYTHONIOENCODING"] = "utf-8"

# Windows 下设置控制台代码页为 UTF-8
if sys.platform == "win32":
    import subprocess

    with contextlib.suppress(builtins.BaseException):
        subprocess.run(["chcp", "65001"], shell=True, capture_output=True)  # nosec B602

    # Windows 下设置标准输入输出编码
    # 注意：不要在模块加载时包装 stdout/stderr，因为这会与 uvicorn 等库的日志配置冲突
    # 仅在需要时在 chinese_input 函数中进行包装


def chinese_input(prompt: str) -> str:
    """
    跨平台中文输入函数（增强版）

    Args:
        prompt: 提示文本

    Returns:
        用户输入的字符串
    """
    # 确保每次调用前都设置编码（防止不稳定）
    if sys.platform == "win32":
        import io

        # 重新设置标准输入编码
        if hasattr(sys.stdin, "buffer") and not isinstance(sys.stdin, io.TextIOWrapper):
            sys.stdin = io.TextIOWrapper(
                sys.stdin.buffer,
                encoding="utf-8",
                errors="replace",
                line_buffering=True,
            )

        # 确保标准输出编码正确
        if hasattr(sys.stdout, "buffer") and not isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer,
                encoding="utf-8",
                errors="replace",
                line_buffering=True,
            )

    try:
        # 显示提示
        if prompt:
            sys.stdout.write(prompt)
            sys.stdout.flush()

        # 读取输入
        line = sys.stdin.readline()

        # 去除换行符
        if line.endswith("\n"):
            line = line[:-1]
        elif line.endswith("\r\n"):
            line = line[:-2]

        return line

    except Exception as e:
        # 如果出错，尝试使用标准 input 作为备选
        try:
            return input(prompt)
        except:
            logging.exception("标准输入回退失败")
            # 如果还是失败，返回空字符串
            print(f"[警告] 输入读取失败: {e}", file=sys.stderr)
            return ""


# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 单次加载 .env（后续模块的 load_dotenv 会被跳过）
from dotenv import load_dotenv as _load_dotenv

_load_dotenv(project_root / "config" / ".env")
os.environ["_MIYA_DOTENV_LOADED"] = "1"

# 本地 OCR 模型全局配置 — 初始化前设置，避免联网检查
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

# 使用统一的端口检测工具
from config import Settings
from core import Arbitrator, Entropy, Ethics, Identity, Personality, PromptManager
from core.autonomy_with_personality import get_autonomy_with_personality
from core.constants import Encoding
from core.memory_engine_shim import MemoryEngineShim as MemoryEngine, MemoryEngineShim as MemoryEmotion
from core.system_detector import get_system_detector
from hub import Decision, DecisionHub, Emotion, Scheduler
from hub.platform_adapters import get_adapter
from hub.task_store import TaskStore
from mlink import Message, MLinkCore
from utils.port_utils import check_and_get_port
from webnet import CrossNetEngine, NetManager


class Miya:
    """弥娅系统主类（支持跨平台统一交互）"""

    def __init__(self):
        self.logger = self._setup_logger()
        self.settings = Settings()
        self.logger.info("弥娅系统初始化中...")

        # 【第一阶段】系统环境检测
        self.system_detector = get_system_detector()
        self.system_info = self.system_detector.detect()
        self.logger.info("✅ 系统检测完成:")
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
        self.task_store = TaskStore()
        self.scheduler = Scheduler(task_store=self.task_store)

        # 能力升级桥接（Browser Use + Screen Aware + Plugin SDK）
        self._init_upgrade_bridge()

        # 初始化M-Link
        self.mlink = MLinkCore()

        # 初始化子网
        self.net_manager = NetManager()
        self.cross_net_engine = CrossNetEngine(self.net_manager)

        # 数据库初始化（默认关闭，需要时通过 ENABLE_DATABASES 环境变量启用）
        self._init_databases()

    def _init_databases(self):
        """初始化存储 - SQLite 已替代所有外部数据库"""
        self.logger.info("  [存储] JSON + SQLite（零外部数据库依赖）")

        # 初始化全局记忆系统 (M-Link + MemoryNet)
        self._init_memory_system()

        # 【框架一致性】初始化 ToolNet 子网（符合 MIYA 蛛网式分布式架构）
        self.tool_subnet = None
        self._init_tool_subnet()

        # 【框架一致性】终端工具由 DecisionHub 管理,不在这里初始化

        # 【WebNet】初始化 Web 子网
        self.web_net = None
        self._init_web_net()

        # 【跨端】初始化跨端子网
        self._init_cross_terminal()

        # 初始化 AI 客户端
        self.ai_client = self._init_ai_client()

        # 初始化向量系统
        self._init_vector_system()

        # 初始化 DecisionHub（跨平台统一决策）
        from core.unified_platform.registry import get_registry as get_platform_registry

        self.decision_hub = DecisionHub(
            mlink=self.mlink,
            ai_client=self.ai_client,
            emotion=self.emotion,
            personality=self.personality,
            prompt_manager=self.prompt_manager,
            memory_net=self.memory_net,
            decision_engine=self.decision,
            tool_subnet=self.tool_subnet,
            memory_engine=self.memory_engine,
            scheduler=self.scheduler,
            onebot_client=None,
            identity=self.identity,
            model_pool=getattr(self, "model_pool", None),
            miya_instance=self,
            platform_registry=get_platform_registry(),
        )

        # 将 MemoryManager 注入 Scheduler，使定时任务产出进入记忆系统
        self.scheduler.memory_manager = self.decision_hub.memory_manager

        # 初始化平台适配器
        self.terminal_adapter = get_adapter("terminal")

        # DSH 作为弥娅的"手"/肢体工具 —— 守护进程可调用 DSH 执行任务
        self.dsh_bin_path: Path | None = None
        self.dsh_node_exe: str = "node"
        self._call_dsh_env_cache: dict | None = None
        self._init_dsh_executor()

        # 【自主能力】初始化带人设的自主能力
        self.autonomy_with_personality = get_autonomy_with_personality(
            personality=self.personality,
            emotion=self.emotion,
            memory_engine=self.memory_engine,
            memory_emotion=self.memory_emotion,
        )
        self.autonomy_with_personality.initialize()
        self.logger.info("✅ 自主能力已初始化（含人设集成）")

        # 【WebNet】初始化 Web API 路由器
        self.web_api = None
        self._init_web_api()

        self.logger.info("弥娅系统初始化完成（含跨平台支持）")
        self.identity.awake()

    def _init_upgrade_bridge(self):
        """初始化能力升级桥接（Browser Use + Screen Aware + Plugin SDK）"""
        try:
            from upgrade_bridge import get_upgrade_bridge

            self.upgrade_bridge = get_upgrade_bridge()
            result = self.upgrade_bridge.initialize(
                browser_use_config={"enabled": True},
                screen_aware_config={"enabled": True, "min_interval_seconds": 30.0},
            )
            self.logger.info(
                f"[UpgradeBridge] 能力升级初始化: browser={result.get('browser_use')}, "
                f"screen={result.get('screen_aware')}, plugin={result.get('plugin_sdk')}"
            )
        except Exception as e:
            self.logger.warning(f"[UpgradeBridge] 初始化跳过: {e}")
            self.upgrade_bridge = None

    def _setup_logger(self) -> logging.Logger:
        """设置日志"""
        import os

        logger = logging.getLogger("Miya")
        logger.setLevel(logging.INFO)
        logging.getLogger("faiss.loader").setLevel(logging.WARNING)

        # v7.0: daemon 模式下不添加独立 handler，由 root logger 统一管理
        if os.environ.get("MIYA_DAEMON_MODE"):
            logger.propagate = True
            return logger

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # 文件处理器
        log_dir = Path(__file__).parent / ".." / "logs"
        log_dir.mkdir(exist_ok=True)

        file_handler = logging.FileHandler(
            log_dir / f"miya_{datetime.now().strftime('%Y%m%d')}.log",
            encoding=Encoding.UTF8,
        )
        file_handler.setLevel(logging.DEBUG)

        # 格式化
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

        return logger

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
                scheduler=self.scheduler,
            )
            self.logger.info("ToolNet 子网初始化成功")
            self.logger.info(f"  已注册 {len(self.tool_subnet.registry.tools)} 个工具")
        except Exception as e:
            self.logger.warning(f"ToolNet 子网初始化失败: {e}", exc_info=True)
            self.tool_subnet = None

    def _init_dsh_executor(self):
        """初始化 DSH 执行器 — 守护进程（大脑）调用 DSH（手）的桥梁"""
        import platform
        import shutil

        dsh_dir = project_root / "deepseek-harness"
        cli_candidates = [
            dsh_dir / "apps" / "cli" / "lib" / "bin.js",  # 嵌入式构建产物
        ]
        for candidate in cli_candidates:
            if candidate.exists():
                self.dsh_bin_path = candidate
                break

        node_candidates: list[str] = []
        if platform.system() == "Windows":
            node_candidates = [
                shutil.which("node") or "",
                str(
                    Path.home() / "AppData" / "Roaming" / "fnm" / "node-versions" / "v22" / "installation" / "node.exe"
                ),
                str(Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "nodejs" / "node.exe"),
            ]
        else:
            node_candidates = [
                shutil.which("node") or "",
                "/usr/local/bin/node",
                "/usr/bin/node",
            ]

        for candidate in node_candidates:
            if candidate and Path(candidate).exists():
                self.dsh_node_exe = candidate
                break

        if self.dsh_bin_path:
            self.logger.info(f"[DSH] 执行器就绪: {self.dsh_node_exe} {self.dsh_bin_path.name}")
        else:
            self.logger.warning("[DSH] 未找到 apps/cli/lib/bin.js，守护进程无法调用 DSH")

    def call_dsh(self, task: str, timeout: int = 300, working_dir: str | None = None) -> dict:
        """
        守护进程调用 DSH 执行任务（同步，阻塞等待结果）

        Args:
            task: 自然语言任务描述，如 "在 data/ 目录下创建 test.txt"
            timeout: 超时秒数（headless agent 循环，默认 300s）
            working_dir: 工作目录，默认项目根目录

        Returns:
            {"success": bool, "output": str, "error": str}
        """
        import platform
        import subprocess

        if not self.dsh_bin_path or not self.dsh_bin_path.exists():
            return {"success": False, "output": "", "error": "DSH CLI 未就绪"}

        if self._call_dsh_env_cache is None:
            dotenv_path = project_root / "config" / ".env"
            env_vars: dict[str, str] = {}
            if dotenv_path.exists():
                for line in dotenv_path.read_text(encoding="utf-8").split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        env_vars[key.strip()] = value.strip()
            self._call_dsh_env_cache = env_vars

        env_vars = self._call_dsh_env_cache

        env = {
            **{k: v for k, v in os.environ.items()},
            "DEEPSEEK_API_KEY": env_vars.get("DEEPSEEK_API_KEY", ""),
            "DSH_PERMISSION_MODE": "danger-full-access",  # 等价 CCE 的 bypassPermissions
        }
        try:
            from mcpserver.dsh.config_bridge import ensure_dsh_config

            dsh_config = ensure_dsh_config()
            env["DSH_HOME"] = dsh_config["home"]
        except Exception as e:
            self.logger.debug(f"[DSH] 配置注入跳过（DSH 将使用默认 ~/.dsh）: {e}")

        try:
            creationflags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            cwd = working_dir or str(project_root)

            proc = subprocess.run(
                [self.dsh_node_exe, str(self.dsh_bin_path), "--profile", "headless", task],
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                creationflags=creationflags,
            )
            return {
                "success": proc.returncode == 0,
                "output": proc.stdout,
                "error": proc.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "error": f"DSH 执行超时 ({timeout}s)"}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def _init_web_net(self):
        """初始化 WebNet 子网"""
        try:
            from webnet.webnet import WebNet

            self.web_net = WebNet(memory_engine=self.memory_engine, emotion_manager=self.emotion)
            self.logger.info("WebNet 子网初始化成功")
        except Exception as e:
            self.logger.warning(f"WebNet 初始化失败（可选模块）: {e}")
            self.web_net = None

    def _init_cross_terminal(self):
        """跨端功能已由 Open-ClaudeCode 提供"""
        self.logger.info("跨端功能由 Open-ClaudeCode 提供")
        self.cross_terminal_hub = None

    def _init_memory_system(self):
        """初始化全局记忆系统 (M-Link + MemoryNet)"""
        try:
            from webnet.memory import MemoryNet

            self.mlink = MLinkCore()
            self.logger.info("M-Link 初始化成功")

            self.memory_net = MemoryNet(self.mlink)
            self.logger.info("MemoryNet 全局记忆子网初始化成功")

        except Exception as e:
            self.logger.error(f"全局记忆系统初始化失败: {e}")
            self.mlink = None
            self.memory_net = None

    async def _init_unified_memory_async(self):
        """异步初始化统一记忆系统（在事件循环中调用）"""
        try:
            from memory import get_memory_adapter, get_memory_core

            MIYA_ROOT = Path(__file__).parent.parent.resolve()
            DATA_DIR = str(MIYA_ROOT / "data" / "memory")

            self.unified_memory_core = await get_memory_core(DATA_DIR)
            self.unified_memory_adapter = await get_memory_adapter()

            self.logger.info("[记忆] 统一记忆系统初始化成功")

        except Exception as e:
            self.logger.error(f"[记忆] 统一记忆系统初始化失败: {e}")
            self.unified_memory_core = None
            self.unified_memory_adapter = None

    async def _initialize_memory_net_async(self):
        """异步初始化 MemoryNet + 统一记忆系统（在事件循环中调用）"""
        if self.memory_net:
            try:
                await self.memory_net.initialize()
                self.logger.info("MemoryNet 初始化完成")
            except Exception as e:
                self.logger.error(f"MemoryNet 初始化失败: {e}")

        await self._init_unified_memory_async()

        if self.memory_net and self.memory_net.conversation_history:
            try:
                session_to_clear = "terminal_default"
                await self.memory_net.conversation_history.clear_session(session_to_clear)
                self.logger.info("已清除之前的终端对话历史（新会话开始）")
            except Exception as e:
                self.logger.warning(f"清除对话历史失败: {e}")

    def _init_ai_client(self):
        """初始化AI客户端 - 模型配置从 multi_model_config.json 加载，客户端延迟创建"""
        import os

        from dotenv import load_dotenv

        load_dotenv(Path(__file__).parent.parent / "config" / ".env")

        try:
            from core.model_pool_manager import get_model_pool, resolve_api_key_by_provider

            pool = get_model_pool()
            model_configs = pool.get_model_configs_for_manager()

            if model_configs:
                self.model_pool = pool
                self._model_client_configs: dict = {}
                self._model_clients: dict = {}
                self._model_api_keys: dict = {}

                from core.ai_client import AIClientFactory

                for model_key, model_config in model_configs.items():
                    try:
                        provider_value = model_config.provider
                        if hasattr(provider_value, "value"):
                            provider_value = provider_value.value

                        api_key = ""
                        if model_config.env_key:
                            api_key = os.getenv(model_config.env_key, "")
                        if not api_key and hasattr(model_config, "api_key"):
                            api_key = model_config.api_key or ""
                        if not api_key:
                            api_key = resolve_api_key_by_provider(provider_value.lower())

                        self._model_client_configs[model_key] = {
                            "provider": provider_value,
                            "api_key": api_key,
                            "model": model_config.name,
                            "base_url": model_config.base_url,
                            "temperature": float(os.getenv("AI_TEMPERATURE", "0.7")),
                            "max_tokens": int(os.getenv("AI_MAX_TOKENS", "2000")),
                        }
                        self._model_api_keys[model_key] = api_key
                        self.logger.info(f"  [多模型] {model_key}: {model_config.name} ({model_config.base_url})")
                    except Exception as e:
                        self.logger.warning(f"  [多模型] {model_key} 配置解析失败: {e}")

                self.logger.info(f"模型池初始化成功，已注册 {len(self._model_client_configs)} 个模型")

                default_key = next(iter(self._model_client_configs.keys()), None)
                if default_key:
                    default_client = self._get_or_create_model_client(default_key)
                    if default_client:
                        self.logger.info(f"默认模型: {default_client.model}")
                        return default_client

        except Exception as e:
            self.logger.warning(f"多模型管理器初始化失败: {e}")
            self._ai_client_error = str(e)
            return None

    def _get_or_create_model_client(self, model_key: str):
        """延迟创建模型客户端（首次使用时创建）"""
        if model_key in self._model_clients:
            return self._model_clients[model_key]

        config = self._model_client_configs.get(model_key)
        if not config:
            return None

        try:
            from core.ai_client import AIClientFactory

            client = AIClientFactory.create_client(
                provider=config["provider"],
                api_key=config["api_key"],
                model=config["model"],
                base_url=config["base_url"],
                temperature=config["temperature"],
                max_tokens=config["max_tokens"],
            )

            if client and hasattr(client, "client") and client.client is not None:
                self._model_clients[model_key] = client
                return client
        except Exception as e:
            self.logger.warning(f"  [多模型] {model_key} 延迟创建失败: {e}")
        return None

    def get_model_client(self, model_key: str = None):
        """获取模型客户端（优先从已缓存获取，否则延迟创建）"""
        if model_key and model_key in self._model_clients:
            return self._model_clients[model_key]
        if model_key and hasattr(self, "_model_client_configs") and model_key in self._model_client_configs:
            return self._get_or_create_model_client(model_key)
        return getattr(self, "ai_client", None)

    def _init_vector_system(self):
        """初始化向量系统"""
        try:
            from core.embedding_client import EmbeddingClient, EmbeddingProvider

            self.embedding_client = EmbeddingClient(
                provider=EmbeddingProvider.SENTENCE_TRANSFORMERS,
                model="paraphrase-multilingual-MiniLM-L12-v2",
            )

            # 基于 SQLite 的语义动力学引擎（零外部数据库依赖）
            from memory.semantic_dynamics_engine import get_semantic_dynamics_engine

            self.semantic_engine = get_semantic_dynamics_engine(
                config={"top_k": 10, "fuzzy_threshold": 0.85},
            )
            self.semantic_engine.set_embedding_client(self.embedding_client)

            self.logger.info("向量系统初始化成功（使用Sentence Transformers本地模型 + SQLite）")

        except Exception as e:
            self.logger.warning(f"向量系统初始化失败: {e}，将不使用向量功能")
            self.embedding_client = None
            self.semantic_engine = None

    def _init_web_api(self):
        """初始化 Web API 路由器"""
        try:
            from core.web_api import create_web_api

            self.web_api = create_web_api(web_net=self.web_net, decision_hub=self.decision_hub)

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
            from pathlib import Path

            import uvicorn

            # 使用统一的端口检测工具
            api_port, port_changed = check_and_get_port(8000, port_name="Web API")
            Path(__file__).parent.parent

            # 将实际端口写入配置文件供前端读取
            if port_changed:
                self.logger.info(f"API 端口已切换到 {api_port}，前端将自动检测该端口")
            try:
                from utils.port_utils import write_runtime_ports

                write_runtime_ports({"web_api": api_port})
            except Exception:
                pass

            def run_server(current_api_port):
                max_retries = 3
                for attempt in range(max_retries):
                    try:
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

                            # 安装吟美虚拟主播插件
                            try:
                                from plugins.yinmei.integration import install_yinmei_plugin

                                install_yinmei_plugin(app, enable_scheduler=False)
                                self.logger.info("[Miya] 吟美虚拟主播插件已加载")
                            except ImportError:
                                self.logger.debug("[Miya] 吟美插件未安装")
                            except Exception as e:
                                self.logger.warning(f"[Miya] 吟美插件加载失败: {e}")

                            # 通知主线程服务器即将启动
                            server_ready.set()
                            uvicorn.run(
                                app,
                                host="0.0.0.0",
                                port=current_api_port,
                                log_level="warning",
                            )
                            return True
                        server_ready.set()
                        return False
                    except OSError as e:
                        if e.errno == 10048 and attempt < max_retries - 1:
                            self.logger.warning(f"端口 {current_api_port} 绑定失败，尝试下一个端口...")
                            from utils.port_utils import find_available_port

                            current_api_port = find_available_port(current_api_port + 1, host="0.0.0.0")
                            self.logger.info(f"端口切换到 {current_api_port}，前端将自动检测该端口")
                        else:
                            self.logger.error(f"无法启动服务器: {e}")
                            server_ready.set()
                            raise
                    except Exception as e:
                        self.logger.error(f"启动服务器时发生意外错误: {e}")
                        server_ready.set()
                        raise
                server_ready.set()
                return False

            server_ready = threading.Event()
            server_thread = threading.Thread(target=run_server, args=(api_port,), daemon=True)
            server_thread.start()

            self.logger.info(f"Web API 服务器已在后台启动 (http://0.0.0.0:{api_port})")
        except Exception as e:
            self.logger.warning(f"API 服务器启动失败: {e}")

    async def process_input_async(self, user_input: str, user_id: str = "default") -> str:
        """
        处理用户输入（使用统一跨平台架构）

        Args:
            user_input: 用户输入
            user_id: 用户ID

        Returns:
            系统响应
        """
        # self.logger.info(f"用户输入: {user_input}")  # 注释掉，避免终端输出冗余日志

        # DSH 作为终端执行引擎（手/肢体），通过内置 Bash/Pwsh 工具处理所有终端命令

        # 使用平台适配器转换为M-Link Message
        message = self.terminal_adapter.to_message(
            user_input=user_input,
            context={
                "user_id": user_id,
                "sender_name": user_id,
                "timestamp": datetime.now(),
            },
        )

        # 使用DecisionHub处理（跨平台统一流程）
        # LifeBook 记录统一由 decision_hub.py 负责
        response = await self.decision_hub.process_perception_cross_platform(message)

        # DecisionHub 已经将响应设置到 message.content 中
        # 直接返回响应，如果是 None 则返回空字符串
        self.logger.debug(f"系统响应: {response}")
        return response or ""

    def process_input(self, user_input: str, user_id: str = "default") -> str:
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

        perception_data = {
            "platform": "terminal",
            "content": input_text,
            "user_id": "default",
            "sender_name": from_terminal,
        }

        message = Message(msg_type="text", content=perception_data, source=from_terminal)

        # 使用DecisionHub处理
        response = await self.decision_hub.process_perception_cross_platform(message)

        return response or ""

    def get_system_status(self) -> dict:
        """获取系统状态"""
        status = {
            "identity": self.identity.get_identity(),
            "personality": self.personality.get_profile(),
            "emotion": self.emotion.get_emotion_state(),
            "memory_stats": self.memory_engine.get_memory_stats(),
            "entropy_health": self.entropy.get_health_report(),
            "platform": "terminal",
            "platform_info": self.terminal_adapter.get_platform_info(),
        }

        # M-Link 和 MemoryNet 可能为 None
        if self.mlink:
            status["mlink_stats"] = self.mlink.get_system_stats()
        else:
            status["mlink_stats"] = {}

        if self.memory_net:
            status["memory_net_stats"] = {"initialized": True}
        else:
            status["memory_net_stats"] = {"initialized": False}

        return status

    def shutdown(self) -> None:
        """关闭系统"""
        self.logger.info("弥娅系统正在关闭...")
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

        # 显示系统状态
        print("=" * 50)
        print("【弥娅系统 零号机】")
        print("  认知引擎: DecisionHub")
        print("  已启动")
        print("=" * 50)

        # 启动定时任务调度器
        if miya.scheduler:
            try:
                # 设置终端回调，用于在终端模式下输出提醒
                async def terminal_callback(message: str):
                    print(f"\n【定时提醒】 {message}\n佳: ")

                miya.scheduler.terminal_callback = terminal_callback

                # 在后台线程中启动调度器
                miya.scheduler.start_background()
            except Exception:
                pass

        # 交互循环 - 使用异步主循环
        async def main_loop():
            # 启动主动聊天后台轮询
            if miya.decision_hub and miya.decision_hub.proactive_chat:
                asyncio.create_task(miya.decision_hub.start_proactive_background())

            while True:
                try:
                    # 同步获取用户输入（支持中文）
                    user_input = chinese_input("> ").strip()

                    # 使用文本加载器
                    from core.text_loader import get_farewell, is_farewell

                    if is_farewell(user_input):
                        print(f"{miya.identity.name}: {get_farewell()}")
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

                    if user_input.lower() in ["status", "状态"]:
                        status = miya.get_system_status()
                        print(f"\n=== {miya.identity.name} 系统状态 ===")
                        print(f"版本: {miya.identity.version}")
                        print(f"UUID: {miya.identity.uuid}")
                        print("\n【人格状态】")
                        print(f"  形态: {status['personality']['state']}")
                        print(f"  主导特质: {status['personality']['dominant_trait']}")
                        print("  人格向量:")
                        for trait, value in status["personality"]["vectors"].items():
                            print(f"    {trait}: {value:.2f}")
                        print("\n【情绪状态】")
                        print(f"  主导情绪: {status['emotion']['dominant']}")
                        print(f"  情绪强度: {status['emotion']['intensity']:.2f}")
                        print("  当前情绪:")
                        for emotion, intensity in status["emotion"]["current"].items():
                            print(f"    {emotion}: {intensity:.2f}")
                        print("\n【记忆统计】")
                        print(f"  潮汐记忆: {status['memory_stats'].get('tide_count', 0)}条")
                        print(f"  长期记忆: {status['memory_stats'].get('longterm_count', 0)}条")
                        print("\n【感知状态】")
                        print(f"  全局激活: {status['perception']['global_active']}")
                        print(f"  外部感知: {status['perception']['external_active']}")
                        print(f"  内部感知: {status['perception']['internal_active']}")
                        print("\n【信任统计】")
                        print(f"  平均信任: {status['trust_stats']['avg_score']:.2f}")
                        print(f"  总交互: {status['trust_stats']['total_interactions']}")
                        print("\n【系统健康】")
                        print(f"  熵值: {status['entropy_health']['current_entropy']:.3f}")
                        print(f"  健康状态: {status['entropy_health']['status']}")
                        print()
                        continue

                    # 【自主能力】触发自主改进
                    if user_input.lower() in ["auto", "自动改进", "improve", "自主"]:
                        print(f"\n{miya.identity.name}: 正在进行自主改进...")
                        result = await miya.autonomy_with_personality.personalized_improvement(
                            max_fixes=5, consider_personality=True
                        )
                        print(f"\n{miya.identity.name}: 改进完成！")
                        print(f"  发现问题: {result['problems_found']}")
                        print(f"  做出决策: {result['decisions_made']}")
                        print(f"  尝试修复: {result['fixes_attempted']}")
                        print(f"  成功修复: {result['fixes_successful']}")
                        if result.get("personality_influenced"):
                            print("  人设影响: 是")
                        if result.get("current_emotion"):
                            print(f"  当前情绪: {result['current_emotion']}")
                        print()
                        continue

                    # 【自主能力】查看学习报告
                    if user_input.lower() in ["learn", "学习报告", "报告"]:
                        print(f"\n{miya.identity.name}: 正在生成学习报告...")
                        report = miya.autonomy_with_personality.generate_personalized_report()
                        print(f"\n=== {miya.identity.name} 学习报告 ===")
                        if report.get("personality"):
                            personality = report["personality"]
                            print("\n【人格状态】")
                            vectors = personality.get("vectors", {})
                            print(f"  形态: {personality.get('current_form', {}).get('name', '未知')}")
                            print(f"  专属称呼: {personality.get('current_title', '佳')}")
                            print(f"  状态: {personality.get('state', '未知')}")
                            print("  人格向量:")
                            if vectors:
                                vector_names = {
                                    "warmth": "温暖度",
                                    "logic": "逻辑性",
                                    "creativity": "创造力",
                                    "empathy": "同理心",
                                    "resilience": "韧性",
                                }
                                for key, value in vectors.items():
                                    cn_name = vector_names.get(key, key)
                                    print(f"    {cn_name}: {value:.2f}")
                            print()
                        if report.get("emotion"):
                            emotion = report["emotion"]
                            print("\n【情绪状态】")
                            current_emotion = emotion.get("current_emotion", {})
                            if current_emotion:
                                print(f"  主导情绪: {current_emotion.get('dominant', '未知')}")
                                print(f"  情绪强度: {current_emotion.get('intensity', 0):.2f}")
                                print("  当前情绪:")
                                for emotion_name, intensity in current_emotion.get("current", {}).items():
                                    print(f"    {emotion_name}: {intensity:.2f}")
                            print()
                        if report.get("memory"):
                            print("\n【记忆统计】")
                            stats = report.get("memory", {})
                            print(f"  长期记忆: {stats.get('longterm_count', 0)}条")
                            print(f"  潮汐记忆: {stats.get('tide_count', 0)}条")
                            print(f"  语义记忆: {stats.get('semantic_count', 0)}条")
                            print(f"  知识图谱: {stats.get('graph_count', 0)}条")
                            print()
                        if report.get("learning"):
                            learning = report.get("learning", {})
                            print("\n【学习统计】")
                            print(f"  学习次数: {learning.get('total_learnings', 0)}次")
                            print(f"  改进次数: {learning.get('total_improvements', 0)}次")
                            if learning.get("learning_history"):
                                print("  最近学习:")
                                for item in learning.get("learning_history", [])[:5]:
                                    print(f"    - {item.get('type', '未知')}: {item.get('description', '无描述')}")
                            print()
                        continue

                    if user_input.lower() in ["yes", "y", "是", "确认"]:
                        print(f"{miya.identity.name}: 确认功能已由 Open-ClaudeCode 处理\n")
                        continue

                    if user_input.lower() in ["取消", "cancel", "no", "n"]:
                        print(f"{miya.identity.name}: 取消功能已由 Open-ClaudeCode 处理\n")
                        continue

                    if user_input.lower().startswith("switch ") or user_input.lower() == "list terminals":
                        print(f"{miya.identity.name}: 终端管理已由 Open-ClaudeCode 处理\n")
                        continue

                except KeyboardInterrupt:
                    print("\n\n检测到中断信号...")
                    break

        # 保持系统运行（等待中断）
        while True:
            try:
                import time

                time.sleep(1)
            except KeyboardInterrupt:
                break

    except Exception as e:
        logging.error(f"系统错误: {e}", exc_info=True)
        return 1

    finally:
        if "miya" in locals():
            # 关闭对话历史管理器（等待所有保存任务完成）
            try:
                if miya.memory_net and hasattr(miya.memory_net, "conversation_history"):

                    async def cleanup_conversation_history():
                        await miya.memory_net.conversation_history.close()
                        print("对话历史已保存")

                    asyncio.run(cleanup_conversation_history())
            except Exception as e:
                logging.error(f"关闭对话历史管理器失败: {e}", exc_info=True)

            miya.shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(main())
