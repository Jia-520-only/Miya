"""
自主探索模块
负责主动探索环境、收集信息、做出决策
"""
import logging
from typing import Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import asyncio


class CustomJSONEncoder(json.JSONEncoder):
    """自定义JSON编码器，处理datetime等特殊类型"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()
        return super().default(obj)


logger = logging.getLogger(__name__)


class ExplorationAction(Enum):
    """探索动作类型"""
    READ_FILE = "read_file"
    LIST_FILES = "list_files"
    SEARCH_CONTENT = "search_content"
    EXECUTE_COMMAND = "execute_command"
    ANALYZE_STRUCTURE = "analyze_structure"
    ASK_USER = "ask_user"
    THINK = "think"
    FINISH = "finish"


@dataclass
class ExplorationStep:
    """探索步骤"""
    action: ExplorationAction
    description: str
    params: Dict = field(default_factory=dict)
    result: Optional[str] = None
    reasoning: Optional[str] = None  # 为什么采取这个动作
    confidence: float = 0.0  # 置信度
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            'action': self.action.value,
            'description': self.description,
            'params': self.params,
            'result': self.result,
            'reasoning': self.reasoning,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class ExplorationPlan:
    """探索计划"""
    goal: str
    context: Dict = field(default_factory=dict)
    steps: List[ExplorationStep] = field(default_factory=list)
    max_steps: int = 50
    current_step: int = 0
    completed: bool = False
    findings: List[str] = field(default_factory=list)
    
    def add_step(self, step: ExplorationStep) -> None:
        self.steps.append(step)
        self.current_step += 1
    
    def add_finding(self, finding: str) -> None:
        """添加发现"""
        self.findings.append(finding)
    
    def to_dict(self) -> Dict:
        return {
            'goal': self.goal,
            'context': self.context,
            'steps': [step.to_dict() for step in self.steps],
            'max_steps': self.max_steps,
            'current_step': self.current_step,
            'completed': self.completed,
            'findings': self.findings
        }


class AutonomousExplorer:
    """
    自主探索器
    
    功能：
    1. 主动探索文件系统或代码库
    2. 根据目标制定探索策略
    3. 动态调整探索方向
    4. 记录探索过程和发现
    5. 支持暂停和恢复
    """
    
    def __init__(
        self,
        ai_client=None,
        tool_executor: Optional[Callable] = None,
        max_steps: int = 50,
        max_retries: int = 3
    ):
        """
        初始化自主探索器
        
        Args:
            ai_client: AI客户端（用于决策）
            tool_executor: 工具执行函数
            max_steps: 最大探索步数
            max_retries: 每个动作的最大重试次数
        """
        self.ai_client = ai_client
        self.tool_executor = tool_executor
        self.max_steps = max_steps
        self.max_retries = max_retries
        self.current_plan: Optional[ExplorationPlan] = None
        self.exploration_history: List[ExplorationPlan] = []
    
    async def explore(
        self,
        goal: str,
        context: Optional[Dict] = None,
        initial_knowledge: Optional[Dict] = None
    ) -> ExplorationPlan:
        """
        开始自主探索
        
        Args:
            goal: 探索目标
            context: 上下文信息
            initial_knowledge: 初始知识
            
        Returns:
            探索计划（包含所有步骤和发现）
        """
        plan = ExplorationPlan(
            goal=goal,
            context=context or {},
            max_steps=self.max_steps
        )
        
        self.current_plan = plan
        
        # 添加初始知识到上下文
        if initial_knowledge:
            plan.context.update(initial_knowledge)
            plan.add_finding(f"初始知识: {json.dumps(initial_knowledge, ensure_ascii=False, cls=CustomJSONEncoder)}")
        
        logger.info(f"开始自主探索: {goal}")
        
        # 探索循环
        while plan.current_step < plan.max_steps:
            # 决定下一步动作
            step = await self._decide_next_step(plan)
            
            if step.action == ExplorationAction.FINISH:
                logger.info("探索完成")
                plan.completed = True
                break
            
            # 执行动作
            try:
                result = await self._execute_step(step, plan)
                step.result = result
                
                # 分析结果，更新发现
                await self._analyze_result(step, plan)
                
            except Exception as e:
                logger.error(f"执行步骤失败: {e}")
                step.result = f"错误: {str(e)}"
            
            # 记录步骤
            plan.add_step(step)
            
            # 检查是否达到目标
            if await self._check_goal_achieved(plan):
                logger.info("目标已达成")
                plan.completed = True
                break
        
        # 添加到历史记录
        self.exploration_history.append(plan)
        
        # 生成总结
        plan.add_finding(f"探索完成，共执行 {plan.current_step} 步")
        
        return plan
    
    async def _decide_next_step(self, plan: ExplorationPlan) -> ExplorationStep:
        """
        决定下一步动作
        
        使用AI分析当前状态，决定下一步应该做什么
        """
        if not self.ai_client:
            # 如果没有AI，使用简单的启发式策略
            return self._heuristic_decide(plan)
        
        # 构建决策提示词
        prompt = self._build_decision_prompt(plan)
        
        try:
            # 调用AI获取下一步动作
            response = await self.ai_client.chat_with_system_prompt(
                system_prompt="""你是一个智能探索助手，需要根据当前状态决定下一步的探索动作。

