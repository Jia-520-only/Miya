"""
pytest配置和全局fixtures
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

# 添加项目根目录到路径
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))


# ==================== pytest配置 ====================
def pytest_configure(config):
    """pytest配置"""
    config.addinivalue_line("markers", "slow: 标记为慢速测试（执行时间较长）")
    config.addinivalue_line("markers", "integration: 标记为集成测试")
    config.addinivalue_line("markers", "e2e: 标记为端到端测试")
    config.addinivalue_line("markers", "requires_api: 需要外部API的测试")


# ==================== 异步支持 ====================
@pytest.fixture
def event_loop():
    """创建asyncio事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def anyio_backend():
    """anyio后端配置"""
    return "asyncio"


# ==================== 临时目录和文件 ====================
@pytest.fixture
def temp_dir():
    """临时目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_env_file(temp_dir):
    """临时.env文件"""
    env_file = temp_dir / ".env"
    env_file.write_text("""
DEBUG=true
LOG_LEVEL=DEBUG
AI_PROVIDER=mock
AI_API_KEY=test-api-key-1234567890
AI_MODEL=test-model
LOG_LEVEL=DEBUG
    """)
    return env_file


@pytest.fixture
def temp_config_file(temp_dir):
    """临时配置文件（JSON格式）"""
    config_file = temp_dir / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "app_name": "Miya Test",
                "debug": True,
                "log_level": "DEBUG",
                "ai": {
                    "provider": "mock",
                    "api_key": "test-api-key-1234567890",
                    "model": "test-model",
                    "timeout": 10,
                },
                "terminal": {
                    "max_terminals": 5,
                    "default_type": "cmd",
                    "command_timeout": 10,
                },
            },
            indent=2,
        )
    )
    return config_file


@pytest.fixture
def temp_yaml_config_file(temp_dir):
    """临时配置文件（YAML格式）"""
    config_file = temp_dir / "config.yaml"
    config_file.write_text(
        yaml.dump(
            {
                "app_name": "Miya Test",
                "debug": True,
                "log_level": "DEBUG",
                "ai": {
                    "provider": "mock",
                    "api_key": "test-api-key-1234567890",
                    "model": "test-model",
                },
            },
            default_flow_style=False,
        )
    )
    return config_file


# ==================== Mock对象 ====================
@pytest.fixture
def mock_ai_client():
    """模拟AI客户端"""
    mock = AsyncMock()

    # 配置chat方法
    mock.chat = AsyncMock(return_value="模拟AI响应内容")

    # 配置其他方法
    mock.get_miya_system_prompt = MagicMock(return_value="系统提示词")
    mock.set_tool_registry = MagicMock()
    mock.set_tool_context = MagicMock()

    return mock


@pytest.fixture
def mock_terminal_manager():
    """模拟终端管理器"""
    mock = AsyncMock()

    # 配置基本方法
    mock.create_terminal = AsyncMock(return_value="test-session-001")
    mock.execute_command = AsyncMock(
        return_value={
            "success": True,
            "output": "命令执行成功",
            "error": "",
            "exit_code": 0,
            "execution_time": 0.1,
        }
    )
    mock.get_all_status = MagicMock(
        return_value={
            "test-session-001": {
                "id": "test-session-001",
                "name": "测试终端",
                "type": "cmd",
                "status": "running",
                "directory": "/tmp",
                "is_active": True,
                "command_count": 0,
                "output_count": 0,
            }
        }
    )
    mock.get_session_status = MagicMock(
        return_value={
            "id": "test-session-001",
            "name": "测试终端",
            "type": "cmd",
            "status": "running",
            "directory": "/tmp",
            "is_active": True,
            "command_count": 0,
            "output_count": 0,
        }
    )
    mock.active_session_id = "test-session-001"
    mock.switch_session = AsyncMock()
    mock.close_session = AsyncMock()
    mock.close_all_sessions = AsyncMock()

    return mock


@pytest.fixture
def mock_prompt_manager():
    """模拟提示词管理器"""
    mock = MagicMock()

    # 配置方法
    mock.get_system_prompt = MagicMock(return_value="系统提示词内容")
    mock.user_prompt_template = "用户输入：{user_input}"
    mock.memory_context_enabled = True
    mock.memory_context_max_count = 10

    return mock


@pytest.fixture
def mock_orchestrator(mock_terminal_manager):
    """模拟编排器"""
    mock = AsyncMock()

    # 配置属性
    mock.terminal_manager = mock_terminal_manager

    # 配置方法
    mock.smart_execute = AsyncMock(
        return_value={
            "strategy": "single",
            "session_name": "测试终端",
            "result": {
                "success": True,
                "output": "命令输出",
                "error": "",
                "exit_code": 0,
            },
        }
    )
    mock.collaborative_task = AsyncMock()
    mock.auto_setup_workspace = AsyncMock()

    return mock


# ==================== 测试工具 ====================
@pytest.fixture
def capture_stdout():
    """捕获标准输出"""
    import io
    import sys

    class StdoutCapture:
        def __enter__(self):
            self._original_stdout = sys.stdout
            self._captured_output = io.StringIO()
            sys.stdout = self._captured_output
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            sys.stdout = self._original_stdout

        @property
        def output(self):
            return self._captured_output.getvalue().strip()

    return StdoutCapture


@pytest.fixture
def capture_logs():
    """捕获日志"""
    import io
    import logging

    class LogCapture:
        def __init__(self, logger_name: str = None, level: int = logging.DEBUG):
            self.logger_name = logger_name
            self.level = level
            self.log_capture_string = io.StringIO()

        def __enter__(self):
            # 创建内存handler
            self.ch = logging.StreamHandler(self.log_capture_string)
            self.ch.setLevel(self.level)

            # 配置formatter
            formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
            self.ch.setFormatter(formatter)

            # 添加到logger
            logger = logging.getLogger(self.logger_name) if self.logger_name else logging.getLogger()

            logger.addHandler(self.ch)
            logger.setLevel(self.level)

            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            # 清理handler
            logger = logging.getLogger(self.logger_name) if self.logger_name else logging.getLogger()

            logger.removeHandler(self.ch)

        @property
        def logs(self):
            return self.log_capture_string.getvalue().strip()

        def contains(self, text: str) -> bool:
            return text in self.logs

        def count(self, text: str) -> int:
            return self.logs.count(text)

    return LogCapture


# ==================== 异步测试工具 ====================
@pytest.fixture
def async_context():
    """异步上下文管理器"""

    class AsyncContext:
        def __init__(self):
            self.setup_done = False
            self.teardown_done = False

        async def __aenter__(self):
            self.setup_done = True
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            self.teardown_done = True

    return AsyncContext


# ==================== 测试数据 ====================
@pytest.fixture
def test_conversation_history():
    """测试对话历史"""
    from core.ai_client import AIMessage

    return [
        AIMessage(role="system", content="你是弥娅，一个AI助手"),
        AIMessage(role="user", content="你好"),
        AIMessage(role="assistant", content="你好！我是弥娅，有什么可以帮您的？"),
        AIMessage(role="user", content="今天的天气怎么样？"),
        AIMessage(role="assistant", content="我是一个AI助手，无法获取实时天气信息。"),
    ]


@pytest.fixture
def test_terminal_status():
    """测试终端状态"""
    return {
        "id": "test-session-001",
        "name": "测试终端",
        "type": "cmd",
        "status": "running",
        "directory": "/tmp",
        "is_active": True,
        "command_count": 5,
        "output_count": 10,
        "created_at": "2024-01-01T00:00:00",
        "last_activity": "2024-01-01T00:05:00",
    }


# ==================== 性能测试工具 ====================
@pytest.fixture
def timer():
    """计时器"""
    import time

    class Timer:
        def __enter__(self):
            self.start = time.time()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.end = time.time()
            self.elapsed = self.end - self.start

        @property
        def milliseconds(self):
            return self.elapsed * 1000

    return Timer


# ==================== 清理工具 ====================
@pytest.fixture(autouse=True)
def cleanup_after_test():
    """测试后清理"""
    yield

    # 清理可能残留的全局状态
    import gc

    gc.collect()


# ==================== 测试装饰器 ====================
def skip_if_no_api_key(api_key_env_var: str = "AI_API_KEY"):
    """如果没有API密钥则跳过测试"""

    def decorator(test_func):

        @pytest.mark.skipif(not os.getenv(api_key_env_var), reason=f"需要设置环境变量 {api_key_env_var}")
        def wrapper(*args, **kwargs):
            return test_func(*args, **kwargs)

        return wrapper

    return decorator


def slow_test(test_func):
    """标记为慢速测试"""
    return pytest.mark.slow(test_func)


def integration_test(test_func):
    """标记为集成测试"""
    return pytest.mark.integration(test_func)


def e2e_test(test_func):
    """标记为端到端测试"""
    return pytest.mark.e2e(test_func)


# ============================================================================
# v6.0 新模块 Fixtures (阶段1-4 新增)
# ============================================================================


@pytest.fixture
def mock_embedding_func():
    """模拟嵌入函数"""

    def _embed(text: str) -> list[float]:
        import hashlib

        h = hashlib.sha256(text.encode()).digest()
        return [float(b) / 255.0 for b in h[:32]]

    return _embed


@pytest.fixture
def mock_llm_func():
    """模拟 LLM 调用函数"""

    def _call(prompt: str) -> str:
        return f"Mock response to: {prompt[:50]}..."

    return _call


@pytest.fixture
async def job_queue(temp_dir):
    """认知记忆任务队列"""
    from cognitive.job_queue import JobQueue

    q = JobQueue(
        base_dir=temp_dir / "cognitive/queues",
        stale_timeout_seconds=10.0,
        max_retries=2,
    )
    return q


@pytest.fixture
async def profile_storage(temp_dir):
    """档案存储"""
    from cognitive.profile_storage import ProfileStorage

    return ProfileStorage(
        profiles_dir=temp_dir / "cognitive/profiles",
        revision_keep=3,
    )


@pytest.fixture
async def vector_store(temp_dir):
    """向量存储 (需要 chromadb)"""
    try:
        from cognitive.vector_store import CognitiveVectorStore
    except ImportError:
        pytest.skip("chromadb 未安装")

    store = CognitiveVectorStore(
        persist_directory=str(temp_dir / "cognitive/chromadb"),
        collection_prefix="miya_test",
    )
    await store.initialize()
    return store


@pytest.fixture
async def cognitive_service(
    vector_store,
    job_queue,
    profile_storage,
    mock_embedding_func,
):
    """认知记忆服务"""
    from cognitive.service import CognitiveService

    svc = CognitiveService(
        vector_store=vector_store,
        job_queue=job_queue,
        profile_storage=profile_storage,
        get_embedding=mock_embedding_func,
        top_k=5,
    )
    await svc.initialize()
    return svc


@pytest.fixture
def queue_manager():
    """队列管理器"""
    from services.queue_manager import QueueManager

    return QueueManager(
        models={"default": 0.1, "gpt-4o": 0.1},
        default_interval=0.1,
    )


@pytest.fixture
def auto_pipeline_registry():
    """自动处理管线注册表"""
    from skills.auto_pipeline import AutoPipelineRegistry

    return AutoPipelineRegistry()


@pytest.fixture
def miya_config():
    """v6.0 统一配置 (从 text_config.json 加载)"""
    from config.config_utils import _load_config

    return _load_config()
