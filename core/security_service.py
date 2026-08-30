"""
安全防护模块

功能：
1. 注入攻击检测
2. 敏感词过滤
3. 速率限制
4. 内容安全检测

参考 Undefined 项目的安全防护设计
"""

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    """安全级别"""

    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    DANGEROUS = "dangerous"
    BLOCKED = "blocked"


@dataclass
class SecurityCheckResult:
    """安全检查结果"""

    level: SecurityLevel
    message: str
    blocked: bool = False
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class InjectionDetector:
    """
    注入攻击检测器

    检测常见的注入攻击模式：
    - Prompt Injection
    - SQL Injection
    - Code Injection
    - Command Injection
    """

    def __init__(self):
        # 注入模式
        self.injection_patterns = [
            # Prompt Injection
            r"(ignore|disregard|forget)\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)",
            r"(you\s+are|act\s+as|pretend\s+to\s+be)\s+(now\s+)?(a\s+)?(different|dANgerous)",
            r"system\s*prompt",
            r"#\s*instruction",
            r"<\s*system\s*>",
            r"\{\{.*\}\}",  # 模板注入
            # SQL Injection
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|TRUNCATE)\b.*\b(FROM|INTO|TABLE|WHERE)\b)",
            r"(--|#|/\*|\*/)",
            r"('\s*(OR|AND)\s*')",
            r"(EXEC(\(|UTE)|sp_executesql)",
            # Code Injection
            r"(eval|exec|compile|__import__|open|read|write|os\.system|subprocess)",
            r"(import\s+(os|sys|subprocess|requests|urllib))",
            r"(lambda\s+.*:.*\(|lambda\s+.*:.*\+)",
            r"(\bexec\s*\()",
            # Command Injection
            r"(;\s*(ls|cat|rm|wget|curl|bash|sh|cmd))",
            r"(\|\s*(ls|cat|rm|wget|curl|bash|sh|cmd))",
            r"(`.*`)",
            r"\$\(.*\)",
            # 尝试绕过
            r"(base64|ROT13|URL编码|unicode)",
            r"(\\x[0-9a-fA-F]{2})",
        ]

        self._patterns = [re.compile(p, re.IGNORECASE) for p in self.injection_patterns]

        # 可疑关键词
        self.suspicious_keywords = {
            "hack",
            "exploit",
            "bypass",
            "crack",
            "steal",
            "password",
            "credential",
            "token",
            "secret",
            "api_key",
            "sudo",
            "root",
            "admin",
            "privilege",
            "injection",
            "xss",
            "csrf",
            "vulnerability",
            "malware",
            "virus",
            "trojan",
            "backdoor",
        }

    def check(self, content: str) -> SecurityCheckResult:
        """
        检查内容是否包含注入攻击

        Args:
            content: 待检查的内容

        Returns:
            检查结果
        """
        if not content:
            return SecurityCheckResult(level=SecurityLevel.SAFE, message="内容为空")

        # 检查模式匹配
        for i, pattern in enumerate(self._patterns):
            match = pattern.search(content)
            if match:
                logger.warning(f"[InjectionDetector] 检测到注入模式: {self.injection_patterns[i][:50]}...")
                return SecurityCheckResult(
                    level=SecurityLevel.DANGEROUS,
                    message="检测到可疑注入模式",
                    blocked=True,
                    reason=f"pattern_{i}",
                    metadata={"matched": match.group()[:50]},
                )

        # 检查可疑关键词
        content_lower = content.lower()
        suspicious_found = [kw for kw in self.suspicious_keywords if kw in content_lower]

        if len(suspicious_found) >= 3:
            logger.warning(f"[InjectionDetector] 检测到可疑关键词: {suspicious_found}")
            return SecurityCheckResult(
                level=SecurityLevel.SUSPICIOUS,
                message=f"检测到 {len(suspicious_found)} 个可疑关键词",
                reason="suspicious_keywords",
                metadata={"keywords": suspicious_found},
            )

        return SecurityCheckResult(level=SecurityLevel.SAFE, message="未检测到注入攻击")