可用动作：
- read_file: 读取文件内容
- list_files: 列出目录内容
- search_content: 搜索文件内容
- execute_command: 执行系统命令
- analyze_structure: 分析项目结构
- ask_user: 向用户提问（当无法自主决定时）
- think: 进行深度思考（分析当前信息）
- finish: 完成探索（当目标已达成或无法继续时）

输出格式（JSON）：
{
  "action": "动作名称",
  "description": "动作描述",
  "params": {"参数名": "参数值"},
  "reasoning": "为什么采取这个动作",
  "confidence": 置信度（0.0-1.0）
}""",
                user_message=prompt
            )
            
            return self._parse_decision(response)
            
        except Exception as e:
            logger.error(f"AI决策失败，使用启发式策略: {e}")
            return self._heuristic_decide(plan)
    
    def _build_decision_prompt(self, plan: ExplorationPlan) -> str:
        """构建决策提示词"""
        parts = [
            f"探索目标: {plan.goal}",
            f"已执行步数: {plan.current_step}/{plan.max_steps}",
            f"当前发现数: {len(plan.findings)}",
            "",
            "最近的发现:"
        ]
        
        # 显示最近的发现
        for finding in plan.findings[-5:]:
            parts.append(f"- {finding}")
        
        # 显示最近的步骤
        if plan.steps:
            parts.append("")
            parts.append("最近的步骤:")
            for step in plan.steps[-3:]:
                parts.append(f"- {step.description}: {step.result[:100] if step.result else '无结果'}")
        
        return "\n".join(parts)
    
    def _parse_decision(self, response: str) -> ExplorationStep:
        """解析AI决策"""
        try:
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if not json_match:
                raise ValueError("未找到JSON格式的决策")
            
            data = json.loads(json_match.group())
            
            action_str = data.get('action', 'think')
            action = ExplorationAction(action_str)
            
            return ExplorationStep(
                action=action,
                description=data.get('description', ''),
                params=data.get('params', {}),
                reasoning=data.get('reasoning', ''),
                confidence=data.get('confidence', 0.0)
            )
            
        except Exception as e:
            logger.error(f"解析决策失败: {e}")
            # 默认思考
            return ExplorationStep(
                action=ExplorationAction.THINK,
                description="分析当前状态",
                reasoning=f"解析失败，改为思考: {str(e)}"
            )
    
    def _heuristic_decide(self, plan: ExplorationPlan) -> ExplorationStep:
        """
        启发式决策（当AI不可用时）
        """
        # 简单策略：根据历史步骤决定下一步
        if not plan.steps:
            # 第一步：列出当前目录
            return ExplorationStep(
                action=ExplorationAction.LIST_FILES,
                description="列出当前目录",
                params={'path': plan.context.get('current_path', '.')},
                reasoning="开始探索，先列出当前目录",
                confidence=0.8
            )
        
        # 检查是否有未探索的目录
        last_step = plan.steps[-1]
        if last_step.action == ExplorationAction.LIST_FILES and last_step.result:
            # 尝试读取第一个文件
            import re
            file_match = re.search(r'(\w+\.py)', last_step.result)
            if file_match:
                return ExplorationStep(
                    action=ExplorationAction.READ_FILE,
                    description=f"读取文件 {file_match.group(1)}",
                    params={'path': file_match.group(1)},
                    reasoning="探索第一个Python文件",
                    confidence=0.7
                )
        
        # 默认：思考
        return ExplorationStep(
            action=ExplorationAction.THINK,
            description="分析当前信息",
            reasoning="需要更多信息才能继续",
            confidence=0.5
        )
    
    async def _execute_step(
        self,
        step: ExplorationStep,
        plan: ExplorationPlan
    ) -> str:
        """执行探索步骤"""
        if not self.tool_executor:
            return "未配置工具执行器"
        
        # 将ExplorationAction转换为工具调用
        tool_name = self._action_to_tool_name(step.action)
        if not tool_name:
            return f"不支持的动作: {step.action}"
        
        # 执行工具
        result = await self.tool_executor(tool_name, step.params)
        
        return str(result) if result else "执行完成，无返回结果"
    
    def _action_to_tool_name(self, action: ExplorationAction) -> Optional[str]:
        """将探索动作映射到工具名称"""
        mapping = {
            ExplorationAction.READ_FILE: 'read_file',
            ExplorationAction.LIST_FILES: 'list_files',
            ExplorationAction.SEARCH_CONTENT: 'search_content',
            ExplorationAction.EXECUTE_COMMAND: 'terminal_command',
        }
        return mapping.get(action)
    
    async def _analyze_result(
        self,
        step: ExplorationStep,
        plan: ExplorationPlan
    ) -> None:
        """分析步骤结果，提取发现"""
        if not step.result:
            return
        
        # 简单的发现提取
        findings = []
        
        # 根据动作类型提取不同的发现
        if step.action == ExplorationAction.LIST_FILES:
            # 提取文件列表
            import re
            files = re.findall(r'[\w\-\.]+\.(py|txt|md|json)', step.result)
            if files:
                findings.append(f"发现 {len(files)} 个文件")
        
        elif step.action == ExplorationAction.READ_FILE:
            # 提取关键信息
            import re
            classes = re.findall(r'class\s+(\w+)', step.result)
            functions = re.findall(r'def\s+(\w+)', step.result)
            if classes:
                findings.append(f"文件中定义了 {len(classes)} 个类: {', '.join(classes[:5])}")
            if functions:
                findings.append(f"文件中定义了 {len(functions)} 个函数")
        
        elif step.action == ExplorationAction.SEARCH_CONTENT:
            # 提取搜索结果
            lines = step.result.split('\n')
            if len(lines) > 5:
                findings.append(f"搜索到 {len(lines)} 行匹配内容")
        
        # 添加发现
        for finding in findings:
            plan.add_finding(f"{step.description}: {finding}")
    
    async def _check_goal_achieved(self, plan: ExplorationPlan) -> bool:
        """
        检查是否达到目标
        
        使用AI判断目标是否已达成
        """
        if not self.ai_client:
            # 简单判断：如果有足够的发现
            return len(plan.findings) >= 5
        
        prompt = f"""
