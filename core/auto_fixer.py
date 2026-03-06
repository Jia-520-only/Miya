"""
自动修复器
自动修复可修复的问题
"""
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import shutil
import asyncio
import re


logger = logging.getLogger(__name__)


from core.problem_scanner import Problem, ProblemType, ProblemSeverity


@dataclass
class FixResult:
    """修复结果"""
    success: bool
    problem: Problem
    action_taken: str
    output: str
    time_taken: float
    backup_created: bool = False
    backup_path: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'success': self.success,
            'problem_id': self.problem.id,
            'problem_title': self.problem.title,
            'action_taken': self.action_taken,
            'output': self.output,
            'time_taken': self.time_taken,
            'backup_created': self.backup_created,
            'backup_path': self.backup_path,
            'error': self.error,
        }


@dataclass
class FixPlan:
    """修复计划"""
    problems: List[Problem] = field(default_factory=list)
    estimated_time: float = 0.0
    requires_approval: bool = False
    high_risk_count: int = 0
    auto_fixable_count: int = 0

    def add_problem(self, problem: Problem):
        """添加问题到修复计划"""
        self.problems.append(problem)

        if problem.auto_fixable:
            self.auto_fixable_count += 1

        if problem.severity in [ProblemSeverity.HIGH, ProblemSeverity.CRITICAL]:
            self.high_risk_count += 1
            self.requires_approval = True

        # 估算时间（简单策略：每个问题 2-5 秒）
        self.estimated_time = len(self.problems) * 3.0

    @property
    def problem_count(self) -> int:
        """问题数量"""
        return len(self.problems)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'problem_count': self.problem_count,
            'auto_fixable_count': self.auto_fixable_count,
            'high_risk_count': self.high_risk_count,
            'estimated_time': self.estimated_time,
            'requires_approval': self.requires_approval,
            'problems': [p.id for p in self.problems],
        }