class SensitiveWordFilter:
    """
    敏感词过滤器

    检测和过滤敏感内容
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.sensitive_words: Set[str] = set()
        self.blocked_words: Set[str] = set()

        # 默认敏感词（简化示例）
        self._load_default_words()

        # 加载配置
        if config_path and config_path.exists():
            self._load_config(config_path)

    def _load_default_words(self):
        """加载默认敏感词"""
        # 这是一个简化示例，实际应该从配置文件加载
        self.sensitive_words = {
            # 政治相关（简化示例）
            "敏感词1",
            "敏感词2",
            # 色情相关
            "色情",
            "赌博",
            "毒品",
        }
        self.blocked_words = {
            # 直接阻断的词
            "暴力",
            "恐怖",
            "诈骗",
        }

    def _load_config(self, config_path: Path):
        """加载配置文件"""
        import json

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            self.sensitive_words.update(config.get("sensitive_words", []))
            self.blocked_words.update(config.get("blocked_words", []))

        except Exception as e:
            logger.error(f"[SensitiveWordFilter] 加载配置失败: {e}")

    def check(self, content: str) -> SecurityCheckResult:
        """
        检查敏感词

        Args:
            content: 待检查的内容

        Returns:
            检查结果
        """
        if not content:
            return SecurityCheckResult(level=SecurityLevel.SAFE, message="内容为空")

        content_lower = content.lower()

        # 检查阻断词
        for word in self.blocked_words:
            if word in content_lower:
                logger.warning(f"[SensitiveWordFilter] 检测到阻断词: {word}")
                return SecurityCheckResult(
                    level=SecurityLevel.BLOCKED,
                    message="检测到阻断词",
                    blocked=True,
                    reason="blocked_word",
                    metadata={"word": word},
                )

        # 检查敏感词
        found = [word for word in self.sensitive_words if word in content_lower]

        if found:
            return SecurityCheckResult(
                level=SecurityLevel.SUSPICIOUS,
                message="检测到敏感词",
                reason="sensitive_word",
                metadata={"words": found},
            )

        return SecurityCheckResult(level=SecurityLevel.SAFE, message="未检测到敏感词")

    def add_sensitive_word(self, word: str):
        """添加敏感词"""
        self.sensitive_words.add(word)

    def add_blocked_word(self, word: str):
        """添加阻断词"""
        self.blocked_words.add(word)


class RateLimiter:
    """
    速率限制器

    实现基于时间窗口的速率限制
    """

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        """
        初始化速率限制器

        Args:
            max_requests: 时间窗口内最大请求数
            window_seconds: 时间窗口大小（秒）
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds

        # 请求记录
        self._requests: Dict[str, List[float]] = {}

    def check(self, user_id: str) -> SecurityCheckResult:
        """
        检查用户请求频率

        Args:
            user_id: 用户ID

        Returns:
            检查结果
        """
        now = time.time()

        # 初始化用户记录
        if user_id not in self._requests:
            self._requests[user_id] = []

        # 清理过期记录
        self._requests[user_id] = [t for t in self._requests[user_id] if now - t < self.window_seconds]

        # 检查是否超限
        if len(self._requests[user_id]) >= self.max_requests:
            logger.warning(f"[RateLimiter] 用户 {user_id} 请求超限")
            return SecurityCheckResult(
                level=SecurityLevel.BLOCKED,
                message="请求过于频繁，请稍后再试",
                blocked=True,
                reason="rate_limit",
                metadata={
                    "requests": len(self._requests[user_id]),
                    "limit": self.max_requests,
                    "window": self.window_seconds,
                },
            )

        # 记录请求
        self._requests[user_id].append(now)

        return SecurityCheckResult(level=SecurityLevel.SAFE, message="请求频率正常")

    def reset(self, user_id: str):
        """重置用户限制"""
        if user_id in self._requests:
            self._requests[user_id] = []


class SecurityService:
    """
    安全服务

    整合注入检测、敏感词过滤和速率限制
    """

    def __init__(
        self,
        rate_limit_max: int = 30,
        rate_limit_window: int = 60,
    ):
        # 注入检测器
        self.injection_detector = InjectionDetector()

        # 敏感词过滤器
        self.sensitive_filter = SensitiveWordFilter()

        # 速率限制器
        self.rate_limiter = RateLimiter(rate_limit_max, rate_limit_window)

        # 统计
        self.stats = {
            "total_checks": 0,
            "blocked_count": 0,
            "suspicious_count": 0,
        }

        logger.info("[SecurityService] 安全服务初始化完成")

    def check(self, content: str, user_id: str) -> SecurityCheckResult:
        """
        执行安全检查

        Args:
            content: 待检查的内容
            user_id: 用户ID

        Returns:
            检查结果
        """
        self.stats["total_checks"] += 1

        # 1. 注入检测
        injection_result = self.injection_detector.check(content)
        if injection_result.level == SecurityLevel.DANGEROUS:
            self.stats["blocked_count"] += 1
            return injection_result

        # 2. 敏感词检测
        sensitive_result = self.sensitive_filter.check(content)
        if sensitive_result.level == SecurityLevel.BLOCKED:
            self.stats["blocked_count"] += 1
            return sensitive_result
        elif sensitive_result.level == SecurityLevel.SUSPICIOUS:
            self.stats["suspicious_count"] += 1

        # 3. 速率限制
        rate_result = self.rate_limiter.check(user_id)
        if rate_result.level == SecurityLevel.BLOCKED:
            self.stats["blocked_count"] += 1
            return rate_result

        # 4. 综合判断
        if injection_result.level == SecurityLevel.SUSPICIOUS:
            self.stats["suspicious_count"] += 1
            return injection_result

        return SecurityCheckResult(level=SecurityLevel.SAFE, message="安全检查通过")

    def get_stats(self) -> Dict[str, Any]:
        """获取安全统计"""
        return {
            **self.stats,
            "pass_rate": (
                (self.stats["total_checks"] - self.stats["blocked_count"]) / max(self.stats["total_checks"], 1) * 100
            ),
        }


# 全局实例
_global_security_service: Optional[SecurityService] = None


def get_global_security_service() -> SecurityService:
    """获取全局安全服务"""
    global _global_security_service

    if _global_security_service is None:
        _global_security_service = SecurityService()

    return _global_security_service
