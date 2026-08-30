"""
平台适配器 - 统一各平台的接入方式

职责：
1. 将不同平台的输入转换为统一的M-Link Message格式
2. 将M-Link Message转换回平台特定的响应格式
3. 平台能力检测（可用工具、限制等）

符合弥娅架构：
- 使用M-Link Message格式
- 支持五流传输
- 集成DecisionHub决策中枢
"""
import logging
from typing import Dict, Any, List
from datetime import datetime

from mlink.message import Message, MessageType, FlowType


logger = logging.getLogger(__name__)


class PlatformAdapter:
    """平台适配器基类"""
    
    def __init__(self, platform_name: str):
        self.platform_name = platform_name
        logger.info(f"[平台适配器] 初始化 {platform_name} 适配器")
    
    def to_message(self, user_input: str, context: Dict) -> Message:
        """
        将平台输入转换为M-Link Message
        
        Args:
            user_input: 用户输入
            context: 平台上下文
        
        Returns:
            M-Link Message (data_flow)
        """
        raise NotImplementedError
    
    def from_message(self, message: Message) -> Any:
        """
        将M-Link Message转换为平台响应格式
        
        Args:
            message: M-Link Message
        
        Returns:
            平台特定的响应对象
        """
        raise NotImplementedError
    
    def get_platform_info(self) -> Dict[str, Any]:
        """获取平台信息"""
        return {
            'platform': self.platform_name,
            'available_tools': self._get_available_tools(),
            'restrictions': self._get_restrictions(),
            'capabilities': self._get_capabilities()
        }
    
    def _get_available_tools(self) -> list:
        """获取平台可用工具"""
        raise NotImplementedError
    
    def _get_restrictions(self) -> Dict:
        """获取平台限制"""
        raise NotImplementedError
    
    def _get_capabilities(self) -> Dict:
        """获取平台能力"""
        raise NotImplementedError


class TerminalAdapter(PlatformAdapter):
    """终端平台适配器"""
    
    def __init__(self):
        super().__init__('terminal')
    
    def to_message(self, user_input: str, context: Dict) -> Message:
        """
        终端输入 → M-Link Message
        
        Args:
            user_input: 终端输入
            context: {'user_id': str, 'timestamp': datetime}
        """
        content = {
            'input': user_input,
            'user_id': context.get('user_id', 'terminal_user'),
            'platform': 'terminal',
            'timestamp': context.get('timestamp', datetime.now()),
            'metadata': context.get('metadata', {})
        }
        
        message = Message(
            msg_type=MessageType.DATA.value,
            content=content,
            source='terminal',
            destination='decision_hub',
            priority=1
        )
        
        logger.debug(f"[终端适配器] 输入转换为M-Link Message: {message.message_id}")
        return message
    
    def from_message(self, message: Message) -> str:
        """
        M-Link Message → 终端响应
        
        Args:
            message: M-Link Message
        
        Returns:
            响应文本
        """
        response = message.content.get('response', '')
        logger.debug(f"[终端适配器] M-Link Message转换为响应: {response[:50]}")
        return response
    
    def _get_available_tools(self) -> List[Dict[str, str]]:
        """获取平台可用工具（终端模式）"""
        return [
            {
                'name': 'terminal_execute',
                'description': '执行终端命令（支持 Windows/Linux/MacOS）。可以直接使用系统命令如 ls, pwd, cd, python, npm 等',
                'examples': [
                    '!ls - 列出当前目录文件',
                    '!pwd - 显示当前路径',
                    '!cd <目录> - 切换目录',
                    '!python script.py - 运行Python脚本',
                    '!npm start - 启动Node项目',
                    '!git status - 查看Git状态',
                ]
            },
            {
                'name': 'search_memory',
                'description': '搜索系统记忆（跨平台统一记忆）',
            },
            {
                'name': 'get_status',
                'description': '获取系统状态',
            },
            {
                'name': 'cross_platform_call',
                'description': '跨平台调用：可以触发QQ消息、PC文件操作等',
            },
        ]
    
    def _get_restrictions(self) -> Dict:
        """获取平台限制"""
        return {
            'max_message_length': 10000,
            'supports_media': False,
            'supports_group_chat': False,
            'supports_rich_text': False,
        }
    
    def _get_capabilities(self) -> Dict:
        """获取平台能力"""
        return {
            'execute_commands': True,
            'cross_platform_call': True,  # 可以调用QQ和PC工具
            'real_time_interaction': False,
        }


