"""
WSL管理工具 - 弥娅完全掌控WSL环境

功能：
1. 检测WSL是否安装
2. 列出所有WSL发行版
3. 检测指定发行版的Python环境
4. 自动安装Python环境
5. 打开指定发行版的WSL终端
6. 管理WSL终端会话

符合 MIYA 框架：
- 稳定：职责单一，错误处理完善
- 独立：依赖明确，模块解耦
- 可维修：代码清晰，易于扩展
- 故障隔离：执行失败不影响系统
"""
import logging
import subprocess
import asyncio
import re
from typing import Dict, Any, Optional, List
from pathlib import Path

from webnet.tools.base import BaseTool, ToolContext


class WSLManagerTool(BaseTool):
    """
    WSL管理工具

    让弥娅拥有完全的WSL控制权，可以：
    - 检测WSL安装状态
    - 列出所有WSL发行版
    - 检测WSL环境配置
    - 自动安装Python环境
    - 打开指定发行版的WSL终端
    """

    def __init__(self):
        super().__init__()
        self.name = "wsl_manager"
        self.logger = logging.getLogger("Tool.WSLManager")

    @property
    def config(self) -> Dict[str, Any]:
        """工具配置（OpenAI Function Calling 格式）"""
        return {
            "name": "wsl_manager",
            "description": """管理Windows Subsystem for Linux (WSL)环境。当用户要求检查WSL、打开WSL、启动WSL终端、管理WSL发行版或配置WSL环境时必须调用此工具。

【关键触发词】当用户输入以下任何内容时，必须调用此工具：
1. "打开WSL"、"启动WSL"、"创建WSL终端"、"WSL终端"
2. "查看WSL"、"列出WSL"、"检查WSL"
3. "打开Ubuntu"、"启动Debian"、"打开kali"等（任何WSL发行版名称）
4. "Ubuntu WSL"、"Debian WSL"、"kali linux WSL"等（任何包含发行版名称的短语）

【工作流程】
步骤1: 用户说"打开WSL"或类似时
  → 调用 action="list_distributions" 查看所有可用发行版
  → 列出发行版让用户选择，或使用默认发行版
  
步骤2: 用户说"打开Ubuntu WSL"或类似时
  → 提取发行版名称："Ubuntu"、"Debian"、"kali"等
  → 调用 action="open_wsl", distribution="Ubuntu"（实际名称，大小写要匹配wsl --list显示的）
  → 如果环境检查失败，自动调用 install_environment

步骤3: 用户说"安装WSL"、"配置WSL"时
  → 先调用 check_environment 检查环境
  → 如果缺少组件，调用 install_environment

【发行版名称匹配】
- 必须与 `wsl --list --verbose` 显示的名称完全匹配（区分大小写）
- 常见名称：Ubuntu、Debian、kali-linux、archlinux、Ubuntu-24.04等
- 不要猜测，必须使用list_distributions返回的准确名称

操作类型：
- check_wsl: 检查WSL是否安装
- list_distributions: 列出所有WSL发行版
- check_environment: 检查指定发行版的Python环境
- install_environment: 为指定发行版安装Python环境
- open_wsl: 打开指定发行版的WSL终端
- get_default_distribution: 获取默认WSL发行版

参数说明：
- distribution: WSL发行版名称（必须与list_distributions返回的名称完全匹配）
- skip_python_check: 跳过Python检查（open_wsl时可选，默认false）
- auto_install: 自动安装缺失的环境（check_environment时可选，默认false）

【重要提示】
- 用户说"打开Ubuntu WSL"时，distribution参数应该是"Ubuntu"（不是"Ubuntu-24.04"，除非用户明确指定）
- 如果check_environment返回缺少组件，必须先调用install_environment再调用open_wsl
- 永远不要使用multi_terminal工具打开WSL，只使用wsl_manager工具""",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "check_wsl",
                            "list_distributions",
                            "check_environment",
                            "install_environment",
                            "open_wsl",
                            "get_default_distribution"
                        ],
                        "description": "要执行的操作类型"
                    },
                    "distribution": {
                        "type": "string",
                        "description": "WSL发行版名称（如：Ubuntu、Debian、ArchLinux等）。check_environment、install_environment、open_wsl时建议提供"
                    },
                    "skip_python_check": {
                        "type": "boolean",
                        "description": "是否跳过Python环境检查（仅open_wsl使用）"
                    },
                    "auto_install": {
                        "type": "boolean",
                        "description": "是否自动安装缺失的环境（仅check_environment使用）"
                    }
                },
                "required": ["action"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """
        执行WSL管理操作

        Args:
            args: 工具参数
            context: 执行上下文

        Returns:
            执行结果字符串
        """
        action = args.get("action", "")

        if not action:
            return "❌ 缺少action参数"

        try:
            if action == "check_wsl":
                return await self._check_wsl()
            elif action == "list_distributions":
                return await self._list_distributions()
            elif action == "check_environment":
                return await self._check_environment(args, context)
            elif action == "install_environment":
                return await self._install_environment(args, context)
            elif action == "open_wsl":
                return await self._open_wsl(args, context)
            elif action == "get_default_distribution":
                return await self._get_default_distribution()
            else:
                return f"❌ 未知的操作: {action}"

        except Exception as e:
            self.logger.error(f"执行操作失败: {e}", exc_info=True)
            return f"❌ 操作执行失败: {str(e)}"

    async def _check_wsl(self) -> str:
        """检查WSL是否安装"""
        try:
            result = subprocess.run(
                ["wsl", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                version_info = result.stdout.strip()
                return f"✅ WSL已安装\n\n{version_info}"
            else:
                return "❌ WSL未安装或配置不正确"

        except FileNotFoundError:
            return "❌ WSL未找到。请安装WSL：https://aka.ms/wsl2"
        except Exception as e:
            return f"❌ 检查WSL时出错: {str(e)}"

    async def _list_distributions(self) -> str:
        """列出所有WSL发行版"""
        try:
            # 使用 --list --verbose 获取详细信息
            result = subprocess.run(
                ["wsl", "--list", "--verbose"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                return f"❌ 获取WSL发行版列表失败: {result.stderr}"

            output = result.stdout.strip()
            lines = output.split('\n')

            # 解析发行版列表
            distributions = []
            for line in lines[1:]:  # 跳过标题行
                if line.strip():
                    # 解析格式：NAME            STATE           VERSION
                    parts = line.split()
                    if len(parts) >= 3:
                        name = parts[0]
                        state = parts[1]
                        version = parts[2]
                        is_default = name.startswith('*')

                        # 清理默认标记
                        clean_name = name.replace('*', '').strip()

                        distributions.append({
                            'name': clean_name,
                            'state': state,
                            'version': version,
                            'is_default': is_default
                        })

            if not distributions:
                return "📭 没有找到WSL发行版"

            # 格式化输出
            result_str = f"📋 WSL发行版列表（共 {len(distributions)} 个）\n\n"

            for dist in distributions:
                default_marker = "★ 默认" if dist['is_default'] else "  "
                state_emoji = "🟢 运行中" if dist['state'] == 'Running' else "⚪ 已停止"
                version_name = "WSL 2" if dist['version'] == '2' else "WSL 1"

                result_str += f"{default_marker} [{dist['name']}]\n"
                result_str += f"   状态: {state_emoji}\n"
                result_str += f"   版本: {version_name}\n\n"

            return result_str

        except Exception as e:
            return f"❌ 获取发行版列表时出错: {str(e)}"

    async def _check_environment(self, args: Dict[str, Any], context: ToolContext) -> str:
        """检查指定发行版的Python环境"""
        distribution = args.get("distribution")
        auto_install = args.get("auto_install", False)

        if not distribution:
            # 如果没有指定发行版，使用默认发行版
            default_dist = await self._get_default_distribution_name()
            if default_dist:
                distribution = default_dist
                self.logger.info(f"使用默认WSL发行版: {distribution}")
            else:
                return "❌ 请指定WSL发行版名称"

        try:
            # 检查Python3
            python_check = await self._run_wsl_command(
                distribution,
                "python3 --version"
            )

            python_version = None
            if python_check['success']:
                python_version = python_check['stdout'].strip()

            # 检查pip
            pip_check = await self._run_wsl_command(
                distribution,
                "python3 -m pip --version"
            )

            pip_version = None
            if pip_check['success']:
                pip_version = pip_check['stdout'].strip()

            # 检查aiohttp
            aiohttp_check = await self._run_wsl_command(
                distribution,
                "python3 -c \"import aiohttp; print('aiohttp OK')\""
            )

            aiohttp_available = aiohttp_check['success']

            # 构建结果
            result = f"🔍 [{distribution}] 环境检查结果\n\n"

            result += f"Python3: "
            if python_version:
                result += f"✅ {python_version}\n"
            else:
                result += "❌ 未安装\n"

            result += f"pip: "
            if pip_version:
                result += f"✅ {pip_version}\n"
            else:
                result += "❌ 未安装\n"

            result += f"aiohttp: "
            if aiohttp_available:
                result += "✅ 已安装\n"
            else:
                result += "❌ 未安装\n"

            # 如果有缺失的组件
            if not python_version or not pip_version or not aiohttp_available:
                result += "\n⚠️ 发现缺失的环境组件\n"
                result += "建议运行 install_environment 操作来自动安装环境\n"

                if auto_install:
                    result += "\n🚀 正在自动安装环境...\n"
                    install_result = await self._install_environment(args, context)
                    result += "\n" + install_result

            else:
                result += "\n✅ WSL环境已完整配置，可以正常使用终端代理"

            return result

        except Exception as e:
            return f"❌ 检查环境时出错: {str(e)}"

    async def _install_environment(self, args: Dict[str, Any], context: ToolContext) -> str:
        """为指定发行版安装Python环境"""
        distribution = args.get("distribution")

        if not distribution:
            # 如果没有指定发行版，使用默认发行版
            default_dist = await self._get_default_distribution_name()
            if default_dist:
                distribution = default_dist
            else:
                return "❌ 请指定WSL发行版名称"

        result = f"🚀 [{distribution}] 安装Python环境\n\n"

        try:
            # 更新软件包列表
            result += "📦 更新软件包列表...\n"
            update_result = await self._run_wsl_command(
                distribution,
                "sudo apt-get update -qq"
            )
            if not update_result['success']:
                result += f"⚠️ 更新失败: {update_result['stderr']}\n"
            else:
                result += "✅ 更新完成\n"

            # 安装Python3和pip
            result += "📦 安装Python3和pip...\n"
            install_python = await self._run_wsl_command(
                distribution,
                "sudo apt-get install -y python3 python3-pip python3-dev"
            )
            if not install_python['success']:
                result += f"⚠️ 安装失败: {install_python['stderr']}\n"
            else:
                result += "✅ Python3和pip安装完成\n"

            # 安装aiohttp（使用apt安装系统包）
            result += "📦 安装aiohttp...\n"
            install_aiohttp = await self._run_wsl_command(
                distribution,
                "sudo apt-get install -y python3-aiohttp"
            )
            if not install_aiohttp['success']:
                result += f"⚠️ aiohttp安装失败: {install_aiohttp['stderr']}\n"
                result += "📝 提示: 可能需要手动安装: sudo apt-get install python3-aiohttp\n"
            else:
                result += "✅ aiohttp安装完成\n"

            result += "\n✅ 环境安装完成！现在可以使用WSL终端代理了"

            return result

        except Exception as e:
            return f"❌ 安装环境时出错: {str(e)}"

    async def _open_wsl(self, args: Dict[str, Any], context: ToolContext) -> str:
        """打开指定发行版的WSL终端"""
        distribution = args.get("distribution")
        skip_python_check = args.get("skip_python_check", False)

        # 如果没有指定发行版，使用默认发行版
        if not distribution:
            default_dist = await self._get_default_distribution_name()
            if default_dist:
                distribution = default_dist
            else:
                return "❌ 请指定WSL发行版名称"

        # 如果需要检查环境
        if not skip_python_check:
            env_check = await self._check_environment(args, context)
            # 检查是否所有组件都已安装
            if "❌ 未安装" in env_check:
                return env_check + "\n\n请先安装环境，或者使用 skip_python_check=true 跳过检查"

        try:
            # 获取项目根目录
            work_dir = str(Path(__file__).parent.parent.parent)

            # Windows路径转换为WSL路径
            wsl_work_dir = work_dir.replace("\\", "/")
            if len(wsl_work_dir) >= 2 and wsl_work_dir[1] == ":":
                drive_letter = wsl_work_dir[0].lower()
                wsl_work_dir = f"/mnt/{drive_letter}{wsl_work_dir[2:]}"

            # WSL中的脚本路径
            wsl_agent_script = wsl_work_dir + "/core/terminal_agent.py"

            # 生成会话ID
            import uuid
            session_id = str(uuid.uuid4())[:8]

            # 方案1: 使用 Windows Terminal 的 wt.exe
            try:
                # 根据发行版名称调整profile参数
                # Ubuntu发行版可能叫 "Ubuntu" 或 "Ubuntu-24.04"
                profile_name = distribution
                wsl_cmd = f'wt.exe -w 0 new-tab --profile "{profile_name}" -- wsl.exe -d {distribution} -- bash -c "cd {wsl_work_dir} && echo 正在启动弥娅终端代理... && python3 {wsl_agent_script} --session-id {session_id} && exec bash"'

                subprocess.Popen(
                    wsl_cmd,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                self.logger.info(f"已使用 Windows Terminal 打开 WSL [{distribution}] 窗口: {session_id}")

                result = f"✅ 已打开WSL终端\n"
                result += f"发行版: {distribution}\n"
                result += f"会话ID: {session_id}\n"
                result += f"工作目录: {work_dir}"

                return result

            except FileNotFoundError:
                # 方案2: 使用 start wsl
                self.logger.warning("Windows Terminal 未找到，使用 start wsl 命令")
                wsl_cmd = f'start wsl -d {distribution} bash -c "cd {wsl_work_dir} && echo 正在启动弥娅终端代理... && python3 {wsl_agent_script} --session-id {session_id} && exec bash"'

                subprocess.Popen(
                    wsl_cmd,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                self.logger.info(f"已使用 start wsl 打开 WSL [{distribution}] 窗口: {session_id}")

                result = f"✅ 已打开WSL终端\n"
                result += f"发行版: {distribution}\n"
                result += f"会话ID: {session_id}\n"
                result += f"工作目录: {work_dir}\n"
                result += f"注意: 使用了start命令打开窗口"

                return result

        except Exception as e:
            return f"❌ 打开WSL终端时出错: {str(e)}"

    async def _get_default_distribution(self) -> str:
        """获取默认WSL发行版"""
        default_dist = await self._get_default_distribution_name()

        if default_dist:
            return f"✅ 默认WSL发行版: {default_dist}"
        else:
            return "❌ 未找到默认WSL发行版"

    async def _get_default_distribution_name(self) -> Optional[str]:
        """获取默认WSL发行版名称"""
        try:
            result = subprocess.run(
                ["wsl", "--list", "--verbose"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                return None

            lines = result.stdout.strip().split('\n')
            for line in lines[1:]:  # 跳过标题行
                if line.strip() and line.startswith('*'):
                    # 提取默认发行版名称
                    parts = line.split()
                    if len(parts) >= 3:
                        return parts[0].replace('*', '').strip()

            return None

        except Exception as e:
            self.logger.error(f"获取默认发行版失败: {e}")
            return None

    async def _run_wsl_command(self, distribution: str, command: str) -> Dict[str, Any]:
        """
        在指定WSL发行版中执行命令

        Args:
            distribution: WSL发行版名称
            command: 要执行的命令

        Returns:
            包含success、stdout、stderr的字典
        """
        try:
            result = subprocess.run(
                ["wsl", "-d", distribution, "bash", "-c", command],
                capture_output=True,
                text=True,
                timeout=30
            )

            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }

        except Exception as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """验证参数"""
        action = args.get("action")

        if not action:
            return False, "缺少必填参数: action"

        if action in ["check_environment", "install_environment", "open_wsl"]:
            distribution = args.get("distribution")
            if not distribution:
                # 允许不指定发行版（使用默认发行版）
                pass

        return True, None
