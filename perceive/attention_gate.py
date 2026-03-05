"""
稀疏激活·过滤闸门
实现注意力机制和信息过滤
"""
from typing import Dict, List, Callable, Optional
import random


class AttentionGate:
    """注意力闸门"""

    def __init__(self, activation_rate: float = 0.3):
        self.activation_rate = activation_rate  # 激活率

        # 注意力权重
        self.attention_weights = {}

        # 过滤规则
        self.filter_rules = []

        # 注意力历史
        self.attention_history = []

    def process(self, inputs: List[Dict]) -> List[Dict]:
        """
        处理输入，应用注意力闸门

        Args:
            inputs: 输入信息列表

        Returns:
            通过闸门的输出
        """
        # 应用过滤规则
        filtered = self._apply_filters(inputs)

        # 计算注意力分数
        scored = self._calculate_attention_scores(filtered)

        # 稀疏激活
        activated = self._sparse_activate(scored)

        # 记录历史
        self._record_attention(inputs, activated)

        return activated

    def _apply_filters(self, inputs: List[Dict]) -> List[Dict]:
        """应用过滤规则"""
        filtered = []

        for inp in inputs:
            should_pass = True

            for rule in self.filter_rules:
                if not rule(inp):
                    should_pass = False
                    break

            if should_pass:
                filtered.append(inp)

        return filtered

    def _calculate_attention_scores(self, inputs: List[Dict]) -> List[Dict]:
        """计算注意力分数"""
        scored = []

        for inp in inputs:
            # 基础分数
            base_score = inp.get('priority', 0.5)

            # 类型权重
            input_type = inp.get('type', 'default')
            type_weight = self.attention_weights.get(input_type, 0.5)

            # 新鲜度权重
            recency = inp.get('recency', 0.5)

            # 综合分数
            final_score = (base_score * 0.4 +
                          type_weight * 0.4 +
                          recency * 0.2)

            scored.append({
                **inp,
                'attention_score': round(final_score, 3)
            })

        return scored

    def _sparse_activate(self, scored: List[Dict]) -> List[Dict]:
        """稀疏激活"""
        if not scored:
            return []

        # 按分数排序
        scored.sort(key=lambda x: x['attention_score'], reverse=True)

        # 计算激活数量
        activate_count = max(1, int(len(scored) * self.activation_rate))

        # 返回激活的输入
        return scored[:activate_count]

    def add_filter_rule(self, rule: Callable[[Dict], bool]) -> None:
        """添加过滤规则"""
        self.filter_rules.append(rule)

    def set_attention_weight(self, input_type: str, weight: float) -> None:
        """设置注意力权重"""
        self.attention_weights[input_type] = max(0.0, min(1.0, weight))

    def set_activation_rate(self, rate: float) -> None:
        """设置激活率"""
        self.activation_rate = max(0.1, min(1.0, rate))

    def _record_attention(self, inputs: List[Dict], outputs: List[Dict]) -> None:
        """记录注意力历史"""
        self.attention_history.append({
            'input_count': len(inputs),
            'output_count': len(outputs),
            'pass_rate': len(outputs) / len(inputs) if inputs else 0,
            'timestamp': self._get_timestamp()
        })

        # 只保留最近100条
        if len(self.attention_history) > 100:
            self.attention_history = self.attention_history[-100:]

    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()

    def get_attention_stats(self) -> Dict:
        """获取注意力统计"""
        if not self.attention_history:
            return {'total': 0}

        total_inputs = sum(h['input_count'] for h in self.attention_history)
        total_outputs = sum(h['output_count'] for h in self.attention_history)
        avg_pass_rate = sum(h['pass_rate'] for h in self.attention_history) / len(self.attention_history)

        return {
            'total_processed': len(self.attention_history),
            'total_inputs': total_inputs,
            'total_outputs': total_outputs,
            'avg_pass_rate': round(avg_pass_rate, 3),
            'activation_rate': self.activation_rate
        }