class QQAdapter(PlatformAdapter):
    """QQ平台适配器"""
    
    def __init__(self):
        super().__init__('qq')
    
    def to_message(self, user_input: str, context: Dict) -> Message:
        """
        QQ消息 → M-Link Message
        
        Args:
            user_input: QQ消息内容
            context: {
                'user_id': int,
                'group_id': int,
                'sender_name': str,
                'message_type': str,
                'is_at_bot': bool,
                'at_list': list,
                'timestamp': datetime
            }
        """
        content = {
            'content': user_input,
            'input': user_input,  # 兼容两种字段名
            'user_id': context.get('user_id'),
            'group_id': context.get('group_id'),
            'sender_name': context.get('sender_name'),
            'message_type': context.get('message_type', 'private'),
            'is_at_bot': context.get('is_at_bot', False),
            'at_list': context.get('at_list', []),
            'platform': 'qq',
            'timestamp': context.get('timestamp', datetime.now()),
            'metadata': context.get('metadata', {})
        }
        
        message = Message(
            msg_type=MessageType.DATA.value,
            content=content,
            source='qq_net',
            destination='decision_hub',
            priority=1
        )
        
        logger.debug(f"[QQ适配器] 输入转换为M-Link Message: {message.message_id}")
        return message
    
    def from_message(self, message: Message) -> Dict:
        """
        M-Link Message → QQ响应（需要发送的格式）
        
        Args:
            message: M-Link Message
        
        Returns:
            {'response': str, 'action': str, 'message_id': int}
        """
        response_data = {
            'response': message.content.get('response', ''),
            'action': message.content.get('action', 'send_message'),
            'message_id': message.content.get('message_id'),
        }
        
        logger.debug(f"[QQ适配器] M-Link Message转换为响应: {response_data['response'][:50]}")
        return response_data
    
    def _get_available_tools(self) -> List[str]:
        """获取平台可用工具"""
        return [
            'qq_send_message',      # 发送QQ消息
            'qq_send_like',        # QQ点赞
            'qq_get_group_info',    # 获取QQ群信息
            'pc_open_file',        # 跨平台：打开PC文件
            'pc_control_system',   # 跨平台：控制系统
            'pc_screenshot',       # 跨平台：截图
            'search_memory',         # 搜索记忆
            'get_status',           # 获取状态
        ]
    
    def _get_restrictions(self) -> Dict:
        """获取平台限制"""
        return {
            'max_message_length': 5000,
            'supports_media': True,
            'supports_group_chat': True,
            'supports_rich_text': True,
        }
    
    def _get_capabilities(self) -> Dict:
        """获取平台能力"""
        return {
            'execute_commands': False,
            'cross_platform_call': True,  # 可以调用PC工具
            'real_time_interaction': True,
        }


class PCUIAdapter(PlatformAdapter):
    """PC UI平台适配器"""

    def __init__(self):
        super().__init__('pc_ui')

    def to_message(self, user_input: str, context: Dict) -> Message:
        """
        PC UI输入 → M-Link Message

        Args:
            user_input: PC UI输入
            context: {
                'user_id': str,
                'session_id': str,
                'timestamp': datetime
            }
        """
        content = {
            'input': user_input,
            'user_id': context.get('user_id', 'pc_user'),
            'session_id': context.get('session_id'),
            'platform': 'pc_ui',
            'timestamp': context.get('timestamp', datetime.now()),
            'metadata': context.get('metadata', {})
        }

        message = Message(
            msg_type=MessageType.DATA.value,
            content=content,
            source='pc_ui',
            destination='decision_hub',
            priority=1
        )

        logger.debug(f"[PC UI适配器] 输入转换为M-Link Message: {message.message_id}")
        return message

    def from_message(self, message: Message) -> Dict:
        """
        M-Link Message → PC UI响应

        Args:
            message: M-Link Message

        Returns:
            {'response': str, 'emotion': dict, 'state': dict}
        """
        response_data = {
            'response': message.content.get('response', ''),
            'emotion': message.content.get('emotion'),
            'state': message.content.get('state'),
        }

        logger.debug(f"[PC UI适配器] M-Link Message转换为响应: {response_data['response'][:50]}")
        return response_data

    def _get_available_tools(self) -> List[str]:
        """获取平台可用工具"""
        return [
            'pc_open_file',         # 打开文件
            'pc_control_system',    # 控制系统
            'pc_screenshot',        # 截图
            'music_play',           # 播放音乐
            'note_create',          # 创建笔记
            'qq_send_message',      # 跨平台：发送QQ消息
            'qq_send_like',        # 跨平台：QQ点赞
            'search_memory',        # 搜索记忆
            'get_status',          # 获取状态
        ]

    def _get_restrictions(self) -> Dict:
        """获取平台限制"""
        return {
            'max_message_length': 50000,
            'supports_media': True,
            'supports_group_chat': True,
            'supports_rich_text': True,
        }

    def _get_capabilities(self) -> Dict:
        """获取平台能力"""
        return {
            'execute_commands': True,
            'cross_platform_call': True,  # 可以调用所有平台工具
            'real_time_interaction': True,
        }


