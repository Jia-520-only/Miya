"""
高级编排器
整合任务规划、自主探索、智能执行和思维链，实现Claude级别的能力
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio
import json

from .task_planner import TaskPlanner, Task, TaskStatus
from .autonomous_explorer import AutonomousExplorer, ExplorationPlan
from .intelligent_executor import IntelligentExecutor, ExecutionResult
from .chain_of_thought import ChainOfThought, ThoughtType

logger = logging.getLogger(__name__)


class AdvancedOrchestrator:
    """
    高级编排器
    
    整合所有新能力，实现：
    1. 复杂任务的智能规划
    2. 主动探索环境
    3. 可靠的任务执行
    4. 结构化的思考过程
    
    使用场景：
    - 复杂的多步骤任务
    - 需要探索代码库的任务
    - 需要深度推理的问题
    """
    
    def __init__(
        self,
        ai_client,
        tool_executor: callable,
        storage_dir: Optional[str] = None
    ):
        """
        初始化高级编排器
        
        Args:
            ai_client: AI客户端
            tool_executor: 工具执行函数
            storage_dir: 存储目录
        """
        self.ai_client = ai_client
        self.tool_executor = tool_executor
        self.storage_dir = storage_dir
        
        # 初始化各模块
        self.task_planner = TaskPlanner(ai_client=ai_client)
        self.explorer = AutonomousExplorer(
            ai_client=ai_client,
            tool_executor=tool_executor
        )
        self.executor = IntelligentExecutor(
            tool_executor=tool_executor,
            enable_rollback=True,
            enable_result_validation=True
        )
        self.chain_of_thought = ChainOfThought(ai_client=ai_client)
        
        logger.info("高级编排器初始化成功")
    
    async def process_complex_task(
        self,
        goal: str,
        context: Optional[Dict] = None,
        enable_exploration: bool = True,
        enable_cot: bool = True
    ) -> Dict:
        """
        处理复杂任务（核心入口）
        
        流程：
        1. 使用思维链分析目标
        2. 分解为子任务
        3. 如果需要，进行探索
        4. 执行任务
        5. 反思和总结
        
        Args:
            goal: 目标描述
            context: 上下文信息
            enable_exploration: 是否启用探索
            enable_cot: 是否启用思维链
            
        Returns:
            执行结果
        """
        start_time = datetime.now()
        logger.info(f"开始处理复杂任务: {goal}")
        
        result = {
            'goal': goal,
            'success': False,
            'steps': [],
            'findings': [],
            'conclusion': None,
            'execution_time': 0.0
        }
        
        try:
            # 步骤1: 思维链分析
            if enable_cot:
                logger.info("步骤1: 思维链分析")
                cot_result = await self._analyze_with_cot(goal, context)
                result['steps'].append({
                    'phase': '思维链分析',
                    'success': cot_result['success'],
                    'summary': cot_result['summary']
                })
                result['thought_chain'] = cot_result['chain']
                
                if not cot_result['success']:
                    logger.warning("思维链分析失败，继续执行")
            
            # 步骤2: 任务规划
            logger.info("步骤2: 任务规划")
            planning_result = await self._plan_tasks(goal, context)
            result['steps'].append({
                'phase': '任务规划',
                'success': planning_result['success'],
                'summary': planning_result['summary']
            })
            
            if not planning_result['success']:
                result['conclusion'] = "任务规划失败"
                return result
            
            # 步骤3: 主动探索（如果需要）
            if enable_exploration and planning_result['needs_exploration']:
                logger.info("步骤3: 主动探索")
                exploration_result = await self._explore_if_needed(goal, context)
                result['steps'].append({
                    'phase': '主动探索',
                    'success': exploration_result['success'],
                    'summary': exploration_result['summary']
                })
                result['findings'].extend(exploration_result['findings'])
                
                # 根据探索结果更新任务
                if exploration_result['findings']:
                    logger.info("根据探索结果更新任务规划")
                    await self._update_tasks_from_exploration(exploration_result)
            
            # 步骤4: 执行任务
            logger.info("步骤4: 执行任务")
            execution_result = await self._execute_tasks()
            result['steps'].append({
                'phase': '任务执行',
                'success': execution_result['success'],
                'summary': execution_result['summary'],
                'details': execution_result['details']
            })
            
            result['success'] = execution_result['success']
            result['task_results'] = execution_result['results']
            
            # 步骤5: 反思和总结
            if result['success'] and enable_cot:
                logger.info("步骤5: 反思总结")
                reflection = await self._reflect_on_execution(result)
                result['reflection'] = reflection
                result['conclusion'] = reflection.get('conclusion', '任务执行完成')
            else:
                result['conclusion'] = "任务执行完成" if result['success'] else "任务执行失败"
            
        except Exception as e:
            logger.error(f"处理复杂任务失败: {e}", exc_info=True)
            result['success'] = False
            result['conclusion'] = f"处理失败: {str(e)}"
        
        # 计算执行时间
        result['execution_time'] = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"复杂任务处理完成: {'成功' if result['success'] else '失败'} (耗时 {result['execution_time']:.2f}秒)")
        
        return result
    
    async def _analyze_with_cot(self, goal: str, context: Optional[Dict]) -> Dict:
        """使用思维链分析"""
        try:
            chain = await self.chain_of_thought.analyze(goal, context)
            
            summary = self.chain_of_thought.get_chain_summary(chain)
            
            return {
                'success': True,
                'chain': chain.to_dict(),
                'summary': f"思维链完成，共 {len(chain.steps)} 个思考步骤"
            }
            
        except Exception as e:
            logger.error(f"思维链分析失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'summary': f"思维链分析失败: {str(e)}"
            }
    
    async def _plan_tasks(self, goal: str, context: Optional[Dict]) -> Dict:
        """规划任务"""
        try:
            # 获取可用工具
            # TODO: 从工具注册表获取
            tools = []
            
            # 分解任务
            tasks = await self.task_planner.decompose_task(
                goal=goal,
                context=context,
                tools=tools
            )
            
            # 添加任务到规划器
            self.task_planner.add_tasks(tasks)
            
            # 评估是否需要探索
            needs_exploration = self._needs_exploration(tasks, goal)
            
            summary = f"规划完成，共 {len(tasks)} 个任务"
            if needs_exploration:
                summary += "（建议先进行探索）"
            
            return {
                'success': True,
                'tasks': [task.to_dict() for task in tasks],
                'needs_exploration': needs_exploration,
                'summary': summary
            }
            
        except Exception as e:
            logger.error(f"任务规划失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'summary': f"任务规划失败: {str(e)}"
            }
    
    def _needs_exploration(self, tasks: List[Task], goal: str) -> bool:
        """判断是否需要探索"""
        # 如果任务中包含文件操作或搜索，可能需要探索
        exploration_keywords = ['文件', '目录', '搜索', '探索', '分析', '查看']
        
        for task in tasks:
            description = task.description.lower()
            for keyword in exploration_keywords:
                if keyword in description:
                    return True
        
        # 检查目标本身
        goal_lower = goal.lower()
        for keyword in exploration_keywords:
            if keyword in goal_lower:
                return True
        
        return False
    
    async def _explore_if_needed(self, goal: str, context: Optional[Dict]) -> Dict:
        """进行探索"""
        try:
            plan = await self.explorer.explore(
                goal=goal,
                context=context,
                initial_knowledge={'tasks': [t.to_dict() for t in self.task_planner.get_all_tasks()]}
            )
            
            findings = plan.findings
            
            return {
                'success': True,
                'plan': plan.to_dict(),
                'findings': findings,
                'summary': f"探索完成，共 {len(findings)} 条发现"
            }
            
        except Exception as e:
            logger.error(f"探索失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'findings': [],
                'summary': f"探索失败: {str(e)}"
            }
    
    async def _update_tasks_from_exploration(self, exploration_result: Dict) -> None:
        """根据探索结果更新任务"""
        # 简单实现：将发现添加到上下文
        findings = exploration_result['findings']
        if findings:
            # 更新任务描述，包含发现的信息
            for task in self.task_planner.get_all_tasks():
                if task.status == TaskStatus.PENDING:
                    task.metadata['exploration_findings'] = findings
    
    async def _execute_tasks(self) -> Dict:
        """执行所有任务"""
        try:
            # 获取所有就绪的任务
            ready_tasks = self.task_planner.get_ready_tasks()
            
            if not ready_tasks:
                return {
                    'success': True,
                    'results': {},
                    'summary': "没有需要执行的任务"
                }
            
            # 准备任务列表
            task_list = []
            for task in ready_tasks:
                if task.tool_name:
                    task_list.append({
                        'task_id': task.id,
                        'tool_name': task.tool_name,
                        'params': task.tool_params,
                        'retry_on_failure': True,
                        'max_retries': task.max_retries
                    })
                    
                    # 标记任务为开始
                    self.task_planner.mark_task_started(task.id)
            
            # 执行任务
            results = {}
            if task_list:
                # 使用智能执行器
                execution_results = await self.executor.execute_tasks(
                    tasks=task_list,
                    parallel=False,  # 顺序执行，因为有依赖
                    stop_on_error=False
                )
                
                # 更新任务状态
                for task_id, exec_result in execution_results.items():
                    if exec_result.success:
                        self.task_planner.mark_task_completed(
                            task_id,
                            exec_result.output or "完成"
                        )
                    else:
                        self.task_planner.mark_task_failed(
                            task_id,
                            exec_result.error or "执行失败"
                        )
                    
                    results[task_id] = exec_result.to_dict()
            
            success = self.task_planner.is_complete()
            
            summary = f"任务执行完成: {len(results)} 个任务"
            if not success:
                summary += f"（待完成: {len([t for t in self.task_planner.get_all_tasks() if t.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED]])}）"
            
            return {
                'success': success,
                'results': results,
                'summary': summary,
                'details': self.task_planner.get_summary()
            }
            
        except Exception as e:
            logger.error(f"任务执行失败: {e}")
            return {
                'success': False,
                'results': {},
                'summary': f"任务执行失败: {str(e)}",
                'details': None
            }
    
    async def _reflect_on_execution(self, result: Dict) -> Dict:
        """反思执行过程"""
        reflection = {
            'successful_tasks': [],
            'failed_tasks': [],
            'learnings': [],
            'improvements': []
        }
        
        # 分析成功和失败的任务
        task_results = result.get('task_results', {})
        for task_id, task_result in task_results.items():
            if task_result.get('success'):
                reflection['successful_tasks'].append(task_id)
            else:
                reflection['failed_tasks'].append(task_id)
        
        # 生成学习点
        if reflection['successful_tasks']:
            reflection['learnings'].append(
                f"成功完成了 {len(reflection['successful_tasks'])} 个任务"
            )
        
        if reflection['failed_tasks']:
            reflection['improvements'].append(
                f"需要改进 {len(reflection['failed_tasks'])} 个失败的任务"
            )
        
        # 查找反思结果
        if 'thought_chain' in result:
            reflection['cot_reflection'] = await self.chain_of_thought.reflect_on_chain()
            reflection['improvements'].extend(
                reflection['cot_reflection'].get('suggested_improvements', [])
            )
        
        # 生成结论
        if result['success']:
            conclusion = "任务成功完成"
            if reflection['failed_tasks']:
                conclusion += f"（部分任务失败，但不影响整体结果）"
        else:
            conclusion = "任务未完全完成"
        
        reflection['conclusion'] = conclusion
        
        return reflection
    
    def generate_report(self, result: Dict) -> str:
        """生成执行报告"""
        lines = [
            "# 复杂任务执行报告",
            "",
            f"**目标**: {result.get('goal', '未指定')}",
            f"**状态**: {'成功' if result.get('success') else '失败'}",
            f"**执行时间**: {result.get('execution_time', 0):.2f}秒",
            "",
            "## 执行步骤"
        ]
        
        for i, step in enumerate(result.get('steps', []), 1):
            lines.append(f"\n### {i}. {step.get('phase', '未知阶段')}")
            lines.append(f"- 状态: {'成功' if step.get('success') else '失败'}")
            lines.append(f"- 摘要: {step.get('summary', '无')}")
        
        # 添加发现
        if result.get('findings'):
            lines.append("\n## 探索发现")
            for finding in result.get('findings', [])[:10]:
                lines.append(f"- {finding}")
        
        # 添加结论
        lines.append("\n## 结论")
        lines.append(result.get('conclusion', '无结论'))
        
        # 添加反思
        if result.get('reflection'):
            reflection = result['reflection']
            lines.append("\n## 反思")
            
            if reflection.get('successful_tasks'):
                lines.append(f"**成功任务**: {', '.join(reflection['successful_tasks'])}")
            
            if reflection.get('failed_tasks'):
                lines.append(f"**失败任务**: {', '.join(reflection['failed_tasks'])}")
            
            if reflection.get('learnings'):
                lines.append("\n**学习点**:")
                for learning in reflection['learnings']:
                    lines.append(f"- {learning}")
            
            if reflection.get('improvements'):
                lines.append("\n**改进建议**:")
                for improvement in reflection['improvements']:
                    lines.append(f"- {improvement}")
        
        return "\n".join(lines)
    
    async def cleanup(self) -> None:
        """清理资源"""
        await self.executor.shutdown()
        logger.info("高级编排器已清理")
