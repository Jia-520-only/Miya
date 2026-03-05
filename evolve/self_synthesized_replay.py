"""
自合成排练（Self-Synthesized Replay, SSR）
基于ACL 2024论文，利用LLM生成合成实例进行回放，抵消新旧知识冲突
"""
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
from core.constants import Encoding

logger = logging.getLogger(__name__)


class SynthesisStrategy(Enum):
    """合成策略"""
    MIX = "mix"           # 混合新旧知识
    CONTRAST = "contrast"   # 对比新旧知识
    BRIDGE = "bridge"       # 桥接新旧知识


@dataclass
class SyntheticExample:
    """合成样本"""
    example_id: str
    old_knowledge: str
    new_knowledge: str
    synthesized_text: str
    strategy: SynthesisStrategy
    timestamp: float = field(default_factory=time.time)
    usage_count: int = 0
    effectiveness: float = 0.5  # 0-1


class SelfSynthesizedReplay:
    """自合成排练"""

    def __init__(self, llm_generate_fn: Optional[callable] = None):
        self.llm_generate_fn = llm_generate_fn

        # 合成样本缓冲区
        self.replay_buffer: List[SyntheticExample] = []
        self.buffer_size = 1000

        # 知识对（旧知识 -> 新知识）
        self.knowledge_pairs: List[Tuple[str, str]] = []

        # 统计信息
        self.synthesis_stats = {
            'total_synthesized': 0,
            'effective_examples': 0,
            'by_strategy': {}
        }

    def add_knowledge_pair(
        self,
        old_knowledge: str,
        new_knowledge: str
    ) -> bool:
        """
        添加知识对

        Args:
            old_knowledge: 旧知识
            new_knowledge: 新知识

        Returns:
            是否成功
        """
        self.knowledge_pairs.append((old_knowledge, new_knowledge))

        # 自动触发合成
        if self.llm_generate_fn:
            self.synthesize_examples(old_knowledge, new_knowledge)

        logger.debug(f"[SSR] 添加知识对: old={len(old_knowledge)}, new={len(new_knowledge)}")
        return True

    def synthesize_examples(
        self,
        old_knowledge: str,
        new_knowledge: str,
        num_examples: int = 3
    ) -> List[SyntheticExample]:
        """
        合成训练样本

        Args:
            old_knowledge: 旧知识
            new_knowledge: 新知识
            num_examples: 合成数量

        Returns:
            合成样本列表
        """
        if not self.llm_generate_fn:
            logger.warning("[SSR] LLM生成函数未设置，返回空列表")
            return []

        examples = []

        strategies = [
            SynthesisStrategy.MIX,
            SynthesisStrategy.CONTRAST,
            SynthesisStrategy.BRIDGE
        ]

        for strategy in strategies:
            synthesized_text = self._generate_synthesized_text(
                old_knowledge,
                new_knowledge,
                strategy
            )

            if synthesized_text:
                example = SyntheticExample(
                    example_id=self._generate_example_id(),
                    old_knowledge=old_knowledge,
                    new_knowledge=new_knowledge,
                    synthesized_text=synthesized_text,
                    strategy=strategy
                )

                examples.append(example)

        # 添加到缓冲区
        for example in examples:
            self._add_to_buffer(example)

        self.synthesis_stats['total_synthesized'] += len(examples)

        logger.info(f"[SSR] 合成样本: {len(examples)}个, 策略={strategy.value}")
        return examples

    def sample_replay_batch(
        self,
        batch_size: int = 10,
        strategy: Optional[SynthesisStrategy] = None
    ) -> List[SyntheticExample]:
        """
        采样回放批次

        Args:
            batch_size: 批次大小
            strategy: 策略过滤（可选）

        Returns:
            样本批次
        """
        candidates = self.replay_buffer

        # 策略过滤
        if strategy:
            candidates = [
                ex for ex in candidates
                if ex.strategy == strategy
            ]

        # 优先采样（基于有效性和使用次数）
        scored_candidates = [
            (ex.effectiveness / (ex.usage_count + 1), ex)
            for ex in candidates
        ]

        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        # 采样top-k
        batch = [ex for _, ex in scored_candidates[:batch_size]]

        # 更新使用次数
        for example in batch:
            example.usage_count += 1

        logger.debug(f"[SSR] 采样回放批次: {len(batch)}个")
        return batch

    def update_effectiveness(
        self,
        example_id: str,
        effectiveness: float
    ) -> bool:
        """
        更新样本有效性

        Args:
            example_id: 样本ID
            effectiveness: 有效性（0-1）

        Returns:
            是否成功
        """
        for example in self.replay_buffer:
            if example.example_id == example_id:
                # 指数移动平均
                example.effectiveness = (
                    0.7 * example.effectiveness +
                    0.3 * effectiveness
                )

                if example.effectiveness > 0.7:
                    self.synthesis_stats['effective_examples'] += 1

                logger.debug(f"[SSR] 更新有效性: {example_id}={effectiveness:.3f}")
                return True

        return False

    def prune_buffer(self, threshold_days: int = 7):
        """
        剪枝缓冲区（移除低效样本）

        Args:
            threshold_days: 天数阈值
        """
        current_time = time.time()
        threshold = current_time - threshold_days * 86400

        initial_size = len(self.replay_buffer)

        # 移除低效且旧的样本
        self.replay_buffer = [
            ex for ex in self.replay_buffer
            if (ex.effectiveness >= 0.5 or ex.timestamp > threshold)
        ]

        removed = initial_size - len(self.replay_buffer)
        logger.info(f"[SSR] 剪枝缓冲区: 移除 {removed} 个低效样本")

    def _generate_synthesized_text(
        self,
        old_knowledge: str,
        new_knowledge: str,
        strategy: SynthesisStrategy
    ) -> Optional[str]:
        """
        生成合成文本

        Args:
            old_knowledge: 旧知识
            new_knowledge: 新知识
            strategy: 合成策略

        Returns:
            合成文本
        """
        # 策略提示词模板
        strategy_prompts = {
            SynthesisStrategy.MIX: f"""
            旧知识: {old_knowledge}
            新知识: {new_knowledge}

            请生成3个对话样本，每个样本都要同时体现旧知识和新知识的内容。
            样本应该自然、连贯，就像在同一个对话中。
            """,

            SynthesisStrategy.CONTRAST: f"""
            旧知识: {old_knowledge}
            新知识: {new_knowledge}

            请生成3个对话样本，展示旧知识和新知识之间的对比或冲突。
            样本应该清晰地展示两者的差异。
            """,

            SynthesisStrategy.BRIDGE: f"""
            旧知识: {old_knowledge}
            新知识: {new_knowledge}

            请生成3个对话样本，展示如何从旧知识过渡到新知识。
            样本应该逻辑连贯，合理地连接两者。
            """
        }

        prompt = strategy_prompts.get(strategy, strategy_prompts[SynthesisStrategy.MIX])

        try:
            # 调用LLM生成
            if self.llm_generate_fn:
                response = self.llm_generate_fn(prompt)
                return response

        except Exception as e:
            logger.error(f"[SSR] 生成合成文本失败: {e}")

        return None

    def _add_to_buffer(self, example: SyntheticExample):
        """添加样本到缓冲区"""
        self.replay_buffer.append(example)

        # 缓冲区管理
        if len(self.replay_buffer) > self.buffer_size:
            # 移除最旧且低效的样本
            self.replay_buffer.sort(
                key=lambda ex: (ex.effectiveness, ex.timestamp)
            )
            self.replay_buffer.pop(0)

    def _generate_example_id(self) -> str:
        """生成样本ID"""
        import uuid
        return f"ssr_{uuid.uuid4().hex[:12]}"

    def get_replay_schedule(
        self,
        total_steps: int = 100,
        replay_interval: int = 10
    ) -> List[int]:
        """
        获取回放计划

        Args:
            total_steps: 总步数
            replay_interval: 回放间隔

        Returns:
            需要回放的步数列表
        """
        schedule = []

        for step in range(total_steps):
            if step % replay_interval == 0:
                schedule.append(step)

        return schedule

    def save_buffer(self, filepath: Optional[str] = None):
        """
        保存缓冲区到磁盘

        Args:
            filepath: 文件路径（可选）
        """
        if filepath is None:
            filepath = "data/ssr_replay_buffer.json"

        data = {
            'examples': [
                {
                    'example_id': ex.example_id,
                    'old_knowledge': ex.old_knowledge,
                    'new_knowledge': ex.new_knowledge,
                    'synthesized_text': ex.synthesized_text,
                    'strategy': ex.strategy.value,
                    'timestamp': ex.timestamp,
                    'usage_count': ex.usage_count,
                    'effectiveness': ex.effectiveness
                }
                for ex in self.replay_buffer
            ],
            'statistics': self.synthesis_stats,
            'saved_at': time.time()
        }

        with open(filepath, 'w', encoding=Encoding.UTF8) as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"[SSR] 保存缓冲区: {len(self.replay_buffer)}个样本")

    def load_buffer(self, filepath: Optional[str] = None) -> bool:
        """
        从磁盘加载缓冲区

        Args:
            filepath: 文件路径（可选）

        Returns:
            是否成功
        """
        if filepath is None:
            filepath = "data/ssr_replay_buffer.json"

        try:
            with open(filepath, 'r', encoding=Encoding.UTF8) as f:
                data = json.load(f)

            self.replay_buffer = [
                SyntheticExample(
                    example_id=ex['example_id'],
                    old_knowledge=ex['old_knowledge'],
                    new_knowledge=ex['new_knowledge'],
                    synthesized_text=ex['synthesized_text'],
                    strategy=SynthesisStrategy(ex['strategy']),
                    timestamp=ex.get('timestamp', time.time()),
                    usage_count=ex.get('usage_count', 0),
                    effectiveness=ex.get('effectiveness', 0.5)
                )
                for ex in data.get('examples', [])
            ]

            self.synthesis_stats = data.get('statistics', {})

            logger.info(f"[SSR] 加载缓冲区: {len(self.replay_buffer)}个样本")
            return True

        except Exception as e:
            logger.error(f"[SSR] 加载缓冲区失败: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        strategy_counts = {}
        for example in self.replay_buffer:
            strat = example.strategy.value
            strategy_counts[strat] = strategy_counts.get(strat, 0) + 1

        return {
            'buffer_size': len(self.replay_buffer),
            'knowledge_pairs': len(self.knowledge_pairs),
            'total_synthesized': self.synthesis_stats.get('total_synthesized', 0),
            'effective_examples': self.synthesis_stats.get('effective_examples', 0),
            'effectiveness_rate': (
                self.synthesis_stats.get('effective_examples', 0) /
                max(self.synthesis_stats.get('total_synthesized', 1), 1)
            ),
            'by_strategy': strategy_counts
        }
