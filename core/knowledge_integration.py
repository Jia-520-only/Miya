"""
知识集成模块
第四阶段核心模块 - 将记忆、模式学习与自主决策引擎集成
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from core.system_memory import SystemMemory, get_system_memory, MemoryType
from core.pattern_learner import PatternLearner, get_pattern_learner, PatternMatch
from core.autonomous_engine import AutonomousEngine, get_autonomous_engine
from core.problem_scanner import Problem


logger = logging.getLogger(__name__)


class KnowledgeIntegration:
    """知识集成器"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.memory = get_system_memory()
        self.learner = get_pattern_learner()
        self.engine = get_autonomous_engine()

        # 集成统计
        self.stats = {
            'decisions_enhanced': 0,
            'patterns_found': 0,
            'memories_accessed': 0,
            'best_practices_applied': 0,
        }

    def enhance_decision(
        self,
        problem: Problem,
        fix_suggestion: str
    ) -> Dict[str, Any]:
        """
        增强决策

        Args:
            problem: 问题对象
            fix_suggestion: 修复建议

        Returns:
            增强的决策信息
        """
        self.stats['decisions_enhanced'] += 1

        enhancement = {
            'original_decision': None,
            'pattern_matches': [],
            'historical_success_rate': 0.0,
            'recommended_action': fix_suggestion,
            'confidence_boost': 0.0,
            'additional_suggestions': [],
            'warnings': [],
        }

        # 1. 查找匹配的模式
        pattern_matches = self.learner.find_matching_patterns(
            problem_type=problem.type.value,
            severity=problem.severity.value,
            file_path=problem.file_path or '',
        )

        if pattern_matches:
            self.stats['patterns_found'] += len(pattern_matches)

            best_match = pattern_matches[0]
            enhancement['pattern_matches'] = [
                {
                    'pattern_key': m.pattern.pattern_key,
                    'similarity': m.similarity,
                    'confidence': m.confidence,
                    'recommendation': m.recommendation,
                }
                for m in pattern_matches[:3]
            ]

            # 使用最佳模式增强建议
            if best_match.similarity > 0.8 and best_match.confidence > 0.8:
                enhancement['recommended_action'] = best_match.pattern.features.get('fix_action_type', fix_suggestion)
                enhancement['confidence_boost'] = 0.2
                enhancement['historical_success_rate'] = best_match.pattern.success_rate

        # 2. 查询历史修复记录
        fix_history = self.memory.get_fix_history(
            problem_type=problem.type.value,
            file_path=problem.file_path,
            limit=5
        )

        if fix_history:
            self.stats['memories_accessed'] += 1

            # 计算历史成功率
            success_count = sum(1 for f in fix_history if f.success)
            historical_rate = success_count / len(fix_history) if fix_history else 0.0
            enhancement['historical_success_rate'] = max(
                enhancement['historical_success_rate'],
                historical_rate
            )

            # 检查是否有失败的记录
            failed_fixes = [f for f in fix_history if not f.success]
            if failed_fixes:
                enhancement['warnings'].append(
                    f"该问题类型之前有 {len(failed_fixes)} 次失败的修复尝试，请谨慎处理"
                )

        # 3. 查询最佳实践
        best_practice = self.memory.get_best_practice(
            context=f"{problem.type.value}:{problem.severity.value}"
        )

        if best_practice:
            self.stats['best_practices_applied'] += 1

            if 'suggested_fix' in best_practice:
                enhancement['additional_suggestions'].append(best_practice['suggested_fix'])

            if 'warnings' in best_practice:
                enhancement['warnings'].extend(best_practice['warnings'])

        # 4. 记录用户偏好
        user_pref = self.memory.get_user_preference('fix_style')
        if user_pref:
            enhancement['additional_suggestions'].append(
                f"根据用户偏好，建议采用 {user_pref} 风格的修复"
            )

        return enhancement

    def record_fix_outcome(
        self,
        problem: Problem,
        fix_action: str,
        success: bool,
        execution_time: float,
        backup_path: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        """
        记录修复结果

        Args:
            problem: 问题对象
            fix_action: 修复动作
            success: 是否成功
            execution_time: 执行时间
            backup_path: 备份路径
            error_message: 错误消息
        """
        # 记录到记忆系统
        self.memory.record_fix(
            problem_id=problem.id,
            problem_type=problem.type.value,
            severity=problem.severity.value,
            file_path=problem.file_path or '',
            fix_action=fix_action,
            success=success,
            execution_time=execution_time,
            backup_path=backup_path,
            error_message=error_message,
        )

        # 学习模式
        self.learner.learn_from_fix(
            problem_type=problem.type.value,
            severity=problem.severity.value,
            file_path=problem.file_path or '',
            fix_action=fix_action,
            success=success,
            execution_time=execution_time,
        )

        # 如果成功，更新最佳实践
        if success:
            self._update_best_practice(problem, fix_action, execution_time)

    def _update_best_practice(
        self,
        problem: Problem,
        fix_action: str,
        execution_time: float
    ):
        """更新最佳实践"""
        context = f"{problem.type.value}:{problem.severity.value}"

        # 获取现有最佳实践
        existing = self.memory.get_best_practice(context)

        if existing:
            # 检查是否更好
            if 'avg_time' in existing and execution_time < existing['avg_time']:
                # 更快的修复方式
                existing['suggested_fix'] = fix_action
                existing['avg_time'] = execution_time
                existing['success_count'] = existing.get('success_count', 0) + 1
        else:
            # 创建新的最佳实践
            self.memory.save_best_practice(
                context=context,
                practice={
                    'suggested_fix': fix_action,
                    'avg_time': execution_time,
                    'success_count': 1,
                    'warnings': [],
                },
                confidence=0.5  # 初始置信度较低
            )

    def get_recommended_fix(
        self,
        problem: Problem
    ) -> Optional[str]:
        """
        获取推荐修复方案

        Args:
            problem: 问题对象

        Returns:
            推荐的修复方案
        """
        # 查找匹配模式
        pattern_matches = self.learner.find_matching_patterns(
            problem_type=problem.type.value,
            severity=problem.severity.value,
            file_path=problem.file_path or '',
        )

        if not pattern_matches:
            return None

        # 返回最佳匹配的修复动作
        best_match = pattern_matches[0]

        if best_match.similarity > 0.8 and best_match.confidence > 0.8:
            return best_match.pattern.features.get('fix_action_type')

        return None

    def analyze_success_patterns(self) -> Dict[str, Any]:
        """
        分析成功模式

        Returns:
            分析结果
        """
        # 获取高成功率模式
        high_success_patterns = [
            p for p in self.learner.patterns.values()
            if p.success_rate >= 0.8 and p.total_occurrences >= 3
        ]

        analysis = {
            'total_high_success': len(high_success_patterns),
            'patterns_by_type': {},
            'most_successful': [],
            'fastest_fixes': [],
        }

        # 按类型分组
        for pattern in high_success_patterns:
            ptype = pattern.type.value
            if ptype not in analysis['patterns_by_type']:
                analysis['patterns_by_type'][ptype] = []

            analysis['patterns_by_type'][ptype].append({
                'pattern_key': pattern.pattern_key,
                'success_rate': pattern.success_rate,
                'occurrences': pattern.total_occurrences,
                'avg_time': pattern.metadata.get('avg_execution_time', 0),
            })

        # 最成功的模式
        analysis['most_successful'] = sorted(
            high_success_patterns,
            key=lambda p: p.success_rate,
            reverse=True
        )[:5]

        # 最快的修复
        with_time = [
            p for p in high_success_patterns
            if 'avg_execution_time' in p.metadata
        ]
        analysis['fastest_fixes'] = sorted(
            with_time,
            key=lambda p: p.metadata['avg_execution_time']
        )[:5]

        return analysis

    def generate_learning_report(self) -> str:
        """生成学习报告"""
        lines = [
            "知识集成与学习报告",
            "=" * 70,
            "",
            "集成统计:",
        ]

        for key, value in self.stats.items():
            lines.append(f"  {key}: {value}")

        # 模式分析
        pattern_analysis = self.learner.analyze_patterns()

        lines.extend([
            "",
            "模式分析:",
            f"  总模式数: {pattern_analysis['total_patterns']}",
            f"  高置信度模式: {pattern_analysis['high_confidence_patterns']}",
            f"  平均成功率: {pattern_analysis['avg_success_rate']:.1%}",
            f"  最高成功率: {pattern_analysis['max_success_rate']:.1%}",
        ])

        # 记忆统计
        memory_stats = self.memory.get_statistics()

        lines.extend([
            "",
            "记忆统计:",
            f"  总记忆: {memory_stats['total_memories']}",
            f"  修复历史: {memory_stats['total_fixes']}",
            f"  成功率: {memory_stats['success_rate']:.1%}",
        ])

        # 成功模式分析
        success_analysis = self.analyze_success_patterns()

        lines.extend([
            "",
            "高成功率模式:",
            f"  总数: {success_analysis['total_high_success']}",
        ])

        if success_analysis['most_successful']:
            lines.append("  最成功的模式:")
            for pattern in success_analysis['most_successful'][:3]:
                lines.append(
                    f"    - {pattern.pattern_key}: "
                    f"{pattern.success_rate:.1%} "
                    f"({pattern.total_occurrences} 次)"
                )

        return "\n".join(lines)

    def save_all(self):
        """保存所有数据"""
        self.memory.save()
        self.learner.save()
        self.logger.info("知识集成数据已保存")

    def load_all(self):
        """加载所有数据"""
        self.memory.load()
        self.learner.load()
        self.logger.info("知识集成数据已加载")

    def cleanup(self, days: int = 30):
        """
        清理旧数据

        Args:
            days: 天数
        """
        self.learner.forget_old_patterns(days)
        self.logger.info(f"已清理 {days} 天前的旧数据")


# 单例
_integration_instance: Optional[KnowledgeIntegration] = None


def get_knowledge_integration() -> KnowledgeIntegration:
    """获取知识集成器单例"""
    global _integration_instance
    if _integration_instance is None:
        _integration_instance = KnowledgeIntegration()
    return _integration_instance
