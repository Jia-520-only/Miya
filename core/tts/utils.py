"""
TTS 工具函数
包含文本处理、分割等工具

MIYA TTS 系统的工具层
"""

import re
from typing import List


def filter_text(text: str, filter_brackets: bool = True, filter_special_chars: bool = True) -> str:
    """
    过滤文本,移除括号和特殊字符

    Args:
        text: 原始文本
        filter_brackets: 是否过滤括号
        filter_special_chars: 是否过滤特殊字符

    Returns:
        str: 过滤后的文本
    """
    # 过滤括号内容 【xxx】 (xxx) <xxx>
    if filter_brackets:
        text = re.sub(r"【.*?】", "", text)
        text = re.sub(r"（.*?）", "", text)
        text = re.sub(r"\(.*?\)", "", text)
        text = re.sub(r"<.*?>", "", text)

    # 过滤特殊字符
    if filter_special_chars:
        # 保留中文、英文、数字、基本标点
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9，。！？、；：""' "（）《》【】\\s,\\.!?;:'\\-]", "", text)

    # 清理多余空格
    text = re.sub(r"\s+", "", text)

    return text.strip()


def split_text_for_qq(text: str, max_length: int = 200) -> List[str]:
    """
    将文本分割为适合QQ发送的片段

    Args:
        text: 原始文本
        max_length: 最大长度

    Returns:
        List[str]: 分割后的文本片段
    """
    if len(text) <= max_length:
        return [text]

    segments = []
    current = ""

    # 按句子分割
    sentences = re.split(r"([。！？\n])", text)

    for sentence in sentences:
        if not sentence:
            continue

        if len(current) + len(sentence) <= max_length:
            current += sentence
        else:
            if current:
                segments.append(current)
            current = sentence

    if current:
        segments.append(current)

    return segments
