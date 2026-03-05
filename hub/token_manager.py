"""
Token管理器 - 专门负责Token估算和压缩

目的: 分离Token管理职责,遵循单一职责原则
      将原本混合在GameMemoryManager中的Token功能独立出来
"""

import logging
from typing import List, Dict
import tiktoken


logger = logging.getLogger(__name__)


class TokenManager:
    """
    Token管理器

    职责:
    1. Token数量估算
    2. 对话压缩触发判断
    3. 摘要生成策略

    设计原则:
    - 单一职责: 只负责Token相关功能
    - 无状态: 不存储数据,只提供工具方法
    - 可复用: 可以被多个模块使用
    """

    def __init__(self):
        """初始化Token管理器"""
        try:
            self._tokenizer = tiktoken.get_encoding("cl100k_base")
            logger.info("[TokenManager] Token估算器初始化成功(cl100k_base)")
        except Exception as e:
            logger.warning(f"[TokenManager] Token估算器初始化失败: {e}")
            self._tokenizer = None

    def estimate_tokens(self, text: str) -> int:
        """
        估算文本的token数量

        Args:
            text: 输入文本

        Returns:
            token数量
        """
        if not text:
            return 0

        if self._tokenizer:
            try:
                return len(self._tokenizer.encode(text))
            except Exception as e:
                logger.warning(f"[TokenManager] Tiktoken估算失败: {e}")

        # 降级估算: 中文1字符≈1.5token, 英文1单词≈1.5token
        return len(text) // 2 + len(text.split())

    def estimate_conversation_tokens(self, messages: List[Dict[str, str]]) -> int:
        """
        估算对话列表的总token数

        Args:
            messages: 消息列表 [{'role': 'user', 'content': '...'}, ...]

        Returns:
            总token数
        """
        total = 0
        for msg in messages:
            # 角色标记约10个token
            total += 10
            total += self.estimate_tokens(msg.get('content', ''))
        return total

    def should_compress(self, current_tokens: int, limit: int = 100000, threshold: float = 0.9) -> bool:
        """
        判断是否需要压缩

        Args:
            current_tokens: 当前token数
            limit: 限制token数
            threshold: 触发阈值比例(0.9表示达到90%时触发)

        Returns:
            是否需要压缩
        """
        return current_tokens > limit * threshold

    def estimate_messages_to_remove(
        self,
        current_tokens: int,
        target_tokens: int,
        avg_tokens_per_message: int = 100
    ) -> int:
        """
        估算需要移除的消息数量

        Args:
            current_tokens: 当前token数
            target_tokens: 目标token数
            avg_tokens_per_message: 平均每条消息的token数

        Returns:
            需要移除的消息数量
        """
        tokens_to_remove = current_tokens - target_tokens
        return max(1, int(tokens_to_remove / avg_tokens_per_message))

    def generate_summary(self, messages: List[Dict[str, str]]) -> str:
        """
        生成对话摘要

        Args:
            messages: 消息列表

        Returns:
            摘要文本
        """
        # 提取对话内容
        dialogue_text = "\n".join([
            f"{'玩家' if m.get('role') == 'user' else 'KP(弥娅)'}: {m.get('content', '')}"
            for m in messages
        ])

        # 简单的关键词摘要(避免额外的AI调用)
        summary_lines = []

        # 提取关键信息
        keywords = {
            "检定/判定": ["检定", "判定", "skill check"],
            "战斗": ["战斗", "攻击", "combat", "attack"],
            "探索": ["探索", "调查", "探索", "investigate"],
            "骰子": ["骰子", "投掷", "dice", "roll"],
        }

        for keyword, patterns in keywords.items():
            if any(pattern in dialogue_text for pattern in patterns):
                summary_lines.append(f"• 进行了{keyword}")

        # 提取角色行动
        user_actions = [msg for msg in messages if msg.get('role') == 'user']
        if user_actions:
            summary_lines.append(f"• 玩家进行了{len(user_actions)}次行动")

        # 统计KP回复
        kp_responses = [msg for msg in messages if msg.get('role') == 'assistant']
        if kp_responses:
            summary_lines.append(f"• KP进行了{len(kp_responses)}次描述和回应")

        if not summary_lines:
            summary_lines.append("• 进行了常规对话交互")

        return "\n".join(summary_lines)

    def calculate_compression_ratio(
        self,
        current_messages: int,
        target_messages: int = 20
    ) -> float:
        """
        计算压缩比例

        Args:
            current_messages: 当前消息数
            target_messages: 目标消息数

        Returns:
            压缩比例(0.0-1.0)
        """
        if current_messages <= target_messages:
            return 0.0
        return 1.0 - (target_messages / current_messages)


# 全局单例
_token_manager = None


def get_token_manager() -> TokenManager:
    """获取Token管理器单例"""
    global _token_manager
    if _token_manager is None:
        _token_manager = TokenManager()
    return _token_manager
