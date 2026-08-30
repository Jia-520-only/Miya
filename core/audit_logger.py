"""
Miya 审计日志模块 - 安全加强
===============================

该模块提供全面的审计日志功能,记录所有配置变更、命令执行和访问行为。
支持日志查询、分析和报告生成。
包含数据脱敏功能以保护敏感信息。

设计目标:
- 记录所有关键操作
- 不可篡改的日志存储
- 便于查询和分析
- 支持日志归档和清理
- 自动脱敏敏感数据（密码、令牌、个人信息等）
"""

import asyncio
import json
import logging
import re
import threading
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """审计事件类型"""

    # 配置管理
    CONFIG_READ = "config:read"
    CONFIG_WRITE = "config:write"
    CONFIG_DELETE = "config:delete"
    CONFIG_RELOAD = "config:reload"

    # API访问
    API_ACCESS = "api:access"
    API_KEY_CREATE = "api_key:create"
    API_KEY_REVOKE = "api_key:revoke"
    API_KEY_DELETE = "api_key:delete"

    # IoT操作
    IOT_DEVICE_CONNECT = "iot:device:connect"
    IOT_DEVICE_DISCONNECT = "iot:device:disconnect"
    IOT_COMMAND_SEND = "iot:command:send"
    IOT_RULE_EXECUTE = "iot:rule:execute"

    # 系统操作
    SYSTEM_STARTUP = "system:startup"
    SYSTEM_SHUTDOWN = "system:shutdown"
    SYSTEM_ERROR = "system:error"

    # 用户操作
    USER_LOGIN = "user:login"
    USER_LOGOUT = "user:logout"
    USER_ACTION = "user:action"


