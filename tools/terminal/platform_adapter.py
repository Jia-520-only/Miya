"""
平台适配器模块
为不同平台提供统一的命令接口
"""
import subprocess
import shlex
import logging
import os
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

from .platform_detector import Platform, detect_platform

logger = logging.getLogger(__name__)


class PlatformAdapter(ABC):
    """平台适配器基类"""

    def __init__(self):
        self.platform = detect_platform()

    @abstractmethod
    def execute_command(self, command: str, timeout: int = 30) -> Tuple[int, str, str]:
        """
        执行命令

        Args:
            command: 命令字符串
            timeout: 超时时间（秒）

        Returns:
            Tuple[int, str, str]: (返回码, 标准输出, 错误输出)
        """
        pass

    @abstractmethod
    def translate_command(self, command: str, target_platform: Optional[Platform] = None) -> str:
        """
        命令翻译（跨平台转换）

        Args:
            command: 原始命令
            target_platform: 目标平台（None 表示当前平台）

        Returns:
            str: 翻译后的命令
        """
        pass

    @abstractmethod
    def get_shell_command(self, command: str) -> str:
        """
        获取适合当前平台的 shell 命令

        Args:
            command: 命令字符串

        Returns:
            str: 完整的 shell 命令
        """
        pass


class WindowsAdapter(PlatformAdapter):
    """Windows 平台适配器（PowerShell）"""

    def __init__(self):
        super().__init__()
        logger.info("初始化 Windows 适配器 (PowerShell)")

    def execute_command(self, command: str, timeout: int = 30) -> Tuple[int, str, str]:
        """执行 PowerShell 命令"""
        try:
            # 展开路径中的 ~ 符号
            expanded_command = self._expand_home_directory(command)
            # 转换为 PowerShell 命令
            ps_command = self.translate_command(expanded_command)

            logger.debug(f"执行 PowerShell 命令: {ps_command}")

            # 执行命令
            result = subprocess.run(
                ['powershell', '-Command', ps_command],
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='replace'
            )

            return result.returncode, result.stdout, result.stderr

        except subprocess.TimeoutExpired:
            return -1, "", f"命令执行超时（{timeout}秒）"
        except Exception as e:
            return -1, "", f"命令执行失败: {str(e)}"

    def _expand_home_directory(self, command: str) -> str:
        """
        展开命令中的 ~ 路径和特殊目录别名

        Windows:
        - ~ -> C:/Users/用户名
        - ~/Desktop -> [Environment]::GetFolderPath('Desktop')
        - ~/Documents -> C:/Users/用户名/Documents
        - 桌面/文件.txt -> [Environment]::GetFolderPath('Desktop')/文件.txt
        - 桌面上的文件.txt -> [Environment]::GetFolderPath('Desktop')/文件.txt

        Args:
            command: 原始命令

        Returns:
            str: 展开路径后的命令
        """
        import re

        # 获取用户主目录
        home_dir = os.path.expanduser('~')
        if not home_dir or home_dir == '~':
            home_dir = os.environ.get('USERPROFILE', 'C:/Users/Default')

        # 获取桌面路径（使用环境变量获取真实路径）
        desktop_path = os.environ.get('USERPROFILE', 'C:/Users/Default') + '\\Desktop'

        # 修复 PowerShell 环境变量问题：将 %USERNAME% 替换为实际用户名
        # 匹配 C:\Users\%USERNAME%\Desktop 或类似模式
        username = os.environ.get('USERNAME', 'Default')
        command = re.sub(
            r'C:\\Users\\%USERNAME%\\Desktop',
            os.path.join(home_dir, 'Desktop').replace('\\', '\\\\'),
            command
        )
        command = re.sub(
            r'C:\\Users\\%USERNAME%',
            home_dir.replace('\\', '\\\\'),
            command
        )

        # 特殊处理:中文"桌面"目录别名
        # 匹配 "桌面/文件.txt" 或 "桌面上的文件.txt" 或 "桌面\文件.txt"
        quote = '"'
        command = re.sub(
            r'桌面[/\\]([^"\s]+|"[^"]+")',
            lambda m: f'{quote}{os.path.join(desktop_path, m.group(1).strip(quote))}{quote}' if quote in m.group(1) else os.path.join(desktop_path, m.group(1).strip(quote)),
            command
        )

        # 匹配 "桌面上的文件.txt"
        command = re.sub(
            r'桌面上的([^"\s]+|"[^"]+")',
            lambda m: f'{quote}{os.path.join(desktop_path, m.group(1).strip(quote))}{quote}' if quote in m.group(1) else os.path.join(desktop_path, m.group(1).strip(quote)),
            command
        )

        # 替换 ~/路径（保留引号）
        # 匹配 "~/Desktop", ~/Documents, ~/"路径" 等
        pattern = r'~[/\\]([^\s"]+|"[^"]+")'
        def replace_home(m):
            path = m.group(1).strip('"')
            expanded = os.path.join(home_dir, path)
            # 如果原始有引号，保持引号
            return f'"{expanded}"' if '"' in m.group(1) else expanded

        expanded = re.sub(pattern, replace_home, command)

        # 替换单独的 ~（保留引号）
        if '~' == command.strip('"'):
            expanded = f'"{home_dir}"' if '"' in command else home_dir
        else:
            expanded = expanded.replace('~', home_dir)

        logger.debug(f"路径展开: {command} -> {expanded}")
        return expanded

    def translate_command(self, command: str, target_platform: Optional[Platform] = None) -> str:
        """将通用命令转换为 PowerShell 命令"""
        # 先展开命令中的 ~ 路径
        expanded_command = self._expand_home_directory(command)
        command = expanded_command

        # 智能修复路径中的错误用户名
        # 将 C:\Users\任意用户名\Desktop\ 替换为实际用户名路径
        import re

        # 获取当前用户桌面路径
        current_desktop = os.path.join(os.environ.get("USERPROFILE", "C:/Users/Default"), "Desktop")

        # 替换带引号的路径 "C:\Users\任意用户名\Desktop\文件.txt"
        pattern = r'"C:\\Users\\[^\\]+\\Desktop\\([^"]+)"'
        def fix_quoted_path(m):
            filename = m.group(1)
            new_path = os.path.join(current_desktop, filename)
            return f'"{new_path}"'
        command = re.sub(pattern, fix_quoted_path, command)

        # 替换不带引号的路径 C:\Users\任意用户名\Desktop\文件.txt
        # 注意:只替换不在引号内的路径
        pattern = r"(?<!\")C:\\Users\\[^\\]+\\Desktop\\([^\\\"\\s]+)(?!\")"
        command = re.sub(
            pattern,
            lambda m: '"' + os.path.join(current_desktop, m.group(1)) + '"',
            command
        )

        # 命令映射表
        command_map = {
            # 基础命令
            'ls': 'Get-ChildItem',
            'dir': 'Get-ChildItem',
            'pwd': 'Get-Location',
            'cd': 'Set-Location',
            'cat': 'Get-Content',
            'type': 'Get-Content',  # Windows CMD 原生命令
            'more': 'Get-Content',
            'less': 'Get-Content',
            'head': 'Select-Object -First',
            'tail': 'Select-Object -Last',

            # 文件操作
            'rm': 'Remove-Item',
            'rmdir': 'Remove-Item',
            'mv': 'Move-Item',
            'cp': 'Copy-Item',
            'touch': 'New-Item -ItemType File',
            'mkdir': 'New-Item -ItemType Directory',

            # 系统信息
            'ps': 'Get-Process',
            'top': 'Get-Process | Sort-Object CPU -Descending',
            'df': 'Get-PSDrive',
            'du': '{Get-ChildItem -Recurse | Measure-Object -Property Length -Sum}.Sum / 1MB',

            # 网络命令（PowerShell 和原生命令混用）
            'ping': 'Test-Connection',
            'ifconfig': 'Get-NetIPConfiguration',
            'netstat': 'netstat.exe',  # 直接使用 netstat.exe

            # 文本搜索 - grep 转换为 Select-String
            'grep': 'Select-String',
            'find': 'Get-ChildItem -Recurse -Filter',
            'where': 'where.exe',

            # 应用程序启动（Windows 使用 start 命令）
            'firefox': 'start firefox',
            'chrome': 'start chrome',
            'msedge': 'start msedge',
            'notepad': 'notepad',
            'explorer': 'explorer',
        }

        # 分割命令（考虑引号）
        import shlex
        try:
            parts = shlex.split(command)
        except:
            # 如果解析失败，使用简单的分割
            parts = command.split()

        if not parts:
            return command

        cmd = parts[0]
        # 保留参数中的引号（如果有）
        args = command[len(cmd):].strip() if len(command) > len(cmd) else ''

        # 特殊处理：grep 转换为 Select-String
        if cmd == 'grep':
            # 解析 grep 参数并转换为 PowerShell Select-String
            # grep -r "pattern" directory -> Select-String -Path directory -Pattern "pattern" -Recurse
            # grep "pattern" file -> Select-String -Path file -Pattern "pattern"

            import re
            # 移除 -i (忽略大小写，PowerShell 默认支持)
            args_clean = re.sub(r'\s*-i\b', '', args)

            # 检查是否有 -r 递归参数
            has_recurse = '-r' in args_clean
            args_clean = re.sub(r'\s*-r\b', '', args_clean)

            # 尝试提取模式和路径
            # grep "pattern" path 或 grep -r "pattern" path
            grep_pattern_match = re.search(r'["\']([^"\']+)["\']', args_clean)
            grep_path_match = re.search(r'(["\']?[^\s"\']+["\']?)\s*$', args_clean)

            if grep_pattern_match:
                pattern = grep_pattern_match.group(1)
                # 获取路径（如果有）
                remaining = args_clean.replace(f'"{pattern}"', '').replace(f"'{pattern}'", '').strip()
                if remaining and remaining != '-r':
                    path = remaining
                    if has_recurse:
                        return f'Select-String -Path "{path}" -Pattern "{pattern}" -Recurse'
                    else:
                        return f'Select-String -Path "{path}" -Pattern "{pattern}"'
                else:
                    # 没有路径，搜索当前目录
                    if has_recurse:
                        return f'Select-String -Path . -Pattern "{pattern}" -Recurse'
                    else:
                        return f'Select-String -Path . -Pattern "{pattern}"'
            else:
                # 如果无法解析，返回原始命令（可能会失败）
                return command

        # 特殊处理：find 命令
        if cmd == 'find' and '-name' in args:
            # find . -name "*.py" -> Get-ChildItem -Recurse -Filter "*.py"
            import re
            name_match = re.search(r'-name\s+([^\s]+)', args)
            path_match = re.match(r'^([^\s]+)', args)

            if name_match:
                pattern = name_match.group(1).strip('"\'')
                path = path_match.group(1) if path_match else '.'
                return f'Get-ChildItem -Path "{path}" -Recurse -Filter {pattern}'

        # 特殊处理：type 命令（Windows 查看文件内容）
        if cmd == 'type':
            # type "C:\path\to\file.txt" -> Get-Content "C:\path\to\file.txt"
            # 先展开路径中的 ~ 符号
            expanded_args = self._expand_home_directory(args)
            # 直接使用 Get-Content，保持原有引号
            return f'Get-Content {expanded_args}'

        # 特殊处理：echo 命令（创建文件并写入内容）
        if cmd == 'echo':
            # echo "content" > file.txt -> Set-Content -Path "file.txt" -Value "content"
            import re
            # 先展开路径中的 ~ 符号
            expanded_args = self._expand_home_directory(args)
            # 检查是否有重定向符号
            if '>' in expanded_args:
                parts = expanded_args.split('>')
                if len(parts) == 2:
                    content = parts[0].strip()
                    filename = parts[1].strip()
                    # 移除引号
                    content = content.strip('"\'')
                    filename = filename.strip('"\'')
                    return f'Set-Content -Path "{filename}" -Value "{content}"'
            # 如果没有重定向，直接输出（PowerShell 使用 Write-Output）
            return f'Write-Output "{expanded_args}"'

        # 特殊处理：应用程序启动（使用 start 命令从注册表查找）
        if cmd in ['firefox', 'chrome', 'msedge']:
            return f"start {cmd} {args}".strip()

        # 检查是否需要翻译
        if cmd in command_map:
            translated = command_map[cmd]
            return f"{translated} {args}".strip()

        # Git 命令不需要翻译
        if cmd == 'git':
            return command

        # 已经是 PowerShell 命令，直接返回
        if command.startswith('Get-') or command.startswith('Set-') or command.startswith('New-'):
            return command

        # 如果命令包含特殊操作符（>、>>、| 等），让 PowerShell 直接处理
        if '>' in command or '|' in command:
            return command

        return command

    def get_shell_command(self, command: str) -> str:
        """获取 PowerShell 命令"""
        return f"powershell -Command \"{command}\""


