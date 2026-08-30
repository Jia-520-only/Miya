"""
Token 计数工具模块

使用 tiktoken 精确估算 token 数量，替代粗糙的 len(content)//4 估算。
支持 fallback 到字符级估算（当 tiktoken 不可用时）。
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_ENCODING = None
_ENCODING_NAME = "o200k_base"
_MESSAGE_OVERHEAD = 4


def _get_encoding():
    global _ENCODING
    if _ENCODING is not None:
        return _ENCODING

    try:
        import tiktoken

        _ENCODING = tiktoken.get_encoding(_ENCODING_NAME)
        logger.debug(f"[TokenUtils] 已加载 tiktoken 编码器: {_ENCODING_NAME}")
    except Exception as e:
        logger.warning(f"[TokenUtils] tiktoken 加载失败 ({e})，将使用字符级 fallback 估算")
        _ENCODING = False

    return _ENCODING


def set_encoding_name(name: str):
    global _ENCODING_NAME, _ENCODING
    _ENCODING_NAME = name
    _ENCODING = None


def count_tokens(text: Optional[str]) -> int:
    if not text:
        return 0

    enc = _get_encoding()
    if enc:
        try:
            return len(enc.encode(text))
        except Exception:
            pass

    return max(1, len(text) // 2)


def count_message_tokens(content: str) -> int:
    return count_tokens(content) + _MESSAGE_OVERHEAD


def count_messages_tokens(messages: list) -> int:
    return sum(count_message_tokens(str(m.get("content", ""))) for m in messages)


def truncate_by_tokens(
    messages: list,
    max_tokens: int,
    key: str = "content",
) -> list:
    result = []
    total = 0

    for msg in messages:
        text = str(msg.get(key, "")) if isinstance(msg, dict) else str(getattr(msg, key, ""))
        token_count = count_message_tokens(text)

        if total + token_count > max_tokens:
            break

        result.append(msg)
        total += token_count

    return result
