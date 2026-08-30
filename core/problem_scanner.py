"""
问题扫描器
负责主动发现代码、配置、依赖等问题
"""
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import asyncio
from pathlib import Path


logger = logging.getLogger(__name__)


class ProblemSeverity(Enum):
    """问题严重程度"""
    INFO = "info"       # 信息性提示
    LOW = "low"         # 低优先级
    MEDIUM = "medium"   # 中等优先级
    HIGH = "high"       # 高优先级
    CRITICAL = "critical"  # 严重问题


class ProblemType(Enum):
    """问题类型"""
    LINTER = "linter"           # Linter 错误
    DEPENDENCY = "dependency"   # 依赖问题
    CONFIG = "config"           # 配置问题
    SECURITY = "security"       # 安全问题
    PERFORMANCE = "performance" # 性能问题
    CODE_STYLE = "code_style"   # 代码风格


@dataclass
class Problem:
    """问题对象"""
    id: str                    # 问题ID（唯一标识）
    type: ProblemType          # 问题类型
    severity: ProblemSeverity  # 严重程度
    title: str                 # 问题标题
    description: str           # 详细描述
    file_path: Optional[str] = None  # 相关文件路径
    line_number: Optional[int] = None # 行号
    column: Optional[int] = None     # 列号
    code_snippet: Optional[str] = None  # 代码片段
    suggestions: List[str] = field(default_factory=list)  # 修复建议
    auto_fixable: bool = False  # 是否可自动修复
    confidence: float = 0.0    # 置信度（0.0-1.0）
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'id': self.id,
            'type': self.type.value,
            'severity': self.severity.value,
            'title': self.title,
            'description': self.description,
            'file_path': self.file_path,
            'line_number': self.line_number,
            'column': self.column,
            'code_snippet': self.code_snippet,
            'suggestions': self.suggestions,
            'auto_fixable': self.auto_fixable,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }

    def is_fixable(self) -> bool:
        """是否可修复"""
        return self.auto_fixable

    def requires_approval(self) -> bool:
        """是否需要用户批准"""
        return self.severity in [ProblemSeverity.HIGH, ProblemSeverity.CRITICAL]


class BaseScanner:
    """扫描器基类"""

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"Scanner.{name}")
        self._problems: List[Problem] = []

    async def scan(self, path: str = '.', **kwargs) -> List[Problem]:
        """
        扫描问题

        Args:
            path: 扫描路径
            **kwargs: 其他参数

        Returns:
            发现的问题列表
        """
        raise NotImplementedError

    def clear_problems(self):
        """清空问题列表"""
        self._problems.clear()

    def get_problems(self) -> List[Problem]:
        """获取问题列表"""
        return self._problems.copy()