class LinuxAdapter(PlatformAdapter):
    """Linux 平台适配器（Bash）"""

    def __init__(self):
        super().__init__()
        logger.info("初始化 Linux 适配器 (Bash)")

    def execute_command(self, command: str, timeout: int = 30) -> Tuple[int, str, str]:
        """执行 Bash 命令"""
        try:
            logger.debug(f"执行 Bash 命令: {command}")

            # 执行命令
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='replace'
            )

            return result.returncode, result.stdout, result.stderr

        except subprocess.TimeoutExpired:
            return -1, "", f"命令执行超时（{timeout}秒）"
        except Exception as e:
            return -1, "", f"命令执行失败: {str(e)}"

    def translate_command(self, command: str, target_platform: Optional[Platform] = None) -> str:
        """将通用命令转换为 Bash 命令（Linux 默认已经是 Bash）"""
        # 智能修复路径中的错误用户名
        # Linux 路径格式: /home/旧用户/Desktop/文件.txt 或 /home/旧用户/文件.txt
        import re

        # 获取当前用户主目录和桌面目录
        home_dir = os.path.expanduser('~')
        desktop_dir = os.path.join(home_dir, 'Desktop')

        # 替换带引号的路径 "/home/旧用户/Desktop/文件.txt"
        pattern = r'"/home/[^/]+/Desktop/([^"]+)"'
        def fix_quoted_path(m):
            filename = m.group(1)
            new_path = os.path.join(desktop_dir, filename)
            return f'"{new_path}"'
        command = re.sub(pattern, fix_quoted_path, command)

        # 替换带引号的路径 "/home/旧用户/文件.txt"
        pattern = r'"/home/[^/]+/([^"]+)"'
        def fix_quoted_home(m):
            filename = m.group(1)
            new_path = os.path.join(home_dir, filename)
            return f'"{new_path}"'
        command = re.sub(pattern, fix_quoted_home, command)

        # 替换不带引号的路径 /home/旧用户/Desktop/文件.txt
        # 注意:只替换不在引号内的路径
        pattern = r'(?<!\")/home/[^/]+/Desktop/([^\"/\s]+)(?!\")'
        command = re.sub(
            pattern,
            lambda m: '"' + os.path.join(desktop_dir, m.group(1)) + '"',
            command
        )

        # 替换不带引号的路径 /home/旧用户/文件.txt
        pattern = r'(?<!\")/home/[^/]+/([^\"/\s]+)(?!\")'
        command = re.sub(
            pattern,
            lambda m: '"' + os.path.join(home_dir, m.group(1)) + '"',
            command
        )

        # Linux 命令已经是 Bash 格式，直接返回
        return command

    def get_shell_command(self, command: str) -> str:
        """获取 Bash 命令"""
        return f"/bin/bash -c \"{command}\""


