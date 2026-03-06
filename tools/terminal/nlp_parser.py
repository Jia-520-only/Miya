"""
自然语言解析模块
将自然语言转换为终端命令
"""
import os
import logging
from typing import Optional, Dict, List, Tuple
from enum import Enum
import re

logger = logging.getLogger(__name__)


class CommandIntent(Enum):
    """命令意图"""
    VIEW = "view"           # 查看
    NAVIGATE = "navigate"   # 导航
    DELETE = "delete"       # 删除
    COPY = "copy"          # 复制
    MOVE = "move"          # 移动
    CREATE = "create"       # 创建
    RUN = "run"            # 运行
    CHECK = "check"        # 检查
    SEARCH = "search"      # 搜索
    CHAIN = "chain"        # 命令链
    UNKNOWN = "unknown"     # 未知


class NLPParser:
    """自然语言解析器 - 将自然语言转换为命令"""

    def __init__(self):
        # 关键词到意图的映射
        self.keyword_map = {
            # 查看相关
            '查看': CommandIntent.VIEW,
            '看': CommandIntent.VIEW,
            '显示': CommandIntent.VIEW,
            '列出': CommandIntent.VIEW,
            '浏览': CommandIntent.VIEW,
            '读取': CommandIntent.VIEW,

            # 导航相关
            '进入': CommandIntent.NAVIGATE,
            '切换': CommandIntent.NAVIGATE,
            '去': CommandIntent.NAVIGATE,
            '到': CommandIntent.NAVIGATE,
            '打开': CommandIntent.NAVIGATE,

            # 删除相关
            '删除': CommandIntent.DELETE,
            '移除': CommandIntent.DELETE,
            '清空': CommandIntent.DELETE,
            '擦除': CommandIntent.DELETE,

            # 复制相关
            '复制': CommandIntent.COPY,
            '拷贝': CommandIntent.COPY,

            # 移动相关
            '移动': CommandIntent.MOVE,
            '重命名': CommandIntent.MOVE,

            # 创建相关
            '创建': CommandIntent.CREATE,
            '新建': CommandIntent.CREATE,
            '新建文件夹': CommandIntent.CREATE,
            '新建文件': CommandIntent.CREATE,

            # 运行相关
            '运行': CommandIntent.RUN,
            '执行': CommandIntent.RUN,
            '启动': CommandIntent.RUN,

            # 检查相关
            '检查': CommandIntent.CHECK,
            '测试': CommandIntent.CHECK,
            '验证': CommandIntent.CHECK,

            # 搜索相关
            '搜索': CommandIntent.SEARCH,
            '查找': CommandIntent.SEARCH,
            '寻找': CommandIntent.SEARCH,
            '找': CommandIntent.SEARCH,

            # 命令链相关
            '更新': CommandIntent.CHAIN,
            '安装': CommandIntent.CHAIN,
            '部署': CommandIntent.CHAIN,
            '设置': CommandIntent.CHAIN,
            '配置': CommandIntent.CHAIN,
            '初始化': CommandIntent.CHAIN,
            '搭建': CommandIntent.CHAIN,
            '构建': CommandIntent.CHAIN,
        }

        # 命令链模板映射（自然语言到模板ID）
        self.chain_templates = {
            # Kali 更新
            '更新系统': 'kali_update_system',
            '更新 kali': 'kali_update_system',
            'kali 更新': 'kali_update_system',

            # Kali 工具安装
            '安装工具': 'kali_install_tools',
            '安装安全工具': 'kali_install_tools',

            # Ubuntu 时区
            '设置时区': 'ubuntu_set_timezone',
            '修改时区': 'ubuntu_set_timezone',
            '配置时区': 'ubuntu_set_timezone',

            # Docker 安装
            '安装 docker': 'docker_setup',
            '部署 docker': 'docker_setup',
            '配置 docker': 'docker_setup',

            # Python 项目
            '创建 python 项目': 'python_project_setup',
            '初始化 python 项目': 'python_project_setup',
            '搭建 python 项目': 'python_project_setup',

            # Git 仓库
            '克隆仓库': 'git_setup',
            '拉取代码': 'git_setup',
            '下载代码': 'git_setup',

            # Node.js 项目
            '创建 nodejs 项目': 'nodejs_project_setup',
            '初始化 nodejs 项目': 'nodejs_project_setup',
            '搭建 nodejs 项目': 'nodejs_project_setup',
        }

        # 命令模板映射
        self.command_templates = {
            # 查看命令
            CommandIntent.VIEW: [
                (r'当前目录', 'ls'),
                (r'当前路径', 'pwd'),
                (r'当前文件夹', 'ls'),
                (r'所有文件', 'ls -la'),
                (r'日志(.*)', lambda m: f"tail -n 100 {m.group(1).strip()}"),
                (r'最近(\d+)行日志(.*)', lambda m: f"tail -n {m.group(1)} {m.group(2).strip()}"),
            ],

            # 导航命令
            CommandIntent.NAVIGATE: [
                (r'(.*)目录', lambda m: f"cd {m.group(1).strip()}"),
                (r'(.*)文件夹', lambda m: f"cd {m.group(1).strip()}"),
            ],

            # 删除命令
            CommandIntent.DELETE: [
                (r'(.*)文件', lambda m: f"rm {m.group(1).strip()}"),
                (r'(.*)目录', lambda m: f"rm -rf {m.group(1).strip()}"),
            ],

            # 复制命令
            CommandIntent.COPY: [
                (r'(.*)到(.*)', lambda m: f"cp {m.group(1).strip()} {m.group(2).strip()}"),
            ],

            # 移动命令
            CommandIntent.MOVE: [
                (r'(.*)到(.*)', lambda m: f"mv {m.group(1).strip()} {m.group(2).strip()}"),
            ],

            # 创建命令
            CommandIntent.CREATE: [
                (r'(.*)文件', lambda m: f"touch {m.group(1).strip()}"),
                (r'(.*)目录', lambda m: f"mkdir {m.group(1).strip()}"),
                (r'(.*)文件夹', lambda m: f"mkdir {m.group(1).strip()}"),
            ],

            # 运行命令
            CommandIntent.RUN: [
                (r'测试', 'pytest'),
                (r'构建', 'npm run build'),
                (r'启动', 'npm start'),
            ],

            # 检查命令
            CommandIntent.CHECK: [
                (r'Git状态', 'git status'),
                (r'系统状态', 'ps aux'),
                (r'磁盘使用', 'df -h'),
                (r'内存使用', 'free -h'),
            ],

            # 搜索命令 - 根据平台自动选择
            CommandIntent.SEARCH: [
                (r'(.*)在(.*)中', lambda m: self._get_search_command(m.group(1).strip(), m.group(2).strip())),
                (r'搜索(.*)', lambda m: self._get_search_command(m.group(1).strip(), '.')),
                (r'查找(.*)', lambda m: self._get_find_command(m.group(1).strip())),
            ],
        }

    def parse(self, text: str) -> Tuple[CommandIntent, Optional[str]]:
        """
        解析自然语言输入

        Args:
            text: 自然语言文本

        Returns:
            Tuple[CommandIntent, Optional[str]]: (意图, 生成的命令)
        """
        text = text.strip()
        logger.info(f"解析自然语言: {text}")

        # 0. 优先检查直接命令（常见的 Linux/Windows 命令）
        direct_command = self._check_direct_command(text)
        if direct_command:
            logger.info(f"识别为直接命令: {direct_command}")
            return CommandIntent.VIEW, direct_command

        # 0.5 检查是否是命令链请求
        chain_template = self._check_chain_template(text)
        if chain_template:
            logger.info(f"识别为命令链模板: {chain_template}")
            return CommandIntent.CHAIN, chain_template

        # 1. 提取关键词意图
        intent = self._extract_intent(text)

        # 2. 根据意图匹配命令模板
        command = self._match_template(intent, text)

        if command:
            logger.info(f"生成命令: {command}")
            return intent, command

        # 3. 未匹配到模板，返回意图但无命令
        logger.warning(f"未找到匹配的命令模板")
        return intent, None

    def _get_search_command(self, pattern: str, path: str = '.') -> str:
        """
        根据平台生成搜索命令

        Args:
            pattern: 搜索模式
            path: 搜索路径

        Returns:
            str: 平台特定的搜索命令
        """
        from .platform_detector import Platform, detect_platform
        platform = detect_platform()

        if platform == Platform.WINDOWS:
            # Windows 使用 Select-String
            return f'Select-String -Path "{path}" -Pattern "{pattern}" -Recurse'
        else:
            # Linux/MacOS 使用 grep
            return f'grep -r "{pattern}" {path}'

    def _get_find_command(self, pattern: str) -> str:
        """
        根据平台生成查找命令

        Args:
            pattern: 文件名模式

        Returns:
            str: 平台特定的查找命令
        """
        from .platform_detector import Platform, detect_platform
        platform = detect_platform()

        if platform == Platform.WINDOWS:
            # Windows 使用 Get-ChildItem
            return f'Get-ChildItem -Path . -Recurse -Filter "*{pattern}*"'
        else:
            # Linux/MacOS 使用 find
            return f'find . -name "*{pattern}*"'

    def _check_direct_command(self, text: str) -> Optional[str]:
        """
        检查是否是直接的终端命令

        Args:
            text: 输入文本

        Returns:
            Optional[str]: 如果是直接命令则返回命令本身，否则返回 None
        """
        # 常见的 Linux/Windows 命令列表
        direct_commands = {
            # 文件操作
            'ls', 'll', 'la', 'dir',
            'pwd', 'cd',
            'cat', 'less', 'more', 'head', 'tail',
            'cp', 'copy', 'mv', 'move', 'rm', 'del', 'rmdir',
            'mkdir', 'md', 'touch', 'echo',

            # 系统信息
            'ps', 'top', 'htop',
            'df', 'du', 'free',
            'uname', 'hostname',
            'whoami', 'who', 'w',

            # 网络
            'ping', 'ifconfig', 'ipconfig', 'netstat',
            'curl', 'wget', 'ssh', 'scp',

            # Git
            'git', 'clone', 'push', 'pull', 'status', 'log',

            # 开发工具
            'python', 'python3', 'pip', 'pip3',
            'npm', 'node', 'yarn', 'pnpm',
            'docker', 'docker-compose',
            'grep', 'find', 'locate', 'which', 'where',

            # 文本处理
            'wc', 'sort', 'uniq', 'cut', 'awk', 'sed',

            # 压缩解压
            'tar', 'zip', 'unzip', 'gzip', 'gunzip',

            # 权限管理
            'chmod', 'chown', 'sudo', 'su',

            # 其他
            'man', 'help', 'clear', 'cls',

            # 应用程序
            'firefox', 'chrome', 'google-chrome', 'edge', 'msedge',
            'notepad', 'code', 'vim', 'nano', 'gedit',
            'explorer', 'nautilus', 'dolphin', 'thunar',
            'vlc', 'mpv', 'spotify', 'discord',
        }

        # 检查是否是单个命令
        if text in direct_commands:
            return text

        # 检查是否以已知命令开头（支持带参数的命令）
        for cmd in direct_commands:
            if text.startswith(cmd + ' '):
                return text

        # 检查是否是带连字符的命令（如 ls -la）
        parts = text.split()
        if parts and parts[0] in direct_commands:
            return text

        return None

    def _check_app_launch(self, text: str) -> Optional[str]:
        """
        检查是否是应用程序启动请求

        Args:
            text: 输入文本

        Returns:
            Optional[str]: 如果是应用启动则返回命令，否则返回 None
        """
        # 应用程序名称映射（中文 -> 英文命令）
        app_map = {
            # 浏览器
            '火狐': 'firefox',
            'firefox': 'firefox',
            '谷歌': 'google-chrome' if os.name != 'nt' else 'chrome',
            'chrome': 'chrome',
            '浏览器': 'firefox',  # 默认火狐
            'edge': 'msedge',
            'Edge': 'msedge',
            '微软': 'msedge',

            # 编辑器
            '记事本': 'notepad' if os.name == 'nt' else 'gedit',
            'vscode': 'code',
            'vs': 'code',
            'vim': 'vim',
            'nano': 'nano',

            # 文件管理
            '资源管理器': 'explorer' if os.name == 'nt' else 'nautilus',
            '文件管理': 'explorer' if os.name == 'nt' else 'nautilus',

            # 多媒体
            'vlc': 'vlc',
            'mpv': 'mpv',
            '音乐': 'spotify' if os.name != 'nt' else 'wmplayer',

            # 通讯
            'discord': 'discord',
            '微信': 'wechat',
            'qq': 'qq',
        }

        # 检查"打开"或"启动"模式 - 支持包含关系
        action_keywords = ['打开', '启动', '运行', 'open', 'start', 'run', 'launch']

        # 先检查是否包含动作关键词
        has_action = any(keyword in text for keyword in action_keywords)

        if has_action:
            # 提取应用名 - 在动作关键词之后的内容
            for keyword in action_keywords:
                if keyword in text:
                    # 获取关键词后面的内容
                    idx = text.index(keyword)
                    app_name = text[idx + len(keyword):].strip()

                    # 如果有"我"、"帮我"等前缀,去掉它们
                    if app_name.startswith('我'):
                        app_name = app_name[1:].strip()
                    if app_name.startswith('帮我'):
                        app_name = app_name[2:].strip()

                    # 匹配应用名
                    for cn_name, cmd in app_map.items():
                        if cn_name.lower() in app_name.lower() or app_name.lower() in cn_name.lower():
                            logger.info(f"识别到应用启动: {app_name} -> {cmd}")
                            return cmd

        return None

    def _check_chain_template(self, text: str) -> Optional[str]:
        """
        检查是否是命令链模板请求

        Args:
            text: 输入文本

        Returns:
            Optional[str]: 如果匹配模板则返回模板ID，否则返回 None
        """
        text_lower = text.lower().strip()

        # 检查是否匹配任何模板关键词
        for keyword, template_id in self.chain_templates.items():
            if keyword in text_lower:
                logger.info(f"匹配到命令链模板: {keyword} -> {template_id}")
                return template_id

        return None

    def _extract_intent(self, text: str) -> CommandIntent:
        """从文本中提取意图"""
        for keyword, intent in self.keyword_map.items():
            if keyword in text:
                return intent
        return CommandIntent.UNKNOWN

    def _match_template(self, intent: CommandIntent, text: str) -> Optional[str]:
        """匹配命令模板"""
        if intent not in self.command_templates:
            return None

        templates = self.command_templates[intent]

        for pattern in templates:
            match = re.search(pattern[0], text)
            if match:
                if callable(pattern[1]):
                    # 如果是 lambda 函数，执行它
                    return pattern[1](match)
                else:
                    # 如果是静态命令，直接返回
                    return pattern[1]

        return None

    def get_suggestions(self, text: str) -> List[str]:
        """
        获取命令建议

        Args:
            text: 用户输入

        Returns:
            List[str]: 建议的命令列表
        """
        intent, command = self.parse(text)

        if command:
            return [command]

        # 根据意图提供通用建议
        suggestions = []

        if intent == CommandIntent.VIEW:
            suggestions = [
                'ls -la',           # 查看当前目录所有文件
                'pwd',              # 查看当前路径
                'cat <filename>',   # 查看文件内容
                'tail -f <file>',   # 实时查看日志
            ]
        elif intent == CommandIntent.NAVIGATE:
            suggestions = [
                'cd <directory>',   # 切换目录
                'cd ..',           # 返回上级目录
                'cd ~',            # 回到主目录
            ]
        elif intent == CommandIntent.SEARCH:
            suggestions = [
                'grep -r "keyword" .',    # 搜索文件内容
                'find . -name "*.py"',     # 查找Python文件
                'find . -name "filename"', # 查找文件
            ]
        elif intent == CommandIntent.CHECK:
            suggestions = [
                'git status',       # 检查Git状态
                'ps aux',          # 查看进程
                'df -h',           # 查看磁盘使用
                'free -h',         # 查看内存使用
            ]
        else:
            suggestions = [
                'help',            # 获取帮助
                'ls',              # 列出文件
                'pwd',             # 查看路径
            ]

        return suggestions
