"""
系统监控工具
监控系统资源、进程、服务状态等
"""

import os
import psutil
import platform
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
import json

logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    """系统指标"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used: int
    memory_available: int
    memory_total: int
    disk_usage: float
    disk_used: int
    disk_free: int
    disk_total: int
    network_sent: int
    network_recv: int
    process_count: int
    load_average: Optional[List[float]] = None


@dataclass
class ProcessInfo:
    """进程信息"""
    pid: int
    name: str
    status: str
    cpu_percent: float
    memory_percent: float
    memory_used: int
    num_threads: int
    create_time: float
    exe: Optional[str] = None
    cmd_line: Optional[List[str]] = None


@dataclass
class AlertRule:
    """告警规则"""
    name: str
    metric: str
    threshold: float
    operator: str = '>'
    duration: int = 60  # 持续时间（秒）
    action: str = 'log'  # log, email, webhook
    enabled: bool = True


class SystemMonitor:
    """系统监控主类"""

    def __init__(self, history_size: int = 3600):
        """
        初始化系统监控

        Args:
            history_size: 历史数据保留数量
        """
        self.history_size = history_size
        self.metrics_history: deque = deque(maxlen=history_size)
        self.alert_rules: List[AlertRule] = []
        self.alert_states: Dict[str, Dict] = {}
        self.last_network_stats = None

    def collect_metrics(self) -> SystemMetrics:
        """
        收集系统指标

        Returns:
            系统指标
        """
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)

        # 内存
        memory = psutil.virtual_memory()

        # 磁盘
        disk = psutil.disk_usage('/')

        # 网络
        network = psutil.net_io_counters()

        # 进程数
        process_count = len(psutil.pids())

        # 负载平均值（仅Unix）
        load_average = None
        if hasattr(os, 'getloadavg'):
            load_average = list(os.getloadavg())

        metrics = SystemMetrics(
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_used=memory.used,
            memory_available=memory.available,
            memory_total=memory.total,
            disk_usage=disk.percent,
            disk_used=disk.used,
            disk_free=disk.free,
            disk_total=disk.total,
            network_sent=network.bytes_sent,
            network_recv=network.bytes_recv,
            process_count=process_count,
            load_average=load_average
        )

        self.metrics_history.append(metrics)

        return metrics

    def get_current_metrics(self) -> SystemMetrics:
        """获取当前指标"""
        if not self.metrics_history:
            return self.collect_metrics()
        return self.metrics_history[-1]

    def get_average_metrics(self, duration: int = 300) -> Optional[Dict[str, float]]:
        """
        获取指定时间内的平均指标

        Args:
            duration: 时间范围（秒）

        Returns:
            平均指标
        """
        cutoff_time = datetime.now() - timedelta(seconds=duration)
        relevant_metrics = [
            m for m in self.metrics_history
            if m.timestamp >= cutoff_time
        ]

        if not relevant_metrics:
            return None

        return {
            'cpu_percent': sum(m.cpu_percent for m in relevant_metrics) / len(relevant_metrics),
            'memory_percent': sum(m.memory_percent for m in relevant_metrics) / len(relevant_metrics),
            'disk_usage': sum(m.disk_usage for m in relevant_metrics) / len(relevant_metrics),
            'process_count': sum(m.process_count for m in relevant_metrics) / len(relevant_metrics)
        }

    def get_trend(self, metric: str, duration: int = 300) -> Optional[str]:
        """
        获取指标趋势

        Args:
            metric: 指标名称
            duration: 时间范围（秒）

        Returns:
            趋势（up, down, stable）
        """
        cutoff_time = datetime.now() - timedelta(seconds=duration)
        relevant_metrics = [
            m for m in self.metrics_history
            if m.timestamp >= cutoff_time
        ]

        if len(relevant_metrics) < 2:
            return 'stable'

        first = getattr(relevant_metrics[0], metric)
        last = getattr(relevant_metrics[-1], metric)

        change_percent = ((last - first) / first) * 100 if first != 0 else 0

        if change_percent > 5:
            return 'up'
        elif change_percent < -5:
            return 'down'
        else:
            return 'stable'

    def get_processes(self, limit: int = 10, sort_by: str = 'cpu') -> List[ProcessInfo]:
        """
        获取进程列表

        Args:
            limit: 返回数量限制
            sort_by: 排序字段（cpu, memory, name）

        Returns:
            进程信息列表
        """
        processes = []

        for proc in psutil.process_iter(['pid', 'name', 'status', 'cpu_percent', 'memory_percent', 'num_threads', 'create_time']):
            try:
                proc_info = proc.info
                p = psutil.Process(proc_info['pid'])

                processes.append(ProcessInfo(
                    pid=proc_info['pid'],
                    name=proc_info['name'],
                    status=proc_info['status'],
                    cpu_percent=proc_info['cpu_percent'],
                    memory_percent=proc_info['memory_percent'],
                    memory_used=p.memory_info().rss,
                    num_threads=proc_info['num_threads'],
                    create_time=proc_info['create_time'],
                    exe=p.exe(),
                    cmd_line=p.cmdline()
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # 排序
        if sort_by == 'cpu':
            processes.sort(key=lambda p: p.cpu_percent, reverse=True)
        elif sort_by == 'memory':
            processes.sort(key=lambda p: p.memory_percent, reverse=True)
        elif sort_by == 'name':
            processes.sort(key=lambda p: p.name)

        return processes[:limit]

    def get_process_by_name(self, name: str) -> List[ProcessInfo]:
        """
        根据名称获取进程

        Args:
            name: 进程名称

        Returns:
            进程列表
        """
        all_processes = self.get_processes(limit=1000)
        return [p for p in all_processes if name.lower() in p.name.lower()]

    def get_process_by_pid(self, pid: int) -> Optional[ProcessInfo]:
        """
        根据PID获取进程

        Args:
            pid: 进程ID

        Returns:
            进程信息
        """
        try:
            proc = psutil.Process(pid)
            return ProcessInfo(
                pid=proc.pid,
                name=proc.name(),
                status=proc.status(),
                cpu_percent=proc.cpu_percent(),
                memory_percent=proc.memory_percent(),
                memory_used=proc.memory_info().rss,
                num_threads=proc.num_threads(),
                create_time=proc.create_time(),
                exe=proc.exe(),
                cmd_line=proc.cmdline()
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    def kill_process(self, pid: int) -> bool:
        """
        终止进程

        Args:
            pid: 进程ID

        Returns:
            是否成功
        """
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            logger.info(f"已终止进程: {pid}")
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.error(f"终止进程失败: {e}")
            return False

    def get_system_info(self) -> Dict[str, Any]:
        """
        获取系统信息

        Returns:
            系统信息字典
        """
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time

        return {
            'platform': platform.platform(),
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'hostname': platform.node(),
            'python_version': platform.python_version(),
            'boot_time': boot_time.isoformat(),
            'uptime_seconds': uptime.total_seconds()
        }

    def get_network_connections(self) -> List[Dict[str, Any]]:
        """
        获取网络连接

        Returns:
            连接列表
        """
        connections = []

        for conn in psutil.net_connections():
            try:
                connections.append({
                    'local_address': f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else 'N/A',
                    'remote_address': f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else 'N/A',
                    'status': conn.status,
                    'pid': conn.pid
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return connections[:50]  # 限制返回数量

    def get_disk_io(self) -> Dict[str, Any]:
        """
        获取磁盘IO统计

        Returns:
            磁盘IO信息
        """
        disk_io = psutil.disk_io_counters()
        return {
            'read_count': disk_io.read_count,
            'write_count': disk_io.write_count,
            'read_bytes': disk_io.read_bytes,
            'write_bytes': disk_io.write_bytes,
            'read_time': disk_io.read_time,
            'write_time': disk_io.write_time
        }

    def add_alert_rule(self, rule: AlertRule) -> None:
        """
        添加告警规则

        Args:
            rule: 告警规则
        """
        self.alert_rules.append(rule)
        logger.info(f"添加告警规则: {rule.name}")

    def check_alerts(self) -> List[Dict[str, Any]]:
        """
        检查告警规则

        Returns:
            触发的告警列表
        """
        metrics = self.get_current_metrics()
        triggered_alerts = []

        for rule in self.alert_rules:
            if not rule.enabled:
                continue

            # 获取指标值
            metric_value = getattr(metrics, rule.metric, None)
            if metric_value is None:
                continue

            # 检查条件
            triggered = False
            if rule.operator == '>':
                triggered = metric_value > rule.threshold
            elif rule.operator == '<':
                triggered = metric_value < rule.threshold
            elif rule.operator == '>=':
                triggered = metric_value >= rule.threshold
            elif rule.operator == '<=':
                triggered = metric_value <= rule.threshold
            elif rule.operator == '==':
                triggered = metric_value == rule.threshold

            # 更新告警状态
            if triggered:
                if rule.name not in self.alert_states:
                    self.alert_states[rule.name] = {
                        'first_triggered': datetime.now(),
                        'triggered_count': 0
                    }

                self.alert_states[rule.name]['triggered_count'] += 1
                state = self.alert_states[rule.name]
                duration = (datetime.now() - state['first_triggered']).total_seconds()

                if duration >= rule.duration:
                    triggered_alerts.append({
                        'rule': rule.name,
                        'metric': rule.metric,
                        'current_value': metric_value,
                        'threshold': rule.threshold,
                        'duration': duration,
                        'action': rule.action
                    })
            else:
                if rule.name in self.alert_states:
                    del self.alert_states[rule.name]

        return triggered_alerts

    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        获取指标摘要

        Returns:
            指标摘要
        """
        current = self.get_current_metrics()
        return {
            'timestamp': current.timestamp.isoformat(),
            'cpu': {
                'current': current.cpu_percent,
                'trend': self.get_trend('cpu_percent')
            },
            'memory': {
                'current': current.memory_percent,
                'used_gb': current.memory_used / (1024 ** 3),
                'total_gb': current.memory_total / (1024 ** 3),
                'trend': self.get_trend('memory_percent')
            },
            'disk': {
                'current': current.disk_usage,
                'used_gb': current.disk_used / (1024 ** 3),
                'total_gb': current.disk_total / (1024 ** 3),
                'trend': self.get_trend('disk_usage')
            },
            'network': {
                'sent_gb': current.network_sent / (1024 ** 3),
                'recv_gb': current.network_recv / (1024 ** 3)
            },
            'processes': current.process_count
        }

    def export_metrics(self, output_path: str, format: str = 'json') -> None:
        """
        导出指标数据

        Args:
            output_path: 输出路径
            format: 输出格式（json, csv）
        """
        if format == 'json':
            data = [self._metrics_to_dict(m) for m in self.metrics_history]
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        elif format == 'csv':
            import csv
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                if self.metrics_history:
                    writer = csv.DictWriter(f, fieldnames=[
                        'timestamp', 'cpu_percent', 'memory_percent', 'disk_usage',
                        'process_count', 'network_sent', 'network_recv'
                    ])
                    writer.writeheader()
                    for m in self.metrics_history:
                        writer.writerow({
                            'timestamp': m.timestamp.isoformat(),
                            'cpu_percent': m.cpu_percent,
                            'memory_percent': m.memory_percent,
                            'disk_usage': m.disk_usage,
                            'process_count': m.process_count,
                            'network_sent': m.network_sent,
                            'network_recv': m.network_recv
                        })

        logger.info(f"指标已导出到: {output_path}")

    def _metrics_to_dict(self, metrics: SystemMetrics) -> Dict[str, Any]:
        """将指标转换为字典"""
        return {
            'timestamp': metrics.timestamp.isoformat(),
            'cpu_percent': metrics.cpu_percent,
            'memory_percent': metrics.memory_percent,
            'memory_used': metrics.memory_used,
            'memory_available': metrics.memory_available,
            'memory_total': metrics.memory_total,
            'disk_usage': metrics.disk_usage,
            'disk_used': metrics.disk_used,
            'disk_free': metrics.disk_free,
            'disk_total': metrics.disk_total,
            'network_sent': metrics.network_sent,
            'network_recv': metrics.network_recv,
            'process_count': metrics.process_count
        }


