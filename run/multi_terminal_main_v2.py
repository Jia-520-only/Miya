"""
弥娅V4.0 - 多终端交互Shell

支持单机多终端管理的交互式界面
集成弥娅框架的完整AI能力和统一提示词管理系统
"""

import asyncio
import sys
import os
import platform
import random
import json
from pathlib import Path
from typing import List, Dict, Optional

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.terminal_orchestrator import IntelligentTerminalOrchestrator
from core.terminal_types import TerminalType
from core.prompt_manager import PromptManager
from core.ai_client import AIMessage, AIClientFactory
from dotenv import load_dotenv


class MiyaTerminalAI:
    """弥娅终端AI - 集成完整AI能力"""

    def __init__(self):
        """初始化AI系统"""
        # 初始化提示词管理器
        self.prompt_manager = PromptManager()

        # 加载配置
        self._load_config()

        # 初始化AI客户端
        self.ai_client = None
        self._init_ai_client()

        # 对话历史
        self.conversation_history: List[AIMessage] = []

        # 终端状态上下文
        self.terminal_context: Dict = {}

        # 是否启用AI处理
        self.ai_enabled = True

    def _load_config(self):
        """加载配置"""
        try:
            config_path = Path(__file__).parent.parent / 'config' / '.env'
            if config_path.exists():
                load_dotenv(config_path)

                # 加载终端模式专用提示词
                terminal_prompt_path = Path(__file__).parent.parent / 'prompts' / 'miya_terminal.json'
                if terminal_prompt_path.exists():
                    with open(terminal_prompt_path, 'r', encoding='utf-8') as f:
                        prompt_config = json.load(f)
                    self.prompt_manager._custom_system_prompt = prompt_config.get('system_prompt', '')
                    self.prompt_manager.user_prompt_template = prompt_config.get('user_prompt_template', '用户输入：{user_input}')
                    self.prompt_manager.memory_context_enabled = prompt_config.get('memory_context_enabled', True)
                    self.prompt_manager.memory_context_max_count = prompt_config.get('memory_context_max_count', 10)
        except Exception as e:
            print(f"[警告] 加载配置失败: {e}")

    def _init_ai_client(self):
        """初始化AI客户端"""
        try:
            api_key = os.getenv('DEEPSEEK_API_KEY') or os.getenv('OPENAI_API_KEY')
            if not api_key:
                self.ai_enabled = False
                print("[弥娅] 未配置AI API密钥,使用基础交互模式")
                return

            provider = os.getenv('AI_PROVIDER', 'deepseek')
            model = os.getenv('AI_MODEL', 'deepseek-chat')

            self.ai_client = AIClientFactory.create_client(
                provider=provider,
                api_key=api_key,
                model=model,
                personality=None  # 使用统一提示词管理
            )
            print("[弥娅] AI系统初始化完成")
        except Exception as e:
            self.ai_enabled = False
            print(f"[警告] AI客户端初始化失败: {e}, 使用基础交互模式")

    def get_greeting(self) -> str:
        """获取随机问候"""
        greetings = [
            "在的!我是弥娅,您的多终端智能助手~",
            "你好呀!弥娅在线为您服务",
            "在呢~有什么我可以帮您的吗?",
            "弥娅来了!请问有什么指令?",
            "我在!随时准备执行您的任务"
        ]
        return random.choice(greetings)

    def is_greeting(self, text: str) -> bool:
        """判断是否为问候"""
        greetings = ['在吗', '你好', 'hi', 'hello', '在', '嗨', '您好', '哈喽']
        text_lower = text.lower().strip()
        return any(g in text_lower for g in greetings)

    def get_help_response(self) -> str:
        """获取帮助响应"""
        return """弥娅多终端管理系统 v4.0

🎯 核心功能:
  • 单机多终端: 同时控制多个CMD/PowerShell/Bash终端
  • AI智能编排: 自动分析任务并分配到最优终端
  • 并行执行: 多终端同时执行任务提高效率
  • 远程连接: 支持SSH连接远程服务器
  • 自然语言理解: 像和人对话一样,我理解您的意图

📝 常用命令:
  !help          - 查看完整命令帮助
  !list           - 列出所有终端
  !create <name>  - 创建新终端
  ? <任务描述>    - AI智能执行任务

💡 对话示例:
  "帮我看看当前目录有什么文件" - 我会自动执行 ls/dir
  "在终端1运行Python脚本,终端2查看日志" - 我会智能分配并执行
  "我想创建一个新的PowerShell终端" - 我会自动创建
  "看看现在的终端状态" - 我会列出所有终端信息

需要更多帮助,请输入 !help"""

    def get_system_prompt(self) -> str:
        """获取当前系统提示词"""
        return self.prompt_manager.get_system_prompt()

    def get_prompt_info(self) -> dict:
        """获取提示词信息"""
        return {
            'system_prompt': self.get_system_prompt()[:100] + '...' if len(self.get_system_prompt()) > 100 else self.get_system_prompt(),
            'user_template': self.prompt_manager.user_prompt_template,
            'memory_enabled': self.prompt_manager.memory_context_enabled,
            'memory_max_count': self.prompt_manager.memory_context_max_count
        }

    async def process_with_ai(
        self,
        user_input: str,
        terminal_manager: Optional[object] = None
    ) -> Dict:
        """使用AI处理用户输入

        Args:
            user_input: 用户输入
            terminal_manager: 终端管理器实例

        Returns:
            处理结果
        """
        if not self.ai_enabled or not self.ai_client:
            return {
                'success': False,
                'type': 'conversation',
                'message': 'AI未配置,使用基础交互模式',
                'needs_command': False,
                'commands': []
            }

        # 更新终端上下文
        if terminal_manager:
            all_status = terminal_manager.get_all_status()
            self.terminal_context = {
                'terminals': all_status,
                'active_session': terminal_manager.active_session_id,
                'system': platform.system(),
                'current_dir': os.getcwd()
            }

        # 构建消息
        system_prompt = self.get_system_prompt()

        messages = [AIMessage(role='system', content=system_prompt)]

        # 添加历史对话(保留最近10轮)
        if self.conversation_history:
            messages.extend(self.conversation_history[-10:])

        # 添加当前用户输入
        messages.append(AIMessage(role='user', content=user_input))

        # 调用AI
        try:
            response = await self.ai_client.chat(
                messages=messages,
                use_miya_prompt=False  # 已经在system中包含
            )

            # 保存到历史
            self.conversation_history.append(AIMessage(role='user', content=user_input))
            self.conversation_history.append(AIMessage(role='assistant', content=response))

            # 分析响应,判断是否需要执行命令
            return self._analyze_ai_response(response, terminal_manager)

        except Exception as e:
            return {
                'success': False,
                'type': 'error',
                'message': f'AI处理失败: {e}',
                'needs_command': False,
                'commands': []
            }

    def _analyze_ai_response(self, response: str, terminal_manager: Optional[object]) -> Dict:
        """分析AI响应,判断意图

        Args:
            response: AI响应内容
            terminal_manager: 终端管理器

        Returns:
            分析结果
        """
        # 检查是否包含执行命令的标记
        # AI可以通过特定格式返回需要执行的命令

        commands = []

        # 简单的实现: 检查是否包含终端命令格式
        # 更好的方式是让AI返回结构化数据

        # 检查是否是明确的命令执行请求
        cmd_keywords = ['执行', '运行', 'run', 'execute', 'cmd', 'command']
        if any(keyword in response.lower() for keyword in cmd_keywords):
            return {
                'success': True,
                'type': 'command_execution',
                'message': response,
                'needs_command': True,
                'commands': commands
            }

        # 默认为对话响应
        return {
            'success': True,
            'type': 'conversation',
            'message': response,
            'needs_command': False,
            'commands': []
        }


