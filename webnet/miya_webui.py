"""
弥娅 Management WebUI

参考 Undefined 项目的 Management-first WebUI 设计：
- 即使配置缺失也能先进入管理态
- 配置引导、补全、启动 Bot
- 日志查看、运行时探针
- 远程管理支持

提供：
1. 管理 API（Management API）：配置、日志、Bot 启停
2. 运行时 API（Runtime API）：探针、记忆只读查询
3. Web 管理界面
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BotStatus(Enum):
    """Bot 状态"""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class SystemStats:
    """系统统计"""

    uptime: float = 0
    total_messages: int = 0
    total_commands: int = 0
    active_sessions: int = 0
    memory_usage_mb: float = 0
    cpu_percent: float = 0
    tool_calls_success: int = 0
    tool_calls_failed: int = 0
    last_updated: str = ""


@dataclass
class ConfigStatus:
    """配置状态"""

    ai_api_key: bool = False
    ai_model: bool = False
    onebot_ws_url: bool = False
    bot_qq: bool = False
    redis: bool = False
    milvus: bool = False
    neo4j: bool = False


class MiyaWebUI:
    """
    弥娅 Web 管理界面

    功能：
    1. 配置管理：查看、编辑、保存配置
    2. 状态监控：Bot 状态、系统资源、工具调用统计
    3. 日志查看：实时日志、过滤、搜索
    4. 远程管理：启动/停止 Bot、重新加载配置
    """

    def __init__(self, config_dir: Optional[Path] = None, data_dir: Optional[Path] = None):
        # 路径配置
        self.config_dir = config_dir or Path(__file__).parent.parent / "config"
        self.data_dir = data_dir or Path(__file__).parent.parent / "data"

        # 日志目录
        self.logs_dir = self.data_dir.parent / "logs"

        # Bot 状态
        self.bot_status = BotStatus.STOPPED
        self.bot_start_time: Optional[float] = None
        self._status_lock = asyncio.Lock()

        # 系统统计
        self.stats = SystemStats()
        self.stats_start_time = time.time()

        # Miya 实例引用
        self.miya_instance = None

        # 日志缓存
        self._log_cache: List[Dict] = []
        self._max_log_cache = 1000

        logger.info("[MiyaWebUI] Web 管理界面初始化完成")

    def set_miya_instance(self, miya_instance):
        """设置 Miya 实例"""
        self.miya_instance = miya_instance

    async def start_bot(self) -> Dict[str, Any]:
        """启动 Bot"""
        async with self._status_lock:
            if self.bot_status == BotStatus.RUNNING:
                return {"success": False, "message": "Bot 已经在运行中"}

            self.bot_status = BotStatus.STARTING
            logger.info("[MiyaWebUI] 正在启动 Bot...")

            try:
                # 模拟启动过程（实际需要启动 QQNet）
                await asyncio.sleep(1)

                self.bot_status = BotStatus.RUNNING
                self.bot_start_time = time.time()
                self.stats_start_time = time.time()

                logger.info("[MiyaWebUI] Bot 启动成功")
                return {"success": True, "message": "Bot 启动成功"}

            except Exception as e:
                self.bot_status = BotStatus.ERROR
                logger.error(f"[MiyaWebUI] Bot 启动失败: {e}")
                return {"success": False, "message": f"启动失败: {str(e)}"}

    async def stop_bot(self) -> Dict[str, Any]:
        """停止 Bot"""
        async with self._status_lock:
            if self.bot_status == BotStatus.STOPPED:
                return {"success": False, "message": "Bot 已经停止"}

            self.bot_status = BotStatus.STOPPING
            logger.info("[MiyaWebUI] 正在停止 Bot...")

            try:
                await asyncio.sleep(0.5)

                self.bot_status = BotStatus.STOPPED
                self.bot_start_time = None

                logger.info("[MiyaWebUI] Bot 已停止")
                return {"success": True, "message": "Bot 已停止"}

            except Exception as e:
                self.bot_status = BotStatus.ERROR
                logger.error(f"[MiyaWebUI] Bot 停止失败: {e}")
                return {"success": False, "message": f"停止失败: {str(e)}"}

    def get_bot_status(self) -> Dict[str, Any]:
        """获取 Bot 状态"""
        uptime = 0
        if self.bot_start_time:
            uptime = time.time() - self.bot_start_time

        return {
            "status": self.bot_status.value,
            "uptime_seconds": uptime,
            "start_time": datetime.fromtimestamp(self.bot_start_time).isoformat() if self.bot_start_time else None,
        }

    def get_system_stats(self) -> SystemStats:
        """获取系统统计"""
        self.stats.uptime = time.time() - self.stats_start_time
        self.stats.last_updated = datetime.now().isoformat()

        # 获取系统资源
        try:
            import psutil

            process = psutil.Process()
            self.stats.memory_usage_mb = process.memory_info().rss / 1024 / 1024
            self.stats.cpu_percent = process.cpu_percent()
        except ImportError:
            pass

        # 从 Miya 实例获取更多信息
        if self.miya_instance:
            try:
                # 尝试获取工具调用统计
                if (hasattr(self.miya_instance, "decision_hub") and self.miya_instance.decision_hub) and hasattr(
                    self.miya_instance.decision_hub, "tool_subnet"
                ):
                    tool_subnet = self.miya_instance.decision_hub.tool_subnet
                    if tool_subnet:
                        stats = tool_subnet.get_stats()
                        self.stats.tool_calls_success = stats.get("success_calls", 0)
                        self.stats.tool_calls_failed = stats.get("failed_calls", 0)
            except Exception as e:
                logger.debug(f"[MiyaWebUI] 获取统计失败: {e}")

        return self.stats

    def get_config_status(self) -> ConfigStatus:
        """获取配置状态"""
        config_status = ConfigStatus()

        # 读取 .env 文件
        env_path = self.config_dir / ".env"
        if not env_path.exists():
            return config_status

        try:
            with open(env_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 检查配置项
            config_status.ai_api_key = (
                "AI_API_KEY=" in content and content.split("AI_API_KEY=")[1].split("\n")[0].strip() != ""
            )
            config_status.ai_model = (
                "AI_MODEL=" in content and content.split("AI_MODEL=")[1].split("\n")[0].strip() != ""
            )
            config_status.onebot_ws_url = (
                "QQ_ONEBOT_WS_URL=" in content and content.split("QQ_ONEBOT_WS_URL=")[1].split("\n")[0].strip() != ""
            )
            config_status.bot_qq = (
                "QQ_BOT_QQ=" in content and content.split("QQ_BOT_QQ=")[1].split("\n")[0].strip() != ""
            )
            config_status.redis = "REDIS_HOST=" in content
            config_status.milvus = "MILVUS_HOST=" in content
            config_status.neo4j = (
                "NEO4J_PASSWORD=" in content and content.split("NEO4J_PASSWORD=")[1].split("\n")[0].strip() != ""
            )

        except Exception as e:
            logger.error(f"[MiyaWebUI] 读取配置失败: {e}")

        return config_status

    def get_logs(self, lines: int = 100, level: Optional[str] = None) -> List[Dict]:
        """获取日志"""
        log_file = self.logs_dir / "miya.log"

        if not log_file.exists():
            return []

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                all_lines = f.readlines()

            # 获取最后 N 行
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

            # 过滤级别
            if level:
                recent_lines = [l for l in recent_lines if level.upper() in l]

            # 解析日志行
            logs = []
            for line in recent_lines:
                try:
                    # 简单解析：时间 - 级别 - 内容
                    parts = line.strip().split(" - ", 2)
                    if len(parts) >= 3:
                        logs.append(
                            {
                                "time": parts[0],
                                "level": parts[1],
                                "message": parts[2],
                            }
                        )
                except:
                    pass

            return logs[-lines:]

        except Exception as e:
            logger.error(f"[MiyaWebUI] 读取日志失败: {e}")
            return []

    def get_memory_stats(self) -> Dict[str, Any]:
        """获取记忆统计"""
        memory_stats = {
            "short_term": {"count": 0},
            "cognitive": {"events": 0},
            "top_memory": {"count": 0},
        }

        # 检查数据目录
        cognitive_dir = self.data_dir / "cognitive_memory"
        if cognitive_dir.exists():
            # 短期记忆
            short_term_dir = cognitive_dir / "short_term"
            if short_term_dir.exists():
                memory_stats["short_term"]["count"] = len(list(short_term_dir.glob("*.json")))

            # 置顶备忘录
            top_memory_dir = cognitive_dir / "top_memory"
            if top_memory_dir.exists():
                memory_stats["top_memory"]["count"] = len(list(top_memory_dir.glob("*.json")))

            # ChromaDB
            chroma_dir = cognitive_dir / "chromadb"
            if chroma_dir.exists():
                memory_stats["cognitive"]["exists"] = True

        return memory_stats

    def get_health_report(self) -> Dict[str, Any]:
        """获取健康报告"""
        # Bot 状态
        bot_status = self.get_bot_status()

        # 配置状态
        config_status = self.get_config_status()

        # 系统统计
        stats = self.get_system_stats()

        # 记忆统计
        memory = self.get_memory_stats()

        # 综合健康状态
        health_status = "healthy"
        issues = []

        if config_status.bot_qq and not config_status.onebot_ws_url:
            issues.append("QQ 配置不完整")
            health_status = "degraded"

        if self.bot_status != BotStatus.RUNNING:
            issues.append("Bot 未运行")

        return {
            "status": health_status,
            "issues": issues,
            "bot": bot_status,
            "config": {
                "ai_api_key": config_status.ai_api_key,
                "ai_model": config_status.ai_model,
                "onebot_ws_url": config_status.onebot_ws_url,
                "bot_qq": config_status.bot_qq,
                "redis": config_status.redis,
                "milvus": config_status.milvus,
                "neo4j": config_status.neo4j,
            },
            "system": {
                "uptime": stats.uptime,
                "memory_mb": stats.memory_usage_mb,
                "cpu_percent": stats.cpu_percent,
                "tool_calls_success": stats.tool_calls_success,
                "tool_calls_failed": stats.tool_calls_failed,
            },
            "memory": memory,
        }

    def update_stats(self, message_processed: bool = False, command_executed: bool = False):
        """更新统计"""
        if message_processed:
            self.stats.total_messages += 1
        if command_executed:
            self.stats.total_commands += 1


# 全局实例
_global_webui: Optional[MiyaWebUI] = None


def get_global_webui(
    config_dir: Optional[Path] = None,
    data_dir: Optional[Path] = None,
) -> MiyaWebUI:
    """获取全局 WebUI 实例"""
    global _global_webui

    if _global_webui is None:
        _global_webui = MiyaWebUI(config_dir, data_dir)

    return _global_webui


# FastAPI 路由
def create_management_routes(app, webui: MiyaWebUI):
    """创建管理 API 路由"""
    from fastapi import APIRouter

    router = APIRouter(prefix="/api/management", tags=["Management"])

    @router.get("/status")
    async def get_status():
        """获取 Bot 状态"""
        return webui.get_bot_status()

    @router.post("/bot/start")
    async def start_bot():
        """启动 Bot"""
        return await webui.start_bot()

    @router.post("/bot/stop")
    async def stop_bot():
        """停止 Bot"""
        return await webui.stop_bot()

    @router.get("/stats")
    async def get_stats():
        """获取系统统计"""
        stats = webui.get_system_stats()
        return {
            "uptime": stats.uptime,
            "total_messages": stats.total_messages,
            "total_commands": stats.total_commands,
            "memory_mb": stats.memory_usage_mb,
            "cpu_percent": stats.cpu_percent,
            "tool_calls_success": stats.tool_calls_success,
            "tool_calls_failed": stats.tool_calls_failed,
        }

    @router.get("/config/status")
    async def get_config_status():
        """获取配置状态"""
        status = webui.get_config_status()
        return {
            "ai_api_key": status.ai_api_key,
            "ai_model": status.ai_model,
            "onebot_ws_url": status.onebot_ws_url,
            "bot_qq": status.bot_qq,
            "redis": status.redis,
            "milvus": status.milvus,
            "neo4j": status.neo4j,
        }

    @router.get("/logs")
    async def get_logs(lines: int = 100, level: Optional[str] = None):
        """获取日志"""
        return webui.get_logs(lines, level)

    @router.get("/health")
    async def get_health():
        """获取健康报告"""
        return webui.get_health_report()

    @router.get("/memory")
    async def get_memory():
        """获取记忆统计"""
        return webui.get_memory_stats()

    # 注册路由
    app.include_router(router)


def create_runtime_routes(app, webui: MiyaWebUI):
    """创建运行时 API 路由"""
    from fastapi import APIRouter

    router = APIRouter(prefix="/api/runtime", tags=["Runtime"])

    @router.get("/probe")
    async def probe():
        """运行态探针"""
        return {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "bot_status": webui.bot_status.value,
        }

    @router.get("/memory/query")
    async def query_memory(session_id: str, query: str = ""):
        """查询记忆（只读）"""
        # 简化实现，实际可以调用三层认知记忆
        return {
            "session_id": session_id,
            "query": query,
            "results": [],
        }

    @router.get("/profile/{entity_type}/{entity_id}")
    async def get_profile(entity_type: str, entity_id: str):
        """获取用户/群侧写"""
        # 简化实现
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "profile": None,
        }

    # 注册路由
    app.include_router(router)
