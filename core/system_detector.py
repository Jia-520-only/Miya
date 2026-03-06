"""
系统环境检测器
自动检测操作系统、Linux 发行版、Shell、包管理器等信息
"""
import os
import sys
import platform
import subprocess
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)


@dataclass
class SystemInfo:
    """系统信息"""
    os_name: str = "unknown"
    os_version: str = "unknown"
    distro: str = "unknown"  # Linux 发行版
    distro_version: str = "unknown"
    arch: str = "unknown"  # CPU 架构
    shell: str = "unknown"
    python_version: str = "unknown"
    node_version: str = "unknown"  # Node.js 版本（如果安装）
    package_managers: List[str] = field(default_factory=list)
    current_path: str = "unknown"
    home_dir: str = "unknown"

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'os': self.os_name,
            'version': self.os_version,
            'distro': self.distro,
            'distro_version': self.distro_version,
            'arch': self.arch,
            'shell': self.shell,
            'python': self.python_version,
            'node': self.node_version,
            'package_managers': self.package_managers,
            'current_path': self.current_path,
            'home_dir': self.home_dir,
        }

    def is_windows(self) -> bool:
        """是否为 Windows"""
        return self.os_name == "Windows"

    def is_linux(self) -> bool:
        """是否为 Linux"""
        return self.os_name == "Linux"

    def is_macos(self) -> bool:
        """是否为 macOS"""
        return self.os_name == "Darwin"

    def get_best_package_manager(self) -> Optional[str]:
        """获取最佳包管理器"""
        if self.is_windows():
            return next((pm for pm in self.package_managers if pm in ['winget', 'choco', 'scoop']), None)
        elif self.is_linux():
            return next((pm for pm in self.package_managers if pm in ['apt', 'yum', 'dnf', 'pacman', 'apk']), None)
        elif self.is_macos():
            return next((pm for pm in self.package_managers if pm in ['brew']), None)
        return None


class SystemDetector:
    """
    系统环境检测器
    """
    def __init__(self):
        self._cached_info: Optional[SystemInfo] = None

    def detect(self, force_refresh: bool = False) -> SystemInfo:
        """检测系统信息"""
        if not force_refresh and self._cached_info:
            return self._cached_info

        info = SystemInfo()

        # 检测操作系统
        info.os_name = platform.system()
        info.os_version = platform.version()
        info.arch = platform.machine()
        info.current_path = os.getcwd()
        info.home_dir = os.path.expanduser('~')

        # 检测 Linux 发行版
        if info.is_linux():
            info.distro, info.distro_version = self._detect_linux_distro()

        # 检测 Shell
        info.shell = self._detect_shell()

        # 检测 Python 版本
        info.python_version = self._detect_python_version()

        # 检测 Node.js 版本
        info.node_version = self._detect_node_version()

        # 检测包管理器
        info.package_managers = self._detect_package_managers(info)

        # 缓存结果
        self._cached_info = info

        logger.info(f"系统检测完成: {info.os_name} {info.distro} (Python {info.python_version})")
        return info

    def _detect_linux_distro(self) -> tuple[str, str]:
        """检测 Linux 发行版"""
        try:
            # 读取 /etc/os-release
            if os.path.exists('/etc/os-release'):
                with open('/etc/os-release', 'r') as f:
                    content = f.read()

                import re
                name_match = re.search(r'^ID="?([^"\n]+)"?', content, re.MULTILINE)
                version_match = re.search(r'^VERSION_ID="?([^"\n]+)"?', content, re.MULTILINE)

                name = name_match.group(1) if name_match else "unknown"
                version = version_match.group(1) if version_match else "unknown"

                return name, version

            # 使用 lsb_release 命令
            result = subprocess.run(
                ['lsb_release', '-a'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.startswith('Distributor ID:'):
                        distro = line.split(':')[1].strip().lower()
                    elif line.startswith('Release:'):
                        version = line.split(':')[1].strip()
                return distro, version

        except Exception as e:
            logger.warning(f"检测 Linux 发行版失败: {e}")

        return "unknown", "unknown"

    def _detect_shell(self) -> str:
        """检测 Shell 类型"""
        shell_path = os.environ.get('SHELL', '')

        if shell_path:
            shell_name = os.path.basename(shell_path)
            return shell_name

        # 检查 PowerShell (Windows)
        if sys.platform == 'win32':
            try:
                result = subprocess.run(
                    ['powershell', '-Command', '$PSVersionTable.PSVersion'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return 'pwsh' if 'PowerShell Core' in result.stdout else 'powershell'
            except:
                pass

        # 默认返回系统默认 Shell
        if sys.platform == 'win32':
            return 'cmd'
        return 'bash'

    def _detect_python_version(self) -> str:
        """检测 Python 版本"""
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    def _detect_node_version(self) -> str:
        """检测 Node.js 版本"""
        try:
            result = subprocess.run(
                ['node', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                # 移除 'v' 前缀
                return version.lstrip('v')
        except Exception as e:
            logger.debug(f"未检测到 Node.js: {e}")

        return "not_installed"

    def _detect_package_managers(self, info: SystemInfo) -> List[str]:
        """检测可用的包管理器"""
        managers = []

        # Python 包管理器（所有平台都有）
        managers.append('pip')

        # Node.js 包管理器
        if info.node_version != "not_installed":
            managers.append('npm')

            # 检测 yarn
            try:
                result = subprocess.run(
                    ['yarn', '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    managers.append('yarn')
            except:
                pass

            # 检测 pnpm
            try:
                result = subprocess.run(
                    ['pnpm', '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    managers.append('pnpm')
            except:
                pass

        # Windows 包管理器
        if info.is_windows():
            # winget
            try:
                result = subprocess.run(
                    ['winget', '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    managers.append('winget')
            except:
                pass

            # Chocolatey
            try:
                result = subprocess.run(
                    ['choco', '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    managers.append('choco')
            except:
                pass

            # Scoop
            try:
                result = subprocess.run(
                    ['scoop', '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    managers.append('scoop')
            except:
                pass

        # Linux 包管理器
        elif info.is_linux():
            distro = info.distro

            # Debian/Ubuntu 系列
            if distro in ['ubuntu', 'debian', 'linuxmint', 'pop']:
                managers.append('apt')

            # RedHat/CentOS/Fedora 系列
            elif distro in ['fedora', 'rhel', 'centos', 'rocky']:
                managers.append('dnf')
                managers.append('yum')

            # Arch Linux
            elif distro in ['arch', 'manjaro', 'endeavouros']:
                managers.append('pacman')

            # Alpine Linux
            elif distro in ['alpine']:
                managers.append('apk')

        # macOS 包管理器
        elif info.is_macos():
            # Homebrew
            try:
                result = subprocess.run(
                    ['brew', '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    managers.append('brew')
            except:
                pass

        logger.info(f"检测到的包管理器: {', '.join(managers)}")
        return managers


# 全局检测器实例
_global_detector: Optional[SystemDetector] = None


def get_system_detector() -> SystemDetector:
    """获取全局系统检测器实例"""
    global _global_detector
    if _global_detector is None:
        _global_detector = SystemDetector()
    return _global_detector