探索目标: {plan.goal}

当前发现:
{chr(10).join(f'- {f}' for f in plan.findings[-10:])}

目标是否已达成？请回答"是"或"否"，并简要说明原因。
"""
        
        try:
            response = await self.ai_client.chat_with_system_prompt(
                system_prompt="你是探索目标的评估者。根据提供的发现，判断目标是否已达成。",
                user_message=prompt
            )
            
            return "是" in response.lower()
            
        except Exception as e:
            logger.error(f"判断目标达成失败: {e}")
            return False
    
    def get_exploration_summary(self, plan: Optional[ExplorationPlan] = None) -> Dict:
        """获取探索摘要"""
        plan = plan or self.current_plan
        if not plan:
            return {}
        
        # 统计各类型动作的数量
        action_counts = {}
        for step in plan.steps:
            action_counts[step.action.value] = action_counts.get(step.action.value, 0) + 1
        
        return {
            'goal': plan.goal,
            'total_steps': plan.current_step,
            'completed': plan.completed,
            'findings_count': len(plan.findings),
            'action_distribution': action_counts,
            'top_findings': plan.findings[:10]
        }
    
    def get_exploration_report(self, plan: Optional[ExplorationPlan] = None) -> str:
        """生成探索报告（文本格式）"""
        plan = plan or self.current_plan
        if not plan:
            return "无探索记录"
        
        parts = [
            f"# 探索报告",
            f"",
            f"**目标**: {plan.goal}",
            f"**状态**: {'完成' if plan.completed else '未完成'}",
            f"**步骤数**: {plan.current_step}/{plan.max_steps}",
            f"**发现数**: {len(plan.findings)}",
            f"",
            f"## 关键发现",
        ]
        
        for finding in plan.findings[:15]:
            parts.append(f"- {finding}")
        
        parts.append("")
        parts.append("## 执行步骤")
        
        for i, step in enumerate(plan.steps, 1):
            parts.append(f"{i}. {step.description} ({step.action.value})")
            if step.reasoning:
                parts.append(f"   理由: {step.reasoning}")
            if step.result and len(step.result) <= 200:
                parts.append(f"   结果: {step.result}")
            parts.append("")
        
        return "\n".join(parts)
    
    def pause(self) -> None:
        """暂停探索"""
        if self.current_plan:
            logger.info(f"探索已暂停（步骤 {self.current_plan.current_step}/{self.current_plan.max_steps}）")
    
    def resume(self) -> Optional[ExplorationPlan]:
        """恢复探索"""
        if not self.current_plan or self.current_plan.completed:
            return None
        
        logger.info(f"恢复探索（步骤 {self.current_plan.current_step}/{self.current_plan.max_steps}）")
        return self.current_plan
    
    def save_plan(self, path: str, plan: Optional[ExplorationPlan] = None) -> bool:
        """保存探索计划"""
        plan = plan or self.current_plan
        if not plan:
            return False
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(plan.to_dict(), f, ensure_ascii=False, indent=2)
            
            logger.info(f"探索计划已保存到 {path}")
            return True
            
        except Exception as e:
            logger.error(f"保存探索计划失败: {e}")
            return False
    
    def load_plan(self, path: str) -> Optional[ExplorationPlan]:
        """加载探索计划"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            plan = ExplorationPlan(
                goal=data['goal'],
                context=data['context'],
                max_steps=data['max_steps']
            )
            plan.current_step = data['current_step']
            plan.completed = data['completed']
            plan.findings = data['findings']
            
            # 重建步骤
            for step_data in data['steps']:
                step = ExplorationStep(
                    action=ExplorationAction(step_data['action']),
                    description=step_data['description'],
                    params=step_data['params'],
                    result=step_data['result'],
                    reasoning=step_data['reasoning'],
                    confidence=step_data['confidence'],
                    timestamp=datetime.fromisoformat(step_data['timestamp'])
                )
                plan.add_step(step)
            
            self.current_plan = plan
            logger.info(f"探索计划已从 {path} 加载")
            return plan
            
        except Exception as e:
            logger.error(f"加载探索计划失败: {e}")
            return None