class ProblemScanner:
    """
    问题扫描器主类

    职责：
    1. 协调各扫描器工作
    2. 收集和汇总问题
    3. 问题优先级排序
    4. 提供问题过滤和查询
    """

    def __init__(self):
        self.scanners: Dict[str, BaseScanner] = {}
        self.logger = logging.getLogger(__name__)
        self._init_scanners()

    def _init_scanners(self):
        """初始化所有扫描器"""
        try:
            # Linter 扫描器
            from core.linter_scanner import LinterScanner
            self.register_scanner('linter', LinterScanner())
        except Exception as e:
            self.logger.warning(f"LinterScanner 初始化失败: {e}")

        try:
            # 依赖扫描器
            from core.dependency_scanner import DependencyScanner
            self.register_scanner('dependency', DependencyScanner())
        except Exception as e:
            self.logger.warning(f"DependencyScanner 初始化失败: {e}")

        try:
            # 配置扫描器
            from core.config_scanner import ConfigScanner
            self.register_scanner('config', ConfigScanner())
        except Exception as e:
            self.logger.warning(f"ConfigScanner 初始化失败: {e}")

        self.logger.info(f"问题扫描器初始化完成，已加载 {len(self.scanners)} 个扫描器")

    def register_scanner(self, name: str, scanner: BaseScanner):
        """注册扫描器"""
        self.scanners[name] = scanner
        self.logger.info(f"已注册扫描器: {name}")

    def unregister_scanner(self, name: str):
        """注销扫描器"""
        if name in self.scanners:
            del self.scanners[name]
            self.logger.info(f"已注销扫描器: {name}")

    async def scan_all(
        self,
        path: str = '.',
        scanner_names: Optional[List[str]] = None,
        **kwargs
    ) -> List[Problem]:
        """
        运行所有扫描器

        Args:
            path: 扫描路径
            scanner_names: 指定要运行的扫描器列表，None 表示运行所有
            **kwargs: 传递给扫描器的参数

        Returns:
            所有发现的问题
        """
        self.logger.info(f"开始扫描路径: {path}")

        all_problems = []

        # 确定要运行的扫描器
        scanners_to_run = []
        if scanner_names:
            for name in scanner_names:
                if name in self.scanners:
                    scanners_to_run.append(self.scanners[name])
                else:
                    self.logger.warning(f"扫描器不存在: {name}")
        else:
            scanners_to_run = list(self.scanners.values())

        # 并行运行所有扫描器
        tasks = [scanner.scan(path, **kwargs) for scanner in scanners_to_run]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 收集结果
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"扫描器 {scanners_to_run[i].name} 执行失败: {result}")
            elif isinstance(result, list):
                all_problems.extend(result)
                self.logger.info(f"扫描器 {scanners_to_run[i].name} 发现 {len(result)} 个问题")

        # 为问题生成唯一ID
        for i, problem in enumerate(all_problems):
            if not problem.id:
                problem.id = f"{problem.type.value}_{i}_{datetime.now().timestamp()}"

        self.logger.info(f"扫描完成，共发现 {len(all_problems)} 个问题")
        return all_problems

    async def scan_by_type(
        self,
        problem_type: ProblemType,
        path: str = '.',
        **kwargs
    ) -> List[Problem]:
        """
        按问题类型扫描

        Args:
            problem_type: 问题类型
            path: 扫描路径
            **kwargs: 其他参数

        Returns:
            该类型的问题列表
        """
        type_scanner_map = {
            ProblemType.LINTER: 'linter',
            ProblemType.DEPENDENCY: 'dependency',
            ProblemType.CONFIG: 'config',
        }

        scanner_name = type_scanner_map.get(problem_type)
        if not scanner_name or scanner_name not in self.scanners:
            self.logger.warning(f"未找到问题类型 {problem_type.value} 的扫描器")
            return []

        scanner = self.scanners[scanner_name]
        return await scanner.scan(path, **kwargs)

    def prioritize_problems(
        self,
        problems: List[Problem],
        max_count: int = 50
    ) -> List[Problem]:
        """
        问题优先级排序

        排序规则：
        1. 按严重程度排序（CRITICAL > HIGH > MEDIUM > LOW > INFO）
        2. 同严重程度按置信度排序
        3. 可自动修复的优先

        Args:
            problems: 问题列表
            max_count: 最大返回数量

        Returns:
            排序后的问题列表
        """
        # 严重程度权重
        severity_weight = {
            ProblemSeverity.CRITICAL: 100,
            ProblemSeverity.HIGH: 80,
            ProblemSeverity.MEDIUM: 60,
            ProblemSeverity.LOW: 40,
            ProblemSeverity.INFO: 20,
        }

        # 计算总分
        def get_score(problem: Problem) -> float:
            base_score = severity_weight.get(problem.severity, 0)
            confidence_bonus = problem.confidence * 10
            auto_fix_bonus = 5 if problem.auto_fixable else 0
            return base_score + confidence_bonus + auto_fix_bonus

        # 排序
        sorted_problems = sorted(
            problems,
            key=lambda p: get_score(p),
            reverse=True
        )

        return sorted_problems[:max_count]

    def filter_problems(
        self,
        problems: List[Problem],
        severity: Optional[ProblemSeverity] = None,
        problem_type: Optional[ProblemType] = None,
        auto_fixable: Optional[bool] = None,
        file_path: Optional[str] = None
    ) -> List[Problem]:
        """
        过滤问题

        Args:
            problems: 问题列表
            severity: 按严重程度过滤
            problem_type: 按问题类型过滤
            auto_fixable: 是否可自动修复
            file_path: 按文件路径过滤

        Returns:
            过滤后的问题列表
        """
        filtered = problems

        if severity:
            filtered = [p for p in filtered if p.severity == severity]

        if problem_type:
            filtered = [p for p in filtered if p.type == problem_type]

        if auto_fixable is not None:
            filtered = [p for p in filtered if p.auto_fixable == auto_fixable]

        if file_path:
            filtered = [p for p in filtered if p.file_path == file_path]

        return filtered

    def get_statistics(self, problems: List[Problem]) -> Dict:
        """
        获取问题统计信息

        Args:
            problems: 问题列表

        Returns:
            统计信息字典
        """
        stats = {
            'total': len(problems),
            'by_severity': {},
            'by_type': {},
            'auto_fixable': 0,
            'requires_approval': 0,
        }

        for problem in problems:
            # 按严重程度统计
            severity = problem.severity.value
            stats['by_severity'][severity] = stats['by_severity'].get(severity, 0) + 1

            # 按类型统计
            ptype = problem.type.value
            stats['by_type'][ptype] = stats['by_type'].get(ptype, 0) + 1

            # 可自动修复
            if problem.auto_fixable:
                stats['auto_fixable'] += 1

            # 需要批准
            if problem.requires_approval():
                stats['requires_approval'] += 1

        return stats

    def sort_by_priority(self, problems: List[Problem]) -> List[Problem]:
        """
        按优先级排序问题

        Args:
            problems: 问题列表

        Returns:
            排序后的问题列表
        """
        # 严重程度排序权重
        severity_weight = {
            'critical': 5,
            'high': 4,
            'medium': 3,
            'low': 2,
            'info': 1,
        }

        return sorted(
            problems,
            key=lambda p: (
                -severity_weight.get(p.severity.value, 0),  # 严重程度（降序）
                -len(p.suggestions) if p.suggestions else 0,  # 建议数量（降序）
                p.id  # ID（升序）
            )
        )

    def generate_report(self, problems: List[Problem]) -> str:
        """
        生成问题报告

        Args:
            problems: 问题列表

        Returns:
            报告文本
        """
        if not problems:
            return "未发现问题 ✅"

        stats = self.get_statistics(problems)
        prioritized = self.prioritize_problems(problems)

        lines = [
            "=" * 70,
            "问题扫描报告",
            "=" * 70,
            "",
            f"📊 统计信息:",
            f"   总计: {stats['total']} 个问题",
            f"   可自动修复: {stats['auto_fixable']} 个",
            f"   需要批准: {stats['requires_approval']} 个",
            "",
            f"按严重程度分布:",
        ]

        for severity in ['critical', 'high', 'medium', 'low', 'info']:
            count = stats['by_severity'].get(severity, 0)
            if count > 0:
                icon = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢', 'info': '🔵'}[severity]
                lines.append(f"   {icon} {severity.upper()}: {count}")

        lines.extend([
            "",
            "按类型分布:",
        ])

        for ptype, count in stats['by_type'].items():
            lines.append(f"   • {ptype}: {count}")

        lines.extend([
            "",
            "=" * 70,
            "Top 10 问题 (按优先级排序)",
            "=" * 70,
            "",
        ])

        for i, problem in enumerate(prioritized[:10], 1):
            severity_icon = {
                ProblemSeverity.CRITICAL: '🔴',
                ProblemSeverity.HIGH: '🟠',
                ProblemSeverity.MEDIUM: '🟡',
                ProblemSeverity.LOW: '🟢',
                ProblemSeverity.INFO: '🔵'
            }[problem.severity]

            fixable_icon = '✅' if problem.auto_fixable else '⚠️'

            lines.extend([
                f"{i}. {severity_icon} {fixable_icon} {problem.title}",
                f"   类型: {problem.type.value} | 严重: {problem.severity.value}",
                f"   描述: {problem.description[:100]}...",
            ])

            if problem.file_path:
                location = f"{problem.file_path}"
                if problem.line_number:
                    location += f":{problem.line_number}"
                lines.append(f"   位置: {location}")

            if problem.suggestions:
                lines.append(f"   建议: {problem.suggestions[0][:80]}...")

            lines.append("")

        lines.append("=" * 70)

        return "\n".join(lines)


# 全局扫描器实例
_global_scanner: Optional[ProblemScanner] = None


def get_problem_scanner() -> ProblemScanner:
    """获取全局问题扫描器实例"""
    global _global_scanner
    if _global_scanner is None:
        _global_scanner = ProblemScanner()
    return _global_scanner
