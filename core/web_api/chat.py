"""
对话相关 API
处理 Web 端对话请求
支持 SSE 流式响应，与 QQ 端灵魂处理逻辑一致
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator, Dict

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from starlette.requests import Request

from .models import ChatRequest

logger = logging.getLogger(__name__)

# SSE 心跳间隔（秒）
SSE_HEARTBEAT_INTERVAL = 5
# SSE 心跳消息
SSE_HEARTBEAT = ": heartbeat\n\n"


class BotMessageAccumulator:
    """累积机器人消息片段"""

    def __init__(self):
        self.full_text = ""
        self.reasoning_text = ""
        self.tool_calls = []
        self.current_tool_call = None

    def add_plain(self, text: str, **kwargs):
        self.full_text += text

    def add_reasoning(self, text: str):
        self.reasoning_text += text

    def get_final_result(self) -> Dict:
        return {
            "response": self.full_text,
            "reasoning": self.reasoning_text,
            "tool_calls": self.tool_calls,
        }


class ChatRoutes:
    """对话路由"""

    def __init__(self, web_net, decision_hub):
        """初始化对话路由

        Args:
            web_net: WebNet 实例
            decision_hub: DecisionHub 实例
        """
        self.web_net = web_net
        self.decision_hub = decision_hub

    def setup_routes(self, router):
        """设置对话相关路由"""

        @router.post("/chat")
        async def chat_message(request: ChatRequest, req: Request):
            """发送聊天消息"""
            try:
                from mlink.message import Message
                from fastapi import Request

                # 确定平台类型（优先使用请求中的platform，否则默认为web）
                platform = request.platform or "desktop"

                perception = {
                    "platform": platform,
                    "content": request.message,
                    "user_id": request.session_id,
                    "sender_name": f"{platform}用户-{request.session_id[:8]}",
                }

                message = Message(
                    msg_type="data",
                    content=perception,
                    source="web_api",
                    destination="decision_hub",
                )

                # 获取处理前的状态
                (self.decision_hub.emotion.get_emotion_state() if self.decision_hub.emotion else None)
                (self.decision_hub.personality.get_profile() if self.decision_hub.personality else None)

                # 调用 DecisionHub 处理消息
                response = await self.decision_hub.process_perception_cross_platform(message)

                if not response:
                    response = "抱歉，我无法处理您的请求。"

                # 获取处理后的状态
                emotion_after = self.decision_hub.emotion.get_emotion_state() if self.decision_hub.emotion else None
                personality_after = (
                    self.decision_hub.personality.get_profile() if self.decision_hub.personality else None
                )

                # 确保返回正确格式
                emotion_result = None
                if emotion_after:
                    emotion_result = {
                        "dominant": emotion_after.get("dominant", "平静"),
                        "intensity": emotion_after.get("intensity", 0.5),
                    }

                personality_result = None
                if personality_after:
                    # 正确的人格数据格式
                    personality_result = {
                        "state": personality_after.get("dominant", "empathy"),  # 使用主导特质
                        "vectors": personality_after.get(
                            "vectors",
                            {
                                "warmth": 0.5,
                                "logic": 0.5,
                                "creativity": 0.5,
                                "empathy": 0.5,
                                "resilience": 0.5,
                            },
                        ),
                    }

                files = None
                try:
                    from core.platform_context import get_current_platform_adapter

                    adapter = get_current_platform_adapter()
                    if adapter and hasattr(adapter, "last_file_info") and adapter.last_file_info:
                        fi = adapter.last_file_info
                        files = [
                            {
                                "name": fi["name"],
                                "size": fi["size"],
                                "mime_type": fi["mime_type"],
                                "url": fi["url"],
                                "base64": fi["base64"],
                            }
                        ]
                        url = fi["url"]
                        response += f"\n\n📄 [{fi['name']}]({url})"
                        adapter.last_file_info = None
                except Exception:
                    pass

                return {
                    "response": response,
                    "timestamp": datetime.utcnow().isoformat(),
                    # 弥娅核心状态
                    "emotion": emotion_result,
                    "personality": personality_result,
                    "files": files,
                    # 工具调用信息（如果有）
                    "tools_used": getattr(self.decision_hub, "_last_tools_used", []),
                    # 记忆检索信息
                    "memory_retrieved": getattr(self.decision_hub, "_last_memory_retrieved", False),
                }
            except Exception as e:
                logger.error(f"[WebAPI] 聊天处理失败: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

    def get_router(self):
        """获取路由器（返回None，因为使用setup_routes方式）"""
        return None

    async def _sse_chat_stream(self, request: ChatRequest, session_id: str) -> AsyncGenerator[str, None]:
        """SSE 流式聊天生成器 - 核心灵魂处理逻辑

        与 QQ 端 / Napcat 完全一致的处理流程：
        1. 创建 M-Link Message
        2. 通过 DecisionHub.process_perception_cross_platform
        3. 灵魂发生器 + AI Client + 工具编排
        4. 流式 SSE 输出
        """
        from mlink.message import Message

        platform = request.platform or "desktop"
        perception = {
            "platform": platform,
            "content": request.message,
            "user_id": request.user_id or session_id,
            "sender_name": f"web用户-{session_id[:8]}",
            "message_type": "private",
        }
        message = Message(
            msg_type="data",
            content=perception,
            source="web_api",
            destination="decision_hub",
        )

        try:
            yield f"data: {json.dumps({'type': 'session_id', 'data': None, 'session_id': session_id}, ensure_ascii=False)}\n\n"

            message_accumulator = BotMessageAccumulator()

            async with asyncio.timeout(120):
                response = await self.decision_hub.process_perception_cross_platform(message)

            if not response:
                response = "抱歉，弥娅无法处理这个请求呢。"

            response_data = {
                "type": "plain",
                "data": response,
                "chain_type": "final",
                "streaming": False,
            }
            yield f"data: {json.dumps(response_data, ensure_ascii=False)}\n\n"

            personality_state = (
                self.decision_hub.personality.get_profile()
                if self.decision_hub and hasattr(self.decision_hub, "personality") and self.decision_hub.personality
                else None
            )
            if personality_state:
                yield f"data: {json.dumps({'type': 'personality', 'data': personality_state}, ensure_ascii=False)}\n\n"

            final_result = message_accumulator.get_final_result()
            final_result["response"] = response
            final_result["timestamp"] = datetime.utcnow().isoformat()
            final_result["personality"] = personality_state
            yield f"data: {json.dumps({'type': 'done', 'data': final_result}, ensure_ascii=False)}\n\n"

        except asyncio.TimeoutError:
            logger.error("[SSE Chat] 处理超时")
            yield f"data: {json.dumps({'type': 'error', 'message': '处理超时，请稍后重试'}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"[SSE Chat] 处理错误: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    def create_sse_endpoint(self):
        """创建 SSE 流式聊天端点（作为独立函数供 router 使用）"""
        from .models import ChatRequest

        async def sse_chat(request: Request, chat_req: ChatRequest):
            session_id = chat_req.session_id or "default"

            return StreamingResponse(
                self._sse_chat_stream(chat_req, session_id),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        return sse_chat
