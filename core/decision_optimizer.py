"""
决策优化器
优化决策策略，学习最佳实践
"""
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
import json
from pathlib import Path

from core.autonomous_engine import AutonomousEngine, Decision, RiskLevel, DecisionType


logger = logging.getLogger(__name__)


class OptimizationStrategy(Enum):
    """优化策略"""
    CONSERVATIVE = "conservative"  # 保守，减少自动执行
    BALANCED = "balanced"          # 平衡
    AGGRESSIVE = "aggressive"      # 激进，增加自动执行


@dataclass
class DecisionPattern:
    """决策模式"""
    pattern_id: str
    problem_type: str
    severity: str
    file_pattern: str
    success_rate: float
    total_decisions: int
    successful_decisions: int
    recommended_action: DecisionType
    confidence: float
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class OptimizationReport:
    """优化报告"""
    timestamp: datetime
    strategy: OptimizationStrategy
    patterns_analyzed: int
    recommendations: List[str]
    risk_adjustments: Dict[str, Any]
    performance_metrics: Dict[str, Any]


class DecisionOptimizer:
    """决策优化器"""
    
    def __init__(self, engine: AutonomousEngine):
        self.logger = logging.getLogger(__name__)
        self.engine = engine
        
        # 决策模式库
        self.patterns: List[DecisionPattern] = []
        
        # 策略配置
        self.current_strategy = OptimizationStrategy.BALANCED
        self.min_confidence_threshold = 0.7
        self.min_decisions_for_pattern = 3
        
        # 性能指标
        self.metrics = {
            'total_patterns': 0,
            'high_confidence_patterns': 0,
            'optimization_cycles': 0,
            'last_optimization': None,
        }
        
        # 优化历史
        self.optimization_history: List[OptimizationReport] = []
        
        # 加载历史模式
        self.load_patterns()
    
    def analyze_decisions(self) -> List[DecisionPattern]:
        """
        分析历史决策，提取模式
        
        Returns:
            决策模式列表
        """
        self.logger.info("开始分析历史决策...")
        
        # 按问题类型和严重程度分组
        groups = defaultdict(list)
        
        for decision in self.engine.decisions:
            # 获取问题信息
            problem = None
            for p in self.engine.problem_scanner.all_problems:
                if p.id == decision.problem_id:
                    problem = p
                    break
            
            if not problem:
                continue
            
            # 创建分组键
            file_pattern = self._extract_file_pattern(problem.file_path)
            key = (problem.problem_type, problem.severity, file_pattern)
            groups[key].append(decision)
        
        # 分析每个组
        patterns = []
        
        for (problem_type, severity, file_pattern), decisions in groups.items():
            if len(decisions) < self.min_decisions_for_pattern:
                continue
            
            # 计算成功率
            successful = sum(1 for d in decisions if d.result == 'success')
            success_rate = successful / len(decisions)
            
            # 推荐操作
            if success_rate >= 0.9:
                recommended_action = DecisionType.AUTO_FIX
                confidence = success_rate
            elif success_rate >= 0.7:
                recommended_action = DecisionType.AUTO_FIX
                confidence = success_rate * 0.9
            else:
                recommended_action = DecisionType.MANUAL_REVIEW
                confidence = 1.0 - success_rate
            
            pattern = DecisionPattern(
                pattern_id=f"{problem_type}_{severity}_{file_pattern}_{len(decisions)}",
                problem_type=problem_type,
                severity=severity,
                file_pattern=file_pattern,
                success_rate=success_rate,
                total_decisions=len(decisions),
                successful_decisions=successful,
                recommended_action=recommended_action,
                confidence=confidence,
            )
            patterns.append(pattern)
        
        self.patterns = patterns
        self.metrics['total_patterns'] = len(patterns)
        self.metrics['high_confidence_patterns'] = sum(1 for p in patterns if p.confidence >= self.min_confidence_threshold)
        
        self.logger.info(f"分析完成，发现 {len(patterns)} 个决策模式")
        return patterns
    
    def _extract_file_pattern(self, file_path: Optional[str]) -> str:
        """提取文件模式"""
        if not file_path:
            return "unknown"
        
        path = Path(file_path)
        
        # 获取扩展名
        ext = path.suffix if path.suffix else "no_ext"
        
        # 获取目录
        if len(path.parts) > 1:
            dir_name = path.parts[-2]
        else:
            dir_name = "root"
        
        return f"{dir_name}/*{ext}"
    
    def optimize_strategy(self) -> OptimizationReport:
        """
        优化决策策略
        
        Returns:
            优化报告
        """
        self.logger.info("开始优化决策策略...")
        
        # 分析决策
        patterns = self.analyze_decisions()
        
        # 生成建议
        recommendations = []
        risk_adjustments = {}
        
        # 分析成功率
        if not patterns:
            recommendations.append("没有足够的决策数据进行优化")
            recommendations.append("继续收集决策数据")
        else:
            avg_success_rate = sum(p.success_rate for p in patterns) / len(patterns)
            
            # 根据成功率调整策略
            if avg_success_rate >= 0.9:
                self.current_strategy = OptimizationStrategy.AGGRESSIVE
                recommendations.append("自动修复成功率很高，可以增加自动执行范围")
                risk_adjustments['auto_approve_threshold'] = RiskLevel.MEDIUM.name
            
            elif avg_success_rate >= 0.7:
                self.current_strategy = OptimizationStrategy.BALANCED
                recommendations.append("自动修复成功率良好，保持当前策略")
                risk_adjustments['auto_approve_threshold'] = RiskLevel.LOW.name
            
            else:
                self.current_strategy = OptimizationStrategy.CONSERVATIVE
                recommendations.append("自动修复成功率较低，建议更加谨慎")
                recommendations.append("增加用户确认环节")
                risk_adjustments['auto_approve_threshold'] = RiskLevel.SAFE.name
            
            # 模式建议
            high_confidence_patterns = [p for p in patterns if p.confidence >= self.min_confidence_threshold]
            if high_confidence_patterns:
                recommendations.append(f"发现 {len(high_confidence_patterns)} 个高置信度模式")
                for pattern in high_confidence_patterns[:5]:
                    recommendations.append(
                        f"  - {pattern.problem_type}/{pattern.severity}: "
                        f"成功率 {pattern.success_rate:.1%}, 推荐 {pattern.recommended_action.value}"
                    )
        
        # 性能指标
        performance_metrics = {
            'total_decisions': len(self.engine.decisions),
            'patterns_found': len(patterns),
            'avg_success_rate': sum(p.success_rate for p in patterns) / len(patterns) if patterns else 0,
            'high_confidence_patterns': self.metrics['high_confidence_patterns'],
        }
        
        # 创建报告
        report = OptimizationReport(
            timestamp=datetime.now(),
            strategy=self.current_strategy,
            patterns_analyzed=len(patterns),
            recommendations=recommendations,
            risk_adjustments=risk_adjustments,
            performance_metrics=performance_metrics,
        )
        
        self.optimization_history.append(report)
        self.metrics['optimization_cycles'] += 1
        self.metrics['last_optimization'] = datetime.now()
        
        self.logger.info(f"优化完成，策略: {self.current_strategy.value}")
        return report
    
    def get_recommendation(self, problem_type: str, severity: str, file_path: Optional[str]) -> Optional[DecisionType]:
        """
        获取针对特定问题的决策建议
        
        Args:
            problem_type: 问题类型
            severity: 严重程度
            file_path: 文件路径
            
        Returns:
            推荐的决策类型
        """
        file_pattern = self._extract_file_pattern(file_path)
        
        # 查找匹配的模式
        for pattern in self.patterns:
            if (pattern.problem_type == problem_type and 
                pattern.severity == severity and 
                pattern.file_pattern == file_pattern and
                pattern.confidence >= self.min_confidence_threshold):
                return pattern.recommended_action
        
        # 没有找到匹配模式
        return None
    
    def save_patterns(self, file_path: str = ".decision_patterns.json"):
        """保存决策模式"""
        try:
            data = {
                'patterns': [
                    {
                        'pattern_id': p.pattern_id,
                        'problem_type': p.problem_type,
                        'severity': p.severity,
                        'file_pattern': p.file_pattern,
                        'success_rate': p.success_rate,
                        'total_decisions': p.total_decisions,
                        'successful_decisions': p.successful_decisions,
                        'recommended_action': p.recommended_action.value,
                        'confidence': p.confidence,
                        'last_updated': p.last_updated.isoformat(),
                    }
                    for p in self.patterns
                ],
                'strategy': self.current_strategy.value,
                'metrics': self.metrics,
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"决策模式已保存: {file_path}")
            
        except Exception as e:
            self.logger.error(f"保存决策模式失败: {e}")
    
    def load_patterns(self, file_path: str = ".decision_patterns.json"):
        """加载决策模式"""
        try:
            path = Path(file_path)
            if not path.exists():
                return
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 恢复模式
            self.patterns = []
            for p_data in data.get('patterns', []):
                pattern = DecisionPattern(
                    pattern_id=p_data['pattern_id'],
                    problem_type=p_data['problem_type'],
                    severity=p_data['severity'],
                    file_pattern=p_data['file_pattern'],
                    success_rate=p_data['success_rate'],
                    total_decisions=p_data['total_decisions'],
                    successful_decisions=p_data['successful_decisions'],
                    recommended_action=DecisionType(p_data['recommended_action']),
                    confidence=p_data['confidence'],
                    last_updated=datetime.fromisoformat(p_data['last_updated']),
                )
                self.patterns.append(pattern)
            
            # 恢复策略
            self.current_strategy = OptimizationStrategy(data.get('strategy', 'balanced'))
            
            # 恢复指标
            self.metrics.update(data.get('metrics', {}))
            
            self.logger.info(f"已加载 {len(self.patterns)} 个决策模式")
            
        except Exception as e:
            self.logger.error(f"加载决策模式失败: {e}")
    
    def generate_optimization_summary(self) -> str:
        """生成优化摘要"""
        lines = [
            "决策优化摘要",
            "=" * 60,
            f"策略: {self.current_strategy.value}",
            f"优化次数: {self.metrics['optimization_cycles']}",
            f"总模式数: {self.metrics['total_patterns']}",
            f"高置信度模式: {self.metrics['high_confidence_patterns']}",
            "",
            "最新建议:",
        ]
        
        if self.optimization_history:
            latest_report = self.optimization_history[-1]
            for rec in latest_report.recommendations:
                lines.append(f"  - {rec}")
        else:
            lines.append("  尚未进行优化")
        
        lines.extend([
            "",
            "高置信度模式:",
        ])
        
        high_conf = [p for p in self.patterns if p.confidence >= self.min_confidence_threshold]
        if high_conf:
            for p in high_conf[:10]:
                lines.append(
                    f"  {p.problem_type}/{p.severity}: "
                    f"成功率 {p.success_rate:.1%} "
                    f"({p.successful_decisions}/{p.total_decisions})"
                )
        else:
            lines.append("  暂无")
        
        return "\n".join(lines)


# 单例
_optimizer_instance: Optional[DecisionOptimizer] = None


def get_decision_optimizer(engine: Optional[AutonomousEngine] = None) -> DecisionOptimizer:
    """获取决策优化器单例"""
    global _optimizer_instance
    if _optimizer_instance is None:
        if engine is None:
            engine = get_autonomous_engine()
        _optimizer_instance = DecisionOptimizer(engine)
    return _optimizer_instance
