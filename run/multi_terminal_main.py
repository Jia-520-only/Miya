"""
弥娅V4.0 - 多终端交互Shell

支持单机多终端管理的交互式界面
"""

import asyncio
import sys
import os
from core.terminal_orchestrator import IntelligentTerminalOrchestrator
from core.terminal_types import TerminalType

class MiyaMultiTerminalShell:
    """弥娅多终端交互Shell"""
    
    def __init__(self):
        self.orchestrator = IntelligentTerminalOrchestrator()
        self.running = True
    
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
                print("[弥娅] 再见！")
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
║  📊  实时监控    │  🧠  深度思考    │  🎯  智能路由  ║
╚════════════════════════════════════════════════════════════╝

输入 '!help' 查看命令帮助
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
        """处理用户输入"""
        
        # 空输入
        if not user_input:
            return
        
        # 系统命令
        if user_input.startswith('!'):
            await self._handle_system_command(user_input)
        
        # AI命令
        elif user_input.startswith('?'):
            await self._handle_ai_command(user_input)
        
        # 普通命令 - 在当前终端执行
        else:
            if self.orchestrator.terminal_manager.active_session_id:
                result = await self.orchestrator.terminal_manager.execute_command(
                    self.orchestrator.terminal_manager.active_session_id,
                    user_input
                )
                
                # 显示结果
                if result.output:
                    print(f"\n{result.output}\n")
            else:
                print("\n[弥娅] 没有活动终端，请先创建或切换终端\n")
    
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
            else:
                print("[用法] !switch <session_id>")
        
        elif cmd == '!close' or cmd == '!del':
            # 关闭终端
            if len(parts) > 1:
                await self.orchestrator.terminal_manager.close_session(
                    parts[1]
                )
                print(f"[弥娅] 已关闭终端 {parts[1]}")
            else:
                print("[用法] !close <session_id>")
        
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
                await self.orchestrator.collaborative_task(task_desc)
            else:
                print("[用法] !collab <task_description>")
        
        elif cmd == '!workspace' or cmd == '!ws':
            # 自动设置工作空间
            if len(parts) > 2:
                project_type = parts[1]
                project_dir = ' '.join(parts[2:])
                await self.orchestrator.auto_setup_workspace(
                    project_type, project_dir
                )
            else:
                print("[用法] !workspace <project_type> <project_dir>")
        
        elif cmd == '!status' or cmd == '!info':
            # 详细状态
            await self._show_detailed_status()
        
        elif cmd == '!exit' or cmd == '!quit':
            # 退出
            self.running = False
        
        else:
            print(f"[未知命令] {cmd}")
            print("输入 '!help' 查看帮助")
    
    async def _handle_ai_command(self, command: str):
        """处理AI命令"""
        
        parts = command.split(maxsplit=1)
        cmd = parts[0]
        
        if cmd == '?' or cmd == '?ai':
            # AI智能执行
            if len(parts) > 1:
                task = parts[1]
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
        
        print(f"[成功] 创建终端: {name} (ID: {session_id})")
        print(f"       类型: {term_type.value}")
    
    async def _list_terminals(self):
        """列出所有终端"""
        
        all_status = self.orchestrator.terminal_manager.get_all_status()
        
        if not all_status:
            print("\n[弥娅] 当前没有打开的终端\n")
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
            print("\n[弥娅] 当前没有打开的终端\n")
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
║                                                               ║
║  💡  普通命令:                                              ║
║    直接输入命令                - 在当前终端执行                   ║
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
