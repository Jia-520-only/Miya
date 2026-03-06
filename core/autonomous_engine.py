"""
自主决策引擎
第三阶段核心模块 - 让弥娅具备完全自主的决策和执行能力
"""
import logging
import asyncio
import json
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from core.system_detector import get_system_detector
from core.problem_scanner import ProblemScanner, Problem
from core.auto_fixer import AutoFixer, FixResult


logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """风险等级"""
    SAFE = 1        # 安全，可自动执行
    LOW = 2         # 低风险，可自动执行
    MEDIUM = 3      # 中等风险，需要记录
    HIGH = 4        # 高风险，需要用户确认
    CRITICAL = 5    # 极高风险，拒绝执行

    def __lt__(self, other):
        if isinstance(other, RiskLevel):
            return self.value < other.value
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, RiskLevel):
            return self.value <= other.value
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, RiskLevel):
            return self.value > other.value
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, RiskLevel):
            return self.value >= other.value
        return NotImplemented


class DecisionType(Enum):
    """决策类型"""
    AUTO_FIX = "auto_fix"           # 自动修复
    MANUAL_REVIEW = "manual_review" # 人工审查
    ESCALATE = "escalate"           # 上报给用户
    IGNORE = "ignore"               # 忽略
    DEFER = "defer"                 # 延后处理


@dataclass
class Decision:
    """决策记录"""
    id: str
    problem_id: str
    decision_type: DecisionType
    risk_level: RiskLevel
    reasoning: str
    action_taken: Optional[str] = None
    result: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    approved: bool = False
    auto_approved: bool = False


@dataclass
class ImprovementAction:
    """改进行动"""
    id: str
    description: str
    action_type: str  # 'fix', 'optimize', 'refactor', 'add_feature'
    priority: int
    estimated_time: int  # 分钟
    risk_level: RiskLevel
    status: str = 'pending'  # pending, approved, in_progress, completed, failed
    created_at: datetime = field(default_factory=datetime.now)


