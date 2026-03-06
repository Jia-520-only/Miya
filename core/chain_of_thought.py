"""
思维链模块
支持多步骤推理、思考过程记录、回溯和反思
"""
import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import re

logger = logging.getLogger(__name__)


class ThoughtType(Enum):
    """思考类型"""
    ANALYSIS = "analysis"  # 分析
    DEDUCTION = "deduction"  # 推演
    HYPOTHESIS = "hypothesis"  # 假设
    REFLECTION = "reflection"  # 反思
    PLANNING = "planning"  # 规划
    DECISION = "decision"  # 决策
    QUESTION = "question"  # 提问
    ANSWER = "answer"  # 回答


@dataclass
class ThoughtStep:
    """思考步骤"""
    id: str
    thought_type: ThoughtType
    content: str
    reasoning: str  # 详细推理过程
    confidence: float = 0.0  # 置信度
    evidence: List[str] = field(default_factory=list)  # 支持证据
    alternatives: List[str] = field(default_factory=list)  # 替代方案
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'thought_type': self.thought_type.value,
            'content': self.content,
            'reasoning': self.reasoning,
            'confidence': self.confidence,
            'evidence': self.evidence,
            'alternatives': self.alternatives,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }


@dataclass
class ThoughtChain:
    """思维链"""
    id: str
    goal: str  # 目标
    context: Dict = field(default_factory=dict)
    steps: List[ThoughtStep] = field(default_factory=list)
    conclusion: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    def add_step(self, step: ThoughtStep) -> None:
        """添加思考步骤"""
        self.steps.append(step)
    
    def set_conclusion(self, conclusion: str) -> None:
        """设置结论"""
        self.conclusion = conclusion
        self.completed_at = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'goal': self.goal,
            'context': self.context,
            'steps': [step.to_dict() for step in self.steps],
            'conclusion': self.conclusion,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }


