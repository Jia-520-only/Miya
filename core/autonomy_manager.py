"""
自主能力集成模块
将自主决策引擎集成到主程序中
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

from core.autonomous_engine import AutonomousEngine, get_autonomous_engine
from core.decision_optimizer import DecisionOptimizer, get_decision_optimizer
from core.system_detector import get_system_detector


logger = logging.getLogger(__name__)


class AutonomyManager:
    """自主能力管理器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.engine: Optional[AutonomousEngine] = None
        self.optimizer: Optional[DecisionOptimizer] = None
        self.system_detector = get_system_detector()
        
        # 配置
        self.auto_improvement_enabled = False
        self.improvement_interval = 300  # 5分钟
        self.auto_approve_threshold = "low"
        
        # 初始化状态
        self.is_initialized = False
    
    def initialize(self):
        """初始化自主能力"""
        if self.is_initialized:
            self.logger.warning("自主能力已初始化")
            return
        
        self.logger.info("🚀 初始化自主能力...")
        
        # 初始化引擎
        self.engine = get_autonomous_engine()
        self.optimizer = get_decision_optimizer(self.engine)
        
        # 设置回调
        self._setup_callbacks()
        
        # 加载历史状态
        self.engine.load_state()
        
        self.is_initialized = True
        self.logger.info("✅ 自主能力初始化完成")
    
    def _setup_callbacks(self):
        """设置回调函数"""
        def on_decision(decision, problem):
            """决策回调"""
            self.logger.info(
                f"📋 决策: {decision.id} | "
                f"风险: {decision.risk_level.name} | "
                f"类型: {decision.decision_type.value} | "
                f"自动批准: {decision.auto_approved}"
            )
        
        def on_fix_start(decision, problem):
            """修复开始回调"""
            self.logger.info(
                f"🔧 开始修复: {problem.id} | "
                f"文件: {problem.file_path or 'N/A'}"
            )
        
        def on_fix_complete(decision, problem, result):
            """修复完成回调"""
            if result.success:
                self.logger.info(
                    f"✅ 修复成功: {problem.id} | "
                    f"修复文件: {len(result.fixed_files)} | "
                    f"耗时: {result.execution_time:.2f}s"
                )
            else:
                self.logger.warning(
                    f"❌ 修复失败: {problem.id} | "
                    f"错误: {result.error_message}"
                )
        
        self.engine.on_decision = on_decision
        self.engine.on_fix_start = on_fix_start
        self.engine.on_fix_complete = on_fix_complete
    
    def enable_auto_improvement(self, interval: int = 300):
        """
        启用自动改进
        
        Args:
            interval: 改进间隔（秒）
        """
        if not self.is_initialized:
            self.initialize()
        
        self.improvement_interval = interval
        self.auto_improvement_enabled = True
        
        self.engine.improvement_interval = interval
        self.engine.start_background_improvement()
        
        self.logger.info(f"🔄 自动改进已启用，间隔: {interval}秒")
    
    def disable_auto_improvement(self):
        """禁用自动改进"""
        self.auto_improvement_enabled = False
        self.engine.stop_background_improvement()
        
        self.logger.info("🛑 自动改进已禁用")
    
    async def manual_improvement(
        self,
        max_fixes: int = 10,
        auto_approve: bool = True
    ) -> Dict[str, Any]:
        """
        手动触发改进

        Args:
            max_fixes: 最大修复数量
            auto_approve: 是否自动批准高风险操作

        Returns:
            改进结果
        """
        if not self.is_initialized:
            self.initialize()

        self.logger.info("🚀 手动触发改进...")
        result = await self.engine.manual_improvement(max_fixes, auto_approve)

        return result
    
    def optimize_decisions(self) -> Dict[str, Any]:
        """
        优化决策策略
        
        Returns:
            优化报告
        """
        if not self.is_initialized:
            self.initialize()
        
        self.logger.info("📊 优化决策策略...")
        report = self.optimizer.optimize_strategy()
        
        # 应用风险调整
        if report.risk_adjustments.get('auto_approve_threshold'):
            threshold_name = report.risk_adjustments['auto_approve_threshold']
            from core.autonomous_engine import RiskLevel
            self.engine.auto_approve_threshold = RiskLevel[threshold_name]
        
        return {
            'strategy': report.strategy.value,
            'patterns_analyzed': report.patterns_analyzed,
            'recommendations': report.recommendations,
            'risk_adjustments': report.risk_adjustments,
            'performance_metrics': report.performance_metrics,
        }
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        if not self.is_initialized:
            return {
                'initialized': False,
                'auto_improvement_enabled': False,
            }
        
        # 获取引擎状态
        engine_status = {
            'total_decisions': self.engine.stats['total_decisions'],
            'auto_decisions': self.engine.stats['auto_decisions'],
            'manual_decisions': self.engine.stats['manual_decisions'],
            'successful_fixes': self.engine.stats['successful_fixes'],
            'failed_fixes': self.engine.stats['failed_fixes'],
            'improvements_made': self.engine.stats['improvements_made'],
            'is_running': self.engine.is_running,
            'last_improvement_time': (
                self.engine.last_improvement_time.isoformat()
                if self.engine.last_improvement_time
                else None
            ),
        }
        
        # 获取优化器状态
        optimizer_status = {
            'strategy': self.optimizer.current_strategy.value,
            'total_patterns': self.optimizer.metrics['total_patterns'],
            'high_confidence_patterns': self.optimizer.metrics['high_confidence_patterns'],
            'optimization_cycles': self.optimizer.metrics['optimization_cycles'],
        }
        
        return {
            'initialized': True,
            'auto_improvement_enabled': self.auto_improvement_enabled,
            'improvement_interval': self.improvement_interval,
            'engine': engine_status,
            'optimizer': optimizer_status,
        }
    
    def generate_report(self) -> Dict[str, Any]:
        """生成完整报告"""
        if not self.is_initialized:
            return {
                'error': '未初始化'
            }
        
        # 系统信息
        system_info = self.system_detector.detect()
        
        # 引擎报告
        engine_report = self.engine.generate_improvement_report()
        
        # 优化器摘要
        optimization_summary = self.optimizer.generate_optimization_summary()
        
        # 最近决策
        recent_decisions = self.engine.get_recent_decisions(10)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'system': system_info.to_dict(),
            'autonomy': {
                'status': self.get_status(),
                'engine_report': engine_report,
                'optimization_summary': optimization_summary,
                'recent_decisions': [
                    {
                        'id': d.id,
                        'problem_id': d.problem_id,
                        'decision_type': d.decision_type.value,
                        'risk_level': d.risk_level.name,
                        'reasoning': d.reasoning,
                        'result': d.result,
                        'timestamp': d.timestamp.isoformat(),
                    }
                    for d in recent_decisions
                ],
            },
        }
    
    def save_all(self):
        """保存所有状态"""
        if not self.is_initialized:
            return
        
        self.engine.save_state()
        self.optimizer.save_patterns()
        
        self.logger.info("所有状态已保存")
    
    def shutdown(self):
        """关闭"""
        if self.auto_improvement_enabled:
            self.disable_auto_improvement()
        
        self.save_all()
        
        self.logger.info("自主能力已关闭")


# 单例
_manager_instance: Optional[AutonomyManager] = None


def get_autonomy_manager() -> AutonomyManager:
    """获取自主能力管理器单例"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = AutonomyManager()
    return _manager_instance
