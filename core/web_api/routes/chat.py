"""
WebAPI 路由 — 对话与 SSE 流式
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/send")
async def chat_send(content: str = "", platform: str = "terminal"):
    return {"response": "", "soul_data": {}}


@router.post("/stop")
async def chat_stop():
    return {"status": "stopped"}
