"""
弹性权重固着（Elastic Weight Consolidation）
基于EWC算法防止持续学习中的灾难性遗忘
"""
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from core.constants import Encoding

logger = logging.getLogger(__name__)


@dataclass
class EWCParams:
    """EWC参数"""
    lambda_ewc: float = 0.1  # EWC正则化强度
    online_mode: bool = True   # 在线模式（动态更新Fisher）
    gamma: float = 0.95       # Fisher衰减因子（在线模式）


@dataclass
class TaskFishers:
    """任务Fisher信息矩阵"""
    task_id: str
    fisher_matrix: Dict[str, float] = field(default_factory=dict)
    optimal_params: Dict[str, float] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    weight: float = 1.0  # 任务权重


class ElasticWeightConsolidation:
    """弹性权重固着"""

    def __init__(self, lambda_ewc: float = 0.1, online_mode: bool = True):
        self.params = EWCParams(lambda_ewc=lambda_ewc, online_mode=online_mode)

        # Fisher信息矩阵（按任务存储）
        self.task_fishers: Dict[str, TaskFishers] = {}

        # 当前模型参数（简化版）
        self.current_params: Dict[str, float] = {}

        # 存储路径
        self.storage_path = Path("data/ewc_state")
        self.storage_path.mkdir(exist_ok=True)

    def compute_fisher(
        self,
        task_id: str,
        model_params: Dict[str, float],
        loss_gradients: Dict[str, float]
    ) -> bool:
        """
        计算Fisher信息矩阵

        Fisher = E[(∂L/∂θ)²]

        Args:
            task_id: 任务ID
            model_params: 模型参数
            loss_gradients: 损失梯度

        Returns:
            是否成功
        """
        try:
            fisher_matrix = {}

            # 计算每个参数的Fisher信息
            for param_name in model_params:
                gradient = loss_gradients.get(param_name, 0.0)
                fisher_matrix[param_name] = gradient ** 2

            # 创建任务Fisher
            if task_id not in self.task_fishers:
                self.task_fishers[task_id] = TaskFishers(task_id=task_id)

            task_fisher = self.task_fishers[task_id]

            if self.params.online_mode and task_fisher.fisher_matrix:
                # 在线模式：衰减旧Fisher，加入新Fisher
                for param_name in fisher_matrix:
                    old_fisher = task_fisher.fisher_matrix.get(param_name, 0.0)
                    new_fisher = fisher_matrix[param_name]

                    # 指数移动平均
                    task_fisher.fisher_matrix[param_name] = (
                        self.params.gamma * old_fisher +
                        (1.0 - self.params.gamma) * new_fisher
                    )
            else:
                # 离线模式：直接使用新Fisher
                task_fisher.fisher_matrix = fisher_matrix

            # 保存最优参数
            task_fisher.optimal_params = model_params.copy()
            task_fisher.updated_at = time.time()

            logger.info(f"[EWC] 计算Fisher: {task_id}, 参数数: {len(fisher_matrix)}")
            return True

        except Exception as e:
            logger.error(f"[EWC] 计算Fisher失败: {e}")
            return False

    def compute_ewc_loss(
        self,
        current_params: Dict[str, float],
        task_weights: Optional[Dict[str, float]] = None
    ) -> float:
        """
        计算EWC正则化损失

        L_EWC = Σ λ_i/2 * F_i * (θ - θ*_i)²

        Args:
            current_params: 当前参数
            task_weights: 任务权重（可选）

        Returns:
            EWC损失
        """
        ewc_loss = 0.0

        for task_id, task_fisher in self.task_fishers.items():
            weight = task_weights.get(task_id, task_fisher.weight)
            fisher = task_fisher.fisher_matrix
            optimal = task_fisher.optimal_params

            for param_name in fisher:
                if param_name in current_params and param_name in optimal:
                    # 计算参数偏移
                    param_diff = current_params[param_name] - optimal[param_name]
                    fisher_val = fisher[param_name]

                    # EWC损失项
                    ewc_loss += weight * fisher_val * (param_diff ** 2)

        ewc_loss = ewc_loss * self.params.lambda_ewc * 0.5
        return ewc_loss

    def update_current_params(self, new_params: Dict[str, float]):
        """
        更新当前参数

        Args:
            new_params: 新参数
        """
        self.current_params = new_params.copy()

    def add_task_weight(self, task_id: str, weight: float):
        """
        添加或更新任务权重

        Args:
            task_id: 任务ID
            weight: 权重
        """
        if task_id in self.task_fishers:
            self.task_fishers[task_id].weight = weight
            logger.info(f"[EWC] 更新任务权重: {task_id}={weight}")

    def merge_tasks(self, task_ids: List[str], merged_id: str):
        """
        合并多个任务（用于任务合并）

        Args:
            task_ids: 任务ID列表
            merged_id: 合并后的任务ID
        """
        if merged_id in self.task_fishers:
            return

        merged_fisher = TaskFishers(task_id=merged_id)

        for task_id in task_ids:
            if task_id not in self.task_fishers:
                continue

            task_fisher = self.task_fishers[task_id]

            # 合并Fisher矩阵
            for param_name, fisher_val in task_fisher.fisher_matrix.items():
                if param_name in merged_fisher.fisher_matrix:
                    merged_fisher.fisher_matrix[param_name] += fisher_val
                else:
                    merged_fisher.fisher_matrix[param_name] = fisher_val

            # 合并最优参数（简单平均）
            for param_name, opt_val in task_fisher.optimal_params.items():
                if param_name in merged_fisher.optimal_params:
                    merged_fisher.optimal_params[param_name] += opt_val
                    count = len([tid for tid in task_ids if param_name in self.task_fishers[tid].optimal_params])
                    merged_fisher.optimal_params[param_name] /= count
                else:
                    merged_fisher.optimal_params[param_name] = opt_val

        self.task_fishers[merged_id] = merged_fisher
        logger.info(f"[EWC] 合并任务: {task_ids} -> {merged_id}")

    def get_ewc_regularization_term(
        self,
        param_name: str,
        current_value: float
    ) -> float:
        """
        获取单个参数的EWC正则化项

        Args:
            param_name: 参数名称
            current_value: 当前值

        Returns:
            正则化梯度
        """
        gradient = 0.0

        for task_fisher in self.task_fishers.values():
            if param_name in task_fisher.fisher_matrix and param_name in task_fisher.optimal_params:
                fisher_val = task_fisher.fisher_matrix[param_name]
                optimal_val = task_fisher.optimal_params[param_name]

                # ∇L_EWC = λ * F * (θ - θ*)
                gradient += task_fisher.weight * fisher_val * (current_value - optimal_val)

        return gradient * self.params.lambda_ewc

    def estimate_forgetting(
        self,
        task_id: str,
        current_params: Dict[str, float]
    ) -> float:
        """
        估计遗忘程度

        Args:
            task_id: 任务ID
            current_params: 当前参数

        Returns:
            遗忘分数（0-1，越高遗忘越多）
        """
        if task_id not in self.task_fishers:
            return 0.0

        task_fisher = self.task_fishers[task_id]
        fisher = task_fisher.fisher_matrix
        optimal = task_fisher.optimal_params

        total_fisher = sum(fisher.values())
        if total_fisher == 0:
            return 0.0

        # 计算加权偏移
        weighted_shift = 0.0

        for param_name in fisher:
            if param_name in current_params and param_name in optimal:
                param_diff = current_params[param_name] - optimal[param_name]
                fisher_val = fisher[param_name]
                weighted_shift += fisher_val * (param_diff ** 2)

        forgetting = weighted_shift / total_fisher
        return min(forgetting, 1.0)

    def prune_tasks(self, max_tasks: int = 10):
        """
        剪枝任务（保留最重要的任务）

        Args:
            max_tasks: 最大任务数
        """
        if len(self.task_fishers) <= max_tasks:
            return

        # 按权重排序
        sorted_tasks = sorted(
            self.task_fishers.items(),
            key=lambda x: x[1].weight,
            reverse=True
        )

        # 保留top-k
        to_keep = dict(sorted_tasks[:max_tasks])
        removed = len(self.task_fishers) - max_tasks

        self.task_fishers = to_keep
        logger.info(f"[EWC] 剪枝任务: 保留 {max_tasks}, 移除 {removed}")

    def save_state(self):
        """保存EWC状态到磁盘"""
        try:
            state = {
                'lambda_ewc': self.params.lambda_ewc,
                'online_mode': self.params.online_mode,
                'gamma': self.params.gamma,
                'task_fishers': {
                    task_id: {
                        'task_id': tf.task_id,
                        'fisher_matrix': tf.fisher_matrix,
                        'optimal_params': tf.optimal_params,
                        'weight': tf.weight,
                        'created_at': tf.created_at
                    }
                    for task_id, tf in self.task_fishers.items()
                },
                'current_params': self.current_params,
                'saved_at': time.time()
            }

            filepath = self.storage_path / "ewc_state.json"
            with open(filepath, 'w', encoding=Encoding.UTF8) as f:
                json.dump(state, f, indent=2)

            logger.info(f"[EWC] 保存状态: {len(self.task_fishers)}个任务")

        except Exception as e:
            logger.error(f"[EWC] 保存状态失败: {e}")

    def load_state(self) -> bool:
        """从磁盘加载EWC状态"""
        try:
            filepath = self.storage_path / "ewc_state.json"
            if not filepath.exists():
                return False

            with open(filepath, 'r', encoding=Encoding.UTF8) as f:
                state = json.load(f)

            self.params = EWCParams(
                lambda_ewc=state.get('lambda_ewc', 0.1),
                online_mode=state.get('online_mode', True),
                gamma=state.get('gamma', 0.95)
            )

            self.task_fishers = {}
            for task_id, tf_data in state.get('task_fishers', {}).items():
                self.task_fishers[task_id] = TaskFishers(
                    task_id=tf_data['task_id'],
                    fisher_matrix=tf_data.get('fisher_matrix', {}),
                    optimal_params=tf_data.get('optimal_params', {}),
                    weight=tf_data.get('weight', 1.0),
                    created_at=tf_data.get('created_at', time.time())
                )

            self.current_params = state.get('current_params', {})

            logger.info(f"[EWC] 加载状态: {len(self.task_fishers)}个任务")
            return True

        except Exception as e:
            logger.error(f"[EWC] 加载状态失败: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_tasks': len(self.task_fishers),
            'lambda_ewc': self.params.lambda_ewc,
            'online_mode': self.params.online_mode,
            'avg_fisher_size': sum(
                len(tf.fisher_matrix)
                for tf in self.task_fishers.values()
            ) / max(len(self.task_fishers), 1),
            'estimated_forgetting': {
                task_id: self.estimate_forgetting(task_id, self.current_params)
                for task_id in self.task_fishers
            }
        }