class MiyaMultiTerminalShell:
    """弥娅多终端交互Shell - 完整AI能力版本"""

    def __init__(self):
        self.orchestrator = IntelligentTerminalOrchestrator()
        self.running = True
        # 初始化AI系统
        self.ai = MiyaTerminalAI()
        # 显示提示词信息
        prompt_info = self.ai.get_prompt_info()
        print(f"[弥娅] 已加载统一提示词配置")
        print(f"        AI功能: {'启用' if self.ai.ai_enabled else '禁用'}")
        print(f"        记忆功能: {'启用' if prompt_info['memory_enabled'] else '禁用'}")

    async def start(self):
        """启动多终端Shell"""

        self._show_banner()

        # 创建默认终端
        await self._init_default_terminals()

        # 主循环
        while self.running:
            try:
                user_input = await self._get_prompt_input()

                if not user_input:
                    continue

                await self._process_input(user_input)

            except KeyboardInterrupt:
                print("\n[弥娅] 正在关闭所有终端...")
                await self.orchestrator.terminal_manager.close_all_sessions()
                print("[弥娅] 期待下次再见到您~ 再见!")
                self.running = False
                break
            except Exception as e:
                print(f"\n[错误] {e}")

    def _show_banner(self):
        """显示横幅"""
        print("""
╔════════════════════════════════════════════════════════════╗
║                  弥娅 V4.0 - 多终端智能管理系统            ║
║                  Miya Multi-Terminal System             ║
╠════════════════════════════════════════════════════════════╣
║  🖥️  单机多终端  │  🤖  AI智能编排  │  🔄  协同执行  ║
║  📊  实时监控    │  🧠  自然语言理解  │  🎯  智能路由  ║
╚════════════════════════════════════════════════════════════╝

输入 '!help' 查看命令帮助
直接输入自然语言或命令,我会理解您的意图~
        """)

    async def _init_default_terminals(self):
        """初始化默认终端"""

        # 根据系统创建默认终端
        system = platform.system()

        if system == "Windows":
            # Windows: 创建CMD
            cmd_id = await self.orchestrator.terminal_manager.create_terminal(
                name="CMD主终端",
                terminal_type=TerminalType.CMD
            )

            await self.orchestrator.terminal_manager.switch_session(cmd_id)

        elif system == "Linux":
            # Linux: 创建Bash
            bash_id = await self.orchestrator.terminal_manager.create_terminal(
                name="Bash主终端",
                terminal_type=TerminalType.BASH
            )

            await self.orchestrator.terminal_manager.switch_session(bash_id)

        elif system == "Darwin":
            # macOS: 创建Zsh
            zsh_id = await self.orchestrator.terminal_manager.create_terminal(
                name="Zsh主终端",
                terminal_type=TerminalType.ZSH
            )

            await self.orchestrator.terminal_manager.switch_session(zsh_id)

    async def _get_prompt_input(self) -> str:
        """获取用户输入"""

        # 获取活动终端
        active_session = self.orchestrator.terminal_manager.active_session_id
        session_info = None

        if active_session:
            session_info = self.orchestrator.terminal_manager.get_session_status(
                active_session
            )

        # 构建提示符
        if session_info:
            active_mark = "★" if session_info['is_active'] else ""
            prompt = f"[弥娅] {session_info['name']}{active_mark} > "
        else:
            prompt = "[弥娅] > "

        return input(prompt).strip()

    async def _process_input(self, user_input: str):
        """处理用户输入 - 使用AI智能处理"""

        # 空输入
        if not user_input:
            return

        # 系统命令
        if user_input.startswith('!'):
            await self._handle_system_command(user_input)

        # AI命令
        elif user_input.startswith('?'):
            await self._handle_ai_command(user_input)

        # 普通输入 - 使用AI智能处理
        else:
            # 检查是否为问候
            if self.ai.is_greeting(user_input):
                print(f"\n{self.ai.get_greeting()}\n")
                return

            # 检查是否为帮助请求
            if user_input.lower().strip() in ['help', '帮助']:
                print(f"\n{self.ai.get_help_response()}\n")
                return

            # 使用AI处理所有其他输入
            if self.ai.ai_enabled:
                result = await self.ai.process_with_ai(
                    user_input,
                    self.orchestrator.terminal_manager
                )

                if result['success']:
                    # 显示AI的回复
                    if result['message']:
                        print(f"\n{result['message']}\n")

                    # 如果需要执行命令
                    if result['needs_command'] and result.get('commands'):
                        await self._execute_ai_commands(result['commands'])
                else:
                    # AI处理失败,回退到直接执行命令模式
                    await self._execute_direct_command(user_input)
            else:
                # AI未启用,直接执行命令
                await self._execute_direct_command(user_input)

    async def _execute_ai_commands(self, commands: List[Dict]):
        """执行AI生成的命令"""
        for cmd_info in commands:
            session_id = cmd_info.get('session_id')
            command = cmd_info.get('command')

            if session_id and command:
                result = await self.orchestrator.terminal_manager.execute_command(
                    session_id,
                    command
                )

                if result.output:
                    print(f"[{session_id}] {result.output}\n")

    async def _execute_direct_command(self, command: str):
        """直接执行命令(当AI未启用或失败时)"""
        if self.orchestrator.terminal_manager.active_session_id:
            print(f"\n[执行命令] {command}\n")

            try:
                result = await self.orchestrator.terminal_manager.execute_command(
                    self.orchestrator.terminal_manager.active_session_id,
                    command
                )

                # 显示结果
                if result.output and result.output.strip():
                    print(f"{result.output}\n")

                if result.error and result.error.strip():
                    print(f"[错误] {result.error}\n")

                if not result.success:
                    print(f"[状态] 命令执行失败 (退出码: {result.exit_code})\n")

            except Exception as e:
                print(f"[错误] 执行命令时出错: {e}\n")
                print(f"提示: 请确认 '{command}' 是有效的系统命令\n")
        else:
            print("\n[弥娅] 还没有创建终端呢~ 使用 !create <name> 创建一个吧!\n")

    async def _handle_system_command(self, command: str):
        """处理系统命令"""

        parts = command.split()
        cmd = parts[0].lower()

        if cmd == '!help' or cmd == '!h':
            self._show_help()

        elif cmd == '!create' or cmd == '!new':
            # 创建新终端
            await self._create_terminal(parts)

        elif cmd == '!list' or cmd == '!ls':
            # 列出所有终端
            await self._list_terminals()

        elif cmd == '!switch' or cmd == '!use':
            # 切换终端
            if len(parts) > 1:
                await self.orchestrator.terminal_manager.switch_session(
                    parts[1]
                )
                print(f"[弥娅] 已切换到终端 {parts[1]}")
            else:
                print("[弥娅] 告诉我要切换到哪个终端呢? 用法: !switch <session_id>")

        elif cmd == '!close' or cmd == '!del':
            # 关闭终端
            if len(parts) > 1:
                await self.orchestrator.terminal_manager.close_session(
                    parts[1]
                )
                print(f"[弥娅] 已为您关闭终端 {parts[1]}")
            else:
                print("[弥娅] 告诉我要关闭哪个终端呢? 用法: !close <session_id>")

        elif cmd == '!parallel':
            # 并行执行
            await self._execute_parallel(parts[1:])

        elif cmd == '!sequence':
            # 顺序执行
            await self._execute_sequence(parts[1:])

        elif cmd == '!collab':
            # 协同任务
            if len(parts) > 1:
                task_desc = ' '.join(parts[1:])
                print(f"[弥娅] 好的,让我来分析并执行这个任务: {task_desc}")
                await self.orchestrator.collaborative_task(task_desc)
            else:
                print("[弥娅] 告诉我您想执行什么任务呢? 用法: !collab <任务描述>")

        elif cmd == '!workspace' or cmd == '!ws':
            # 自动设置工作空间
            if len(parts) > 2:
                project_type = parts[1]
                project_dir = ' '.join(parts[2:])
                print(f"[弥娅] 好的,让我来帮您设置 {project_type} 工作空间")
                await self.orchestrator.auto_setup_workspace(
                    project_type, project_dir
                )
            else:
                print("[弥娅] 告诉我项目类型和目录哦~ 用法: !workspace <project_type> <project_dir>")

        elif cmd == '!status' or cmd == '!info':
            # 详细状态
            await self._show_detailed_status()

        elif cmd == '!exit' or cmd == '!quit':
            # 退出
            print(f"[弥娅] 期待下次再见到您~ 再见!")
            self.running = False

        else:
            print(f"[弥娅] 我不太理解 '{cmd}' 这个命令呢...")
            print("输入 '!help' 查看所有可用命令吧")

    async def _handle_ai_command(self, command: str):
        """处理AI命令"""

        parts = command.split(maxsplit=1)
        cmd = parts[0]

        if cmd == '?' or cmd == '?ai':
            # AI智能执行
            if len(parts) > 1:
                task = parts[1]
                print(f"[弥娅] 好的,让我来分析这个任务: {task}")
                result = await self.orchestrator.smart_execute(task)
                print(f"\n[执行结果]")
                print(f"  策略: {result.get('strategy', 'unknown')}")

                if result.get('session_name'):
                    print(f"  终端: {result['session_name']}")

                if 'result' in result:
                    print(f"  输出: {result['result']['output'][:100]}...")

                if 'results' in result:
                    print(f"  并行结果: {len(result['results'])}个终端")
                    for sid, res in result['results'].items():
                        print(f"    {sid}: {res['success']}")

        else:
            print(f"[未知AI命令] {cmd}")
            print("输入 '?help' 查看帮助")

    async def _create_terminal(self, parts: List[str]):
        """创建新终端"""

        name = None
        term_type = TerminalType.CMD

        # 解析参数
        i = 1
        while i < len(parts):
            if parts[i] == '-t' or parts[i] == '--type':
                if i + 1 < len(parts):
                    term_type = TerminalType.from_string(parts[i + 1])
                    i += 2
                else:
                    print("[错误] -t 参数需要值")
                    return
            else:
                name = parts[i]
                i += 1

        if not name:
            count = len(self.orchestrator.terminal_manager.sessions)
            name = f"终端{count+1}"

        session_id = await self.orchestrator.terminal_manager.create_terminal(
            name=name,
            terminal_type=term_type
        )

        print(f"[弥娅] 已为您创建终端: {name} (ID: {session_id})")
        print(f"        类型: {term_type.value}")
        print(f"        提示: 使用 !switch {session_id} 切换到这个终端")

    async def _list_terminals(self):
        """列出所有终端"""

        all_status = self.orchestrator.terminal_manager.get_all_status()

        if not all_status:
            print("\n[弥娅] 当前还没有创建任何终端呢~")
            print("提示: 使用 !create <name> 来创建一个新终端吧!\n")
            return

        print(f"\n{'='*70}")
        print(f"{'终端列表':<20} {'类型':<15} {'状态':<10} {'目录':<20}")
        print(f"{'='*70}")

        for session_id, status in all_status.items():
            active_mark = "★" if status['is_active'] else " "
            print(f"{active_mark} {status['name']:<18} {status['type']:<15} "
                  f"{status['status']:<10} {status['directory'][:20]:<20}")

        print(f"{'='*70}\n")

    async def _execute_parallel(self, parts: List[str]):
        """并行执行命令"""

        if not parts:
            print("用法: !parallel <session1:cmd1> <session2:cmd2>")
            return

        commands = {}
        for part in parts:
            if ':' in part:
                sid, cmd = part.split(':', 1)
                commands[sid] = cmd

        if commands:
            print(f"[并行执行] {len(commands)}个任务")
            results = await self.orchestrator.terminal_manager.execute_parallel(
                commands
            )

            for sid, result in results.items():
                mark = "✓" if result.success else "✗"
                output = result.output[:80] if result.output else ""
                print(f"  {sid}: {mark} {output}")

    async def _execute_sequence(self, parts: List[str]):
        """顺序执行命令"""

        if len(parts) < 2:
            print("用法: !sequence <session_id> <cmd1> <cmd2> ...")
            return

        session_id = parts[0]
        commands = parts[1:]

        print(f"[顺序执行] {len(commands)}个命令在终端 {session_id}")

        results = await self.orchestrator.terminal_manager.execute_sequence(
            session_id, commands
        )

        for i, result in enumerate(results, 1):
            mark = "✓" if result.success else "✗"
            cmd = commands[i-1][:40]
            print(f"  命令{i}: {mark} {cmd}")

    async def _show_detailed_status(self):
        """显示详细状态"""

        all_status = self.orchestrator.terminal_manager.get_all_status()

        if not all_status:
            print("\n[弥娅] 当前还没有创建任何终端呢~\n")
            return

        print(f"\n{'='*70}")
        print("                弥娅多终端系统状态")
        print(f"{'='*70}")

        for session_id, status in all_status.items():
            active_str = " (活动中)" if status['is_active'] else ""
            print(f"\n📱 终端: {status['name']}{active_str}")
            print(f"   ID: {session_id}")
            print(f"   类型: {status['type']}")
            print(f"   状态: {status['status']}")
            print(f"   目录: {status['directory']}")
            print(f"   命令历史: {status['command_count']}条")
            print(f"   输出记录: {status['output_count']}条")

        print(f"\n{'='*70}\n")

    def _show_help(self):
        """显示帮助"""
        print("""
╔════════════════════════════════════════════════════════════╗
║                    弥娅多终端管理系统 - 帮助                  ║
╠════════════════════════════════════════════════════════════╣
║                                                               ║
║  🖥️  终端管理:                                              ║
║    !create <name> [-t type]  - 创建新终端                       ║
║    !list                     - 列出所有终端                     ║
║    !switch <session_id>      - 切换活动终端                     ║
║    !close <session_id>       - 关闭指定终端                     ║
║    !status                   - 显示详细状态                     ║
║                                                               ║
║  ⚡  执行模式:                                              ║
║    !parallel <sid:cmd>...    - 多终端并行执行                   ║
║    !sequence <sid> <cmd>...   - 单终端顺序执行                   ║
║    !collab <task>           - 多终端协同任务                   ║
║    !workspace <type> <dir>   - 自动设置工作空间                 ║
║                                                               ║
║  🤖  AI智能:                                               ║
║    ? <task>                  - AI智能执行任务                   ║
║    直接输入自然语言或命令      - 我会理解您的意图并智能处理        ║
║                                                               ║
║  💡  自然语言示例:                                          ║
║    "帮我看看当前目录有什么文件"    - 自动执行 ls/dir           ║
║    "创建一个PowerShell终端"      - 自动创建终端               ║
║    "在终端1运行Python脚本"        - 智能分配并执行             ║
║                                                               ║
║  🚪  退出:                                                  ║
║    !exit / !quit             - 退出系统                         ║
║    Ctrl+C                   - 强制退出                         ║
║                                                               ║
╚════════════════════════════════════════════════════════════╝
        """)


# 主入口
async def main():
    """主函数"""
    shell = MiyaMultiTerminalShell()
    await shell.start()


if __name__ == "__main__":
    asyncio.run(main())
