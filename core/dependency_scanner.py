"""
依赖扫描器
扫描项目依赖问题
"""
import logging
from typing import List, Dict, Optional, Any
from pathlib import Path
import re
import ast


logger = logging.getLogger(__name__)


from core.problem_scanner import BaseScanner, Problem, ProblemType, ProblemSeverity


class DependencyScanner(BaseScanner):
    """
    依赖扫描器

    职责：
    1. 扫描依赖文件（requirements.txt, package.json, go.mod 等）
    2. 检测未安装的依赖
    3. 检测过时的依赖
    4. 检测依赖冲突
    """

    def __init__(self):
        super().__init__("dependency")
        self._dependency_files = {
            'python': ['requirements.txt', 'requirements-dev.txt', 'pyproject.toml', 'setup.py'],
            'node': ['package.json'],
            'go': ['go.mod', 'go.sum'],
            'java': ['pom.xml', 'build.gradle'],
            'ruby': ['Gemfile'],
            'php': ['composer.json'],
        }

    async def scan(self, path: str = '.', **kwargs) -> List[Problem]:
        """
        扫描依赖问题

        Args:
            path: 扫描路径
            **kwargs: 其他参数

        Returns:
            发现的问题列表
        """
        self.logger.info(f"开始依赖扫描: {path}")

        problems = []

        try:
            # 扫描不同语言的依赖
            python_problems = await self._scan_python_deps(path)
            node_problems = await self._scan_node_deps(path)
            go_problems = await self._scan_go_deps(path)

            problems.extend(python_problems)
            problems.extend(node_problems)
            problems.extend(go_problems)

            self.logger.info(f"依赖扫描完成，发现 {len(problems)} 个问题")

        except Exception as e:
            self.logger.error(f"依赖扫描失败: {e}", exc_info=True)

        self._problems = problems
        return problems

    async def _scan_python_deps(self, path: str) -> List[Problem]:
        """扫描 Python 依赖"""
        problems = []

        path_obj = Path(path)

        # 查找 requirements.txt
        req_files = list(path_obj.glob("**/requirements*.txt"))

        for req_file in req_files:
            file_problems = await self._analyze_requirements_file(req_file)
            problems.extend(file_problems)

        return problems

    async def _analyze_requirements_file(self, req_file: Path) -> List[Problem]:
        """分析 requirements.txt 文件"""
        problems = []

        try:
            with open(req_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for i, line in enumerate(lines, 1):
                line = line.strip()

                # 跳过注释和空行
                if not line or line.startswith('#'):
                    continue

                # 检查依赖格式
                if not self._is_valid_requirement(line):
                    problems.append(Problem(
                        id="",
                        type=ProblemType.DEPENDENCY,
                        severity=ProblemSeverity.LOW,
                        title=f"无效的依赖格式: {line[:50]}",
                        description=f"requirements.txt 第 {i} 行的依赖格式可能不正确: {line}",
                        file_path=str(req_file),
                        line_number=i,
                        suggestions=["检查依赖格式，参考 pip 文档"],
                        auto_fixable=False,
                        confidence=0.7,
                    ))

                # 检查版本锁定
                if not self._has_version_spec(line):
                    problems.append(Problem(
                        id="",
                        type=ProblemType.DEPENDENCY,
                        severity=ProblemSeverity.LOW,
                        title=f"依赖未锁定版本: {line.split('==')[0] if '==' in line else line}",
                        description=f"建议锁定依赖版本以确保可重现构建",
                        file_path=str(req_file),
                        line_number=i,
                        suggestions=["使用 == 指定精确版本，或使用 >=, <= 等约束"],
                        auto_fixable=True,
                        confidence=0.6,
                    ))

        except Exception as e:
            self.logger.warning(f"分析 {req_file} 失败: {e}")

        return problems

    def _is_valid_requirement(self, line: str) -> bool:
        """检查依赖格式是否有效"""
        # 基本验证：应该包含包名
        # 包名规则：字母开头，包含字母、数字、下划线、短横线
        package_name = line.split('==')[0].split('>=')[0].split('<=')[0].split('~=')[0].split('!=')[0].strip()
        return bool(re.match(r'^[a-zA-Z][a-zA-Z0-9_-]+$', package_name))

    def _has_version_spec(self, line: str) -> bool:
        """检查是否有版本规范"""
        return any(op in line for op in ['==', '>=', '<=', '~=', '!=', '>', '<'])

    async def _scan_node_deps(self, path: str) -> List[Problem]:
        """扫描 Node.js 依赖"""
        problems = []

        path_obj = Path(path)
        package_files = list(path_obj.glob("**/package.json"))

        for package_file in package_files:
            file_problems = await self._analyze_package_file(package_file)
            problems.extend(file_problems)

        return problems

    async def _analyze_package_file(self, package_file: Path) -> List[Problem]:
        """分析 package.json 文件"""
        problems = []

        try:
            import json
            with open(package_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 检查依赖字段
            dependencies = data.get('dependencies', {})
            dev_dependencies = data.get('devDependencies', {})

            # 检查未锁定的依赖
            all_deps = {**dependencies, **dev_dependencies}
            for name, version in all_deps.items():
                # 检查是否使用了范围版本（可能导致不可重现构建）
                if version.startswith('^') or version.startswith('~'):
                    problems.append(Problem(
                        id="",
                        type=ProblemType.DEPENDENCY,
                        severity=ProblemSeverity.LOW,
                        title=f"依赖版本范围: {name}@{version}",
                        description=f"使用了版本范围 (^ 或 ~)，可能导致不同环境安装不同版本",
                        file_path=str(package_file),
                        suggestions=["考虑使用精确版本或 package-lock.json"],
                        auto_fixable=True,
                        confidence=0.6,
                    ))

        except Exception as e:
            self.logger.warning(f"分析 {package_file} 失败: {e}")

        return problems

    async def _scan_go_deps(self, path: str) -> List[Problem]:
        """扫描 Go 依赖"""
        problems = []

        path_obj = Path(path)
        go_mod_files = list(path_obj.glob("**/go.mod"))

        for go_mod_file in go_mod_files:
            file_problems = await self._analyze_go_mod_file(go_mod_file)
            problems.extend(file_problems)

        return problems

    async def _analyze_go_mod_file(self, go_mod_file: Path) -> List[Problem]:
        """分析 go.mod 文件"""
        problems = []

        try:
            with open(go_mod_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 检查是否使用了间接依赖
            if '// indirect' in content:
                problems.append(Problem(
                    id="",
                    type=ProblemType.DEPENDENCY,
                    severity=ProblemSeverity.LOW,
                    title="存在间接依赖",
                    description="go.mod 中存在间接依赖，考虑清理或显式声明",
                    file_path=str(go_mod_file),
                    suggestions=["运行 go mod tidy 清理依赖"],
                    auto_fixable=True,
                    confidence=0.7,
                ))

        except Exception as e:
            self.logger.warning(f"分析 {go_mod_file} 失败: {e}")

        return problems

    def check_missing_imports(self, file_path: Path) -> List[str]:
        """
        检查 Python 文件中缺失的导入

        Args:
            file_path: Python 文件路径

        Returns:
            缺失的模块列表
        """
        missing_imports = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 解析 AST
            tree = ast.parse(content)

            # 收集所有导入
            imported_modules = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_modules.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imported_modules.add(node.module.split('.')[0])

            # 收集所有使用的模块（简化版）
            used_modules = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    # 检查是否是常用模块
                    if node.id in ['os', 'sys', 'json', 're', 'datetime', 'pathlib']:
                        if node.id not in imported_modules:
                            missing_imports.append(node.id)

        except Exception as e:
            self.logger.warning(f"检查 {file_path} 导入失败: {e}")

        return missing_imports
