"""
KL散度监控器
监控在线训练过程中的KL散度，防止对齐崩溃
"""
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import numpy as np
from core.constants import Encoding

logger = logging.getLogger(__name__)


class KLAlertLevel(Enum):
    """KL警报级别"""
    NORMAL = "normal"           # 正常范围
    WARNING = "warning"         # 警告
    CRITICAL = "critical"        # 严重
    COLLAPSE = "collapse"        # 对齐崩溃


@dataclass
class KLSnapshot:
    """KL快照"""
    timestamp: float
    kl_divergence: float
    policy_entropy: float
    target_kl: float
    alert_level: KLAlertLevel


@dataclass
class KLMonitorConfig:
    """KL监控配置"""
    warning_threshold: float = 0.1      # 警告阈值
    critical_threshold: float = 0.2      # 严重阈值
    collapse_threshold: float = 0.3        # 崩溃阈值
    window_size: int = 100                # 监控窗口
    check_interval: int = 10               # 检查间隔（步数）


class KLDivergenceMonitor:
    """KL散度监控器"""

    def __init__(self, config: Optional[KLMonitorConfig] = None):
        self.config = config or KLMonitorConfig()

        # KL历史
        self.kl_history: List[float] = []

        # KL快照
        self.snapshots: List[KLSnapshot] = []

        # 警报历史
        self.alerts: List[Dict[str, Any]] = []

        # 统计信息
        self.stats = {
            'total_checks': 0,
            'warning_count': 0,
            'critical_count': 0,
            'collapse_count': 0,
            'avg_kl': 0.0,
            'max_kl': 0.0
        }

        # 上次检查步数
        self.last_check_step = 0

    def check_kl_divergence(
        self,
        current_kl: float,
        target_kl: float = 0.05,
        step: int = 0
    ) -> Tuple[KLAlertLevel, Dict[str, Any]]:
        """
        检查KL散度

        Args:
            current_kl: 当前KL散度
            target_kl: 目标KL散度
            step: 当前步数

        Returns:
            (警报级别, 详细信息）
        """
        # 记录KL
        self.kl_history.append(current_kl)
        self.stats['total_checks'] += 1

        # 更新统计
        self.stats['avg_kl'] = np.mean(self.kl_history)
        self.stats['max_kl'] = np.max(self.kl_history)

        # 判断警报级别
        alert_level = self._determine_alert_level(current_kl)

        # 更新警报计数
        if alert_level == KLAlertLevel.WARNING:
            self.stats['warning_count'] += 1
        elif alert_level == KLAlertLevel.CRITICAL:
            self.stats['critical_count'] += 1
        elif alert_level == KLAlertLevel.COLLAPSE:
            self.stats['collapse_count'] += 1

        # 创建快照
        snapshot = KLSnapshot(
            timestamp=time.time(),
            kl_divergence=current_kl,
            policy_entropy=self._estimate_entropy(),
            target_kl=target_kl,
            alert_level=alert_level
        )

        self.snapshots.append(snapshot)

        # 记录警报
        if alert_level != KLAlertLevel.NORMAL:
            self.alerts.append({
                'timestamp': time.time(),
                'step': step,
                'kl_divergence': current_kl,
                'alert_level': alert_level.value,
                'message': self._generate_alert_message(alert_level, current_kl)
            })

            logger.warning(
                f"[KLMonitor] KL散度警报: "
                f"{alert_level.value}, KL={current_kl:.4f}"
            )

        self.last_check_step = step

        return alert_level, self._get_diagnostics()

    def should_check(self, step: int) -> bool:
        """
        判断是否应该检查

        Args:
            step: 当前步数

        Returns:
            是否应该检查
        """
        return step % self.config.check_interval == 0

    def get_windowed_stats(self, window_size: Optional[int] = None) -> Dict[str, float]:
        """
        获取窗口统计

        Args:
            window_size: 窗口大小（可选，默认使用配置）

        Returns:
            统计信息
        """
        window_size = window_size or self.config.window_size
        recent_kls = self.kl_history[-window_size:]

        if not recent_kls:
            return {
                'mean': 0.0,
                'std': 0.0,
                'min': 0.0,
                'max': 0.0
            }

        return {
            'mean': float(np.mean(recent_kls)),
            'std': float(np.std(recent_kls)),
            'min': float(np.min(recent_kls)),
            'max': float(np.max(recent_kls)),
            'count': len(recent_kls),
            'trend': self._calculate_trend(recent_kls)
        }

    def is_kl_collapsed(self) -> bool:
        """
        判断KL是否已崩溃

        Returns:
            是否崩溃
        """
        if len(self.kl_history) < self.config.window_size:
            return False

        window_stats = self.get_windowed_stats()
        return window_stats['mean'] > self.config.collapse_threshold

    def recommend_action(self) -> Optional[str]:
        """
        推荐行动

        Returns:
            行动建议
        """
        if len(self.kl_history) < self.config.check_interval:
            return "积累更多数据后再判断"

        current_kl = self.kl_history[-1]
        alert_level = self._determine_alert_level(current_kl)

        if alert_level == KLAlertLevel.COLLAPSE:
            return "紧急：停止训练，降低学习率或检查奖励模型"

        elif alert_level == KLAlertLevel.CRITICAL:
            return "严重：考虑降低学习率或增加KL惩罚"

        elif alert_level == KLAlertLevel.WARNING:
            return "警告：监控KL散度趋势"

        else:
            return "正常：继续训练"

    def get_alert_report(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取警报报告

        Args:
            limit: 返回数量

        Returns:
            警报列表
        """
        return self.alerts[-limit:]

    def reset_monitor(self):
        """重置监控器"""
        self.kl_history = []
        self.snapshots = []
        self.alerts = []

        self.stats = {
            'total_checks': 0,
            'warning_count': 0,
            'critical_count': 0,
            'collapse_count': 0,
            'avg_kl': 0.0,
            'max_kl': 0.0
        }

        logger.info("[KLMonitor] 监控器已重置")

    def _determine_alert_level(self, kl_divergence: float) -> KLAlertLevel:
        """判断警报级别"""
        if kl_divergence >= self.config.collapse_threshold:
            return KLAlertLevel.COLLAPSE
        elif kl_divergence >= self.config.critical_threshold:
            return KLAlertLevel.CRITICAL
        elif kl_divergence >= self.config.warning_threshold:
            return KLAlertLevel.WARNING
        else:
            return KLAlertLevel.NORMAL

    def _estimate_entropy(self) -> float:
        """估计策略熵"""
        if len(self.kl_history) < 2:
            return 0.0

        # 基于KL历史估计熵
        recent_kls = self.kl_history[-self.config.window_size:]
        variance = np.var(recent_kls) if len(recent_kls) > 0 else 0.0

        # 熵与方差正相关
        return float(np.sqrt(variance))

    def _calculate_trend(self, values: List[float]) -> str:
        """计算趋势"""
        if len(values) < 3:
            return "stable"

        # 线性回归
        x = np.arange(len(values))
        y = np.array(values)

        slope = np.polyfit(x, y, 1)[0]

        if slope > 0.01:
            return "increasing"
        elif slope < -0.01:
            return "decreasing"
        else:
            return "stable"

    def _generate_alert_message(
        self,
        alert_level: KLAlertLevel,
        kl_divergence: float
    ) -> str:
        """生成警报消息"""
        messages = {
            KLAlertLevel.NORMAL: f"KL散度正常: {kl_divergence:.4f}",
            KLAlertLevel.WARNING: f"KL散度警告: {kl_divergence:.4f} (阈值: {self.config.warning_threshold})",
            KLAlertLevel.CRITICAL: f"KL散度严重: {kl_divergence:.4f} (阈值: {self.config.critical_threshold})",
            KLAlertLevel.COLLAPSE: f"KL散度崩溃: {kl_divergence:.4f} (阈值: {self.config.collapse_threshold})"
        }

        return messages.get(alert_level, "")

    def _get_diagnostics(self) -> Dict[str, Any]:
        """获取诊断信息"""
        window_stats = self.get_windowed_stats()

        return {
            'current_kl': self.kl_history[-1] if self.kl_history else 0.0,
            'window_stats': window_stats,
            'alert_count': {
                'warning': self.stats['warning_count'],
                'critical': self.stats['critical_count'],
                'collapse': self.stats['collapse_count']
            },
            'recommendation': self.recommend_action()
        }

    def save_state(self, filepath: Optional[str] = None):
        """保存状态到磁盘"""
        if filepath is None:
            filepath = "data/kl_monitor_state.json"

        data = {
            'config': {
                'warning_threshold': self.config.warning_threshold,
                'critical_threshold': self.config.critical_threshold,
                'collapse_threshold': self.config.collapse_threshold
            },
            'kl_history': self.kl_history,
            'snapshots': [
                {
                    'timestamp': s.timestamp,
                    'kl_divergence': s.kl_divergence,
                    'policy_entropy': s.policy_entropy,
                    'target_kl': s.target_kl,
                    'alert_level': s.alert_level.value
                }
                for s in self.snapshots[-100:]  # 只保留最近100个
            ],
            'alerts': self.alerts[-50:],  # 只保留最近50个
            'statistics': self.stats,
            'saved_at': time.time()
        }

        with open(filepath, 'w', encoding=Encoding.UTF8) as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info("[KLMonitor] 保存状态成功")

    def load_state(self, filepath: Optional[str] = None) -> bool:
        """从磁盘加载状态"""
        if filepath is None:
            filepath = "data/kl_monitor_state.json"

        try:
            with open(filepath, 'r', encoding=Encoding.UTF8) as f:
                data = json.load(f)

            config_data = data.get('config', {})
            self.config = KLMonitorConfig(
                warning_threshold=config_data.get('warning_threshold', 0.1),
                critical_threshold=config_data.get('critical_threshold', 0.2),
                collapse_threshold=config_data.get('collapse_threshold', 0.3)
            )

            self.kl_history = data.get('kl_history', [])

            self.snapshots = []
            for s_data in data.get('snapshots', []):
                self.snapshots.append(KLSnapshot(
                    timestamp=s_data['timestamp'],
                    kl_divergence=s_data['kl_divergence'],
                    policy_entropy=s_data['policy_entropy'],
                    target_kl=s_data['target_kl'],
                    alert_level=KLAlertLevel(s_data['alert_level'])
                ))

            self.alerts = data.get('alerts', [])
            self.stats = data.get('statistics', {})

            logger.info("[KLMonitor] 加载状态成功")
            return True

        except Exception as e:
            logger.error(f"[KLMonitor] 加载状态失败: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_checks': self.stats['total_checks'],
            'warning_count': self.stats['warning_count'],
            'critical_count': self.stats['critical_count'],
            'collapse_count': self.stats['collapse_count'],
            'avg_kl': self.stats['avg_kl'],
            'max_kl': self.stats['max_kl'],
            'current_kl': self.kl_history[-1] if self.kl_history else 0.0,
            'window_stats': self.get_windowed_stats(),
            'recommendation': self.recommend_action()
        }