class AutoFixer:
    """
    自动修复器

    职责：
    1. 判断问题是否可自动修复
    2. 创建修复计划
    3. 执行修复
    4. 备份和回滚
    """

    def __init__(self, backup_dir: Optional[str] = None):
        """
        初始化自动修复器

        Args:
            backup_dir: 备份目录，默认为项目根目录下的 .backup
        """
        self.logger = logging.getLogger(__name__)

        if backup_dir:
            self.backup_dir = Path(backup_dir)
        else:
            # 默认使用项目根目录下的 .backup
            self.backup_dir = Path(__file__).parent.parent / '.backup'

        self.backup_dir.mkdir(parents=True, exist_ok=True)

        self._fix_strategies = {
            ProblemType.LINTER: self._fix_linter_problem,
            ProblemType.DEPENDENCY: self._fix_dependency_problem,
            ProblemType.CONFIG: self._fix_config_problem,
        }

    def can_fix(self, problem: Problem) -> bool:
        """
        判断问题是否可自动修复

        Args:
            problem: 问题对象

        Returns:
            是否可修复
        """
        # 基本检查
        if not problem.auto_fixable:
            return False

        # 检查是否有对应的修复策略
        strategy = self._fix_strategies.get(problem.type)
        if not strategy:
            return False

        return True

    def create_fix_plan(
        self,
        problems: List[Problem],
        max_count: int = 10,
        require_approval_for: Optional[List[ProblemSeverity]] = None
    ) -> FixPlan:
        """
        创建修复计划

        Args:
            problems: 问题列表
            max_count: 最多修复的问题数
            require_approval_for: 需要批准的严重程度列表

        Returns:
            修复计划
        """
        plan = FixPlan()

        # 按优先级排序
        from core.problem_scanner import ProblemScanner
        scanner = ProblemScanner()
        prioritized = scanner.prioritize_problems(problems, max_count=max_count)

        # 筛选可修复的问题
        for problem in prioritized:
            if self.can_fix(problem):
                # 检查是否需要批准
                if require_approval_for and problem.severity in require_approval_for:
                    plan.requires_approval = True

                plan.add_problem(problem)

        self.logger.info(
            f"创建修复计划: {len(plan.problems)} 个问题, "
            f"预计耗时 {plan.estimated_time:.1f} 秒"
        )

        return plan

    async def fix_problem(
        self,
        problem: Problem,
        create_backup: bool = True
    ) -> FixResult:
        """
        修复单个问题

        Args:
            problem: 问题对象
            create_backup: 是否创建备份

        Returns:
            修复结果
        """
        start_time = datetime.now()

        self.logger.info(f"开始修复问题: {problem.title}")

        backup_path = None
        backup_created = False

        # 创建备份
        if create_backup and problem.file_path:
            backup_path = await self._create_backup(problem.file_path)
            backup_created = backup_path is not None

        try:
            # 获取修复策略
            strategy = self._fix_strategies.get(problem.type)
            if not strategy:
                raise ValueError(f"没有针对 {problem.type} 的修复策略")

            # 执行修复
            action_taken, output = await strategy(problem)

            time_taken = (datetime.now() - start_time).total_seconds()

            result = FixResult(
                success=True,
                problem=problem,
                action_taken=action_taken,
                output=output,
                time_taken=time_taken,
                backup_created=backup_created,
                backup_path=backup_path
            )

            self.logger.info(f"修复成功: {problem.title} (耗时 {time_taken:.2f}秒)")

        except Exception as e:
            time_taken = (datetime.now() - start_time).total_seconds()
            error_msg = f"修复失败: {str(e)}"

            self.logger.error(error_msg)

            result = FixResult(
                success=False,
                problem=problem,
                action_taken="无",
                output="",
                time_taken=time_taken,
                backup_created=backup_created,
                backup_path=backup_path,
                error=error_msg
            )

        return result

    async def fix_batch(
        self,
        problems: List[Problem],
        create_backup: bool = True,
        stop_on_error: bool = False
    ) -> List[FixResult]:
        """
        批量修复问题

        Args:
            problems: 问题列表
            create_backup: 是否创建备份
            stop_on_error: 遇到错误是否停止

        Returns:
            修复结果列表
        """
        results = []

        for problem in problems:
            if not self.can_fix(problem):
                self.logger.warning(f"问题不可修复: {problem.title}")
                continue

            result = await self.fix_problem(problem, create_backup)
            results.append(result)

            if not result.success and stop_on_error:
                self.logger.error("遇到错误，停止修复")
                break

        return results

    async def _create_backup(self, file_path: str) -> Optional[str]:
        """
        创建文件备份

        Args:
            file_path: 文件路径

        Returns:
            备份文件路径，失败返回 None
        """
        try:
            source = Path(file_path)
            if not source.exists():
                self.logger.warning(f"文件不存在，无法备份: {file_path}")
                return None

            # 生成备份文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{source.name}.{timestamp}.backup"
            backup_path = self.backup_dir / backup_name

            # 创建备份
            shutil.copy2(source, backup_path)

            self.logger.info(f"备份已创建: {backup_path}")
            return str(backup_path)

        except Exception as e:
            self.logger.error(f"创建备份失败: {e}")
            return None

    async def _fix_linter_problem(self, problem: Problem) -> tuple[str, str]:
        """修复 Linter 问题"""
        file_path = problem.file_path
        if not file_path:
            raise ValueError("没有文件路径")

        source = Path(file_path)
        if not source.exists():
            raise ValueError(f"文件不存在: {file_path}")

        # 读取文件
        with open(source, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 根据问题描述修复
        action_taken = "无"
        output = ""

        if 'unused import' in problem.description.lower():
            # 删除未使用的 import
            if problem.line_number:
                line_idx = problem.line_number - 1
                if line_idx < len(lines):
                    removed_line = lines.pop(line_idx)
                    action_taken = f"删除了未使用的 import: {removed_line.strip()}"
                    output = f"已删除第 {problem.line_number} 行的未使用的 import"

        elif 'trailing whitespace' in problem.description.lower():
            # 删除尾随空格
            if problem.line_number:
                line_idx = problem.line_number - 1
                if line_idx < len(lines):
                    lines[line_idx] = lines[line_idx].rstrip() + '\n'
                    action_taken = f"删除了第 {problem.line_number} 行的尾随空格"
                    output = "已删除尾随空格"

        elif 'missing newline' in problem.description.lower():
            # 添加缺失的换行符
            if not lines or not lines[-1].endswith('\n'):
                lines.append('\n')
                action_taken = "在文件末尾添加了换行符"
                output = "已添加缺失的换行符"

        else:
            raise ValueError(f"不支持的 Linter 问题类型: {problem.description}")

        # 写回文件
        with open(source, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        return action_taken, output

    async def _fix_dependency_problem(self, problem: Problem) -> tuple[str, str]:
        """修复依赖问题"""
        file_path = problem.file_path
        if not file_path:
            raise ValueError("没有文件路径")

        # 依赖问题通常需要人工干预
        raise ValueError("依赖问题需要手动修复，请参考建议")

    async def _fix_config_problem(self, problem: Problem) -> tuple[str, str]:
        """修复配置问题"""
        file_path = problem.file_path
        if not file_path:
            raise ValueError("没有文件路径")

        source = Path(file_path)
        if not source.exists():
            raise ValueError(f"文件不存在: {file_path}")

        # 读取文件
        with open(source, 'r', encoding='utf-8') as f:
            content = f.read()

        # 根据问题描述修复
        action_taken = "无"
        output = ""

        if 'toml' in file_path.lower() and '等号' in problem.description:
            # 替换冒号为等号
            content = re.sub(r'^([^=]+):(.+)$', r'\1=\2', content, flags=re.MULTILINE)
            action_taken = "替换了 TOML 文件中的冒号为等号"
            output = "已修复 TOML 语法错误"

        elif 'ini' in file_path.lower():
            # INI 文件修复
            lines = content.split('\n')
            fixed_lines = []

            for line in lines:
                # 检查是否有冒号但不是节标题
                if ':' in line and not line.startswith('['):
                    # 尝试替换为等号
                    line = line.replace(':', '=', 1)
                fixed_lines.append(line)

            content = '\n'.join(fixed_lines)
            action_taken = "修复了 INI 文件格式"
            output = "已修复 INI 语法错误"

        else:
            raise ValueError(f"不支持的配置问题: {problem.description}")

        # 写回文件
        with open(source, 'w', encoding='utf-8') as f:
            f.write(content)

        return action_taken, output

    def restore_backup(self, backup_path: str, target_path: str) -> bool:
        """
        恢复备份

        Args:
            backup_path: 备份文件路径
            target_path: 目标文件路径

        Returns:
            是否成功
        """
        try:
            backup = Path(backup_path)
            target = Path(target_path)

            if not backup.exists():
                self.logger.error(f"备份文件不存在: {backup_path}")
                return False

            # 创建备份的备份（在恢复前）
            if target.exists():
                final_backup = self._create_backup_sync(target_path)
            else:
                final_backup = None

            # 恢复
            shutil.copy2(backup, target)

            self.logger.info(f"已从备份恢复: {backup_path} -> {target_path}")
            return True

        except Exception as e:
            self.logger.error(f"恢复备份失败: {e}")
            return False

    def _create_backup_sync(self, file_path: str) -> Optional[str]:
        """
        同步创建文件备份

        Args:
            file_path: 文件路径

        Returns:
            备份文件路径，失败返回 None
        """
        try:
            source = Path(file_path)
            if not source.exists():
                self.logger.warning(f"文件不存在，无法备份: {file_path}")
                return None

            # 生成备份文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{source.name}.{timestamp}.backup"
            backup_path = self.backup_dir / backup_name

            # 创建备份
            shutil.copy2(source, backup_path)

            self.logger.info(f"备份已创建: {backup_path}")
            return str(backup_path)

        except Exception as e:
            self.logger.error(f"创建备份失败: {e}")
            return None