class AutonomousEngine:
    """自主决策引擎"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.system_detector = get_system_detector()
        self.problem_scanner = ProblemScanner()
        self.auto_fixer = AutoFixer()
        
        # 决策历史
        self.decisions: List[Decision] = []
        
        # 待处理的改进行动
        self.pending_actions: List[ImprovementAction] = []
        
        # 持续改进循环配置
        self.improvement_interval = 300  # 5分钟
        self.max_improvements_per_cycle = 5
        self.auto_approve_threshold = RiskLevel.LOW
        
        # 运行状态
        self.is_running = False
        self.background_task = None
        self.last_improvement_time = None
        
        # 统计信息
        self.stats = {
            'total_decisions': 0,
            'auto_decisions': 0,
            'manual_decisions': 0,
            'successful_fixes': 0,
            'failed_fixes': 0,
            'improvements_made': 0,
        }
        
        # 风险评估规则
        self._setup_risk_rules()
        
        # 回调函数
        self.on_decision: Optional[Callable] = None
        self.on_fix_start: Optional[Callable] = None
        self.on_fix_complete: Optional[Callable] = None
    
    def _setup_risk_rules(self):
        """设置风险评估规则"""
        self.risk_rules = {
            # 文件操作风险
            'file_modify': {
                'safe_extensions': ['.txt', '.md', '.log', '.json'],
                'critical_files': ['.env', 'config.py', '__init__.py'],
                'critical_patterns': ['config', 'settings', 'auth', 'credential'],
            },
            
            # 命令执行风险
            'command_execution': {
                'safe_commands': ['ls', 'dir', 'echo', 'cat', 'pwd', 'cd'],
                'dangerous_commands': ['rm', 'del', 'format', 'shutdown', 'reboot'],
            },
            
            # 修改风险
            'modification': {
                'max_lines_per_fix': 100,
                'max_files_per_batch': 5,
            },
        }
    
    def assess_risk(self, problem: Problem, fix_action: str) -> RiskLevel:
        """
        评估修复风险

        Args:
            problem: 问题对象
            fix_action: 修复动作描述

        Returns:
            风险等级
        """
        risk_score = 0

        # 基于问题严重程度
        severity_value = problem.severity.value if hasattr(problem.severity, 'value') else str(problem.severity)
        if severity_value == 'critical':
            risk_score += 3
        elif severity_value == 'high':
            risk_score += 2
        elif severity_value == 'medium':
            risk_score += 1

        # 基于问题类型
        type_value = problem.type.value if hasattr(problem.type, 'value') else str(problem.type)
        if type_value == 'security':
            risk_score += 2
        elif type_value == 'dependency':
            risk_score += 1

        # 基于修复动作
        if 'delete' in fix_action.lower() or 'remove' in fix_action.lower():
            risk_score += 2

        if 'modify' in fix_action.lower() or 'change' in fix_action.lower():
            risk_score += 1

        # 检查文件路径
        if problem.file_path:
            file_path = Path(problem.file_path)

            # 关键文件
            if file_path.name in self.risk_rules['file_modify']['critical_files']:
                risk_score += 3

            # 检查文件名模式
            for pattern in self.risk_rules['file_modify']['critical_patterns']:
                if pattern in file_path.name.lower():
                    risk_score += 2

        # 转换为风险等级
        if risk_score <= 2:
            return RiskLevel.SAFE
        elif risk_score <= 4:
            return RiskLevel.LOW
        elif risk_score <= 6:
            return RiskLevel.MEDIUM
        elif risk_score <= 8:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL
    
    def make_decision(self, problem: Problem, fix_suggestion: str = "") -> Decision:
        """
        对问题做出决策
        
        Args:
            problem: 问题对象
            fix_suggestion: 修复建议
            
        Returns:
            决策对象
        """
        decision_id = f"decision_{datetime.now().strftime('%Y%m%d%H%M%S')}_{problem.id}"
        
        # 评估风险
        risk_level = self.assess_risk(problem, fix_suggestion)
        
        # 做出决策
        if risk_level <= self.auto_approve_threshold:
            decision_type = DecisionType.AUTO_FIX
            approved = True
            auto_approved = True
            reasoning = f"风险等级 {risk_level.name} 低于阈值，自动批准"
        elif risk_level <= RiskLevel.MEDIUM:
            decision_type = DecisionType.AUTO_FIX
            approved = True
            auto_approved = False
            reasoning = f"风险等级 {risk_level.name}，记录批准"
        elif risk_level == RiskLevel.HIGH:
            decision_type = DecisionType.MANUAL_REVIEW
            approved = False
            auto_approved = False
            reasoning = f"风险等级 {risk_level.name}，需要用户确认"
        else:  # CRITICAL
            decision_type = DecisionType.ESCALATE
            approved = False
            auto_approved = False
            reasoning = f"风险等级 {risk_level.name}，拒绝自动执行"
        
        decision = Decision(
            id=decision_id,
            problem_id=problem.id,
            decision_type=decision_type,
            risk_level=risk_level,
            reasoning=reasoning,
            approved=approved,
            auto_approved=auto_approved,
        )
        
        self.decisions.append(decision)
        self.stats['total_decisions'] += 1
        
        if auto_approved:
            self.stats['auto_decisions'] += 1
        else:
            self.stats['manual_decisions'] += 1
        
        # 回调
        if self.on_decision:
            try:
                self.on_decision(decision, problem)
            except Exception as e:
                self.logger.error(f"决策回调失败: {e}")
        
        return decision
    
    def execute_decision(self, decision: Decision, problem: Problem) -> Optional[FixResult]:
        """
        执行决策
        
        Args:
            decision: 决策对象
            problem: 问题对象
            
        Returns:
            修复结果
        """
        if not decision.approved:
            self.logger.warning(f"决策未批准，跳过执行: {decision.id}")
            return None
        
        if decision.decision_type == DecisionType.IGNORE or decision.decision_type == DecisionType.DEFER:
            self.logger.info(f"决策类型为 {decision.decision_type.value}，跳过执行")
            return None
        
        # 执行修复
        try:
            self.logger.info(f"开始执行决策: {decision.id}")
            
            # 回调
            if self.on_fix_start:
                try:
                    self.on_fix_start(decision, problem)
                except Exception as e:
                    self.logger.error(f"修复开始回调失败: {e}")
            
            # 使用 AutoFixer 执行修复
            fix_plan = self.auto_fixer.create_fix_plan([problem])
            result = self.auto_fixer.execute_fix_plan(fix_plan, auto_approve=True)
            
            # 更新决策
            decision.action_taken = "auto_fix"
            decision.result = "success" if result.success else "failed"
            
            # 更新统计
            if result.success:
                self.stats['successful_fixes'] += 1
            else:
                self.stats['failed_fixes'] += 1
            
            # 回调
            if self.on_fix_complete:
                try:
                    self.on_fix_complete(decision, problem, result)
                except Exception as e:
                    self.logger.error(f"修复完成回调失败: {e}")
            
            self.logger.info(f"决策执行完成: {decision.id}, 结果: {decision.result}")
            return result
            
        except Exception as e:
            self.logger.error(f"执行决策失败: {e}")
            decision.action_taken = "auto_fix"
            decision.result = f"error: {str(e)}"
            self.stats['failed_fixes'] += 1
            return None
    
    async def improvement_cycle(self):
        """
        持续改进循环
        每隔一定时间自动扫描和修复问题
        """
        self.logger.info("🔄 启动持续改进循环")

        while self.is_running:
            try:
                cycle_start = time.time()

                # 扫描问题
                self.logger.info("🔍 开始扫描问题...")
                problems = await self.problem_scanner.scan_all()

                if not problems:
                    self.logger.info("✅ 没有发现新问题")
                else:
                    self.logger.info(f"📊 发现 {len(problems)} 个问题")

                    # 优先处理高风险问题
                    high_priority_problems = [
                        p for p in problems
                        if p.severity.value in ['critical', 'high']
                    ]

                    # 限制每次修复的数量
                    problems_to_fix = high_priority_problems[:self.max_improvements_per_cycle]

                    for problem in problems_to_fix:
                        # 做出决策
                        decision = self.make_decision(problem)

                        # 执行决策
                        if decision.approved:
                            result = self.execute_decision(decision, problem)

                            if result and result.success:
                                self.stats['improvements_made'] += 1

                # 记录改进时间
                self.last_improvement_time = datetime.now()

                # 计算等待时间
                elapsed = time.time() - cycle_start
                wait_time = max(0, self.improvement_interval - elapsed)

                self.logger.info(f"⏱️  下次改进循环将在 {wait_time:.1f} 秒后开始")

                # 等待
                await asyncio.sleep(wait_time)

            except Exception as e:
                self.logger.error(f"改进循环出错: {e}")
                import traceback
                traceback.print_exc()
                
                # 出错后等待一段时间再重试
                await asyncio.sleep(60)
    
    def start_background_improvement(self):
        """启动后台改进循环"""
        if self.is_running:
            self.logger.warning("改进循环已在运行")
            return
        
        self.is_running = True
        
        # 在新线程中运行异步循环
        def run_async_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.improvement_cycle())
            finally:
                loop.close()
        
        thread = threading.Thread(target=run_async_loop, daemon=True)
        thread.start()
        
        self.logger.info("✅ 后台改进循环已启动")
    
    def stop_background_improvement(self):
        """停止后台改进循环"""
        self.is_running = False
        self.logger.info("🛑 后台改进循环已停止")
    
    async def manual_improvement(self, max_fixes: int = 10, auto_approve: bool = True) -> Dict[str, Any]:
        """
        手动触发改进

        Args:
            max_fixes: 最大修复数量
            auto_approve: 是否自动批准高风险操作

        Returns:
            改进结果
        """
        self.logger.info(f"🚀 手动触发改进，最大修复数: {max_fixes}")

        result = {
            'scanned': False,
            'problems_found': 0,
            'decisions_made': 0,
            'fixes_attempted': 0,
            'fixes_successful': 0,
            'fixes_failed': 0,
            'errors': [],
        }

        try:
            # 扫描问题
            problems = await self.problem_scanner.scan_all()
            result['problems_found'] = len(problems)
            result['scanned'] = True

            if not problems:
                self.logger.info("✅ 没有发现需要处理的问题")
                return result

            # 优先级排序
            problems = self.problem_scanner.sort_by_priority(problems)

            # 限制修复数量
            problems_to_fix = problems[:max_fixes]

            for problem in problems_to_fix:
                try:
                    # 做出决策
                    decision = self.make_decision(problem)
                    result['decisions_made'] += 1

                    # 如果需要自动批准
                    if auto_approve and not decision.approved:
                        decision.approved = True
                        decision.reasoning += " (手动触发，自动批准)"

                    # 执行决策
                    if decision.approved:
                        result['fixes_attempted'] += 1
                        fix_result = self.execute_decision(decision, problem)

                        if fix_result:
                            if fix_result.success:
                                result['fixes_successful'] += 1
                            else:
                                result['fixes_failed'] += 1

                except Exception as e:
                    error_msg = f"处理问题 {problem.id} 失败: {str(e)}"
                    self.logger.error(error_msg)
                    result['errors'].append(error_msg)

            self.logger.info(f"✅ 手动改进完成: {result['fixes_successful']}/{result['fixes_attempted']} 成功")
            return result

        except Exception as e:
            error_msg = f"手动改进失败: {str(e)}"
            self.logger.error(error_msg)
            result['errors'].append(error_msg)
            return result
    
    def generate_improvement_report(self) -> Dict[str, Any]:
        """生成改进报告"""
        return {
            'timestamp': datetime.now().isoformat(),
            'statistics': self.stats,
            'decisions': {
                'total': len(self.decisions),
                'auto_approved': sum(1 for d in self.decisions if d.auto_approved),
                'manual_approved': sum(1 for d in self.decisions if d.approved and not d.auto_approved),
                'not_approved': sum(1 for d in self.decisions if not d.approved),
            },
            'decision_types': {
                dt.value: sum(1 for d in self.decisions if d.decision_type == dt)
                for dt in DecisionType
            },
            'risk_levels': {
                rl.name: sum(1 for d in self.decisions if d.risk_level == rl)
                for rl in RiskLevel
            },
            'last_improvement_time': self.last_improvement_time.isoformat() if self.last_improvement_time else None,
            'is_running': self.is_running,
        }
    
    def get_recent_decisions(self, limit: int = 20) -> List[Decision]:
        """获取最近的决策记录"""
        return self.decisions[-limit:]
    
    def save_state(self, file_path: str = ".autonomous_engine_state.json"):
        """保存状态"""
        try:
            state = {
                'decisions': [
                    {
                        'id': d.id,
                        'problem_id': d.problem_id,
                        'decision_type': d.decision_type.value,
                        'risk_level': d.risk_level.name,
                        'reasoning': d.reasoning,
                        'action_taken': d.action_taken,
                        'result': d.result,
                        'timestamp': d.timestamp.isoformat(),
                        'approved': d.approved,
                        'auto_approved': d.auto_approved,
                    }
                    for d in self.decisions
                ],
                'stats': self.stats,
                'last_improvement_time': self.last_improvement_time.isoformat() if self.last_improvement_time else None,
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"状态已保存: {file_path}")
            
        except Exception as e:
            self.logger.error(f"保存状态失败: {e}")
    
    def load_state(self, file_path: str = ".autonomous_engine_state.json"):
        """加载状态"""
        try:
            if not Path(file_path).exists():
                self.logger.info(f"状态文件不存在: {file_path}")
                return
            
            with open(file_path, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            # 恢复决策
            self.decisions = []
            for d_data in state.get('decisions', []):
                decision = Decision(
                    id=d_data['id'],
                    problem_id=d_data['problem_id'],
                    decision_type=DecisionType(d_data['decision_type']),
                    risk_level=RiskLevel[d_data['risk_level']],
                    reasoning=d_data['reasoning'],
                    action_taken=d_data.get('action_taken'),
                    result=d_data.get('result'),
                    timestamp=datetime.fromisoformat(d_data['timestamp']),
                    approved=d_data['approved'],
                    auto_approved=d_data['auto_approved'],
                )
                self.decisions.append(decision)
            
            # 恢复统计
            self.stats.update(state.get('stats', {}))
            
            # 恢复最后改进时间
            if state.get('last_improvement_time'):
                self.last_improvement_time = datetime.fromisoformat(state['last_improvement_time'])
            
            self.logger.info(f"状态已加载: {file_path}")
            
        except Exception as e:
            self.logger.error(f"加载状态失败: {e}")


# 单例
_engine_instance: Optional[AutonomousEngine] = None


def get_autonomous_engine() -> AutonomousEngine:
    """获取自主决策引擎单例"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = AutonomousEngine()
    return _engine_instance