class MacOSAdapter(LinuxAdapter):
    """MacOS 平台适配器（兼容 Linux Bash）"""

    def __init__(self):
        super().__init__()
        logger.info("初始化 MacOS 适配器 (Bash)")

    def translate_command(self, command: str, target_platform: Optional[Platform] = None) -> str:
        """将通用命令转换为 Bash 命令（MacOS 默认已经是 Bash）"""
        # 智能修复路径中的错误用户名
        # MacOS 路径格式: /Users/旧用户/Desktop/文件.txt 或 /Users/旧用户/文件.txt
        import re

        # 获取当前用户主目录和桌面目录
        home_dir = os.path.expanduser('~')
        desktop_dir = os.path.join(home_dir, 'Desktop')

        # 替换带引号的路径 "/Users/旧用户/Desktop/文件.txt"
        pattern = r'"/Users/[^/]+/Desktop/([^"]+)"'
        def fix_quoted_path(m):
            filename = m.group(1)
            new_path = os.path.join(desktop_dir, filename)
            return f'"{new_path}"'
        command = re.sub(pattern, fix_quoted_path, command)

        # 替换带引号的路径 "/Users/旧用户/文件.txt"
        pattern = r'"/Users/[^/]+/([^"]+)"'
        def fix_quoted_home(m):
            filename = m.group(1)
            new_path = os.path.join(home_dir, filename)
            return f'"{new_path}"'
        command = re.sub(pattern, fix_quoted_home, command)

        # 替换不带引号的路径 /Users/旧用户/Desktop/文件.txt
        # 注意:只替换不在引号内的路径
        pattern = r'(?<!\")/Users/[^/]+/Desktop/([^\"/\s]+)(?!\")'
        command = re.sub(
            pattern,
            lambda m: '"' + os.path.join(desktop_dir, m.group(1)) + '"',
            command
        )

        # 替换不带引号的路径 /Users/旧用户/文件.txt
        pattern = r'(?<!\")/Users/[^/]+/([^\"/\s]+)(?!\")'
        command = re.sub(
            pattern,
            lambda m: '"' + os.path.join(home_dir, m.group(1)) + '"',
            command
        )

        # MacOS 命令已经是 Bash 格式，直接返回
        return command


def get_platform_adapter(platform: Optional[Platform] = None) -> PlatformAdapter:
    """
    获取平台适配器

    Args:
        platform: 指定平台（None 表示自动检测）

    Returns:
        PlatformAdapter: 平台适配器实例
    """
    if platform is None:
        platform = detect_platform()

    if platform == Platform.WINDOWS:
        return WindowsAdapter()
    elif platform == Platform.LINUX:
        return LinuxAdapter()
    elif platform == Platform.MACOS:
        return MacOSAdapter()
    else:
        logger.warning(f"未知平台 {platform}，使用默认适配器")
        return LinuxAdapter()  # 默认使用 Linux 适配器
