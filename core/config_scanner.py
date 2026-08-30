"""
配置扫描器
扫描配置文件问题
"""
import logging
from typing import List, Dict, Optional, Any
from pathlib import Path
import json
import re


logger = logging.getLogger(__name__)


from core.problem_scanner import BaseScanner, Problem, ProblemType, ProblemSeverity


class ConfigScanner(BaseScanner):
    """
    配置扫描器

    职责：
    1. 扫描配置文件（.env, config.json, .ini 等）
    2. 检测配置错误
    3. 检测安全问题（如硬编码密码）
    4. 检测过时配置
    """

    def __init__(self):
        super().__init__("config")
        self._config_patterns = {
            '.env': self._scan_env_file,
            '.json': self._scan_json_file,
            '.yaml': self._scan_yaml_file,
            '.yml': self._scan_yaml_file,
            '.ini': self._scan_ini_file,
            '.toml': self._scan_toml_file,
        }

        # 常见的敏感配置键
        self._sensitive_keys = [
            'password', 'passwd', 'pwd',
            'secret', 'api_key', 'apikey', 'api-key',
            'token', 'access_token', 'refresh_token',
            'private_key', 'private_key', 'privatekey',
            'auth', 'authorization',
        ]

    async def scan(self, path: str = '.', **kwargs) -> List[Problem]:
        """
        扫描配置问题

        Args:
            path: 扫描路径
            **kwargs: 其他参数

        Returns:
            发现的问题列表
        """
        self.logger.info(f"开始配置扫描: {path}")

        problems = []

        try:
            path_obj = Path(path)

            # 查找所有配置文件
            config_files = []
            for pattern in self._config_patterns.keys():
                config_files.extend(path_obj.glob(f"**/*{pattern}"))

            # 排除 .git 目录和 node_modules
            config_files = [
                f for f in config_files
                if '.git' not in str(f) and 'node_modules' not in str(f)
            ]

            # 扫描每个配置文件
            for config_file in config_files:
                file_problems = await self._scan_config_file(config_file)
                problems.extend(file_problems)

            self.logger.info(f"配置扫描完成，发现 {len(problems)} 个问题")

        except Exception as e:
            self.logger.error(f"配置扫描失败: {e}", exc_info=True)

        self._problems = problems
        return problems

    async def _scan_config_file(self, config_file: Path) -> List[Problem]:
        """
        扫描单个配置文件

        Args:
            config_file: 配置文件路径

        Returns:
            发现的问题列表
        """
        suffix = config_file.suffix.lower()

        scanner_func = self._config_patterns.get(suffix)
        if not scanner_func:
            return []

        try:
            return scanner_func(config_file)
        except Exception as e:
            self.logger.warning(f"扫描 {config_file} 失败: {e}")
            return []

    def _scan_env_file(self, env_file: Path) -> List[Problem]:
        """扫描 .env 文件"""
        problems = []

        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for i, line in enumerate(lines, 1):
                line = line.strip()

                # 跳过注释和空行
                if not line or line.startswith('#'):
                    continue

                # 检查等号
                if '=' not in line:
                    problems.append(Problem(
                        id="",
                        type=ProblemType.CONFIG,
                        severity=ProblemSeverity.MEDIUM,
                        title=f"无效的环境变量格式: {line[:50]}",
                        description=f".env 文件第 {i} 行缺少等号或格式不正确",
                        file_path=str(env_file),
                        line_number=i,
                        suggestions=["使用 KEY=VALUE 格式"],
                        auto_fixable=True,
                        confidence=0.8,
                    ))
                    continue

                key, value = line.split('=', 1)

                # 检查敏感信息
                if self._is_sensitive_key(key) and value:
                    problems.append(Problem(
                        id="",
                        type=ProblemType.SECURITY,
                        severity=ProblemSeverity.HIGH,
                        title=f"敏感信息泄露: {key}",
                        description=f".env 文件中包含敏感配置项，建议使用环境变量或密钥管理服务",
                        file_path=str(env_file),
                        line_number=i,
                        suggestions=["使用密钥管理服务（如 AWS Secrets Manager, HashiCorp Vault）", "确保 .env 在 .gitignore 中"],
                        auto_fixable=False,
                        confidence=0.9,
                        metadata={'sensitive_key': key}
                    ))

                # 检查硬编码值
                if self._is_hardcoded_value(value):
                    problems.append(Problem(
                        id="",
                        type=ProblemType.SECURITY,
                        severity=ProblemSeverity.MEDIUM,
                        title=f"可能的硬编码值: {key}",
                        description=f".env 文件中可能包含硬编码的凭证",
                        file_path=str(env_file),
                        line_number=i,
                        suggestions=["使用占位符或从密钥管理服务读取"],
                        auto_fixable=False,
                        confidence=0.6,
                    ))

        except Exception as e:
            self.logger.warning(f"分析 {env_file} 失败: {e}")

        return problems

    def _scan_json_file(self, json_file: Path) -> List[Problem]:
        """扫描 JSON 配置文件"""
        problems = []

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 检查 JSON 语法
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                problems.append(Problem(
                    id="",
                    type=ProblemType.CONFIG,
                    severity=ProblemSeverity.HIGH,
                    title=f"JSON 语法错误: {json_file.name}",
                    description=f"JSON 文件解析失败: {str(e)}",
                    file_path=str(json_file),
                    suggestions=["修复 JSON 语法错误", "使用 JSON 验证工具检查"],
                    auto_fixable=False,
                    confidence=1.0,
                ))
                return problems

            # 检查敏感信息
            sensitive_issues = self._check_sensitive_in_dict(data, str(json_file))
            problems.extend(sensitive_issues)

        except Exception as e:
            self.logger.warning(f"分析 {json_file} 失败: {e}")

        return problems

    def _scan_yaml_file(self, yaml_file: Path) -> List[Problem]:
        """扫描 YAML 配置文件"""
        problems = []

        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 检查 YAML 基本语法（简化版）
            if content.count('---') > 1:
                problems.append(Problem(
                    id="",
                    type=ProblemType.CONFIG,
                    severity=ProblemSeverity.LOW,
                    title=f"多文档 YAML: {yaml_file.name}",
                    description=f"YAML 文件包含多个文档分隔符 (---)",
                    file_path=str(yaml_file),
                    suggestions=["确认是否需要多个文档", "考虑拆分为单独的文件"],
                    auto_fixable=False,
                    confidence=0.5,
                ))

        except Exception as e:
            self.logger.warning(f"分析 {yaml_file} 失败: {e}")

        return problems

    def _scan_ini_file(self, ini_file: Path) -> List[Problem]:
        """扫描 INI 配置文件"""
        problems = []

        try:
            with open(ini_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for i, line in enumerate(lines, 1):
                line_stripped = line.strip()

                # 跳过注释和空行
                if not line_stripped or line_stripped.startswith('#') or line_stripped.startswith(';'):
                    continue

                # 检查键值对格式
                if '=' not in line_stripped and ':' not in line_stripped:
                    # 可能是节标题 [section]
                    if not (line_stripped.startswith('[') and line_stripped.endswith(']')):
                        problems.append(Problem(
                            id="",
                            type=ProblemType.CONFIG,
                            severity=ProblemSeverity.LOW,
                            title=f"无效的 INI 格式: {line[:50]}",
                            description=f"INI 文件第 {i} 行格式不正确",
                            file_path=str(ini_file),
                            line_number=i,
                            suggestions=["使用 KEY=VALUE 或 [section] 格式"],
                            auto_fixable=True,
                            confidence=0.7,
                        ))

        except Exception as e:
            self.logger.warning(f"分析 {ini_file} 失败: {e}")

        return problems

    def _scan_toml_file(self, toml_file: Path) -> List[Problem]:
        """扫描 TOML 配置文件"""
        problems = []

        try:
            with open(toml_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 检查基本 TOML 语法（简化版）
            # TOML 需要 key = value 格式
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                line_stripped = line.strip()

                # 跳过注释和空行
                if not line_stripped or line_stripped.startswith('#'):
                    continue

                # 检查键值对格式
                if '=' in line_stripped and not line_stripped.startswith('['):
                    # 应该使用等号而不是冒号
                    if ':' in line_stripped and line_stripped.index(':') < line_stripped.index('='):
                        problems.append(Problem(
                            id="",
                            type=ProblemType.CONFIG,
                            severity=ProblemSeverity.MEDIUM,
                            title=f"可能的 TOML 语法错误",
                            description=f"TOML 使用等号 (=) 而不是冒号 (:)",
                            file_path=str(toml_file),
                            line_number=i,
                            suggestions=["将冒号 (:) 替换为等号 (=)"],
                            auto_fixable=True,
                            confidence=0.8,
                        ))

        except Exception as e:
            self.logger.warning(f"分析 {toml_file} 失败: {e}")

        return problems

    def _is_sensitive_key(self, key: str) -> bool:
        """检查是否是敏感配置键"""
        key_lower = key.lower()
        return any(sensitive in key_lower for sensitive in self._sensitive_keys)

    def _is_hardcoded_value(self, value: str) -> bool:
        """检查是否是硬编码的值"""
        # 简单启发式：检查是否像密码或密钥
        if not value:
            return False

        # 检查长度和复杂度
        if len(value) > 20 and re.search(r'[A-Z]', value) and re.search(r'[0-9]', value):
            return True

        # 检查常见的密码模式
        if re.match(r'^[A-Za-z0-9+/=]{20,}$', value):
            return True

        return False

    def _check_sensitive_in_dict(
        self,
        data: Any,
        file_path: str,
        prefix: str = ""
    ) -> List[Problem]:
        """
        递归检查字典中的敏感信息

        Args:
            data: 数据（字典或列表）
            file_path: 文件路径
            prefix: 键前缀

        Returns:
            发现的问题列表
        """
        problems = []

        if isinstance(data, dict):
            for key, value in data.items():
                current_key = f"{prefix}.{key}" if prefix else key

                if self._is_sensitive_key(key):
                    problems.append(Problem(
                        id="",
                        type=ProblemType.SECURITY,
                        severity=ProblemSeverity.HIGH,
                        title=f"敏感信息泄露: {key}",
                        description=f"配置文件中包含敏感配置项: {current_key}",
                        file_path=file_path,
                        suggestions=["移除敏感信息或使用占位符", "使用环境变量"],
                        auto_fixable=False,
                        confidence=0.9,
                    ))

                # 递归检查嵌套结构
                if isinstance(value, (dict, list)):
                    problems.extend(
                        self._check_sensitive_in_dict(value, file_path, current_key)
                    )

        elif isinstance(data, list):
            for i, item in enumerate(data):
                current_key = f"{prefix}[{i}]"
                if isinstance(item, (dict, list)):
                    problems.extend(
                        self._check_sensitive_in_dict(item, file_path, current_key)
                    )

        return problems
