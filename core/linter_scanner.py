"""
Linter 扫描器
扫描代码的 lint 错误和警告
"""
import logging
from typing import List, Dict, Optional, Any
from pathlib import Path
import asyncio

from core.problem_scanner import BaseScanner, Problem, ProblemType, ProblemSeverity


logger = logging.getLogger(__name__)


class LinterScanner(BaseScanner):
    """
    Linter 扫描器

    职责：
    1. 调用 read_lints 工具扫描 lint 错误
    2. 解析 lint 错误
    3. 转换为 Problem 对象
    4. 分类和优先级排序
    """

    def __init__(self):
        super().__init__("linter")
        self._tool_executor = None

    def set_tool_executor(self, executor):
        """设置工具执行器"""
        self._tool_executor = executor
        self.logger.debug("工具执行器已设置")

    async def scan(self, path: str = '.', **kwargs) -> List[Problem]:
        """
        扫描 lint 错误

        Args:
            path: 扫描路径
            **kwargs: 其他参数

        Returns:
            发现的问题列表
        """
        self.logger.info(f"开始 Linter 扫描: {path}")

        problems = []

        try:
            # 调用 read_lints 工具
            linter_results = await self._read_lints(path)

            # 转换为 Problem 对象
            for result in linter_results:
                problem = self._parse_linter_result(result)
                if problem:
                    problems.append(problem)

            self.logger.info(f"Linter 扫描完成，发现 {len(problems)} 个问题")

        except Exception as e:
            self.logger.error(f"Linter 扫描失败: {e}", exc_info=True)

        self._problems = problems
        return problems

    async def _read_lints(self, path: str) -> List[Dict]:
        """
        读取 lint 错误

        Args:
            path: 扫描路径

        Returns:
            Linter 错误列表
        """
        if not self._tool_executor:
            self.logger.warning("工具执行器未设置，尝试直接调用")
            return await self._read_lints_direct(path)

        try:
            # 使用工具执行器调用 read_lints
            result = await self._tool_executor('read_lints', {'paths': path})
            return self._parse_lints_response(result)
        except Exception as e:
            self.logger.error(f"通过工具执行器调用 read_lints 失败: {e}")
            # 降级：尝试直接调用
            return await self._read_lints_direct(path)

    async def _read_lints_direct(self, path: str) -> List[Dict]:
        """
        直接读取 lint 错误（降级方案）

        Args:
            path: 扫描路径

        Returns:
            Linter 错误列表
        """
        # 这里模拟一些 lint 错误，实际应该调用真实的 linter
        # 在真实环境中，这里会调用 IDE 的 linter 接口
        return []

    def _parse_lints_response(self, response: str) -> List[Dict]:
        """
        解析 lints 响应

        Args:
            response: read_lints 的响应

        Returns:
            解析后的错误列表
        """
        # 解析响应，提取错误信息
        # 这里需要根据实际的响应格式进行解析
        linter_errors = []

        # 示例解析逻辑（需要根据实际响应调整）
        try:
            import json
            if response.startswith('{'):
                data = json.loads(response)
                linter_errors = data.get('errors', [])
            else:
                # 文本格式解析
                for line in response.split('\n'):
                    if ':' in line and 'error' in line.lower():
                        # 解析类似 "file.py:10: error: message" 的格式
                        parts = line.split(':', 3)
                        if len(parts) >= 4:
                            linter_errors.append({
                                'file': parts[0].strip(),
                                'line': int(parts[1]),
                                'column': int(parts[2]),
                                'message': parts[3].strip()
                            })
        except Exception as e:
            self.logger.warning(f"解析 lints 响应失败: {e}")

        return linter_errors

    def _parse_linter_result(self, result: Dict) -> Optional[Problem]:
        """
        解析单个 linter 结果为 Problem 对象

        Args:
            result: linter 错误字典

        Returns:
            Problem 对象，如果解析失败则返回 None
        """
        try:
            file_path = result.get('file', '')
            line_number = result.get('line')
            message = result.get('message', '')
            severity = result.get('severity', 'error')

            # 转换严重程度
            severity_map = {
                'error': ProblemSeverity.HIGH,
                'warning': ProblemSeverity.MEDIUM,
                'info': ProblemSeverity.LOW,
            }
            problem_severity = severity_map.get(severity.lower(), ProblemSeverity.MEDIUM)

            # 生成建议
            suggestions = self._generate_suggestions(message, file_path)

            # 判断是否可自动修复
            auto_fixable = self._is_auto_fixable(message, file_path)

            problem = Problem(
                id="",  # 会在 ProblemScanner 中生成
                type=ProblemType.LINTER,
                severity=problem_severity,
                title=f"Linter 错误: {message[:50]}",
                description=message,
                file_path=file_path,
                line_number=line_number,
                suggestions=suggestions,
                auto_fixable=auto_fixable,
                confidence=0.9,
                metadata={
                    'linter_type': result.get('linter', 'unknown'),
                    'rule_id': result.get('rule', 'unknown'),
                }
            )

            return problem

        except Exception as e:
            self.logger.error(f"解析 linter 结果失败: {e}")
            return None

    def _generate_suggestions(self, message: str, file_path: str) -> List[str]:
        """
        生成修复建议

        Args:
            message: 错误消息
            file_path: 文件路径

        Returns:
            建议列表
        """
        suggestions = []

        # 基于常见错误模式生成建议
        lower_message = message.lower()

        if 'unused import' in lower_message:
            suggestions.append("删除未使用的 import 语句")
        elif 'undefined variable' in lower_message:
            suggestions.append("检查变量是否已定义或导入")
        elif 'missing module' in lower_message:
            suggestions.append("安装缺失的模块或检查导入路径")
        elif 'syntax error' in lower_message:
            suggestions.append("检查代码语法，确保括号、引号等匹配")
        elif 'indentation' in lower_message:
            suggestions.append("检查代码缩进，使用一致的缩进风格")
        else:
            suggestions.append("根据错误提示修改代码")

        return suggestions

    def _is_auto_fixable(self, message: str, file_path: str) -> bool:
        """
        判断是否可自动修复

        Args:
            message: 错误消息
            file_path: 文件路径

        Returns:
            是否可自动修复
        """
        # 某些错误类型可以自动修复
        auto_fixable_patterns = [
            'unused import',
            'unused variable',
            'trailing whitespace',
            'missing newline',
            'missing whitespace',
        ]

        lower_message = message.lower()
        return any(pattern in lower_message for pattern in auto_fixable_patterns)

    def is_supported_path(self, path: str) -> bool:
        """
        判断路径是否支持 linter 检查

        Args:
            path: 文件路径

        Returns:
            是否支持
        """
        # 支持的文件扩展名
        supported_extensions = [
            '.py',   # Python
            '.js',   # JavaScript
            '.ts',   # TypeScript
            '.jsx',  # React JSX
            '.tsx',  # React TSX
            '.go',   # Go
            '.java', # Java
            '.c',    # C
            '.cpp',  # C++
            '.rs',   # Rust
            '.rb',   # Ruby
            '.php',  # PHP
        ]

        path_obj = Path(path)

        # 如果是目录，支持
        if path_obj.is_dir():
            return True

        # 如果是文件，检查扩展名
        if path_obj.is_file():
            return path_obj.suffix.lower() in supported_extensions

        return False

    def get_linter_types(self) -> List[str]:
        """
        获取可用的 linter 类型

        Returns:
            linter 类型列表
        """
        # 常见的 linter 类型
        return [
            'pylint',     # Python
            'flake8',     # Python
            'mypy',       # Python (类型检查)
            'eslint',     # JavaScript/TypeScript
            'tslint',     # TypeScript
            'golangci-lint',  # Go
            'checkstyle', # Java
            'clang-tidy', # C/C++
            'clippy',     # Rust
        ]