class ChainOfThought:
    """
    思维链引擎
    
    功能：
    1. 结构化思考过程
    2. 多步骤推理
    3. 思考回溯和修正
    4. 自我反思和改进
    5. 思考过程可视化
    6. 思考历史管理
    """
    
    def __init__(self, ai_client=None, storage_path: Optional[str] = None):
        """
        初始化思维链引擎
        
        Args:
            ai_client: AI客户端（用于生成思考步骤）
            storage_path: 存储路径
        """
        self.ai_client = ai_client
        self.storage_path = storage_path
        self.current_chain: Optional[ThoughtChain] = None
        self.chain_history: List[ThoughtChain] = []
        self._step_id_counter = 0
    
    def _generate_step_id(self) -> str:
        """生成步骤ID"""
        self._step_id_counter += 1
        return f"step_{self._step_id_counter}"
    
    def _generate_chain_id(self) -> str:
        """生成思维链ID"""
        return f"chain_{datetime.now().timestamp()}"
    
    async def start_chain(
        self,
        goal: str,
        context: Optional[Dict] = None
    ) -> ThoughtChain:
        """
        开始新的思维链
        
        Args:
            goal: 目标
            context: 上下文
            
        Returns:
            思维链对象
        """
        chain = ThoughtChain(
            id=self._generate_chain_id(),
            goal=goal,
            context=context or {}
        )
        
        self.current_chain = chain
        self._step_id_counter = 0
        
        logger.info(f"开始思维链: {goal}")
        
        return chain
    
    async def add_thought_step(
        self,
        thought_type: ThoughtType,
        content: str,
        reasoning: str,
        confidence: float = 0.0,
        evidence: Optional[List[str]] = None,
        alternatives: Optional[List[str]] = None,
        use_ai: bool = True
    ) -> ThoughtStep:
        """
        添加思考步骤
        
        Args:
            thought_type: 思考类型
            content: 思考内容
            reasoning: 推理过程
            confidence: 置信度
            evidence: 支持证据
            alternatives: 替代方案
            use_ai: 是否使用AI增强思考
            
        Returns:
            思考步骤对象
        """
        if not self.current_chain:
            raise RuntimeError("没有活动的思维链")
        
        # 如果启用AI增强，让AI完善思考步骤
        if use_ai and self.ai_client:
            enhanced = await self._enhance_thought(
                self.current_chain,
                thought_type,
                content,
                reasoning
            )
            content = enhanced.get('content', content)
            reasoning = enhanced.get('reasoning', reasoning)
            confidence = enhanced.get('confidence', confidence)
            evidence = enhanced.get('evidence', evidence or [])
            alternatives = enhanced.get('alternatives', alternatives or [])
        
        step = ThoughtStep(
            id=self._generate_step_id(),
            thought_type=thought_type,
            content=content,
            reasoning=reasoning,
            confidence=confidence,
            evidence=evidence or [],
            alternatives=alternatives or []
        )
        
        self.current_chain.add_step(step)
        
        logger.debug(f"添加思考步骤: {thought_type.value} - {content[:50]}")
        
        return step
    
    async def _enhance_thought(
        self,
        chain: ThoughtChain,
        thought_type: ThoughtType,
        content: str,
        reasoning: str
    ) -> Dict:
        """使用AI增强思考步骤"""
        try:
            prompt = f"""
当前目标: {chain.goal}

思考类型: {thought_type.value}
思考内容: {content}
推理过程: {reasoning}

请完善这个思考步骤，提供：
1. 更详细的推理过程
2. 置信度评估（0.0-1.0）
3. 支持证据（如果有）
4. 替代方案（如果有）

以JSON格式回复:
{{
  "content": "完善后的内容",
  "reasoning": "完善的推理过程",
  "confidence": 0.8,
  "evidence": ["证据1", "证据2"],
  "alternatives": ["替代方案1", "替代方案2"]
}}
"""
            
            response = await self.ai_client.chat_with_system_prompt(
                system_prompt="你是一个思考增强助手，帮助完善和丰富思考步骤。",
                user_message=prompt
            )
            
            # 提取JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
            
        except Exception as e:
            logger.warning(f"AI增强思考失败: {e}")
        
        return {
            'content': content,
            'reasoning': reasoning,
            'confidence': 0.5,
            'evidence': [],
            'alternatives': []
        }
    
    async def analyze(self, problem: str, context: Optional[Dict] = None) -> ThoughtChain:
        """
        分析问题（自动生成完整的思维链）
        
        Args:
            problem: 问题描述
            context: 上下文
            
        Returns:
            完整的思维链
        """
        if not self.ai_client:
            # 没有AI，创建简单的思维链
            await self.start_chain(problem, context)
            await self.add_thought_step(
                ThoughtType.ANALYSIS,
                "分析问题",
                "AI客户端未配置，无法进行深度分析",
                confidence=0.3,
                use_ai=False
            )
            self.current_chain.set_conclusion("需要AI支持以进行深入分析")
            return self.current_chain
        
        # 开始思维链
        await self.start_chain(problem, context)
        
        # 1. 问题分析
        await self.add_thought_step(
            ThoughtType.ANALYSIS,
            "分析问题的核心",
            "首先需要理解问题的本质和关键要素",
            confidence=0.7
        )
        
        # 2. 假设生成
        await self.add_thought_step(
            ThoughtType.HYPOTHESIS,
            "生成可能的解决方案",
            "基于问题分析，提出多个可能的解决方向",
            confidence=0.6
        )
        
        # 3. 推理验证
        await self.add_thought_step(
            ThoughtType.DEDUCTION,
            "验证假设的合理性",
            "通过逻辑推理验证每个假设的可行性",
            confidence=0.5
        )
        
        # 4. 反思和改进
        await self.add_thought_step(
            ThoughtType.REFLECTION,
            "反思推理过程",
            "检查是否有遗漏或错误的推理",
            confidence=0.4
        )
        
        # 5. 做出决策
        await self.add_thought_step(
            ThoughtType.DECISION,
            "确定最佳方案",
            "基于分析、推理和反思，选择最佳解决方案",
            confidence=0.8
        )
        
        # 设置结论
        self.current_chain.set_conclusion("思维链分析完成")
        
        # 保存到历史
        self.chain_history.append(self.current_chain)
        
        return self.current_chain
    
    async def reflect_on_chain(self, chain: Optional[ThoughtChain] = None) -> Dict:
        """
        反思维链过程
        
        Args:
            chain: 要反思的思维链，默认为当前链
            
        Returns:
            反思结果
        """
        chain = chain or self.current_chain
        if not chain:
            return {}
        
        reflection = {
            'total_steps': len(chain.steps),
            'avg_confidence': 0.0,
            'type_distribution': {},
            'suggested_improvements': []
        }
        
        # 计算平均置信度
        if chain.steps:
            reflection['avg_confidence'] = sum(
                s.confidence for s in chain.steps
            ) / len(chain.steps)
        
        # 统计思考类型分布
        for step in chain.steps:
            ttype = step.thought_type.value
            reflection['type_distribution'][ttype] = \
                reflection['type_distribution'].get(ttype, 0) + 1
        
        # 生成改进建议
        if reflection['avg_confidence'] < 0.5:
            reflection['suggested_improvements'].append(
                "平均置信度较低，建议增加更多的证据支持"
            )
        
        if reflection['total_steps'] < 3:
            reflection['suggested_improvements'].append(
                "思考步骤过少，建议进行更深入的分析"
            )
        
        if ThoughtType.REFLECTION.value not in reflection['type_distribution']:
            reflection['suggested_improvements'].append(
                "缺少反思步骤，建议添加自我反思环节"
            )
        
        return reflection
    
    def get_chain_summary(self, chain: Optional[ThoughtChain] = None) -> str:
        """获取思维链摘要"""
        chain = chain or self.current_chain
        if not chain:
            return "无思维链"
        
        lines = [
            f"# 思维链摘要",
            f"",
            f"**目标**: {chain.goal}",
            f"**步骤数**: {len(chain.steps)}",
            f"**状态**: {'完成' if chain.completed_at else '进行中'}",
            f"",
            f"## 思考步骤"
        ]
        
        for i, step in enumerate(chain.steps, 1):
            icon = self._get_type_icon(step.thought_type)
            lines.append(
                f"{i}. {icon} {step.thought_type.value} - "
                f"{step.content[:80]}... (置信度: {step.confidence:.2f})"
            )
            
            if step.evidence:
                lines.append(f"   证据: {', '.join(step.evidence)}")
            
            if step.alternatives:
                lines.append(f"   替代方案: {', '.join(step.alternatives)}")
        
        if chain.conclusion:
            lines.append("")
            lines.append(f"## 结论")
            lines.append(chain.conclusion)
        
        return "\n".join(lines)
    
    def _get_type_icon(self, thought_type: ThoughtType) -> str:
        """获取思考类型的图标"""
        icons = {
            ThoughtType.ANALYSIS: "🔍",
            ThoughtType.DEDUCTION: "🧠",
            ThoughtType.HYPOTHESIS: "💡",
            ThoughtType.REFLECTION: "🤔",
            ThoughtType.PLANNING: "📋",
            ThoughtType.DECISION: "✅",
            ThoughtType.QUESTION: "❓",
            ThoughtType.ANSWER: "💬"
        }
        return icons.get(thought_type, "•")
    
    def get_chain_tree(self, chain: Optional[ThoughtChain] = None) -> str:
        """获取思维链树状视图"""
        chain = chain or self.current_chain
        if not chain:
            return "无思维链"
        
        lines = [
            f"思维链: {chain.goal}",
            "│"
        ]
        
        for i, step in enumerate(chain.steps):
            is_last = (i == len(chain.steps) - 1)
            prefix = "└──" if is_last else "├──"
            
            lines.append(f"{prefix} {step.thought_type.value}: {step.content[:60]}...")
            
            if step.evidence:
                evidence_prefix = "    └──" if is_last else "    │"
                lines.append(f"{evidence_prefix} 证据: {', '.join(step.evidence[:2])}")
            
            if i < len(chain.steps) - 1:
                lines.append("│" if is_last else "│")
        
        if chain.conclusion:
            lines.append("└── 结论: " + chain.conclusion[:60] + "...")
        
        return "\n".join(lines)
    
    def backtrack_to(self, step_id: str) -> bool:
        """
        回溯到指定步骤
        
        Args:
            step_id: 步骤ID
            
        Returns:
            是否成功回溯
        """
        if not self.current_chain:
            return False
        
        try:
            # 找到步骤的索引
            step_index = None
            for i, step in enumerate(self.current_chain.steps):
                if step.id == step_id:
                    step_index = i
                    break
            
            if step_index is None:
                logger.warning(f"未找到步骤 {step_id}")
                return False
            
            # 删除该步骤之后的所有步骤
            self.current_chain.steps = self.current_chain.steps[:step_index + 1]
            self.current_chain.completed_at = None
            
            logger.info(f"回溯到步骤 {step_id}")
            return True
            
        except Exception as e:
            logger.error(f"回溯失败: {e}")
            return False
    
    def save_chain(self, path: str, chain: Optional[ThoughtChain] = None) -> bool:
        """保存思维链"""
        chain = chain or self.current_chain
        if not chain:
            return False
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(chain.to_dict(), f, ensure_ascii=False, indent=2)
            
            logger.info(f"思维链已保存到 {path}")
            return True
            
        except Exception as e:
            logger.error(f"保存思维链失败: {e}")
            return False
    
    def load_chain(self, path: str) -> Optional[ThoughtChain]:
        """加载思维链"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            chain = ThoughtChain(
                id=data['id'],
                goal=data['goal'],
                context=data['context']
            )
            
            if data.get('created_at'):
                chain.created_at = datetime.fromisoformat(data['created_at'])
            
            if data.get('completed_at'):
                chain.completed_at = datetime.fromisoformat(data['completed_at'])
            
            # 重建步骤
            for step_data in data['steps']:
                step = ThoughtStep(
                    id=step_data['id'],
                    thought_type=ThoughtType(step_data['thought_type']),
                    content=step_data['content'],
                    reasoning=step_data['reasoning'],
                    confidence=step_data.get('confidence', 0.0),
                    evidence=step_data.get('evidence', []),
                    alternatives=step_data.get('alternatives', []),
                    timestamp=datetime.fromisoformat(step_data['timestamp']),
                    metadata=step_data.get('metadata', {})
                )
                chain.add_step(step)
            
            chain.conclusion = data.get('conclusion')
            
            self.current_chain = chain
            logger.info(f"思维链已从 {path} 加载")
            return chain
            
        except Exception as e:
            logger.error(f"加载思维链失败: {e}")
            return None
    
    def export_markdown(self, chain: Optional[ThoughtChain] = None) -> str:
        """导出为Markdown格式"""
        chain = chain or self.current_chain
        if not chain:
            return ""
        
        lines = [
            f"# 思维链报告",
            f"",
            f"**目标**: {chain.goal}",
            f"**创建时间**: {chain.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**完成时间**: {chain.completed_at.strftime('%Y-%m-%d %H:%M:%S') if chain.completed_at else '进行中'}",
            f"",
            f"## 思考过程"
        ]
        
        for i, step in enumerate(chain.steps, 1):
            lines.append(f"\n### 步骤 {i}: {step.thought_type.value}")
            lines.append(f"**内容**: {step.content}")
            lines.append(f"**置信度**: {step.confidence:.2f}")
            lines.append(f"**推理过程**:")
            lines.append(f"> {step.reasoning}")
            
            if step.evidence:
                lines.append(f"\n**支持证据**:")
                for evidence in step.evidence:
                    lines.append(f"- {evidence}")
            
            if step.alternatives:
                lines.append(f"\n**替代方案**:")
                for alt in step.alternatives:
                    lines.append(f"- {alt}")
        
        if chain.conclusion:
            lines.append(f"\n## 结论")
            lines.append(chain.conclusion)
        
        return "\n".join(lines)