class AuditEventLevel(Enum):
    """审计事件级别"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """审计事件"""

    event_id: str
    event_type: AuditEventType
    level: AuditEventLevel
    timestamp: datetime
    user_id: Optional[str] = None
    api_key_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    action: Optional[str] = None
    status: str = "success"
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data["event_type"] = self.event_type.value
        data["level"] = self.level.value
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEvent":
        """从字典创建"""
        data["event_type"] = AuditEventType(data["event_type"])
        data["level"] = AuditEventLevel(data["level"])
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class AuditLogger:
    # Patterns for sensitive data that should be redacted
    SENSITIVE_PATTERNS = [
        # Passwords
        (
            r'(?i)(password|passwd|pwd)["\']?\s*[:=]\s*["\']?[^"\'\s,}]+',
            r'\1="[REDACTED]"',
        ),
        (r'(?i)"?(password|passwd|pwd)"?\s*:\s*"[^"]*"', r'"\1":"[REDACTED]"'),
        # API keys/tokens
        (
            r'(?i)(api[_\s]?key|token|auth[_\s]?key|access[_\s]?token|secret[_\s]?key)["\']?\s*[:=]\s*["\']?[^"\'\s,}]+',
            r'\1="[REDACTED]"',
        ),
        (
            r'(?i)"?(api[_\s]?key|token|auth[_\s]?key|access[_\s]?token|secret[_\s]?key)"?\s*:\s*"[^"]*"',
            r'"\1":"[REDACTED]"',
        ),
        # Personal data
        (
            r'(?i)(ssn|social[_\s]?security)["\']?\s*[:=]\s*["\']?[^"\'\s,}]+',
            r'\1="[REDACTED]"',
        ),
        (r'(?i)"?(ssn|social[_\s]?security)"?\s*:\s*"[^"]*"', r'"\1":"[REDACTED]"'),
        (
            r'(?i)(credit[_\s]?card|ccv|cvc)["\']?\s*[:=]\s*["\']?[^"\'\s,}]+',
            r'\1="[REDACTED]"',
        ),
        (r'(?i)"?(credit[_\s]?card|ccv|cvc)"?\s*:\s*"[^"]*"', r'"\1":"[REDACTED]"'),
        (r'(?i)(email|e-mail)["\']?\s*[:=]\s*["\']?[^"\'\s,}]+', r'\1="[REDACTED]"'),
        (r'(?i)"?(email|e-mail)"?\s*:\s*"[^"]*"', r'"\1":"[REDACTED]"'),
    ]
    """审计日志管理器"""

    def __init__(
        self,
        log_dir: str = "logs/audit",
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        max_files: int = 100,
        enable_console: bool = True,
    ):
        self.log_dir = Path(log_dir)
        self.max_file_size = max_file_size
        self.max_files = max_files
        self.enable_console = enable_console

        # 创建日志目录
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 当前日志文件
        self._current_log_file = self._get_current_log_file()
        self._current_file_size = 0
        if self._current_log_file.exists():
            self._current_file_size = self._current_log_file.stat().st_size

        # 内存缓存
        self._event_cache: List[AuditEvent] = []
        self._cache_lock = threading.Lock()

        # 写入线程
        self._write_queue = asyncio.Queue()
        self._write_task: Optional[asyncio.Task] = None

        logger.info(f"[审计日志] 初始化完成, 日志目录={self.log_dir}")

    def _get_current_log_file(self) -> Path:
        """获取当前日志文件"""
        date_str = datetime.now().strftime("%Y%m%d")
        return self.log_dir / f"audit_{date_str}.log"

    def _rotate_log_file(self):
        """轮转日志文件"""
        if not self._current_log_file.exists():
            return

        # 检查文件大小
        if self._current_log_file.stat().st_size >= self.max_file_size:
            # 添加序号
            base_name = self._current_log_file.stem
            extension = self._current_log_file.suffix

            # 查找下一个可用的序号
            counter = 1
            while True:
                new_name = f"{base_name}_{counter}{extension}"
                new_path = self._current_log_file.parent / new_name
                if not new_path.exists():
                    self._current_log_file.rename(new_path)
                    break
                counter += 1

            # 更新当前文件
            self._current_log_file = self._get_current_log_file()
            self._current_file_size = 0
            self._clean_old_logs()

            logger.info(f"[审计日志] 日志文件已轮转: {self._current_log_file}")

    def _clean_old_logs(self):
        """清理旧日志文件"""
        log_files = list(self.log_dir.glob("audit_*.log*"))

        # 按修改时间排序
        log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        # 删除超过数量的文件
        for log_file in log_files[self.max_files :]:
            try:
                log_file.unlink()
                logger.debug(f"[审计日志] 删除旧日志: {log_file}")
            except Exception as e:
                logger.error(f"[审计日志] 删除日志失败: {e}")

    def log_event(
        self,
        event_type: AuditEventType,
        level: AuditEventLevel = AuditEventLevel.INFO,
        user_id: Optional[str] = None,
        api_key_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        status: str = "success",
        message: str = "",
        details: Optional[Dict[str, Any]] = None,
    ):
        """记录审计事件"""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            level=level,
            timestamp=datetime.now(),
            user_id=user_id,
            api_key_id=api_key_id,
            ip_address=ip_address,
            user_agent=user_agent,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            status=status,
            message=message,
            details=details or {},
        )

        # 添加到缓存
        with self._cache_lock:
            self._event_cache.append(event)

            # 保持缓存大小合理
            if len(self._event_cache) > 1000:
                self._event_cache = self._event_cache[-1000:]

        # 写入日志
        self._write_event(event)

        # 控制台输出
        if self.enable_console:
            console_msg = f"[审计] {event_type.value} - {message}"
            if level == AuditEventLevel.ERROR or level == AuditEventLevel.CRITICAL:
                logger.error(console_msg)
            elif level == AuditEventLevel.WARNING:
                logger.warning(console_msg)
            else:
                logger.info(console_msg)

    def _redact_sensitive_data(self, text: str) -> str:
        """
        Redact sensitive data from text using predefined patterns.
        """
        if not isinstance(text, str):
            return text

        redacted = text
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            redacted = re.sub(pattern, replacement, redacted)
        return redacted

    def _write_event(self, event: AuditEvent):
        """写入事件到文件"""
        try:
            # 检查是否需要轮转
            self._rotate_log_file()

            # Convert event to dict and redact sensitive data
            event_dict = event.to_dict()

            # Redact sensitive fields in the details
            if "details" in event_dict and isinstance(event_dict["details"], dict):
                for key, value in event_dict["details"].items():
                    if isinstance(value, str):
                        event_dict["details"][key] = self._redact_sensitive_data(value)

            # Also redact in message if it's a string
            if "message" in event_dict and isinstance(event_dict["message"], str):
                event_dict["message"] = self._redact_sensitive_data(event_dict["message"])

            # 写入事件
            event_json = json.dumps(event_dict, ensure_ascii=False) + "\n"

            with open(self._current_log_file, "a", encoding="utf-8") as f:
                f.write(event_json)

            self._current_file_size += len(event_json.encode("utf-8"))

        except Exception as e:
            logger.error(f"[审计日志] 写入事件失败: {e}")

    def query_events(
        self,
        event_type: Optional[AuditEventType] = None,
        level: Optional[AuditEventLevel] = None,
        user_id: Optional[str] = None,
        api_key_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """查询审计事件"""
        results = []

        # 从缓存查询
        with self._cache_lock:
            for event in self._event_cache:
                if self._matches_filter(event, event_type, level, user_id, api_key_id, start_time, end_time):
                    results.append(event)

        # 如果缓存不够,从文件查询
        if len(results) < limit:
            results.extend(
                self._query_from_files(
                    event_type,
                    level,
                    user_id,
                    api_key_id,
                    start_time,
                    end_time,
                    limit - len(results),
                )
            )

        # 排序并限制数量
        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results[:limit]

    def _matches_filter(
        self,
        event: AuditEvent,
        event_type: Optional[AuditEventType],
        level: Optional[AuditEventLevel],
        user_id: Optional[str],
        api_key_id: Optional[str],
        start_time: Optional[datetime],
        end_time: Optional[datetime],
    ) -> bool:
        """检查事件是否匹配过滤条件"""
        if event_type and event.event_type != event_type:
            return False

        if level and event.level != level:
            return False

        if user_id and event.user_id != user_id:
            return False

        if api_key_id and event.api_key_id != api_key_id:
            return False

        if start_time and event.timestamp < start_time:
            return False

        return not (end_time and event.timestamp > end_time)

    def _query_from_files(
        self,
        event_type: Optional[AuditEventType],
        level: Optional[AuditEventLevel],
        user_id: Optional[str],
        api_key_id: Optional[str],
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        limit: int,
    ) -> List[AuditEvent]:
        """从文件查询事件"""
        results = []
        log_files = sorted(self.log_dir.glob("audit_*.log*"), reverse=True)

        for log_file in log_files:
            if len(results) >= limit:
                break

            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if len(results) >= limit:
                            break

                        try:
                            data = json.loads(line.strip())
                            event = AuditEvent.from_dict(data)

                            if self._matches_filter(
                                event,
                                event_type,
                                level,
                                user_id,
                                api_key_id,
                                start_time,
                                end_time,
                            ):
                                results.append(event)

                        except Exception:
                            continue

            except Exception as e:
                logger.error(f"[审计日志] 查询文件失败: {log_file}, 错误: {e}")

        return results

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        # 统计缓存中的事件
        event_counts = defaultdict(int)
        level_counts = defaultdict(int)

        with self._cache_lock:
            for event in self._event_cache:
                event_counts[event.event_type.value] += 1
                level_counts[event.level.value] += 1

        # 获取日志文件信息
        log_files = list(self.log_dir.glob("audit_*.log*"))
        total_size = sum(f.stat().st_size for f in log_files)

        return {
            "total_events": len(self._event_cache),
            "event_types": dict(event_counts),
            "event_levels": dict(level_counts),
            "log_files_count": len(log_files),
            "total_log_size_bytes": total_size,
            "current_log_file": str(self._current_log_file),
        }

    def generate_report(
        self,
        start_time: datetime,
        end_time: datetime,
        output_file: Optional[Path] = None,
    ) -> str:
        """生成审计报告"""
        events = self.query_events(start_time=start_time, end_time=end_time, limit=10000)

        # 统计分析
        event_type_stats = defaultdict(int)
        level_stats = defaultdict(int)
        user_stats = defaultdict(int)
        status_stats = defaultdict(int)

        for event in events:
            event_type_stats[event.event_type.value] += 1
            level_stats[event.level.value] += 1
            if event.user_id:
                user_stats[event.user_id] += 1
            status_stats[event.status] += 1

        # 生成报告
        report_lines = [
            "# Miya 审计报告",
            f"报告时间: {datetime.now().isoformat()}",
            f"时间范围: {start_time.isoformat()} - {end_time.isoformat()}",
            f"总事件数: {len(events)}",
            "",
            "## 事件类型统计",
        ]

        for event_type, count in sorted(event_type_stats.items(), key=lambda x: x[1], reverse=True):
            report_lines.append(f"- {event_type}: {count}")

        report_lines.extend(["", "## 事件级别统计"])

        for level, count in sorted(level_stats.items(), key=lambda x: x[1], reverse=True):
            report_lines.append(f"- {level}: {count}")

        report_lines.extend(["", "## 用户活动统计"])

        for user_id, count in sorted(user_stats.items(), key=lambda x: x[1], reverse=True)[:10]:
            report_lines.append(f"- {user_id}: {count}")

        report_lines.extend(["", "## 状态统计"])

        for status, count in sorted(status_stats.items(), key=lambda x: x[1], reverse=True):
            report_lines.append(f"- {status}: {count}")

        # 添加重要事件
        critical_events = [e for e in events if e.level == AuditEventLevel.CRITICAL]
        error_events = [e for e in events if e.level == AuditEventLevel.ERROR]

        if critical_events:
            report_lines.extend(["", "## 严重事件"])
            for event in critical_events[:20]:
                report_lines.append(f"- [{event.timestamp}] {event.message}")

        if error_events:
            report_lines.extend(["", "## 错误事件"])
            for event in error_events[:20]:
                report_lines.append(f"- [{event.timestamp}] {event.message}")

        report_str = "\n".join(report_lines)

        # 保存到文件
        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(report_str)
            logger.info(f"[审计日志] 报告已保存: {output_file}")

        return report_str


# 全局审计日志实例
_global_audit_logger: Optional[AuditLogger] = None


def get_global_audit_logger() -> AuditLogger:
    """获取全局审计日志实例"""
    global _global_audit_logger
    if _global_audit_logger is None:
        _global_audit_logger = AuditLogger()
    return _global_audit_logger


def set_global_audit_logger(logger: AuditLogger):
    """设置全局审计日志实例"""
    global _global_audit_logger
    _global_audit_logger = logger


# 便捷函数
def audit_log(event_type: AuditEventType, message: str = "", **kwargs):
    """便捷的审计日志记录函数"""
    audit_logger = get_global_audit_logger()
    audit_logger.log_event(event_type=event_type, message=message, **kwargs)


# 示例使用
if __name__ == "__main__":
    # 创建审计日志记录器
    audit_logger = AuditLogger()

    # 记录一些事件
    audit_logger.log_event(
        event_type=AuditEventType.SYSTEM_STARTUP,
        level=AuditEventLevel.INFO,
        message="系统启动",
    )

    audit_logger.log_event(
        event_type=AuditEventType.API_KEY_CREATE,
        level=AuditEventLevel.INFO,
        user_id="user123",
        message="创建API密钥",
    )

    audit_logger.log_event(
        event_type=AuditEventType.IOT_COMMAND_SEND,
        level=AuditEventLevel.WARNING,
        user_id="user123",
        resource_type="device",
        resource_id="device001",
        message="发送IoT命令失败",
        status="failed",
        details={"error": "设备离线"},
    )

    # 查询事件
    events = audit_logger.query_events(event_type=AuditEventType.API_KEY_CREATE, limit=10)

    print(f"查询到 {len(events)} 个事件")
    for event in events:
        print(f"  {event.event_type.value}: {event.message}")

    # 获取统计
    stats = audit_logger.get_stats()
    print(f"统计: {stats}")

    # 生成报告
    from datetime import timedelta

    end_time = datetime.now()
    start_time = end_time - timedelta(days=1)
    report = audit_logger.generate_report(start_time, end_time)
    print(report)