class WebAdapter(PlatformAdapter):
    """Web平台适配器 - 弥娅Web端的掌控者"""

    def __init__(self):
        super().__init__('web')
        self.auto_detected_capabilities = {}
        self.system_resources = {}

    def to_message(self, user_input: str, context: Dict) -> Message:
        """
        Web输入 → M-Link Message

        Args:
            user_input: Web输入
            context: {
                'user_id': str,
                'session_id': str,
                'timestamp': datetime,
                'client_info': dict  # 客户端信息（浏览器、设备等）
            }
        """
        content = {
            'content': user_input,
            'input': user_input,  # 兼容两种字段名
            'user_id': context.get('user_id', 'web_user'),
            'session_id': context.get('session_id', 'web_session'),
            'platform': 'web',
            'timestamp': context.get('timestamp', datetime.now()),
            'client_info': context.get('client_info', {}),
            'metadata': context.get('metadata', {})
        }

        message = Message(
            msg_type=MessageType.DATA.value,
            content=content,
            source='web_api',
            destination='decision_hub',
            priority=1
        )

        logger.debug(f"[Web适配器] 输入转换为M-Link Message: {message.message_id}")
        return message

    def from_message(self, message: Message) -> Dict:
        """
        M-Link Message → Web响应

        Args:
            message: M-Link Message

        Returns:
            {'response': str, 'emotion': dict, 'state': dict, 'system_status': dict}
        """
        response_data = {
            'response': message.content.get('response', ''),
            'emotion': message.content.get('emotion'),
            'state': message.content.get('state'),
            'system_status': message.content.get('system_status'),
            'platform_info': self.get_platform_info()
        }

        logger.debug(f"[Web适配器] M-Link Message转换为响应: {response_data['response'][:50]}")
        return response_data

    def detect_system_capabilities(self) -> Dict:
        """
        自动检测系统能力

        Returns:
            系统能力检测结果
        """
        import platform as sys_platform
        import psutil

        capabilities = {
            'os': {
                'system': sys_platform.system(),
                'version': sys_platform.version(),
                'machine': sys_platform.machine(),
                'python_version': sys_platform.python_version()
            },
            'cpu': {
                'cores': psutil.cpu_count(logical=False),
                'threads': psutil.cpu_count(logical=True),
                'usage_percent': psutil.cpu_percent(interval=1)
            },
            'memory': {
                'total_gb': round(psutil.virtual_memory().total / (1024**3), 2),
                'available_gb': round(psutil.virtual_memory().available / (1024**3), 2),
                'usage_percent': psutil.virtual_memory().percent
            },
            'disk': {
                'total_gb': round(psutil.disk_usage('/').total / (1024**3), 2) if sys_platform.system() == 'Linux' else
                          round(psutil.disk_usage('C:\\').total / (1024**3), 2),
                'free_gb': round(psutil.disk_usage('/').free / (1024**3), 2) if sys_platform.system() == 'Linux' else
                          round(psutil.disk_usage('C:\\').free / (1024**3), 2),
                'usage_percent': psutil.disk_usage('/').percent if sys_platform.system() == 'Linux' else
                                psutil.disk_usage('C:\\').percent
            },
            'network': {
                'connections': len(psutil.net_connections()),
                'interfaces': list(psutil.net_if_addrs().keys())
            }
        }

        self.auto_detected_capabilities = capabilities
        logger.info(f"[Web适配器] 自动检测系统能力: OS={capabilities['os']['system']}, "
                   f"CPU={capabilities['cpu']['cores']}核, 内存={capabilities['memory']['total_gb']}GB")

        return capabilities

    def get_platform_info(self) -> Dict[str, Any]:
        """获取平台信息（包含自动检测结果）"""
        info = super().get_platform_info()

        # 添加自动检测的能力
        if not self.auto_detected_capabilities:
            self.detect_system_capabilities()

        info['system_capabilities'] = self.auto_detected_capabilities
        info['role'] = 'web_master'  # 标记Web端掌控者
        info['auto_detection'] = True

        return info

    def _get_available_tools(self) -> List[Dict[str, Any]]:
        """获取平台可用工具（Web端掌控者能力）"""
        return [
            {
                'name': 'terminal_execute',
                'description': '执行终端命令（支持 Windows/Linux/MacOS）。作为Web端掌控者，可以直接控制系统',
                'examples': [
                    '!ls - 列出当前目录文件',
                    '!pwd - 显示当前路径',
                    '!systeminfo - 查看系统信息',
                    '!python - 运行Python脚本',
                    '!npm start - 启动Node项目',
                    '!git status - 查看Git状态',
                    '!pip install - 安装Python包',
                ]
            },
            {
                'name': 'system_monitor',
                'description': '系统实时监控（CPU、内存、磁盘、网络）',
            },
            {
                'name': 'log_viewer',
                'description': '查看和分析系统日志',
            },
            {
                'name': 'search_memory',
                'description': '搜索系统记忆（跨平台统一记忆）',
            },
            {
                'name': 'get_status',
                'description': '获取弥娅完整系统状态',
            },
            {
                'name': 'autonomy_control',
                'description': '控制自主决策引擎（启动/停止/配置）',
            },
            {
                'name': 'security_control',
                'description': '安全系统控制（IP封禁、限流、威胁分析）',
            },
            {
                'name': 'blog_create',
                'description': '创建博客文章',
            },
            {
                'name': 'blog_read',
                'description': '读取博客文章',
            },
            {
                'name': 'git_operations',
                'description': 'Git操作（提交、推送、拉取、分支管理）',
            },
            {
                'name': 'deploy_control',
                'description': '部署控制（启动/停止服务、环境配置）',
            }
        ]

    def _get_restrictions(self) -> Dict:
        """获取平台限制"""
        return {
            'max_message_length': 10000,
            'supports_media': True,
            'supports_group_chat': False,
            'supports_rich_text': True,
        }

    def _get_capabilities(self) -> Dict:
        """获取平台能力"""
        return {
            'execute_commands': True,  # 支持终端命令
            'cross_platform_call': True,  # Web端掌控者可以调用所有平台工具
            'real_time_interaction': True,
            'system_monitoring': True,  # 系统监控
            'log_management': True,  # 日志管理
            'autonomy_control': True,  # 自主决策控制
            'security_control': True,  # 安全控制
            'deployment_control': True,  # 部署控制
            'auto_detection': True,  # 自动检测
            'full_control': True  # 完全掌控
        }


def get_adapter(platform_name: str) -> PlatformAdapter:
    """
    获取平台适配器

    Args:
        platform_name: 平台名称 ('terminal', 'qq', 'pc_ui', 'web', 'desktop')

    Returns:
        平台适配器实例

    Raises:
        ValueError: 不支持的平台
    """
    adapters = {
        'terminal': TerminalAdapter(),
        'qq': QQAdapter(),
        'pc_ui': PCUIAdapter(),
        'web': WebAdapter(),
        'desktop': PCUIAdapter()  # desktop 平台使用与 PCUI 相同的适配器
    }

    adapter = adapters.get(platform_name)
    if not adapter:
        raise ValueError(f"不支持的平台: {platform_name}，支持的平台: {list(adapters.keys())}")

    return adapter


__all__ = [
    'PlatformAdapter',
    'TerminalAdapter',
    'QQAdapter',
    'PCUIAdapter',
    'WebAdapter',
    'get_adapter',
]
