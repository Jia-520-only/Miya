"""
智能执行器模块
负责执行任务、处理结果、错误恢复、事务管理
"""
import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import asyncio
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class ExecutionState(Enum):
    """执行状态"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLING_BACK = "rolling_back"


@dataclass
class ExecutionResult:
    """执行结果"""
    task_id: str
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'task_id': self.task_id,
            'success': self.success,
            'output': self.output,
            'error': self.error,
            'retry_count': self.retry_count,
            'execution_time': self.execution_time,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }


@dataclass
class RollbackInfo:
    """回滚信息"""
    task_id: str
    state_snapshot: Dict
    rollback_action: Optional[str] = None
    rollback_params: Dict = field(default_factory=dict)


class IntelligentExecutor:
    """
    智能执行器
    
    功能：
    1. 执行任务和子任务
    2. 结果处理和验证
    3. 错误重试和恢复
    4. 事务管理和回滚
    5. 执行状态监控
    6. 并发执行控制
    """
    
    def __init__(
        self,
        tool_executor: Optional[Callable] = None,
        max_concurrent_tasks: int = 3,
        enable_rollback: bool = True,
        enable_result_validation: bool = True
    ):
        """
        初始化智能执行器
        
        Args:
            tool_executor: 工具执行函数
            max_concurrent_tasks: 最大并发任务数
            enable_rollback: 是否启用回滚
            enable_result_validation: 是否启用结果验证
        """
        self.tool_executor = tool_executor
        self.max_concurrent_tasks = max_concurrent_tasks
        self.enable_rollback = enable_rollback
        self.enable_result_validation = enable_result_validation
        
        self.state: ExecutionState = ExecutionState.IDLE
        self.execution_history: List[ExecutionResult] = []
        self.current_task_results: Dict[str, ExecutionResult] = {}
        self.rollback_stack: List[RollbackInfo] = []
        
        # 并发控制
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self.running_tasks: Dict[str, asyncio.Task] = {}
        
        # 回调
        self.on_task_start: Optional[Callable] = None
        self.on_task_complete: Optional[Callable] = None
        self.on_task_fail: Optional[Callable] = None
        self.on_rollback: Optional[Callable] = None
    
    @asynccontextmanager
    async def transaction(self):
        """
        事务上下文管理器
        
        在事务中执行的任务可以被回滚
        """
        # 保存当前状态快照
        snapshot = self._create_state_snapshot()
        
        rollback_info = RollbackInfo(
            task_id=f"transaction_{datetime.now().timestamp()}",
            state_snapshot=snapshot
        )
        
        self.rollback_stack.append(rollback_info)
        
        try:
            yield self
            # 如果没有异常，提交事务
            logger.info("事务提交成功")
            
        except Exception as e:
            # 发生异常，回滚
            logger.error(f"事务失败，开始回滚: {e}")
            await self.rollback(rollback_info)
            raise
    
    def _create_state_snapshot(self) -> Dict:
        """创建状态快照"""
        return {
            'task_results': {k: v.to_dict() for k, v in self.current_task_results.items()},
            'timestamp': datetime.now().isoformat()
        }
    
    async def rollback(self, rollback_info: Optional[RollbackInfo] = None) -> bool:
        """
        回滚到指定状态
        
        Args:
            rollback_info: 回滚信息，如果为None则回滚到上一个事务点
            
        Returns:
            是否回滚成功
        """
        if not self.enable_rollback:
            logger.warning("回滚功能未启用")
            return False
        
        target = rollback_info
        if not target:
            if not self.rollback_stack:
                logger.warning("没有可回滚的状态")
                return False
            target = self.rollback_stack.pop()
        
        self.state = ExecutionState.ROLLING_BACK
        logger.info(f"开始回滚到任务 {target.task_id}")
        
        try:
            # 恢复状态
            if 'task_results' in target.state_snapshot:
                self.current_task_results = {}
                for task_id, result_data in target.state_snapshot['task_results'].items():
                    self.current_task_results[task_id] = ExecutionResult(
                        task_id=result_data['task_id'],
                        success=result_data['success'],
                        output=result_data.get('output'),
                        error=result_data.get('error'),
                        retry_count=result_data.get('retry_count', 0),
                        execution_time=result_data.get('execution_time', 0.0),
                        timestamp=datetime.fromisoformat(result_data['timestamp']),
                        metadata=result_data.get('metadata', {})
                    )
            
            # 触发回滚回调
            if self.on_rollback:
                await self.on_rollback(target)
            
            logger.info("回滚完成")
            self.state = ExecutionState.IDLE
            return True
            
        except Exception as e:
            logger.error(f"回滚失败: {e}")
            self.state = ExecutionState.FAILED
            return False
    
    async def execute_task(
        self,
        task_id: str,
        tool_name: str,
        params: Dict,
        retry_on_failure: bool = True,
        max_retries: int = 3,
        validate_result: bool = None
    ) -> ExecutionResult:
        """
        执行单个任务
        
        Args:
            task_id: 任务ID
            tool_name: 工具名称
            params: 工具参数
            retry_on_failure: 失败时是否重试
            max_retries: 最大重试次数
            validate_result: 是否验证结果
            
        Returns:
            执行结果
        """
        if validate_result is None:
            validate_result = self.enable_result_validation
        
        result = ExecutionResult(task_id=task_id)
        retry_count = 0
        
        # 触发任务开始回调
        if self.on_task_start:
            await self.on_task_start(task_id, tool_name, params)
        
        while retry_count <= max_retries:
            try:
                start_time = datetime.now()
                
                # 执行工具
                if self.tool_executor:
                    output = await self.tool_executor(tool_name, params)
                else:
                    raise RuntimeError("未配置工具执行器")
                
                # 计算执行时间
                execution_time = (datetime.now() - start_time).total_seconds()
                
                # 验证结果
                if validate_result:
                    validation_result = await self._validate_result(tool_name, output, params)
                    if not validation_result['valid']:
                        raise ValueError(f"结果验证失败: {validation_result['reason']}")
                
                # 成功
                result.success = True
                result.output = str(output) if output else None
                result.execution_time = execution_time
                result.retry_count = retry_count
                
                # 保存结果
                self.current_task_results[task_id] = result
                self.execution_history.append(result)
                
                # 触发任务完成回调
                if self.on_task_complete:
                    await self.on_task_complete(task_id, result)
                
                logger.info(f"任务 {task_id} 执行成功（耗时 {execution_time:.2f}秒）")
                return result
                
            except Exception as e:
                retry_count += 1
                result.error = str(e)
                result.retry_count = retry_count
                
                logger.warning(f"任务 {task_id} 执行失败（第{retry_count}次尝试）: {e}")
                
                if not retry_on_failure or retry_count > max_retries:
                    # 达到最大重试次数或不可重试
                    result.success = False
                    self.current_task_results[task_id] = result
                    self.execution_history.append(result)
                    
                    # 触发任务失败回调
                    if self.on_task_fail:
                        await self.on_task_fail(task_id, result)
                    
                    logger.error(f"任务 {task_id} 执行失败: {e}")
                    return result
                
                # 等待后重试
                await asyncio.sleep(min(retry_count * 2, 10))  # 指数退避
    
        return result
    
    async def execute_tasks(
        self,
        tasks: List[Dict],
        parallel: bool = False,
        stop_on_error: bool = True
    ) -> Dict[str, ExecutionResult]:
        """
        批量执行任务
        
        Args:
            tasks: 任务列表 [{'task_id': 'xxx', 'tool_name': 'xxx', 'params': {...}}, ...]
            parallel: 是否并行执行
            stop_on_error: 遇到错误是否停止
            
        Returns:
            任务ID到执行结果的映射
        """
        results = {}
        
        self.state = ExecutionState.RUNNING
        
        if parallel:
            # 并行执行
            async def _execute_single(task_data):
                task_id = task_data['task_id']
                async with self.semaphore:
                    result = await self.execute_task(
                        task_id=task_id,
                        tool_name=task_data['tool_name'],
                        params=task_data.get('params', {}),
                        retry_on_failure=task_data.get('retry_on_failure', True),
                        max_retries=task_data.get('max_retries', 3)
                    )
                    return task_id, result
            
            tasks_to_run = [
                asyncio.create_task(_execute_single(task))
                for task in tasks
            ]
            
            completed, pending = await asyncio.wait(
                tasks_to_run,
                return_when=asyncio.FIRST_EXCEPTION if stop_on_error else asyncio.ALL_COMPLETED
            )
            
            for task in completed:
                try:
                    task_id, result = task.result()
                    results[task_id] = result
                except Exception as e:
                    logger.error(f"获取任务结果失败: {e}")
            
            # 如果有错误且设置了stop_on_error，取消剩余任务
            if stop_on_error and pending:
                for pending_task in pending:
                    pending_task.cancel()
                    try:
                        await pending_task
                    except asyncio.CancelledError:
                        pass
            
        else:
            # 顺序执行
            for task_data in tasks:
                task_id = task_data['task_id']
                
                result = await self.execute_task(
                    task_id=task_id,
                    tool_name=task_data['tool_name'],
                    params=task_data.get('params', {}),
                    retry_on_failure=task_data.get('retry_on_failure', True),
                    max_retries=task_data.get('max_retries', 3)
                )
                
                results[task_id] = result
                
                if not result.success and stop_on_error:
                    logger.error(f"任务 {task_id} 失败，停止后续任务执行")
                    break
        
        self.state = ExecutionState.IDLE
        return results
    
    async def _validate_result(
        self,
        tool_name: str,
        result: Any,
        params: Dict
    ) -> Dict:
        """
        验证执行结果
        
        Args:
            tool_name: 工具名称
            result: 执行结果
            params: 工具参数
            
        Returns:
            {'valid': bool, 'reason': str}
        """
        # 基本验证
        if result is None:
            return {'valid': True, 'reason': '无返回值，视为成功'}
        
        # 检查是否包含错误信息
        if isinstance(result, str):
            error_indicators = ['error', 'exception', 'failed', '失败', '错误']
            result_lower = result.lower()
            for indicator in error_indicators:
                if indicator in result_lower:
                    return {'valid': False, 'reason': f"结果包含错误指示词: {indicator}"}
        
        # 工具特定的验证规则
        validation_rules = {
            'terminal_command': self._validate_terminal_command,
            'read_file': self._validate_read_file,
            'list_files': self._validate_list_files,
            'search_content': self._validate_search_content,
        }
        
        validator = validation_rules.get(tool_name)
        if validator:
            return await validator(result, params)
        
        return {'valid': True, 'reason': '无特定验证规则'}
    
    async def _validate_terminal_command(self, result: Any, params: Dict) -> Dict:
        """验证终端命令结果"""
        if isinstance(result, str):
            # 检查是否包含常见的错误
            error_patterns = [
                r'command not found',
                r'no such file or directory',
                r'permission denied',
                r'找不到命令',
                r'拒绝访问'
            ]
            import re
            for pattern in error_patterns:
                if re.search(pattern, result, re.IGNORECASE):
                    return {'valid': False, 'reason': f"命令执行错误: {pattern}"}
        
        return {'valid': True, 'reason': '命令执行完成'}
    
    async def _validate_read_file(self, result: Any, params: Dict) -> Dict:
        """验证文件读取结果"""
        if result is None:
            return {'valid': False, 'reason': '文件读取返回空结果'}
        
        if isinstance(result, str) and 'File is empty' in result:
            # 空文件也算成功
            return {'valid': True, 'reason': '文件为空'}
        
        return {'valid': True, 'reason': '文件读取成功'}
    
    async def _validate_list_files(self, result: Any, params: Dict) -> Dict:
        """验证文件列表结果"""
        if result is None:
            return {'valid': False, 'reason': '文件列表返回空结果'}
        
        return {'valid': True, 'reason': '文件列表获取成功'}
    
    async def _validate_search_content(self, result: Any, params: Dict) -> Dict:
        """验证内容搜索结果"""
        # 搜索结果为空也可能正常（就是没找到）
        return {'valid': True, 'reason': '搜索完成'}
    
    def get_result(self, task_id: str) -> Optional[ExecutionResult]:
        """获取任务执行结果"""
        return self.current_task_results.get(task_id)
    
    def get_all_results(self) -> Dict[str, ExecutionResult]:
        """获取所有任务执行结果"""
        return self.current_task_results.copy()
    
    def get_execution_stats(self) -> Dict:
        """获取执行统计"""
        total = len(self.execution_history)
        if total == 0:
            return {
                'total': 0,
                'success': 0,
                'failed': 0,
                'success_rate': 0.0,
                'avg_execution_time': 0.0
            }
        
        success_count = sum(1 for r in self.execution_history if r.success)
        failed_count = total - success_count
        avg_time = sum(r.execution_time for r in self.execution_history) / total
        
        return {
            'total': total,
            'success': success_count,
            'failed': failed_count,
            'success_rate': success_count / total,
            'avg_execution_time': avg_time
        }
    
    def clear_history(self) -> None:
        """清空执行历史"""
        self.execution_history.clear()
        logger.info("执行历史已清空")
    
    def clear_current_results(self) -> None:
        """清空当前任务结果"""
        self.current_task_results.clear()
        logger.info("当前任务结果已清空")
    
    def clear_rollback_stack(self) -> None:
        """清空回滚栈"""
        self.rollback_stack.clear()
        logger.info("回滚栈已清空")
    
    def export_execution_report(self) -> str:
        """导出执行报告"""
        stats = self.get_execution_stats()
        
        lines = [
            "# 智能执行器报告",
            "",
            f"**执行统计**:",
            f"- 总任务数: {stats['total']}",
            f"- 成功: {stats['success']}",
            f"- 失败: {stats['failed']}",
            f"- 成功率: {stats['success_rate']:.2%}",
            f"- 平均执行时间: {stats['avg_execution_time']:.2f}秒",
            "",
            f"**回滚功能**: {'启用' if self.enable_rollback else '禁用'}",
            f"**结果验证**: {'启用' if self.enable_result_validation else '禁用'}",
            f"**最大并发**: {self.max_concurrent_tasks}",
            "",
            f"**当前状态**: {self.state.value}",
            f"**回滚栈深度**: {len(self.rollback_stack)}",
            "",
            "## 最近执行记录"
        ]
        
        for result in self.execution_history[-20:]:
            status = "✅" if result.success else "❌"
            lines.append(
                f"{status} {result.task_id} - "
                f"耗时 {result.execution_time:.2f}s - "
                f"重试 {result.retry_count} 次"
            )
            if result.error:
                lines.append(f"   错误: {result.error}")
        
        return "\n".join(lines)
    
    async def pause(self) -> None:
        """暂停执行"""
        if self.state == ExecutionState.RUNNING:
            self.state = ExecutionState.PAUSED
            logger.info("执行器已暂停")
    
    async def resume(self) -> None:
        """恢复执行"""
        if self.state == ExecutionState.PAUSED:
            self.state = ExecutionState.RUNNING
            logger.info("执行器已恢复")
    
    async def shutdown(self) -> None:
        """关闭执行器"""
        # 取消所有正在运行的任务
        for task_id, task in self.running_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"任务 {task_id} 已取消")
        
        self.running_tasks.clear()
        self.state = ExecutionState.IDLE
        logger.info("执行器已关闭")
