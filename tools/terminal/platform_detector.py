"""
平台检测模块
自动检测当前运行平台和 Linux 发行版
"""
import sys
import logging
import os
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class Platform(Enum):
    """支持的平台类型"""
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    UNKNOWN = "unknown"


class LinuxDistro(Enum):
    """Linux 发行版"""
    UBUNTU = "ubuntu"
    DEBIAN = "debian"
    ARCH = "arch"
    FEDORA = "fedora"
    CENTOS = "centos"
    REDHAT = "redhat"
    KALI = "kali"
    MINT = "mint"
    OPENSUSE = "opensuse"
    ALPINE = "alpine"
    GENTOO = "gentoo"
    SOLUS = "solus"
    UNKNOWN = "unknown"


def detect_platform() -> Platform:
    """
    检测当前运行平台

    Returns:
        Platform: 检测到的平台
    """
    if sys.platform == 'win32':
        platform = Platform.WINDOWS
    elif sys.platform.startswith('linux'):
        platform = Platform.LINUX
    elif sys.platform == 'darwin':
        platform = Platform.MACOS
    else:
        platform = Platform.UNKNOWN

    logger.info(f"检测到平台: {platform.value}")
    return platform


def detect_linux_distro() -> LinuxDistro:
    """
    检测 Linux 发行版

    Returns:
        LinuxDistro: 检测到的发行版
    """
    if not is_linux():
        return LinuxDistro.UNKNOWN

    try:
        # 方法1: 检查 /etc/os-release 文件（最通用）
        os_release_path = Path("/etc/os-release")
        if os_release_path.exists():
            with open(os_release_path, 'r', encoding='utf-8') as f:
                content = f.read().lower()
                for distro in LinuxDistro:
                    if distro != LinuxDistro.UNKNOWN:
                        if distro.value in content:
                            logger.info(f"检测到 Linux 发行版: {distro.value}")
                            return distro

        # 方法2: 检查 /etc/*-release 文件
        for distro_name in [
            'ubuntu', 'debian', 'arch', 'fedora', 'centos', 'redhat',
            'kali', 'mint', 'opensuse', 'alpine', 'gentoo'
        ]:
            release_file = Path(f"/etc/{distro_name}-release")
            if release_file.exists():
                logger.info(f"检测到 Linux 发行版: {distro_name}")
                # 尝试转换为枚举值
                for distro in LinuxDistro:
                    if distro.value == distro_name:
                        return distro

        # 方法3: 检查常见的发行版标识文件
        id_files = [
            ('/etc/arch-release', LinuxDistro.ARCH),
            ('/etc/fedora-release', LinuxDistro.FEDORA),
            ('/etc/redhat-release', LinuxDistro.REDHAT),
            ('/etc/centos-release', LinuxDistro.CENTOS),
            ('/etc/alpine-release', LinuxDistro.ALPINE),
        ]

        for file_path, distro in id_files:
            if Path(file_path).exists():
                logger.info(f"检测到 Linux 发行版: {distro.value}")
                return distro

        # 方法4: 使用 lsb_release 命令（如果可用）
        try:
            import subprocess
            result = subprocess.run(
                ['lsb_release', '-i', '-s'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                distro_name = result.stdout.strip().lower()
                for distro in LinuxDistro:
                    if distro.value in distro_name:
                        logger.info(f"检测到 Linux 发行版: {distro.value}")
                        return distro
        except:
            pass

    except Exception as e:
        logger.warning(f"检测 Linux 发行版失败: {e}")

    logger.info("无法识别 Linux 发行版")
    return LinuxDistro.UNKNOWN


def get_platform_name() -> str:
    """
    获取平台名称字符串

    Returns:
        str: 平台名称
    """
    platform = detect_platform()
    if platform == Platform.LINUX:
        distro = detect_linux_distro()
        if distro != LinuxDistro.UNKNOWN:
            return f"linux ({distro.value})"
    return platform.value


def is_windows() -> bool:
    """是否为 Windows 平台"""
    return detect_platform() == Platform.WINDOWS


def is_linux() -> bool:
    """是否为 Linux 平台"""
    return detect_platform() == Platform.LINUX


def is_macos() -> bool:
    """是否为 MacOS 平台"""
    return detect_platform() == Platform.MACOS


def get_system_info() -> dict:
    """
    获取系统信息

    Returns:
        dict: 包含平台、发行版、架构等信息的字典
    """
    info = {
        'platform': detect_platform().value,
        'python_version': sys.version,
        'architecture': sys.maxsize > 2**32 and '64-bit' or '32-bit',
    }

    if is_linux():
        distro = detect_linux_distro()
        info['linux_distro'] = distro.value

        # 获取内核版本
        try:
            with open('/proc/version', 'r', encoding='utf-8') as f:
                info['kernel'] = f.read().strip()
        except:
            pass

    elif is_windows():
        import platform as win_platform
        info['windows_version'] = win_platform.version()
        info['windows_edition'] = win_platform.win32_edition()

    elif is_macos():
        import platform as mac_platform
        info['macos_version'] = mac_platform.mac_ver()[0]

    return info

