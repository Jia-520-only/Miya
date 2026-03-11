"""
终端工具模块
弥娅的终端命令执行能力，集成到 DecisionHub

【框架一致性说明】
- Terminal Tool 是纯命令执行器,不理解自然语言
- 自然语言理解由 DecisionHub + AI (GPT-4o) 完成
- 输出通过人格系统染色
- 命令执行记录到记忆系统
"""
import os
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

from .command_executor import CommandExecutor, ExecutionResult
from .security import SecurityAuditor, SecurityLevel
from .platform_detector import detect_platform, detect_linux_distro, get_system_info
from .command_history import CommandHistory
from .command_chain import CommandChain, CommandChainManager, StepStatus
from .command_templates import CommandChainTemplates

logger = logging.getLogger(__name__)


class TerminalTool:
    """终端工具 - 纯命令执行器（符合弥娅框架）"""

    def __init__(self, config_path: Optional[str] = None, emotion=None, memory_engine=None):
        """
        初始化终端工具

        Args:
            config_path: 配置文件路径
            emotion: 情绪系统（用于人格染色）
            memory_engine: 记忆引擎（用于记录命令执行）
        """
        # 加载配置
        self.config = self._load_config(config_path)

        # 初始化组件
        self.executor = CommandExecutor()
        self.auditor = SecurityAuditor(
            security_level=self.config.get('security_level', 'safe')
        )
        self.history = CommandHistory()

        # 初始化命令链管理器
        self.chain_manager = CommandChainManager()
        self._register_templates()

        # 工作目录
        self.work_dir = os.path.abspath(
            self.config.get('work_dir', os.getcwd())
        )

        # 待确认的命令缓存
        self.pending_command = None
        self.pending_security_level = None

        # 【框架一致性】集成人格系统（情绪染色）
        self.emotion = emotion

        # 【框架一致性】集成记忆系统
        self.memory_engine = memory_engine

        logger.info(f"终端工具初始化成功，工作目录: {self.work_dir}")

    def _register_templates(self):
        """注册命令链模板"""
        templates = CommandChainTemplates.get_all_templates()
        for template_id, template in templates.items():
            self.chain_manager.register_template(template)
        logger.info(f"已注册 {len(templates)} 个命令链模板")

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """加载配置文件"""
        if config_path is None:
            # 默认配置路径
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / 'config' / 'terminal_config.json'

        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # 默认配置
            return {
                'security_level': 'safe',
                'max_execution_time': 30,
                'work_dir': os.getcwd(),
                'enable_history': True,
                'enable_ai': False,
            }

    def execute(self, command: str, user_confirm: Optional[bool] = None) -> Dict[str, Any]:
        """
        执行终端命令（纯命令执行，不理解自然语言）

        【框架一致性说明】
        - 不理解自然语言，只接受直接命令
        - 自然语言理解由 DecisionHub + AI 完成
        - 执行后通过人格染色输出
        - 记录到记忆系统

        Args:
            command: 命令字符串（必须是实际命令，非自然语言）
            user_confirm: 用户是否确认（None 表示需要询问）

        Returns:
            Dict[str, Any]: 执行结果
        """
        logger.info(f"终端工具执行命令: {command}")

        # 1. 安全审计
        security_level, warning = self.auditor.audit(command)
        safety_desc = self.auditor.get_safety_description(command)

        logger.info(f"命令安全等级: {security_level.value} - {safety_desc}")

        # 2. 检查是否需要确认
        needs_confirmation = self.auditor.needs_confirmation(command)

        if needs_confirmation and user_confirm is None:
            # 保存待确认的命令
            self.pending_command = command
            self.pending_security_level = security_level

            return {
                'success': False,
                'message': '命令需要确认',
                'command': command,
                'security_level': security_level.value,
                'warning': warning,
                'safety_description': safety_desc,
                'needs_confirmation': True
            }

        if needs_confirmation and not user_confirm:
            # 取消命令，清除缓存
            self.pending_command = None
            self.pending_security_level = None

            return {
                'success': False,
                'message': '操作已取消',
                'command': command,
            }

        # 3. 执行命令
        try:
            result = self._execute_command(command)
            # 执行成功，清除待确认的命令缓存
            self.pending_command = None
            self.pending_security_level = None
        except Exception as e:
            import traceback
            logger.error(f"命令执行异常: {e}")
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            return {
                'success': False,
                'message': f'命令执行失败: {str(e)}',
                'command': command,
                'return_code': -1,
                'stderr': str(e),
            }

        # 4. 记录历史
        if self.config.get('enable_history', True):
            self.history.record(
                input_text=command,
                command=command,
                result=result
            )

        # 5. 【框架一致性】记录到记忆系统
        if self.memory_engine:
            try:
                # 获取主导情绪
                emotion_type = self.emotion.get_dominant_emotion() if self.emotion else 'neutral'

                # 记录到潮汐记忆
                self.memory_engine.store_tide(
                    memory_id=f"cmd_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
                    content={
                        'type': 'terminal_command',
                        'command': command,
                        'success': result.success,
                        'platform': result.platform,
                        'execution_time': result.execution_time
                    },
                    priority=0.3 if result.success else 0.6,  # 失败的命令优先级更高
                    ttl=3600
                )
                logger.info(f"命令已记录到记忆系统: {command}")
            except Exception as e:
                logger.warning(f"记录到记忆系统失败: {e}")

        # 6. 返回结果（不带人格染色，由调用方处理）
        return {
            'success': result.success,
            'command': command,
            'return_code': result.return_code,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'execution_time': result.execution_time,
            'platform': result.platform,
            'security_level': security_level.value,
        }

    def _execute_command(self, command: str) -> ExecutionResult:
        """
        执行命令（内部方法）

        Args:
            command: 命令字符串

        Returns:
            ExecutionResult: 执行结果
        """
        timeout = self.config.get('max_execution_time', 30)

        # 如果是 cd 命令，特殊处理（更新工作目录）
        if command.startswith('cd '):
            target_dir = command[3:].strip()

            # 处理相对路径和特殊符号
            if target_dir == '..':
                new_dir = os.path.dirname(self.work_dir)
            elif target_dir == '~':
                new_dir = os.path.expanduser('~')
            elif target_dir == '-':
                new_dir = self.history.get_last_directory(self.work_dir) or self.work_dir
            else:
                new_dir = os.path.join(self.work_dir, target_dir)

            # 检查目录是否存在
            if os.path.isdir(new_dir):
                old_dir = self.work_dir
                self.work_dir = os.path.abspath(new_dir)
                logger.info(f"目录切换: {old_dir} -> {self.work_dir}")

                return ExecutionResult(
                    command=command,
                    return_code=0,
                    stdout=f"已切换到: {self.work_dir}",
                    stderr="",
                    success=True,
                    execution_time=0.0,
                    platform=detect_platform().value,
                    timestamp=datetime.now()
                )
            else:
                return ExecutionResult(
                    command=command,
                    return_code=1,
                    stdout="",
                    stderr=f"目录不存在: {new_dir}",
                    success=False,
                    execution_time=0.0,
                    platform=detect_platform().value,
                    timestamp=datetime.now()
                )

        # 其他命令正常执行
        return self.executor.execute(command, timeout=timeout)

    def get_status(self) -> Dict[str, Any]:
        """
        获取工具状态

        Returns:
            Dict[str, Any]: 状态信息
        """
        platform = detect_platform()
        status = {
            'platform': platform.value,
            'work_directory': self.work_dir,
            'security_level': self.config.get('security_level'),
            'statistics': self.executor.get_statistics(),
            'history_count': self.history.get_count(),
        }

        # 如果是 Linux，添加发行版信息
        if platform.value == 'linux':
            distro = detect_linux_distro()
            status['linux_distro'] = distro.value

        return status

    def get_system_info(self) -> Dict[str, Any]:
        """
        获取详细的系统信息

        Returns:
            Dict[str, Any]: 系统信息
        """
        return get_system_info()

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取命令历史

        Args:
            limit: 返回数量限制

        Returns:
            List[Dict[str, Any]]: 命令历史
        """
        return self.history.get_recent(limit)

    def clear_history(self) -> None:
        """清空命令历史"""
        self.history.clear()
        logger.info("命令历史已清空")

    def format_result(self, result: Dict[str, Any]) -> str:
        """
        格式化执行结果供用户查看（带人格染色）

        【框架一致性说明】
        - 通过人格系统染色输出
        - 保持弥娅的"高冷温柔"风格

        Args:
            result: 执行结果字典

        Returns:
            str: 格式化后的字符串（已人格染色）
        """
        # 调试：打印完整的 result
        logger.debug(f"format_result 收到的 result: {result}")

        if not result.get('success'):
            # 执行失败
            if result.get('needs_confirmation'):
                # 需要确认的情况 - 保持简洁
                lines = []
                lines.append(f"⚠️  命令需要确认")
                lines.append(f"命令: {result.get('command')}")
                lines.append(f"安全等级: {result.get('security_level')}")
                if result.get('warning'):
                    lines.append(f"警告: {result.get('warning')}")
                lines.append(f"说明: {result.get('safety_description', '')}")
                lines.append("\n输入 '确认' 继续执行，或输入 '取消' 放弃")
                raw_output = '\n'.join(lines)
            else:
                # 执行失败，提供更详细的错误信息
                error_msg = result.get('message', '未知错误')
                return_code = result.get('return_code', 'unknown')
                stderr = result.get('stderr', '')
                
                if stderr:
                    raw_output = f"❌ 执行失败: {error_msg}\n返回码: {return_code}\n错误信息: {stderr}"
                else:
                    raw_output = f"❌ 执行失败: {error_msg}\n返回码: {return_code}"
        else:
            # 执行成功
            lines = []
            lines.append(f"✅ 命令执行成功")
            lines.append(f"命令: {result.get('command')}")
            lines.append(f"耗时: {result.get('execution_time', 0):.2f}秒")
            lines.append(f"平台: {result.get('platform')}")

            stdout = result.get('stdout', '').strip()
            stderr = result.get('stderr', '').strip()

            if stdout:
                lines.append("\n【输出】")
                lines.append(stdout)

            if stderr:
                lines.append("\n【错误】")
                lines.append(stderr)

            raw_output = '\n'.join(lines)

        # 【框架一致性】通过人格系统染色
        if self.emotion:
            try:
                colored_output = self.emotion.influence_response(raw_output)
                logger.info(f"输出已人格染色")
                return colored_output
            except Exception as e:
                logger.warning(f"人格染色失败: {e}")

        return raw_output

    def get_command_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取命令执行历史

        Args:
            limit: 返回数量限制

        Returns:
            List[Dict[str, Any]]: 命令历史列表
        """
        return self.history.get_recent(limit)

    def get_command_statistics(self) -> Dict[str, Any]:
        """
        获取命令执行统计信息

        Returns:
            Dict[str, Any]: 统计数据
        """
        return self.history.get_statistics()

    # ========== 命令链相关方法 ==========

    def get_available_templates(self) -> List[Dict[str, Any]]:
        """
        获取可用的命令链模板

        Returns:
            模板列表
        """
        templates = CommandChainTemplates.get_all_templates()
        return [
            {
                'id': t.id,
                'name': t.name,
                'description': t.description,
                'steps_count': len(t.steps),
            }
            for t in templates.values()
        ]

    def execute_chain_template(self, template_id: str, **kwargs) -> Dict[str, Any]:
        """
        执行命令链模板

        Args:
            template_id: 模板 ID
            **kwargs: 模板参数

        Returns:
            执行结果
        """
        # 获取模板
        template = self.chain_manager.get_template(template_id)
        if not template:
            return {
                'success': False,
                'message': f'模板不存在: {template_id}',
            }

        # 克隆模板（避免修改原模板）
        from copy import deepcopy
        chain = deepcopy(template)
        chain.id = f"{template_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 注册新命令链
        self.chain_manager.chains[chain.id] = chain

        # 执行命令链
        def executor(command: str) -> Dict[str, Any]:
            """内部执行器"""
            result = self._execute_command(command)
            return {
                'success': result.success,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'execution_time': result.execution_time,
            }

        try:
            success = self.chain_manager.execute_chain(chain.id, executor)

            # 【框架一致性】记录命令链执行到记忆
            if self.memory_engine:
                try:
                    self.memory_engine.store_tide(
                        memory_id=f"chain_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
                        content={
                            'type': 'command_chain',
                            'template_id': template_id,
                            'chain_name': chain.name,
                            'success': success,
                        },
                        priority=0.5,
                        ttl=7200  # 命令链保留更久
                    )
                except Exception as e:
                    logger.warning(f"记录命令链到记忆失败: {e}")

            return {
                'success': success,
                'chain_id': chain.id,
                'chain_name': chain.name,
                'progress': chain.get_progress(),
                'report': chain.get_report(),
            }
        except Exception as e:
            logger.error(f"命令链执行失败: {e}")
            return {
                'success': False,
                'message': f'命令链执行失败: {str(e)}',
                'chain_id': chain.id,
            }

    def get_chain_status(self, chain_id: str) -> Optional[Dict[str, Any]]:
        """
        获取命令链状态

        Args:
            chain_id: 命令链 ID

        Returns:
            状态信息
        """
        chain = self.chain_manager.get_chain(chain_id)
        if not chain:
            return None

        return {
            'id': chain.id,
            'name': chain.name,
            'description': chain.description,
            'status': chain.status.value,
            'progress': chain.get_progress(),
            'report': chain.get_report(),
        }

    def list_chains(self) -> List[Dict[str, Any]]:
        """
        列出所有命令链

        Returns:
            命令链列表
        """
        return self.chain_manager.list_chains()

    def format_chain_result(self, result: Dict[str, Any]) -> str:
        """
        格式化命令链执行结果

        Args:
            result: 执行结果字典

        Returns:
            格式化后的字符串
        """
        if not result.get('success'):
            raw_output = f"❌ 命令链执行失败: {result.get('message', '未知错误')}"
        else:
            lines = []
            lines.append(f"✅ 命令链执行成功")
            lines.append(f"名称: {result.get('chain_name')}")
            lines.append(f"ID: {result.get('chain_id')}")

            progress = result.get('progress', {})
            lines.append(f"进度: {progress.get('progress_percent', 0):.1f}% ({progress.get('completed', 0)}/{progress.get('total', 0)})")

            if 'report' in result:
                lines.append("\n【执行报告】")
                lines.append(result['report'])

            raw_output = '\n'.join(lines)

        # 【框架一致性】通过人格系统染色
        if self.emotion:
            try:
                colored_output = self.emotion.influence_response(raw_output)
                return colored_output
            except Exception as e:
                logger.warning(f"人格染色失败: {e}")

        return raw_output
