"""
工具监控和统计模块
提供工具级别的监控、统计和诊断能力
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict
import logging
import json
from core.constants import Encoding


logger = logging.getLogger(__name__)


@dataclass
class ToolStatistics:
    """工具统计信息"""
    tool_name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    avg_response_time: float = 0.0
    success_rate: float = 1.0
    health_state: str = "healthy"

    def to_dict(self) -> dict:
        return {
            'tool_name': self.tool_name,
            'total_calls': self.total_calls,
            'successful_calls': self.successful_calls,
            'failed_calls': self.failed_calls,
            'avg_response_time': f"{self.avg_response_time:.3f}s",
            'success_rate': f"{self.success_rate:.2%}",
            'health_state': self.health_state,
        }


class ToolMonitor:
    """
    工具监控器

    职责：
    1. 监控所有工具的运行状态
    2. 收集统计信息
    3. 提供诊断报告
    4. 预警和告警
    """

    def __init__(self, tool_registry):
        self.tool_registry = tool_registry
        self.alert_threshold = 0.3  # 失败率告警阈值
        self.critical_threshold = 0.5  # 失败率严重阈值

        # 历史记录
        self.history: List[Dict] = []
        self.max_history_size = 1000

    def get_all_statistics(self) -> List[ToolStatistics]:
        """
        获取所有工具的统计信息

        Returns:
            工具统计列表
        """
        statistics = []
        all_health = self.tool_registry.get_all_tools_health()

        for tool_name, health_info in all_health.items():
            metrics = health_info.get('metrics', {})
            stats = ToolStatistics(
                tool_name=tool_name,
                total_calls=metrics.get('total_calls', 0),
                successful_calls=metrics.get('successful_calls', 0),
                failed_calls=metrics.get('failed_calls', 0),
                success_rate=metrics.get('successful_calls', 0) / max(metrics.get('total_calls', 1), 1),
                health_state=health_info.get('health_state', 'healthy')
            )
            statistics.append(stats)

        return statistics

    def get_problematic_tools(self, failure_rate_threshold: float = 0.3) -> List[ToolStatistics]:
        """
        获取有问题的工具

        Args:
            failure_rate_threshold: 失败率阈值

        Returns:
            问题工具列表
        """
        return [
            stats for stats in self.get_all_statistics()
            if stats.total_calls > 0 and stats.success_rate < (1.0 - failure_rate_threshold)
        ]

    def get_broken_tools(self) -> List[str]:
        """获取已熔断的工具"""
        all_health = self.tool_registry.get_all_tools_health()
        return [
            tool_name
            for tool_name, health_info in all_health.items()
            if health_info.get('health_state') == 'broken'
        ]

    def get_health_summary(self) -> Dict[str, Any]:
        """
        获取健康摘要

        Returns:
            健康摘要字典
        """
        statistics = self.get_all_statistics()
        broken_tools = self.get_broken_tools()

        healthy_count = sum(1 for s in statistics if s.health_state == 'healthy')
        degraded_count = sum(1 for s in statistics if s.health_state == 'degraded')
        unstable_count = sum(1 for s in statistics if s.health_state == 'unstable')
        broken_count = len(broken_tools)

        total_calls = sum(s.total_calls for s in statistics)
        total_successful = sum(s.successful_calls for s in statistics)
        overall_success_rate = total_successful / max(total_calls, 1)

        return {
            'total_tools': len(statistics),
            'healthy_tools': healthy_count,
            'degraded_tools': degraded_count,
            'unstable_tools': unstable_count,
            'broken_tools': broken_count,
            'broken_tool_names': broken_tools,
            'total_calls': total_calls,
            'total_successful': total_successful,
            'total_failed': total_calls - total_successful,
            'overall_success_rate': f"{overall_success_rate:.2%}",
        }

    def generate_report(self) -> str:
        """
        生成监控报告

        Returns:
            报告字符串
        """
        summary = self.get_health_summary()
        problematic = self.get_problematic_tools()

        report = "📊 工具监控报告\n"
        report += "=" * 50 + "\n\n"

        # 健康摘要
        report += "🏥 健康状态:\n"
        report += f"  总工具数: {summary['total_tools']}\n"
        report += f"  健康: {summary['healthy_tools']} ✅\n"
        report += f"  降级: {summary['degraded_tools']} ⚠️\n"
        report += f"  不稳定: {summary['unstable_tools']} ⚡\n"
        report += f"  损坏: {summary['broken_tools']} ❌\n\n"

        # 调用统计
        report += "📈 调用统计:\n"
        report += f"  总调用次数: {summary['total_calls']}\n"
        report += f"  成功: {summary['total_successful']} ✅\n"
        report += f"  失败: {summary['total_failed']} ❌\n"
        report += f"  整体成功率: {summary['overall_success_rate']}\n\n"

        # 损坏的工具
        if summary['broken_tool_names']:
            report += "🚨 已熔断工具:\n"
            for tool_name in summary['broken_tool_names']:
                report += f"  • {tool_name}\n"
            report += "\n"

        # 有问题的工具
        if problematic:
            report += "⚠️ 问题工具:\n"
            for stats in problematic:
                report += f"  • {stats.tool_name}: "
                report += f"成功率 {stats.success_rate:.2%}, "
                report += f"调用 {stats.total_calls} 次\n"
            report += "\n"

        # 时间戳
        report += f"🕐 报告时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

        return report

    def diagnose_tool(self, tool_name: str) -> Optional[Dict]:
        """
        诊断工具

        Args:
            tool_name: 工具名称

        Returns:
            诊断信息
        """
        health = self.tool_registry.get_tool_health(tool_name)
        if not health:
            return None

        diagnosis = {
            'tool_name': tool_name,
            'health': health,
            'recommendation': self._get_recommendation(health),
        }

        return diagnosis

    def _get_recommendation(self, health: Dict) -> str:
        """获取建议"""
        health_state = health.get('health_state')

        recommendations = {
            'healthy': "工具运行正常，无需操作",
            'degraded': "工具偶尔失败，建议检查外部依赖",
            'unstable': "工具频繁失败，建议检查日志和配置",
            'broken': "工具已熔断，请检查错误信息后重置",
        }

        return recommendations.get(health_state, "未知状态")

    def save_history(self):
        """保存历史记录"""
        summary = self.get_health_summary()
        summary['timestamp'] = datetime.now().isoformat()

        self.history.append(summary)

        # 限制历史记录大小
        if len(self.history) > self.max_history_size:
            self.history = self.history[-self.max_history_size:]

    def export_report(self, filepath: str):
        """
        导出报告到文件

        Args:
            filepath: 文件路径
        """
        report = self.generate_report()
        try:
            with open(filepath, 'w', encoding=Encoding.UTF8) as f:
                f.write(report)
            logger.info(f"[ToolMonitor] 报告已导出到: {filepath}")
        except Exception as e:
            logger.error(f"[ToolMonitor] 导出报告失败: {e}")

    def export_health_json(self, filepath: str):
        """
        导出健康状态为JSON

        Args:
            filepath: 文件路径
        """
        data = {
            'summary': self.get_health_summary(),
            'tools': self.tool_registry.get_all_tools_health(),
            'exported_at': datetime.now().isoformat(),
        }

        try:
            with open(filepath, 'w', encoding=Encoding.UTF8) as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"[ToolMonitor] 健康数据已导出到: {filepath}")
        except Exception as e:
            logger.error(f"[ToolMonitor] 导出JSON失败: {e}")


def get_tool_monitor(tool_registry) -> ToolMonitor:
    """获取工具监控器"""
    return ToolMonitor(tool_registry)
