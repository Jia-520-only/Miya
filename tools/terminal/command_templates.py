"""
命令链模板库
预定义常见操作的多步骤命令流程
"""
import logging
from typing import List, Dict, Any
from .command_chain import CommandChain, Step, StepStatus

logger = logging.getLogger(__name__)


class CommandChainTemplates:
    """命令链模板库"""

    @staticmethod
    def kali_update_system() -> CommandChain:
        """Kali Linux 更新系统"""
        chain = CommandChain(
            id="kali_update_system",
            name="Kali Linux 系统更新",
            description="更新 Kali Linux 系统到最新版本"
        )

        chain.add_step(Step(
            id="check_root",
            name="检查 root 权限",
            command="whoami",
            description="检查是否以 root 用户运行",
        ))

        chain.add_step(Step(
            id="update_repos",
            name="更新软件源",
            command="apt update",
            description="更新软件包列表",
            dependencies=["check_root"],
        ))

        chain.add_step(Step(
            id="upgrade_packages",
            name="升级软件包",
            command="apt upgrade -y",
            description="升级已安装的软件包",
            dependencies=["update_repos"],
        ))

        chain.add_step(Step(
            id="dist_upgrade",
            name="发行版升级",
            command="apt dist-upgrade -y",
            description="升级到新版本（如果可用）",
            dependencies=["upgrade_packages"],
        ))

        chain.add_step(Step(
            id="clean_cache",
            name="清理缓存",
            command="apt autoremove -y && apt autoclean",
            description="清理不需要的软件包和缓存",
            dependencies=["dist_upgrade"],
        ))

        return chain

    @staticmethod
    def kali_install_tools(tools: List[str]) -> CommandChain:
        """
        Kali Linux 安装安全工具

        Args:
            tools: 要安装的工具列表（如 ['nmap', 'wireshark', 'metasploit']）
        """
        chain = CommandChain(
            id="kali_install_tools",
            name="Kali 安装安全工具",
            description=f"安装安全工具: {', '.join(tools)}"
        )

        chain.add_step(Step(
            id="check_root",
            name="检查 root 权限",
            command="whoami",
            description="检查是否以 root 用户运行",
        ))

        chain.add_step(Step(
            id="update_repos",
            name="更新软件源",
            command="apt update",
            description="更新软件包列表",
            dependencies=["check_root"],
        ))

        # 为每个工具添加安装步骤
        for i, tool in enumerate(tools):
            chain.add_step(Step(
                id=f"install_{tool}",
                name=f"安装 {tool}",
                command=f"apt install -y {tool}",
                description=f"安装 {tool} 工具",
                dependencies=["update_repos"] + [f"install_{tools[j]}" for j in range(i)],
            ))

        return chain

    @staticmethod
    def ubuntu_set_timezone(timezone: str = "Asia/Shanghai") -> CommandChain:
        """
        Ubuntu 设置时区

        Args:
            timezone: 时区（默认 Asia/Shanghai）
        """
        chain = CommandChain(
            id="ubuntu_set_timezone",
            name="Ubuntu 设置时区",
            description=f"设置系统时区为 {timezone}"
        )

        chain.add_step(Step(
            id="check_root",
            name="检查 root 权限",
            command="whoami",
            description="检查是否以 root 用户运行",
        ))

        chain.add_step(Step(
            id="list_timezones",
            name="列出可用时区",
            command="timedatectl list-timezones | grep -i asia",
            description="列出亚洲时区",
            dependencies=["check_root"],
        ))

        chain.add_step(Step(
            id="set_timezone",
            name="设置时区",
            command=f"timedatectl set-timezone {timezone}",
            description=f"设置时区为 {timezone}",
            dependencies=["list_timezones"],
        ))

        chain.add_step(Step(
            id="verify_timezone",
            name="验证时区",
            command="timedatectl",
            description="验证时区设置是否成功",
            dependencies=["set_timezone"],
        ))

        return chain

    @staticmethod
    def docker_setup() -> CommandChain:
        """Docker 安装和配置"""
        chain = CommandChain(
            id="docker_setup",
            name="Docker 安装配置",
            description="安装和配置 Docker"
        )

        chain.add_step(Step(
            id="check_root",
            name="检查 root 权限",
            command="whoami",
            description="检查是否以 root 用户运行",
        ))

        chain.add_step(Step(
            id="update_repos",
            name="更新软件源",
            command="apt update",
            description="更新软件包列表",
            dependencies=["check_root"],
        ))

        chain.add_step(Step(
            id="install_dependencies",
            name="安装依赖",
            command="apt install -y apt-transport-https ca-certificates curl gnupg lsb-release",
            description="安装 Docker 依赖",
            dependencies=["update_repos"],
        ))

        chain.add_step(Step(
            id="add_docker_key",
            name="添加 Docker GPG 密钥",
            command="curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg",
            description="添加 Docker 官方 GPG 密钥",
            dependencies=["install_dependencies"],
        ))

        chain.add_step(Step(
            id="add_docker_repo",
            name="添加 Docker 仓库",
            command="echo \"deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable\" | tee /etc/apt/sources.list.d/docker.list > /dev/null",
            description="添加 Docker 官方仓库",
            dependencies=["add_docker_key"],
        ))

        chain.add_step(Step(
            id="update_repos_docker",
            name="更新软件源（含 Docker）",
            command="apt update",
            description="更新软件包列表（包含 Docker 仓库）",
            dependencies=["add_docker_repo"],
        ))

        chain.add_step(Step(
            id="install_docker",
            name="安装 Docker",
            command="apt install -y docker-ce docker-ce-cli containerd.io",
            description="安装 Docker Engine",
            dependencies=["update_repos_docker"],
        ))

        chain.add_step(Step(
            id="start_docker",
            name="启动 Docker",
            command="systemctl start docker && systemctl enable docker",
            description="启动并设置 Docker 开机自启",
            dependencies=["install_docker"],
        ))

        chain.add_step(Step(
            id="verify_docker",
            name="验证 Docker",
            command="docker --version && docker run hello-world",
            description="验证 Docker 安装是否成功",
            dependencies=["start_docker"],
        ))

        return chain

    @staticmethod
    def python_project_setup(project_name: str, requirements: List[str] = None) -> CommandChain:
        """
        Python 项目设置

        Args:
            project_name: 项目名称
            requirements: 需求列表（可选）
        """
        chain = CommandChain(
            id="python_project_setup",
            name="Python 项目设置",
            description=f"创建并配置 Python 项目: {project_name}"
        )

        chain.add_step(Step(
            id="create_dir",
            name="创建项目目录",
            command=f"mkdir -p {project_name}",
            description=f"创建 {project_name} 目录",
        ))

        chain.add_step(Step(
            id="create_venv",
            name="创建虚拟环境",
            command=f"cd {project_name} && python3 -m venv venv",
            description="创建 Python 虚拟环境",
            dependencies=["create_dir"],
        ))

        chain.add_step(Step(
            id="activate_venv",
            name="激活虚拟环境",
            command=f"cd {project_name} && source venv/bin/activate",
            description="激活虚拟环境",
            dependencies=["create_venv"],
        ))

        chain.add_step(Step(
            id="upgrade_pip",
            name="升级 pip",
            command=f"cd {project_name} && python -m pip install --upgrade pip",
            description="升级 pip 到最新版本",
            dependencies=["activate_venv"],
        ))

        chain.add_step(Step(
            id="create_requirements",
            name="创建 requirements.txt",
            command=f"cd {project_name} && touch requirements.txt",
            description="创建 requirements.txt 文件",
            dependencies=["create_dir"],
        ))

        if requirements:
            for req in requirements:
                chain.add_step(Step(
                    id=f"install_{req}",
                    name=f"安装 {req}",
                    command=f"cd {project_name} && pip install {req}",
                    description=f"安装 {req}",
                    dependencies=["upgrade_pip"],
                ))

        return chain

    @staticmethod
    def git_setup(repo_url: str, branch: str = "main") -> CommandChain:
        """
        Git 仓库克隆和配置

        Args:
            repo_url: 仓库 URL
            branch: 分支名称（默认 main）
        """
        chain = CommandChain(
            id="git_setup",
            name="Git 仓库设置",
            description=f"克隆并配置 Git 仓库: {repo_url}"
        )

        chain.add_step(Step(
            id="check_git",
            name="检查 Git 安装",
            command="git --version",
            description="检查 Git 是否已安装",
        ))

        chain.add_step(Step(
            id="clone_repo",
            name="克隆仓库",
            command=f"git clone -b {branch} {repo_url}",
            description=f"克隆仓库的 {branch} 分支",
            dependencies=["check_git"],
        ))

        chain.add_step(Step(
            id="show_branch",
            name="显示当前分支",
            command="cd $(basename {repo_url} .git) && git branch",
            description="显示当前所在分支",
            dependencies=["clone_repo"],
        ))

        return chain

    @staticmethod
    def nodejs_project_setup(project_name: str) -> CommandChain:
        """
        Node.js 项目设置

        Args:
            project_name: 项目名称
        """
        chain = CommandChain(
            id="nodejs_project_setup",
            name="Node.js 项目设置",
            description=f"创建并配置 Node.js 项目: {project_name}"
        )

        chain.add_step(Step(
            id="check_node",
            name="检查 Node.js",
            command="node --version && npm --version",
            description="检查 Node.js 和 npm 版本",
        ))

        chain.add_step(Step(
            id="create_dir",
            name="创建项目目录",
            command=f"mkdir -p {project_name}",
            description=f"创建 {project_name} 目录",
        ))

        chain.add_step(Step(
            id="init_project",
            name="初始化项目",
            command=f"cd {project_name} && npm init -y",
            description="初始化 npm 项目",
            dependencies=["create_dir"],
        ))

        chain.add_step(Step(
            id="install_typescript",
            name="安装 TypeScript",
            command=f"cd {project_name} && npm install -D typescript @types/node",
            description="安装 TypeScript 和类型定义",
            dependencies=["init_project"],
        ))

        chain.add_step(Step(
            id="create_tsconfig",
            name="创建 tsconfig.json",
            command=f"cd {project_name} && npx tsc --init",
            description="创建 TypeScript 配置文件",
            dependencies=["install_typescript"],
        ))

        return chain

    @staticmethod
    def get_all_templates() -> Dict[str, CommandChain]:
        """获取所有模板"""
        return {
            "kali_update_system": CommandChainTemplates.kali_update_system(),
            "kali_install_tools": CommandChainTemplates.kali_install_tools(['nmap', 'wireshark']),
            "ubuntu_set_timezone": CommandChainTemplates.ubuntu_set_timezone(),
            "docker_setup": CommandChainTemplates.docker_setup(),
            "python_project_setup": CommandChainTemplates.python_project_setup("my_project"),
            "git_setup": CommandChainTemplates.git_setup("https://github.com/example/repo.git"),
            "nodejs_project_setup": CommandChainTemplates.nodejs_project_setup("my-node-app"),
        }
