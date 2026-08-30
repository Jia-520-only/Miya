"""Quoted Message Parser"""

from typing import Any, Dict, List


class QuotedMessageParser:
    """引用消息解析器"""

    def __init__(self):
        self.enabled = True

    def parse(self, message: str) -> Dict[str, Any]:
        """解析引用消息"""
        return {"has_quote": False, "quoted_text": "", "main_text": message}

    def extract_images(self, message: str) -> List[str]:
        """提取引用消息中的图片"""
        return []

    def extract_text(self, message: str) -> str:
        """提取引用消息文本"""
        return message
