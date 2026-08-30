"""
在线强化学习对齐（Online RLHF）
基于OpenRLHF和Online-RLHF，实现实时反馈循环
"""
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import random
from core.constants import Encoding

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    """反馈类型"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


@dataclass
class FeedbackSample:
    """反馈样本"""
    sample_id: str
    prompt: str
    response: str
    feedback: FeedbackType
    reward: float
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RLHFConfig:
    """RLHF配置"""
    learning_rate: float = 1e-5
    kl_penalty: float = 0.1
    kl_target: float = 0.05
    batch_size: int = 32
    replay_buffer_size: int = 10000
    policy_update_interval: int = 100


class OnlineRLHFLearner:
    """在线RLHF学习器"""

    def __init__(self, config: Optional[RLHFConfig] = None):
        self.config = config or RLHFConfig()

        # 反馈缓冲区
        self.feedback_buffer: List[FeedbackSample] = []

        # 奖励模型（简化版）
        self.reward_model_params: Dict[str, float] = {}

        # 策略模型参数（简化版）
        self.policy_params: Dict[str, float] = {}

        # KL散度历史
        self.kl_history: List[float] = []

        # 统计信息
        self.stats = {
            'total_feedback': 0,
            'positive_ratio': 0.0,
            'avg_reward': 0.0,
            'policy_updates': 0,
            'kl_violations': 0
        }

    def collect_feedback(
        self,
        prompt: str,
        response: str,
        feedback: FeedbackType,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        收集用户反馈

        Args:
            prompt: 提示词
            response: 响应
            feedback: 反馈类型
            metadata: 元数据

        Returns:
            样本ID
        """
        # 计算奖励
        reward = self._compute_reward(feedback)

        # 创建反馈样本
        sample = FeedbackSample(
            sample_id=self._generate_sample_id(),
            prompt=prompt,
            response=response,
            feedback=feedback,
            reward=reward,
            metadata=metadata or {}
        )

        # 添加到缓冲区
        self.feedback_buffer.append(sample)

        # 缓冲区管理
        if len(self.feedback_buffer) > self.config.replay_buffer_size:
            self.feedback_buffer.pop(0)

        # 更新统计
        self.stats['total_feedback'] += 1
        self._update_statistics()

        logger.info(f"[OnlineRLHF] 收集反馈: {sample.sample_id}, 奖励: {reward:.3f}")
        return sample.sample_id

    def update_policy(self) -> Dict[str, float]:
        """
        更新策略（带KL散度约束）

        Args:
            Returns:
            更新指标
        """
        if len(self.feedback_buffer) < self.config.batch_size:
            logger.warning("[OnlineRLHF] 反馈不足，跳过策略更新")
            return {}

        # 采样批次
        batch = self._sample_batch(self.config.batch_size)

        # 计算损失
        policy_loss = self._compute_policy_loss(batch)
        kl_penalty = self._compute_kl_penalty(batch)

        # 总损失（策略损失 + KL惩罚）
        total_loss = policy_loss + kl_penalty

        # 梯度下降（简化版）
        self._gradient_descent(total_loss)

        # 更新统计
        self.stats['policy_updates'] += 1

        # 记录KL散度
        kl_divergence = self._estimate_kl_divergence(batch)
        self.kl_history.append(kl_divergence)

        if kl_divergence > self.config.kl_target * 2:
            self.stats['kl_violations'] += 1

        logger.info(
            f"[OnlineRLHF] 策略更新: "
            f"loss={total_loss:.4f}, kl={kl_divergence:.4f}"
        )

        return {
            'policy_loss': policy_loss,
            'kl_penalty': kl_penalty,
            'total_loss': total_loss,
            'kl_divergence': kl_divergence
        }

    def should_update_policy(self, step: int) -> bool:
        """
        判断是否应该更新策略

        Args:
            step: 当前步数

        Returns:
            是否应该更新
        """
        return step % self.config.policy_update_interval == 0

    def monitor_kl_divergence(
        self,
        window_size: int = 100
    ) -> Dict[str, float]:
        """
        监控KL散度

        Args:
            window_size: 窗口大小

        Returns:
            KL散度统计
        """
        recent_kls = self.kl_history[-window_size:]

        if not recent_kls:
            return {'mean': 0.0, 'std': 0.0, 'max': 0.0, 'min': 0.0}

        import numpy as np

        return {
            'mean': float(np.mean(recent_kls)),
            'std': float(np.std(recent_kls)),
            'max': float(np.max(recent_kls)),
            'min': float(np.min(recent_kls)),
            'current': recent_kls[-1] if recent_kls else 0.0
        }

    def compute_reward(
        self,
        prompt: str,
        response: str
    ) -> float:
        """
        使用奖励模型计算奖励（外部调用）

        Args:
            prompt: 提示词
            response: 响应

        Returns:
            奖励值
        """
        # 简化实现：基于规则
        # 实际应调用训练好的奖励模型
        reward = 0.0

        # 长度惩罚
        if len(response) > 1000:
            reward -= 0.1
        elif len(response) < 50:
            reward -= 0.2

        # 重复惩罚
        if len(response.split()) < 10:
            reward -= 0.1

        return reward

    def _compute_reward(self, feedback: FeedbackType) -> float:
        """计算奖励（基于反馈类型）"""
        reward_map = {
            FeedbackType.POSITIVE: 1.0,
            FeedbackType.NEUTRAL: 0.0,
            FeedbackType.NEGATIVE: -1.0
        }
        return reward_map.get(feedback, 0.0)

    def _sample_batch(self, batch_size: int) -> List[FeedbackSample]:
        """采样批次"""
        if len(self.feedback_buffer) <= batch_size:
            return self.feedback_buffer.copy()

        # 优先采样最近样本
        recent_samples = self.feedback_buffer[-batch_size // 2:]

        # 随机采样剩余部分
        remaining_pool = self.feedback_buffer[:-batch_size // 2]
        random_samples = random.sample(
            remaining_pool,
            min(batch_size // 2, len(remaining_pool))
        )

        return recent_samples + random_samples

    def _compute_policy_loss(self, batch: List[FeedbackSample]) -> float:
        """计算策略损失"""
        # 简化实现：平均负奖励
        avg_reward = sum(s.reward for s in batch) / len(batch)
        return -avg_reward

    def _compute_kl_penalty(self, batch: List[FeedbackSample]) -> float:
        """计算KL散度惩罚"""
        # 估计当前KL
        kl_divergence = self._estimate_kl_divergence(batch)

        # KL惩罚：λ * max(0, KL - KL_target)
        penalty = max(0.0, kl_divergence - self.config.kl_target)
        penalty = self.config.kl_penalty * penalty

        return penalty

    def _estimate_kl_divergence(self, batch: List[FeedbackSample]) -> float:
        """估计KL散度（简化版）"""
        # 简化实现：基于奖励方差
        rewards = [s.reward for s in batch]

        if not rewards:
            return 0.0

        import numpy as np
        return float(np.std(rewards))

    def _gradient_descent(self, loss: float):
        """梯度下降（简化版）"""
        # 简化实现：随机更新参数
        import random

        for param_name in self.policy_params:
            # 模拟梯度
            gradient = (random.random() - 0.5) * 2.0 * loss

            # 更新参数
            self.policy_params[param_name] -= self.config.learning_rate * gradient

    def _update_statistics(self):
        """更新统计信息"""
        if not self.feedback_buffer:
            return

        rewards = [s.reward for s in self.feedback_buffer]
        positives = sum(1 for s in self.feedback_buffer if s.feedback == FeedbackType.POSITIVE)

        self.stats['avg_reward'] = sum(rewards) / len(rewards)
        self.stats['positive_ratio'] = positives / len(self.feedback_buffer)

    def _generate_sample_id(self) -> str:
        """生成样本ID"""
        import uuid
        return f"rlhf_{uuid.uuid4().hex[:12]}"

    def save_state(self, filepath: Optional[str] = None):
        """保存状态到磁盘"""
        if filepath is None:
            filepath = "data/online_rlhf_state.json"

        data = {
            'config': {
                'learning_rate': self.config.learning_rate,
                'kl_penalty': self.config.kl_penalty,
                'batch_size': self.config.batch_size
            },
            'reward_model_params': self.reward_model_params,
            'policy_params': self.policy_params,
            'kl_history': self.kl_history,
            'statistics': self.stats,
            'saved_at': time.time()
        }

        with open(filepath, 'w', encoding=Encoding.UTF8) as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"[OnlineRLHF] 保存状态: {len(self.feedback_buffer)}个样本")

    def load_state(self, filepath: Optional[str] = None) -> bool:
        """从磁盘加载状态"""
        if filepath is None:
            filepath = "data/online_rlhf_state.json"

        try:
            with open(filepath, 'r', encoding=Encoding.UTF8) as f:
                data = json.load(f)

            config_data = data.get('config', {})
            self.config = RLHFConfig(
                learning_rate=config_data.get('learning_rate', 1e-5),
                kl_penalty=config_data.get('kl_penalty', 0.1),
                batch_size=config_data.get('batch_size', 32)
            )

            self.reward_model_params = data.get('reward_model_params', {})
            self.policy_params = data.get('policy_params', {})
            self.kl_history = data.get('kl_history', [])
            self.stats = data.get('statistics', {})

            logger.info("[OnlineRLHF] 加载状态成功")
            return True

        except Exception as e:
            logger.error(f"[OnlineRLHF] 加载状态失败: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_feedback': self.stats['total_feedback'],
            'positive_ratio': self.stats['positive_ratio'],
            'avg_reward': self.stats['avg_reward'],
            'policy_updates': self.stats['policy_updates'],
            'kl_violations': self.stats['kl_violations'],
            'buffer_size': len(self.feedback_buffer),
            'current_kl': self.monitor_kl_divergence(10)['current']
        }
