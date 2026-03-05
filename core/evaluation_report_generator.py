"""
评估报告生成器
生成弥娅系统的评估报告
"""
import json
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
from core.constants import Encoding


@dataclass
class EvaluationReport:
    """评估报告"""
    report_id: str
    timestamp: float
    personality_evaluation: Optional[Dict] = None
    memory_evaluation: Optional[Dict] = None
    moral_evaluation: Optional[Dict] = None
    fact_evaluation: Optional[Dict] = None
    overall_score: float = 0.0
    recommendations: List[str] = field(default_factory=list)
    statistics: Dict = field(default_factory=dict)


class EvaluationReportGenerator:
    """评估报告生成器"""

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def generate_report(
        self,
        personality_eval: Optional[Dict] = None,
        memory_eval: Optional[Dict] = None,
        moral_eval: Optional[Dict] = None,
        fact_eval: Optional[Dict] = None,
        statistics: Optional[Dict] = None
    ) -> EvaluationReport:
        """
        生成评估报告

        Args:
            personality_eval: 人格评估结果
            memory_eval: 记忆评估结果
            moral_eval: 道德评估结果
            fact_eval: 事实评估结果
            statistics: 统计信息

        Returns:
            评估报告
        """
        report = EvaluationReport(
            report_id=self._generate_report_id(),
            timestamp=time.time(),
            personality_evaluation=personality_eval,
            memory_evaluation=memory_eval,
            moral_evaluation=moral_eval,
            fact_evaluation=fact_eval,
            statistics=statistics or {}
        )

        # 计算总体分数
        report.overall_score = self._calculate_overall_score(report)

        # 生成建议
        report.recommendations = self._generate_recommendations(report)

        return report

    def save_report(self, report: EvaluationReport, filename: Optional[str] = None) -> str:
        """
        保存报告到文件

        Args:
            report: 评估报告
            filename: 文件名（可选）

        Returns:
            保存的文件路径
        """
        if filename is None:
            filename = f"evaluation_report_{report.report_id}.json"

        filepath = self.output_dir / filename

        report_dict = {
            'report_id': report.report_id,
            'timestamp': report.timestamp,
            'personality_evaluation': report.personality_evaluation,
            'memory_evaluation': report.memory_evaluation,
            'moral_evaluation': report.moral_evaluation,
            'fact_evaluation': report.fact_evaluation,
            'overall_score': report.overall_score,
            'recommendations': report.recommendations,
            'statistics': report.statistics
        }

        with open(filepath, 'w', encoding=Encoding.UTF8) as f:
            json.dump(report_dict, f, indent=2, ensure_ascii=False)

        return str(filepath)

    def generate_markdown_report(self, report: EvaluationReport) -> str:
        """
        生成Markdown格式的报告

        Args:
            report: 评估报告

        Returns:
            Markdown文本
        """
        lines = []
        lines.append("# 弥娅系统评估报告")
        lines.append("")
        lines.append(f"**报告ID**: {report.report_id}")
        lines.append(f"**生成时间**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(report.timestamp))}")
        lines.append(f"**总体分数**: {report.overall_score:.2f}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # 人格评估
        if report.personality_evaluation:
            lines.append("## 人格评估")
            lines.append("")
            lines.append(f"- **稳定性**: {report.personality_evaluation.get('stability', 'N/A')}")
            lines.append(f"- **一致性**: {report.personality_evaluation.get('consistency', 'N/A')}")
            lines.append(f"- **形态匹配**: {report.personality_evaluation.get('form_match', 'N/A')}")
            lines.append("")

        # 记忆评估
        if report.memory_evaluation:
            lines.append("## 记忆评估")
            lines.append("")
            lines.append(f"- **压缩效率**: {report.memory_evaluation.get('compression_ratio', 'N/A')}")
            lines.append(f"- **保留率**: {report.memory_evaluation.get('retention_rate', 'N/A')}")
            lines.append(f"- **回放次数**: {report.memory_evaluation.get('replay_count', 'N/A')}")
            lines.append("")

        # 道德评估
        if report.moral_evaluation:
            lines.append("## 道德对齐评估")
            lines.append("")
            lines.append(f"- **对齐分数**: {report.moral_evaluation.get('alignment_score', 'N/A')}")
            lines.append(f"- **是否符合**: {'是' if report.moral_evaluation.get('is_aligned', False) else '否'}")
            lines.append("")

            if report.moral_evaluation.get('issues'):
                lines.append("### 发现的问题")
                for issue in report.moral_evaluation['issues']:
                    lines.append(f"- {issue}")
                lines.append("")

        # 事实评估
        if report.fact_evaluation:
            lines.append("## 事实一致性评估")
            lines.append("")
            lines.append(f"- **是否一致**: {'是' if report.fact_evaluation.get('valid', True) else '否'}")
            lines.append(f"- **原因**: {report.fact_evaluation.get('reason', 'N/A')}")
            lines.append("")

        # 建议
        if report.recommendations:
            lines.append("## 改进建议")
            lines.append("")
            for i, rec in enumerate(report.recommendations, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")

        # 统计信息
        if report.statistics:
            lines.append("## 统计信息")
            lines.append("")
            for key, value in report.statistics.items():
                lines.append(f"- **{key}**: {value}")
            lines.append("")

        return "\n".join(lines)

    def _generate_report_id(self) -> str:
        """生成报告ID"""
        return f"eval_{int(time.time())}"

    def _calculate_overall_score(self, report: EvaluationReport) -> float:
        """计算总体分数"""
        scores = []

        if report.personality_evaluation:
            stability = report.personality_evaluation.get('stability', 0.5)
            consistency = report.personality_evaluation.get('consistency', 0.5)
            scores.append((stability + consistency) / 2)

        if report.memory_evaluation:
            scores.append(report.memory_evaluation.get('compression_ratio', 0.5))

        if report.moral_evaluation:
            scores.append(report.moral_evaluation.get('alignment_score', 0.5))

        if report.fact_evaluation:
            scores.append(1.0 if report.fact_evaluation.get('valid', True) else 0.0)

        if not scores:
            return 0.5

        return round(sum(scores) / len(scores), 3)

    def _generate_recommendations(self, report: EvaluationReport) -> List[str]:
        """生成改进建议"""
        recommendations = []

        # 人格建议
        if report.personality_evaluation:
            stability = report.personality_evaluation.get('stability', 1.0)
            consistency = report.personality_evaluation.get('consistency', 1.0)

            if stability < 0.7:
                recommendations.append("人格稳定性偏低，建议加强人格基底约束")

            if consistency < 0.7:
                recommendations.append("人格一致性不足，建议启用人格一致性保障器")

        # 记忆建议
        if report.memory_evaluation:
            retention = report.memory_evaluation.get('retention_rate', 1.0)
            if retention < 0.7:
                recommendations.append("记忆保留率偏低，建议调整记忆压缩阈值")

        # 道德建议
        if report.moral_evaluation:
            if not report.moral_evaluation.get('is_aligned', True):
                recommendations.append("道德对齐检查未通过，建议调整响应生成策略")

        # 总体建议
        if report.overall_score < 0.6:
            recommendations.append("总体评分偏低，建议进行全面系统优化")
        elif report.overall_score < 0.8:
            recommendations.append("系统表现良好，可继续优化细节")

        return recommendations

    def load_report(self, filepath: str) -> Optional[EvaluationReport]:
        """
        从文件加载报告

        Args:
            filepath: 报告文件路径

        Returns:
            评估报告
        """
        try:
            with open(filepath, 'r', encoding=Encoding.UTF8) as f:
                data = json.load(f)

            return EvaluationReport(
                report_id=data['report_id'],
                timestamp=data['timestamp'],
                personality_evaluation=data.get('personality_evaluation'),
                memory_evaluation=data.get('memory_evaluation'),
                moral_evaluation=data.get('moral_evaluation'),
                fact_evaluation=data.get('fact_evaluation'),
                overall_score=data.get('overall_score', 0.0),
                recommendations=data.get('recommendations', []),
                statistics=data.get('statistics', {})
            )
        except Exception as e:
            print(f"[Report] 加载报告失败: {e}")
            return None
