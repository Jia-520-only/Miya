"""
安全审计模块
提供命令安全验证和风险评估
"""
import logging
from typing import List, Dict, Optional, Tuple
from enum import Enum
import re

logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    """安全等级"""
    READ = "read"                    # 只读操作，安全
    WRITE = "write"                  # 写入操作，需要确认
    DANGEROUS = "dangerous"          # 危险操作，需要严格确认


class SecurityAuditor:
    """安全审计器 - 验证命令安全性"""

    def __init__(self, security_level: str = "safe"):
        """
        初始化安全审计器

        Args:
            security_level: 安全等级 (safe/strict/permissive)
        """
        self.security_level = security_level

        # 危险命令黑名单（正则表达式）
        self.blacklist = [
            r'rm\s+-rf\s+/',           # rm -rf / (删除根目录)
            r'dd\s+if=/dev/zero',     # dd 擦除硬盘
            r'mkfs\s+',                # 格式化文件系统
            r':\s*\( :\)\{\ :\|\:& \};:',  # fork bomb
            r'>\s*/dev/sd[a-z]',       # 直接写入硬盘
            r'format\s+[C-Z]:',        # Windows 格式化磁盘
            r'del\s+/f\s+[C-Z]:',      # Windows 删除系统文件
        ]

        # 命令白名单（按安全等级分类）
        self.whitelist = self._build_whitelist()

    def _build_whitelist(self) -> Dict[str, List[str]]:
        """构建命令白名单"""
        return {
            'read': [
                # 基础查看命令
                'ls', 'dir', 'pwd', 'cd',
                'cat', 'more', 'less', 'head', 'tail',
                'grep', 'find', 'where', 'which',

                # Git 只读命令
                'git log', 'git show', 'git diff', 'git status',
                'git branch', 'git remote', 'git tag',

                # 系统信息
                'ps', 'top', 'df', 'du', 'free', 'uptime',
                'uname', 'hostname', 'date', 'whoami',

                # 网络命令
                'ping', 'traceroute', 'nslookup', 'netstat', 'ifconfig',

                # Windows 对应命令
                'Get-ChildItem', 'Get-Location', 'Set-Location',
                'Get-Content', 'Select-String', 'Get-Process',
                'Test-Connection', 'Get-NetIPConfiguration', 'Get-NetTCPConnection',
            ],
            'write': [
                # 文件操作
                'touch', 'mkdir', 'cp', 'mv', 'copy', 'move',
                'echo', 'printf', 'printf', 'tee',

                # Git 写入命令
                'git add', 'git commit', 'git push', 'git pull',
                'git checkout', 'git merge', 'git rebase',

                # Windows 对应命令
                'New-Item', 'Copy-Item', 'Move-Item',
            ],
            'dangerous': [
                # 删除命令
                'rm', 'rmdir', 'del', 'erase',
                'Remove-Item',

                # 系统管理
                'kill', 'pkill', 'killall',
                'Stop-Process',

                # 权限提升
                'sudo', 'su',

                # 系统配置
                'chmod', 'chown', 'chgrp',
            ]
        }

    def audit(self, command: str) -> Tuple[SecurityLevel, Optional[str]]:
        """
        审计命令安全性

        Args:
            command: 待审计的命令

        Returns:
            Tuple[SecurityLevel, Optional[str]]: (安全等级, 警告信息)
        """
        # 1. 检查黑名单
        for pattern in self.blacklist:
            if re.search(pattern, command):
                logger.warning(f"检测到危险命令: {command}")
                return SecurityLevel.DANGEROUS, f"检测到危险命令，可能造成系统损坏: {command}"

        # 2. 检查白名单
        cmd = command.split()[0] if command else ""

        # 检查危险命令
        for dangerous_cmd in self.whitelist['dangerous']:
            if dangerous_cmd == cmd or command.startswith(dangerous_cmd):
                logger.warning(f"检测到危险操作: {command}")
                return SecurityLevel.DANGEROUS, f"危险操作，请确认: {command}"

        # 检查写入命令
        for write_cmd in self.whitelist['write']:
            if write_cmd == cmd or command.startswith(write_cmd):
                logger.info(f"检测到写入操作: {command}")
                return SecurityLevel.WRITE, f"写入操作，请确认: {command}"

        # 检查只读命令
        for read_cmd in self.whitelist['read']:
            if read_cmd == cmd or command.startswith(read_cmd):
                logger.debug(f"检测到只读操作: {command}")
                return SecurityLevel.READ, None

        # 未在白名单中的命令，默认为写入操作
        logger.info(f"未分类命令: {command}")
        return SecurityLevel.WRITE, f"未分类命令，请谨慎执行: {command}"

    def is_safe(self, command: str) -> bool:
        """
        检查命令是否安全（只读操作）

        Args:
            command: 待检查的命令

        Returns:
            bool: 是否安全
        """
        level, _ = self.audit(command)
        return level == SecurityLevel.READ

    def is_dangerous(self, command: str) -> bool:
        """
        检查命令是否危险

        Args:
            command: 待检查的命令

        Returns:
            bool: 是否危险
        """
        level, _ = self.audit(command)
        return level == SecurityLevel.DANGEROUS

    def needs_confirmation(self, command: str) -> bool:
        """
        检查命令是否需要确认

        Args:
            command: 待检查的命令

        Returns:
            bool: 是否需要确认
        """
        level, _ = self.audit(command)
        return level in [SecurityLevel.WRITE, SecurityLevel.DANGEROUS]

    def get_safety_description(self, command: str) -> str:
        """
        获取命令安全描述

        Args:
            command: 待描述的命令

        Returns:
            str: 安全描述
        """
        level, warning = self.audit(command)

        if level == SecurityLevel.READ:
            return "✅ 只读操作 - 安全"
        elif level == SecurityLevel.WRITE:
            return f"⚠️ 写入操作 - 需要确认 ({warning})"
        else:
            return f"🚨 危险操作 - 需要严格确认 ({warning})"
