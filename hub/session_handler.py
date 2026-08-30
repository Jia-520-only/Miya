"""会话处理辅助模块

负责会话的保存、结束处理和日记生成
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from memory.lifebook import get_lifebook

logger = logging.getLogger(__name__)


def _load_topic_keywords() -> Dict[str, List[str]]:
    """从 text_config.json 加载话题关键词"""
    try:
        config_path = Path(__file__).parent.parent / "config" / "text_config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("lifebook", {}).get("topic_keywords", {})
    except Exception as e:
        logger.debug(f"[SessionHandler] 加载话题关键词失败: {e}")
    return {}


class SessionHandler:
    """会话处理器

    职责：
    - 处理会话结束和保存
    - 生成 LifeBook 日记
    - 压缩对话历史
    """

    def __init__(self):
        self.lifebook = get_lifebook()
        self.topic_keywords = _load_topic_keywords()
        if not self.topic_keywords:
            self.topic_keywords = {
                "代码": ["代码", "函数", "bug", "运行", "执行"],
                "生活": ["吃饭", "睡觉", "天气", "今天"],
                "情感": ["开心", "难过", "喜欢", "讨厌"],
                "学习": ["学习", "考试", "作业", "教程"],
                "工作": ["工作", "加班", "开会", "项目"],
            }

    async def handle_session_end(
        self,
        session_id: str,
        platform: str = "terminal",
        memory_net=None,
        messages: Optional[List[Dict]] = None,
        emotion: str = "平静",
        topics: Optional[List[str]] = None,
    ) -> Dict:
        """
        处理会话结束，生成 LifeBook 日记

        Args:
            session_id: 会话ID
            platform: 平台类型
            memory_net: MemoryNet实例
            messages: 对话消息列表 (如果已提取)
            emotion: 情感基调
            topics: 话题标签

        Returns:
            处理结果字典
        """
        try:
            logger.info(f"[会话处理] 开始处理会话结束: {session_id} (平台: {platform})")

            # 获取对话消息
            if messages is None:
                messages = await self._fetch_messages(session_id, platform, memory_net)

            if not messages:
                logger.info("[会话处理] 对话历史为空，跳过日记生成")
                return {"success": True, "message": "对话历史为空"}

            # 生成会话摘要
            summary = self._generate_summary(messages)

            # 写入 LifeBook 日记
            date_key = await self.lifebook.append_session(
                session_id=session_id,
                platform=platform,
                messages=messages,
                summary=summary,
                emotion=emotion,
                topics=topics or self._extract_topics(messages),
            )

            logger.info(f"[会话处理] 会话结束处理完成，日记已写入: {date_key}")
            return {
                "success": True,
                "message": f"会话已保存，日记已写入 {date_key}",
                "date_key": date_key,
                "summary": summary,
            }

        except Exception as e:
            logger.error(f"[会话处理] 处理会话结束失败: {e}", exc_info=True)
            return {"success": False, "message": str(e)}

    async def _fetch_messages(self, session_id: str, platform: str, memory_net=None) -> List[Dict]:
        """获取对话消息（统一检索：优先按 user_id）"""
        messages = []

        if memory_net and hasattr(memory_net, "conversation_history") and memory_net.conversation_history:
            try:
                msgs = await memory_net.conversation_history.get_history(session_id, limit=100)
                if msgs:
                    return [{"role": m.role, "content": m.content} for m in msgs]
            except Exception as e:
                logger.debug(f"[会话处理] memory_net 获取消息失败: {e}")

        return messages

    def _generate_summary(self, messages: List[Dict]) -> str:
        """生成会话摘要"""
        if not messages:
            return ""

        user_msgs = [m for m in messages if m.get("role") == "user"]
        ai_msgs = [m for m in messages if m.get("role") == "assistant"]

        parts = []
        if user_msgs:
            last_user = user_msgs[-1].get("content", "")[:50]
            parts.append(f"用户: {last_user}")
        if ai_msgs:
            last_ai = ai_msgs[-1].get("content", "")[:50]
            parts.append(f"弥娅: {last_ai}")

        return " | ".join(parts) if parts else ""

    def _extract_topics(self, messages: List[Dict]) -> List[str]:
        """从消息中提取话题标签"""
        topics = []
        all_text = " ".join(m.get("content", "") for m in messages)
        for topic, keywords in self.topic_keywords.items():
            if any(kw in all_text for kw in keywords):
                topics.append(topic)
        return topics

    async def generate_daily_summary(self, date_key: Optional[str] = None, custom_summary: str = "") -> Dict:
        """生成每日总结"""
        try:
            file_path = await self.lifebook.generate_daily_summary(
                date_key=date_key,
                custom_summary=custom_summary,
            )
            return {"success": True, "file": file_path}
        except Exception as e:
            logger.error(f"[会话处理] 生成每日总结失败: {e}")
            return {"success": False, "message": str(e)}