class ProcessMonitor:
    """进程监控器"""

    def __init__(self, process_name: str):
        """
        初始化进程监控

        Args:
            process_name: 进程名称
        """
        self.process_name = process_name
        self.history: deque = deque(maxlen=100)

    def monitor(self, interval: int = 60) -> None:
        """
        持续监控进程

        Args:
            interval: 监控间隔（秒）
        """
        import time

        while True:
            processes = self._get_process_info()
            for proc in processes:
                self.history.append(proc)
            time.sleep(interval)

    def _get_process_info(self) -> List[Dict]:
        """获取进程信息"""
        processes = []

        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                if self.process_name.lower() in proc.info['name'].lower():
                    processes.append({
                        'timestamp': datetime.now().isoformat(),
                        'pid': proc.info['pid'],
                        'cpu_percent': proc.info['cpu_percent'],
                        'memory_percent': proc.info['memory_percent']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return processes

    def get_average_cpu(self, duration: int = 300) -> float:
        """获取平均CPU使用率"""
        cutoff_time = datetime.now() - timedelta(seconds=duration)
        relevant = [
            p for p in self.history
            if datetime.fromisoformat(p['timestamp']) >= cutoff_time
        ]

        if not relevant:
            return 0.0

        return sum(p['cpu_percent'] for p in relevant) / len(relevant)

    def get_average_memory(self, duration: int = 300) -> float:
        """获取平均内存使用率"""
        cutoff_time = datetime.now() - timedelta(seconds=duration)
        relevant = [
            p for p in self.history
            if datetime.fromisoformat(p['timestamp']) >= cutoff_time
        ]

        if not relevant:
            return 0.0

        return sum(p['memory_percent'] for p in relevant) / len(relevant)


# 便捷函数
def quick_monitor(duration: int = 60) -> Dict[str, Any]:
    """
    快速监控

    Args:
        duration: 监控时长（秒）

    Returns:
        监控结果
    """
    monitor = SystemMonitor()

    import time
    end_time = time.time() + duration

    while time.time() < end_time:
        monitor.collect_metrics()
        time.sleep(1)

    return {
        'summary': monitor.get_metrics_summary(),
        'trends': {
            'cpu': monitor.get_trend('cpu_percent'),
            'memory': monitor.get_trend('memory_percent'),
            'disk': monitor.get_trend('disk_usage')
        }
    }


if __name__ == "__main__":
    # 示例使用
    monitor = SystemMonitor()

    # 收集指标
    metrics = monitor.collect_metrics()
    print(f"CPU: {metrics.cpu_percent}%")
    print(f"内存: {metrics.memory_percent}%")
    print(f"磁盘: {metrics.disk_usage}%")

    # 获取摘要
    summary = monitor.get_metrics_summary()
    print("\n系统摘要:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    # 添加告警规则
    monitor.add_alert_rule(AlertRule(
        name="CPU高告警",
        metric="cpu_percent",
        threshold=80.0,
        operator=">"
    ))

    # 检查告警
    alerts = monitor.check_alerts()
    print(f"\n告警: {alerts}")
