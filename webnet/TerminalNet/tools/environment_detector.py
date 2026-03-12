"""
跨平台环境检测工具 - 弥娅完全掌控系统环境

功能：
1. 检测操作系统和版本
2. 检测Shell类型和版本
3. 检测包管理器
4. 检测开发环境（Python、Node.js、Git等）
5. 检测系统资源
6. 检测网络配置

符合 MIYA 框架：
- 稳定：职责单一，错误处理完善
- 独立：依赖明确，模块解耦
- 可维修：代码清晰，易于扩展
- 故障隔离：执行失败不影响系统
"""
import logging
import subprocess
import platform
import os
import re
from typing import Dict, Any, Optional, List
from pathlib import Path

from webnet.tools.base import BaseTool, ToolContext


class EnvironmentDetectorTool(BaseTool):
    """
    跨平台环境检测工具

    让弥娅拥有完整的系统环境感知能力，可以：
    - 检测操作系统和发行版
    - 检测Shell环境
    - 检测包管理器
    - 检测开发工具链
    - 检测系统资源
    - 检测网络配置
    """

    def __init__(self):
        super().__init__()
        self.name = "environment_detector"
        self.logger = logging.getLogger("Tool.EnvironmentDetector")
        self._cache = {}

    @property
    def config(self) -> Dict[str, Any]:
        """工具配置（OpenAI Function Calling 格式）"""
        return {
            "name": "environment_detector",
            "description": """检测系统环境和配置信息。当用户要求检查系统、查看环境、了解系统配置或诊断环境问题时调用。

操作类型：
- detect_os: 检测操作系统信息
- detect_shell: 检测Shell环境
- detect_package_managers: 检测包管理器
- detect_dev_tools: 检测开发工具链（Python、Node.js、Git、Docker等）
- detect_system_resources: 检测系统资源（CPU、内存、磁盘）
- detect_network: 检测网络配置
- detect_all: 执行完整的环境检测（包含以上所有）""",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "detect_os",
                            "detect_shell",
                            "detect_package_managers",
                            "detect_dev_tools",
                            "detect_system_resources",
                            "detect_network",
                            "detect_all"
                        ],
                        "description": "要执行的操作类型"
                    },
                    "use_cache": {
                        "type": "boolean",
                        "description": "是否使用缓存（默认true，可加快检测速度）"
                    }
                },
                "required": ["action"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """
        执行环境检测操作

        Args:
            args: 工具参数
            context: 执行上下文

        Returns:
            检测结果字符串
        """
        action = args.get("action", "")
        use_cache = args.get("use_cache", True)

        if not action:
            return "❌ 缺少action参数"

        try:
            if action == "detect_os":
                return await self._detect_os(use_cache)
            elif action == "detect_shell":
                return await self._detect_shell(use_cache)
            elif action == "detect_package_managers":
                return await self._detect_package_managers(use_cache)
            elif action == "detect_dev_tools":
                return await self._detect_dev_tools(use_cache)
            elif action == "detect_system_resources":
                return await self._detect_system_resources(use_cache)
            elif action == "detect_network":
                return await self._detect_network(use_cache)
            elif action == "detect_all":
                return await self._detect_all(use_cache)
            else:
                return f"❌ 未知的操作: {action}"

        except Exception as e:
            self.logger.error(f"执行操作失败: {e}", exc_info=True)
            return f"❌ 操作执行失败: {str(e)}"

    async def _detect_os(self, use_cache: bool = True) -> str:
        """检测操作系统信息"""
        cache_key = "detect_os"
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        result = "💻 操作系统信息\n\n"

        # 基本系统信息
        system = platform.system()
        result += f"系统: {system}\n"
        result += f"架构: {platform.machine()}\n"
        result += f"处理器: {platform.processor()}\n"

        if system == "Windows":
            # Windows详细信息
            result += f"版本: {platform.version()}\n"
            result += f"发行版: {platform.release()}\n"

            # 获取Windows版本名称
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                version = kernel32.GetVersionEx()
                result += f"系统名称: Windows {version[0]}.{version[1]}\n"
            except:
                pass

        elif system == "Linux":
            # Linux详细信息
            result += f"内核版本: {platform.release()}\n"

            # 检测Linux发行版
            try:
                # 尝试读取 /etc/os-release
                if os.path.exists("/etc/os-release"):
                    with open("/etc/os-release", "r") as f:
                        content = f.read()
                        # 提取发行版信息
                        name_match = re.search(r'NAME="([^"]+)"', content)
                        version_match = re.search(r'VERSION="([^"]+)"', content)
                        if name_match:
                            result += f"发行版: {name_match.group(1)}\n"
                        if version_match:
                            result += f"发行版版本: {version_match.group(1)}\n"
            except:
                pass

        elif system == "Darwin":
            # macOS详细信息
            result += f"内核版本: {platform.release()}\n"

            # 获取macOS版本
            try:
                sw_vers = subprocess.run(["sw_vers"], capture_output=True, text=True, timeout=5)
                if sw_vers.returncode == 0:
                    result += "\n" + sw_vers.stdout
            except:
                pass

        # Python信息
        result += f"\nPython版本: {platform.python_version()}\n"
        result += f"Python实现: {platform.python_implementation()}\n"

        if use_cache:
            self._cache[cache_key] = result

        return result

    async def _detect_shell(self, use_cache: bool = True) -> str:
        """检测Shell环境"""
        cache_key = "detect_shell"
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        result = "🐚 Shell环境\n\n"

        system = platform.system()

        if system == "Windows":
            # Windows Shell
            result += f"默认Shell: PowerShell\n"

            # 检查PowerShell版本
            try:
                ps_version = subprocess.run(
                    ["powershell", "-Command", "$PSVersionTable.PSVersion"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if ps_version.returncode == 0:
                    result += f"PowerShell版本: {ps_version.stdout.strip()}\n"
            except:
                pass

            # 检查CMD
            result += "CMD: 可用\n"

            # 检查Git Bash
            git_bash_path = r"C:\Program Files\Git\git-bash.exe"
            if os.path.exists(git_bash_path):
                result += "Git Bash: 已安装\n"

            # 检查WSL
            try:
                wsl_check = subprocess.run(
                    ["wsl", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if wsl_check.returncode == 0:
                    result += "WSL: 已安装\n"
                    # 列出WSL发行版
                    wsl_list = subprocess.run(
                        ["wsl", "--list", "--verbose"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if wsl_list.returncode == 0:
                        result += f"WSL发行版:\n{wsl_list.stdout}\n"
            except:
                pass

        else:
            # Unix-like系统
            shell = os.environ.get("SHELL", "unknown")
            result += f"当前Shell: {shell}\n"

            # 检测Shell版本
            shell_name = shell.split("/")[-1]
            try:
                version_cmd = f"{shell_name} --version"
                version_result = subprocess.run(
                    version_cmd.split(),
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if version_result.returncode == 0:
                    version_line = version_result.stdout.split('\n')[0]
                    result += f"Shell版本: {version_line}\n"
            except:
                pass

            # 检测可用的Shell
            available_shells = []
            for shell_candidate in ["bash", "zsh", "fish", "sh", "dash", "tcsh", "csh"]:
                try:
                    which_result = subprocess.run(
                        ["which", shell_candidate],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if which_result.returncode == 0:
                        available_shells.append(shell_candidate)
                except:
                    pass

            result += f"可用的Shell: {', '.join(available_shells)}\n"

        if use_cache:
            self._cache[cache_key] = result

        return result

    async def _detect_package_managers(self, use_cache: bool = True) -> str:
        """检测包管理器"""
        cache_key = "detect_package_managers"
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        result = "📦 包管理器检测\n\n"

        system = platform.system()

        if system == "Windows":
            # Windows包管理器
            # Chocolatey
            try:
                choco_check = subprocess.run(
                    ["choco", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if choco_check.returncode == 0:
                    result += f"✅ Chocolatey: {choco_check.stdout.strip()}\n"
            except:
                result += "❌ Chocolatey: 未安装\n"

            # Winget
            try:
                winget_check = subprocess.run(
                    ["winget", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if winget_check.returncode == 0:
                    result += f"✅ Winget: {winget_check.stdout.strip()}\n"
            except:
                result += "❌ Winget: 未安装\n"

            # Scoop
            try:
                scoop_check = subprocess.run(
                    ["scoop", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if scoop_check.returncode == 0:
                    result += f"✅ Scoop: {scoop_check.stdout.strip()}\n"
            except:
                result += "❌ Scoop: 未安装\n"

            # npm (Node.js包管理器)
            try:
                npm_check = subprocess.run(
                    ["npm", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if npm_check.returncode == 0:
                    result += f"✅ npm: {npm_check.stdout.strip()}\n"
            except:
                result += "❌ npm: 未安装\n"

            # pip (Python包管理器)
            try:
                pip_check = subprocess.run(
                    ["pip", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if pip_check.returncode == 0:
                    result += f"✅ pip: {pip_check.stdout.strip()}\n"
            except:
                result += "❌ pip: 未安装\n"

        elif system == "Linux":
            # Linux包管理器
            # apt (Debian/Ubuntu)
            try:
                apt_check = subprocess.run(
                    ["apt", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if apt_check.returncode == 0:
                    result += f"✅ apt: {apt_check.stdout.strip()}\n"
            except:
                pass

            # yum/dnf (RHEL/CentOS/Fedora)
            for pm in ["dnf", "yum"]:
                try:
                    pm_check = subprocess.run(
                        [pm, "--version"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if pm_check.returncode == 0:
                        result += f"✅ {pm}: {pm_check.stdout.strip()}\n"
                        break
                except:
                    pass

            # pacman (Arch Linux)
            try:
                pacman_check = subprocess.run(
                    ["pacman", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if pacman_check.returncode == 0:
                    result += f"✅ pacman: 已安装\n"
            except:
                pass

            # snap (Ubuntu)
            try:
                snap_check = subprocess.run(
                    ["snap", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if snap_check.returncode == 0:
                    result += f"✅ snap: {snap_check.stdout.strip()}\n"
            except:
                pass

            # flatpak
            try:
                flatpak_check = subprocess.run(
                    ["flatpak", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if flatpak_check.returncode == 0:
                    result += f"✅ flatpak: {flatpak_check.stdout.strip()}\n"
            except:
                pass

        elif system == "Darwin":
            # macOS包管理器
            # Homebrew
            try:
                brew_check = subprocess.run(
                    ["brew", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if brew_check.returncode == 0:
                    result += f"✅ Homebrew: {brew_check.stdout.strip()}\n"
            except:
                result += "❌ Homebrew: 未安装\n"

            # MacPorts
            try:
                port_check = subprocess.run(
                    ["port", "version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if port_check.returncode == 0:
                    result += f"✅ MacPorts: {port_check.stdout.strip()}\n"
            except:
                result += "❌ MacPorts: 未安装\n"

        if use_cache:
            self._cache[cache_key] = result

        return result

    async def _detect_dev_tools(self, use_cache: bool = True) -> str:
        """检测开发工具链"""
        cache_key = "detect_dev_tools"
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        result = "🔧 开发工具链检测\n\n"

        # Python
        try:
            python_version = subprocess.run(
                ["python", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if python_version.returncode == 0:
                result += f"✅ Python: {python_version.stderr.strip()}\n"
        except:
            result += "❌ Python: 未安装\n"

        # Python3
        try:
            python3_version = subprocess.run(
                ["python3", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if python3_version.returncode == 0:
                result += f"✅ Python3: {python3_version.stdout.strip()}\n"
        except:
            result += "❌ Python3: 未安装\n"

        # Node.js
        try:
            node_version = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if node_version.returncode == 0:
                result += f"✅ Node.js: {node_version.stdout.strip()}\n"
        except:
            result += "❌ Node.js: 未安装\n"

        # npm
        try:
            npm_version = subprocess.run(
                ["npm", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if npm_version.returncode == 0:
                result += f"✅ npm: {npm_version.stdout.strip()}\n"
        except:
            result += "❌ npm: 未安装\n"

        # Git
        try:
            git_version = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if git_version.returncode == 0:
                result += f"✅ Git: {git_version.stdout.strip()}\n"
        except:
            result += "❌ Git: 未安装\n"

        # Docker
        try:
            docker_version = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if docker_version.returncode == 0:
                result += f"✅ Docker: {docker_version.stdout.strip()}\n"
            else:
                result += "❌ Docker: 未安装\n"
        except:
            result += "❌ Docker: 未安装\n"

        # Docker Compose
        try:
            docker_compose_version = subprocess.run(
                ["docker-compose", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if docker_compose_version.returncode == 0:
                result += f"✅ Docker Compose: {docker_compose_version.stdout.strip()}\n"
            else:
                result += "❌ Docker Compose: 未安装\n"
        except:
            result += "❌ Docker Compose: 未安装\n"

        # GCC/Clang
        try:
            gcc_version = subprocess.run(
                ["gcc", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if gcc_version.returncode == 0:
                version_line = gcc_version.stdout.split('\n')[0]
                result += f"✅ GCC: {version_line}\n"
        except:
            pass

        try:
            clang_version = subprocess.run(
                ["clang", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if clang_version.returncode == 0:
                version_line = clang_version.stdout.split('\n')[0]
                result += f"✅ Clang: {version_line}\n"
        except:
            pass

        # Make
        try:
            make_version = subprocess.run(
                ["make", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if make_version.returncode == 0:
                result += f"✅ Make: {make_version.stdout.split(chr(10))[0]}\n"
        except:
            result += "❌ Make: 未安装\n"

        # Java
        try:
            java_version = subprocess.run(
                ["java", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if java_version.returncode == 0 or "version" in java_version.stderr:
                # java -version 输出到stderr
                version_line = java_version.stderr.split('\n')[0] if java_version.stderr else "Unknown"
                result += f"✅ Java: {version_line}\n"
        except:
            result += "❌ Java: 未安装\n"

        # Go
        try:
            go_version = subprocess.run(
                ["go", "version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if go_version.returncode == 0:
                result += f"✅ Go: {go_version.stdout.strip()}\n"
        except:
            result += "❌ Go: 未安装\n"

        if use_cache:
            self._cache[cache_key] = result

        return result

    async def _detect_system_resources(self, use_cache: bool = True) -> str:
        """检测系统资源"""
        cache_key = "detect_system_resources"
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        result = "📊 系统资源\n\n"

        system = platform.system()

        # CPU信息
        result += "CPU:\n"
        try:
            if system == "Windows":
                import wmi
                c = wmi.WMI()
                for cpu in c.Win32_Processor():
                    result += f"  型号: {cpu.Name}\n"
                    result += f"  核心数: {cpu.NumberOfCores}\n"
                    result += f"  逻辑处理器: {cpu.NumberOfLogicalProcessors}\n"
                    break
            elif system == "Linux":
                # CPU信息
                cpuinfo = Path("/proc/cpuinfo").read_text()
                model_name = re.search(r"model name\s*:\s*(.+)", cpuinfo)
                if model_name:
                    result += f"  型号: {model_name.group(1)}\n"
                # CPU核心数
                cpu_count = os.cpu_count()
                result += f"  逻辑处理器: {cpu_count}\n"
            elif system == "Darwin":
                sysctl_result = subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.brand_string"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if sysctl_result.returncode == 0:
                    result += f"  型号: {sysctl_result.stdout.strip()}\n"
                cpu_count = os.cpu_count()
                result += f"  逻辑处理器: {cpu_count}\n"
        except Exception as e:
            result += f"  检测失败: {str(e)}\n"

        # 内存信息
        result += "\n内存:\n"
        try:
            if system == "Windows":
                import psutil
                mem = psutil.virtual_memory()
                total_gb = mem.total / (1024 ** 3)
                available_gb = mem.available / (1024 ** 3)
                result += f"  总内存: {total_gb:.2f} GB\n"
                result += f"  可用内存: {available_gb:.2f} GB\n"
                result += f"  使用率: {mem.percent:.1f}%\n"
            elif system == "Linux":
                meminfo = Path("/proc/meminfo").read_text()
                mem_total = re.search(r"MemTotal:\s+(\d+)", meminfo)
                mem_free = re.search(r"MemFree:\s+(\d+)", meminfo)
                if mem_total:
                    total_gb = int(mem_total.group(1)) / (1024 ** 2)
                    result += f"  总内存: {total_gb:.2f} GB\n"
                if mem_free:
                    free_gb = int(mem_free.group(1)) / (1024 ** 2)
                    result += f"  空闲内存: {free_gb:.2f} GB\n"
            elif system == "Darwin":
                vm_result = subprocess.run(
                    ["vm_stat"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if vm_result.returncode == 0:
                    result += f"  虚拟内存状态:\n{vm_result.stdout}\n"
        except Exception as e:
            result += f"  检测失败: {str(e)}\n"

        # 磁盘空间
        result += "\n磁盘空间:\n"
        try:
            import shutil
            disk_usage = shutil.disk_usage("/")
            total_gb = disk_usage.total / (1024 ** 3)
            used_gb = disk_usage.used / (1024 ** 3)
            free_gb = disk_usage.free / (1024 ** 3)
            result += f"  总空间: {total_gb:.2f} GB\n"
            result += f"  已用空间: {used_gb:.2f} GB\n"
            result += f"  可用空间: {free_gb:.2f} GB\n"
            result += f"  使用率: {disk_usage.percent:.1f}%\n"
        except Exception as e:
            result += f"  检测失败: {str(e)}\n"

        if use_cache:
            self._cache[cache_key] = result

        return result

    async def _detect_network(self, use_cache: bool = True) -> str:
        """检测网络配置"""
        cache_key = "detect_network"
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        result = "🌐 网络配置\n\n"

        system = platform.system()

        # 网络接口
        result += "网络接口:\n"
        try:
            import socket
            hostname = socket.gethostname()
            result += f"  主机名: {hostname}\n"

            # 获取本地IP地址
            try:
                local_ip = socket.gethostbyname(hostname)
                result += f"  本地IP: {local_ip}\n"
            except:
                pass
        except Exception as e:
            result += f"  检测失败: {str(e)}\n"

        # 网络连接
        result += "\n网络连接:\n"
        try:
            if system == "Windows":
                ipconfig_result = subprocess.run(
                    ["ipconfig"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if ipconfig_result.returncode == 0:
                    result += f"{ipconfig_result.stdout}\n"
            elif system == "Linux":
                ip_result = subprocess.run(
                    ["ip", "addr"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if ip_result.returncode == 0:
                    result += f"{ip_result.stdout}\n"
            elif system == "Darwin":
                ifconfig_result = subprocess.run(
                    ["ifconfig"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if ifconfig_result.returncode == 0:
                    result += f"{ifconfig_result.stdout}\n"
        except Exception as e:
            result += f"  检测失败: {str(e)}\n"

        if use_cache:
            self._cache[cache_key] = result

        return result

    async def _detect_all(self, use_cache: bool = True) -> str:
        """执行完整的环境检测"""
        result = "🔍 完整环境检测报告\n"
        result += "=" * 50 + "\n\n"

        result += await self._detect_os(use_cache)
        result += "\n"

        result += await self._detect_shell(use_cache)
        result += "\n"

        result += await self._detect_package_managers(use_cache)
        result += "\n"

        result += await self._detect_dev_tools(use_cache)
        result += "\n"

        result += await self._detect_system_resources(use_cache)
        result += "\n"

        result += await self._detect_network(use_cache)

        return result

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """验证参数"""
        action = args.get("action")
        if not action:
            return False, "缺少必填参数: action"
        return True, None
