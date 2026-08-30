"""
Miya 监控和告警机制模块
================================

该模块提供全面的系统监控和告警功能。
支持指标采集、阈值检查、告警发送和仪表盘展示。

设计目标:
- 实时监控关键指标
- 灵活的告警规则配置
- 多种告警通知方式
- 可视化仪表盘支持
"""

import asyncio
import contextlib
import json
import logging
import smtplib
import statistics
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """指标类型"""

    COUNTER = "counter"  # 计数器
    GAUGE = "gauge"  # 仪表
    HISTOGRAM = "histogram"  # 直方图
    SUMMARY = "summary"  # 摘要


class AlertSeverity(Enum):
    """告警严重级别"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """告警状态"""

    ACTIVE = "active"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"


@dataclass
class Metric:
    """指标"""

    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricData:
    """指标数据(用于历史记录)"""

    metric_name: str
    values: deque
    max_size: int = 1000

    def add_value(self, value: float, timestamp: datetime):
        """添加值"""
        self.values.append((timestamp, value))
        if len(self.values) > self.max_size:
            self.values.popleft()

    def get_values(self, duration: Optional[timedelta] = None) -> List[tuple]:
        """获取值"""
        if duration is None:
            return list(self.values)

        cutoff = datetime.now() - duration
        return [(ts, val) for ts, val in self.values if ts >= cutoff]

    def get_stats(self) -> Dict[str, float]:
        """获取统计信息"""
        if not self.values:
            return {}

        values = [val for _, val in self.values]
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": statistics.mean(values),
            "median": statistics.median(values) if values else 0.0,
            "stddev": statistics.stdev(values) if len(values) > 1 else 0.0,
        }


@dataclass
class AlertRule:
    """告警规则"""

    rule_id: str
    name: str
    metric_name: str
    condition: str  # gt, lt, gte, lte, eq, ne
    threshold: float
    severity: AlertSeverity
    duration: float = 300.0  # 持续时间(秒)
    enabled: bool = True
    labels: Dict[str, str] = field(default_factory=dict)
    description: str = ""


@dataclass
class Alert:
    """告警"""

    alert_id: str
    rule_id: str
    metric_name: str
    severity: AlertSeverity
    status: AlertStatus
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


class MetricCollector:
    """指标采集器"""

    def __init__(self):
        self._metrics: Dict[str, MetricData] = {}
        self._lock = threading.Lock()

    def record(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.GAUGE,
        labels: Optional[Dict[str, str]] = None,
        tags: Optional[Dict[str, str]] = None,
    ):
        """记录指标"""
        timestamp = datetime.now()

        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = MetricData(metric_name=name, values=deque(maxlen=1000))

            self._metrics[name].add_value(value, timestamp)

    def get_metric(self, name: str) -> Optional[MetricData]:
        """获取指标数据"""
        with self._lock:
            return self._metrics.get(name)

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """获取所有指标"""
        with self._lock:
            return {
                name: {"name": metric.metric_name, "count": len(metric.values), "stats": metric.get_stats()}
                for name, metric in self._metrics.items()
            }

    def get_metric_value(self, name: str) -> Optional[float]:
        """获取指标的最新值"""
        metric = self.get_metric(name)
        if metric and metric.values:
            return metric.values[-1][1]
        return None

    def get_metric_stats(self, name: str, duration: timedelta = timedelta(minutes=5)) -> Dict[str, float]:
        """获取指标的统计信息"""
        metric = self.get_metric(name)
        if metric:
            values = [val for _, val in metric.get_values(duration)]
            if values:
                return {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "avg": statistics.mean(values),
                    "median": statistics.median(values),
                    "latest": values[-1],
                }
        return {}


class AlertEngine:
    """告警引擎"""

    def __init__(self, collector: MetricCollector):
        self.collector = collector
        self._rules: Dict[str, AlertRule] = {}
        self._alerts: Dict[str, Alert] = {}
        self._alert_history: List[Alert] = []
        self._alert_conditions: Dict[str, float] = {}  # 规则ID -> 触发时间

        # 告警通知回调
        self._alert_callbacks: List[Callable[[Alert], None]] = []

    def add_rule(self, rule: AlertRule):
        """添加告警规则"""
        self._rules[rule.rule_id] = rule
        logger.info(f"[告警引擎] 添加规则: {rule.name} ({rule.rule_id})")

    def remove_rule(self, rule_id: str):
        """移除告警规则"""
        if rule_id in self._rules:
            del self._rules[rule_id]
            logger.info(f"[告警引擎] 移除规则: {rule_id}")

    def check_rules(self):
        """检查所有告警规则"""
        for rule in self._rules.values():
            if not rule.enabled:
                continue

            self._check_rule(rule)

    def _check_rule(self, rule: AlertRule):
        """检查单个告警规则"""
        metric_value = self.collector.get_metric_value(rule.metric_name)

        if metric_value is None:
            return

        # 检查条件
        triggered = False
        if (
            rule.condition == "gt"
            and metric_value > rule.threshold
            or rule.condition == "lt"
            and metric_value < rule.threshold
            or rule.condition == "gte"
            and metric_value >= rule.threshold
            or rule.condition == "lte"
            and metric_value <= rule.threshold
            or rule.condition == "eq"
            and metric_value == rule.threshold
            or rule.condition == "ne"
            and metric_value != rule.threshold
        ):
            triggered = True

        if triggered:
            self._trigger_alert(rule, metric_value)
        else:
            self._resolve_alert(rule.rule_id)

    def _trigger_alert(self, rule: AlertRule, current_value: float):
        """触发告警"""
        now = datetime.now()

        # 检查是否已存在活动告警
        if rule.rule_id in self._alerts:
            existing_alert = self._alerts[rule.rule_id]
            if existing_alert.status == AlertStatus.ACTIVE:
                return  # 告警已存在,不需要重复触发

        # 检查持续时间
        if rule.rule_id not in self._alert_conditions:
            self._alert_conditions[rule.rule_id] = time.time()
        elif time.time() - self._alert_conditions[rule.rule_id] >= rule.duration:
            # 持续时间足够,触发告警
            del self._alert_conditions[rule.rule_id]

            alert = Alert(
                alert_id=f"{rule.rule_id}_{int(now.timestamp())}",
                rule_id=rule.rule_id,
                metric_name=rule.metric_name,
                severity=rule.severity,
                status=AlertStatus.ACTIVE,
                triggered_at=now,
                message=f"告警: {rule.metric_name} {rule.condition} {rule.threshold}, 当前值: {current_value}",
                details={
                    "rule_name": rule.name,
                    "threshold": rule.threshold,
                    "current_value": current_value,
                    "description": rule.description,
                },
            )

            self._alerts[rule.rule_id] = alert
            self._alert_history.append(alert)

            # 通知
            self._notify_alert(alert)

            logger.warning(f"[告警引擎] 触发告警: {alert.message}")
        else:
            # 持续时间不够
            pass

    def _resolve_alert(self, rule_id: str):
        """解决告警"""
        if rule_id in self._alerts:
            alert = self._alerts[rule_id]
            if alert.status == AlertStatus.ACTIVE:
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.now()
                logger.info(f"[告警引擎] 解决告警: {alert.alert_id}")

            # 清除触发时间
            if rule_id in self._alert_conditions:
                del self._alert_conditions[rule_id]

    def acknowledge_alert(self, alert_id: str):
        """确认告警"""
        for alert in self._alerts.values():
            if alert.alert_id == alert_id and alert.status == AlertStatus.ACTIVE:
                alert.status = AlertStatus.ACKNOWLEDGED
                alert.acknowledged_at = datetime.now()
                logger.info(f"[告警引擎] 确认告警: {alert_id}")

    def _notify_alert(self, alert: Alert):
        """通知告警"""
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"[告警引擎] 通知告警失败: {e}")

    def register_alert_callback(self, callback: Callable[[Alert], None]):
        """注册告警通知回调"""
        self._alert_callbacks.append(callback)

    def get_active_alerts(self) -> List[Alert]:
        """获取活动告警"""
        return [alert for alert in self._alerts.values() if alert.status == AlertStatus.ACTIVE]

    def get_all_alerts(self) -> List[Alert]:
        """获取所有告警"""
        return list(self._alerts.values())


class NotificationService:
    """通知服务"""

    def __init__(self):
        self._email_config: Optional[Dict[str, Any]] = None
        self._webhook_urls: List[str] = []

    def configure_email(
        self, smtp_server: str, smtp_port: int, sender_email: str, sender_password: str, use_tls: bool = True
    ):
        """配置邮件通知"""
        self._email_config = {
            "smtp_server": smtp_server,
            "smtp_port": smtp_port,
            "sender_email": sender_email,
            "sender_password": sender_password,
            "use_tls": use_tls,
        }
        logger.info("[通知服务] 邮件通知已配置")

    def add_webhook(self, url: str):
        """添加Webhook URL"""
        self._webhook_urls.append(url)
        logger.info(f"[通知服务] 添加Webhook: {url}")

    def send_email_alert(self, alert: Alert, recipients: List[str]):
        """发送邮件告警"""
        if not self._email_config:
            logger.warning("[通知服务] 邮件配置未设置")
            return

        try:
            subject = f"[{alert.severity.value.upper()}] Miya 告警: {alert.metric_name}"
            body = self._format_alert_email(alert)

            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = self._email_config["sender_email"]
            msg["To"] = ", ".join(recipients)

            with smtplib.SMTP(self._email_config["smtp_server"], self._email_config["smtp_port"]) as server:
                if self._email_config["use_tls"]:
                    server.starttls()
                server.login(self._email_config["sender_email"], self._email_config["sender_password"])
                server.send_message(msg)

            logger.info(f"[通知服务] 邮件告警已发送: {alert.alert_id}")

        except Exception as e:
            logger.error(f"[通知服务] 发送邮件失败: {e}")

    async def send_webhook_alert(self, alert: Alert):
        """发送Webhook告警"""
        import aiohttp

        payload = {
            "alert_id": alert.alert_id,
            "rule_id": alert.rule_id,
            "metric_name": alert.metric_name,
            "severity": alert.severity.value,
            "status": alert.status.value,
            "message": alert.message,
            "details": alert.details,
            "triggered_at": alert.triggered_at.isoformat(),
        }

        for webhook_url in self._webhook_urls:
            try:
                async with (
                    aiohttp.ClientSession() as session,
                    session.post(webhook_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as response,
                ):
                    if response.status == 200:
                        logger.info(f"[通知服务] Webhook告警已发送: {webhook_url}")
                    else:
                        logger.warning(f"[通知服务] Webhook返回错误: {response.status}")

            except Exception as e:
                logger.error(f"[通知服务] 发送Webhook失败: {webhook_url}, 错误: {e}")

    def _format_alert_email(self, alert: Alert) -> str:
        """格式化告警邮件"""
        lines = [
            "Miya 告警通知",
            "================",
            "",
            f"严重级别: {alert.severity.value.upper()}",
            f"指标名称: {alert.metric_name}",
            f"告警消息: {alert.message}",
            f"触发时间: {alert.triggered_at.isoformat()}",
            "",
            "详细信息:",
        ]

        if alert.details:
            for key, value in alert.details.items():
                lines.append(f"  {key}: {value}")

        return "\n".join(lines)


class MonitoringSystem:
    """监控系统"""

    def __init__(self, check_interval: float = 30.0):
        self.check_interval = check_interval
        self.collector = MetricCollector()
        self.alert_engine = AlertEngine(self.collector)
        self.notification_service = NotificationService()

        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None

        # 注册告警通知回调
        self.alert_engine.register_alert_callback(self._on_alert)

        logger.info(f"[监控系统] 初始化完成, 检查间隔={check_interval}s")

    def _on_alert(self, alert: Alert):
        """告警回调"""
        # 发送Webhook通知
        asyncio.create_task(self.notification_service.send_webhook_alert(alert))

        # 发送邮件通知(如果配置)
        # recipients = ["admin@example.com"]
        # self.notification_service.send_email_alert(alert, recipients)

    def add_default_rules(self):
        """添加默认告警规则"""
        # CPU使用率告警
        self.alert_engine.add_rule(
            AlertRule(
                rule_id="cpu_high",
                name="CPU使用率过高",
                metric_name="system.cpu.usage",
                condition="gt",
                threshold=80.0,
                severity=AlertSeverity.WARNING,
                duration=300.0,
                description="CPU使用率超过80%持续5分钟",
            )
        )

        # 内存使用率告警
        self.alert_engine.add_rule(
            AlertRule(
                rule_id="memory_high",
                name="内存使用率过高",
                metric_name="system.memory.usage",
                condition="gt",
                threshold=85.0,
                severity=AlertSeverity.WARNING,
                duration=300.0,
                description="内存使用率超过85%持续5分钟",
            )
        )

        # API错误率告警
        self.alert_engine.add_rule(
            AlertRule(
                rule_id="api_error_rate",
                name="API错误率过高",
                metric_name="api.error_rate",
                condition="gt",
                threshold=5.0,
                severity=AlertSeverity.ERROR,
                duration=300.0,
                description="API错误率超过5%持续5分钟",
            )
        )

        logger.info("[监控系统] 添加默认告警规则")

    def start(self):
        """启动监控"""
        if self._running:
            logger.warning("[监控系统] 监控已在运行")
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("[监控系统] 监控已启动")

    async def _monitor_loop(self):
        """监控循环"""
        while self._running:
            try:
                # 采集系统指标
                self._collect_system_metrics()

                # 检查告警规则
                self.alert_engine.check_rules()

                # 等待下次检查
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[监控系统] 监控循环错误: {e}")
                await asyncio.sleep(self.check_interval)

    def _collect_system_metrics(self):
        """采集系统指标"""
        import psutil

        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        self.collector.record("system.cpu.usage", cpu_percent, MetricType.GAUGE)

        # 内存使用率
        memory = psutil.virtual_memory()
        self.collector.record("system.memory.usage", memory.percent, MetricType.GAUGE)
        self.collector.record("system.memory.available", memory.available, MetricType.GAUGE)

        # 磁盘使用率
        disk = psutil.disk_usage("/")
        disk_percent = (disk.used / disk.total) * 100
        self.collector.record("system.disk.usage", disk_percent, MetricType.GAUGE)

        logger.debug(f"[监控系统] 采集系统指标: CPU={cpu_percent}%, Memory={memory.percent}%")

    async def stop(self):
        """停止监控"""
        self._running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitor_task

        logger.info("[监控系统] 监控已停止")

    def get_dashboard_data(self) -> Dict[str, Any]:
        """获取仪表盘数据"""
        return {
            "metrics": self.collector.get_all_metrics(),
            "alerts": [
                {
                    "alert_id": alert.alert_id,
                    "rule_id": alert.rule_id,
                    "metric_name": alert.metric_name,
                    "severity": alert.severity.value,
                    "status": alert.status.value,
                    "message": alert.message,
                    "triggered_at": alert.triggered_at.isoformat(),
                }
                for alert in self.alert_engine.get_active_alerts()
            ],
        }


# 全局监控系统实例
_global_monitoring: Optional[MonitoringSystem] = None


def get_global_monitoring() -> MonitoringSystem:
    """获取全局监控系统实例"""
    global _global_monitoring
    if _global_monitoring is None:
        _global_monitoring = MonitoringSystem()
        _global_monitoring.add_default_rules()
    return _global_monitoring


def set_global_monitoring(monitoring: MonitoringSystem):
    """设置全局监控系统实例"""
    global _global_monitoring
    _global_monitoring = monitoring


# 示例使用
if __name__ == "__main__":

    async def test_monitoring():
        # 创建监控系统
        monitoring = MonitoringSystem(check_interval=10.0)

        # 配置Webhook(示例)
        monitoring.notification_service.add_webhook("http://localhost:8080/alerts")

        # 启动监控
        monitoring.start()

        try:
            # 运行一段时间
            await asyncio.sleep(60)

            # 获取仪表盘数据
            dashboard_data = monitoring.get_dashboard_data()
            print(f"仪表盘数据: {json.dumps(dashboard_data, indent=2)}")

            # 获取活动告警
            active_alerts = monitoring.alert_engine.get_active_alerts()
            print(f"活动告警: {len(active_alerts)}")

        finally:
            # 停止监控
            await monitoring.stop()

    asyncio.run(test_monitoring())
