"""
吟美虚拟主播 - FastAPI 路由层
深度嵌入 MIYA 的 FastAPI 架构
"""

import logging
import uuid

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from plugins.yinmei.core.live_stream_hub import LiveStreamHub
from plugins.yinmei.core import SharedData

logger = logging.getLogger(__name__)

yinmei_router = APIRouter(prefix="/api/yinmei", tags=["yinmei"])

_hub: LiveStreamHub = None
_data: SharedData = None


def get_hub() -> LiveStreamHub:
    global _hub, _data
    if _hub is None:
        _hub = LiveStreamHub()
        _data = SharedData()
    return _hub


def get_data() -> SharedData:
    global _data
    if _data is None:
        _data = SharedData()
    return _data


class MsgInput(BaseModel):
    msg: str
    uid: str = "0"
    username: str = "anonymous"


class EmoteInput(BaseModel):
    text: str


class SayInput(BaseModel):
    text: str


# ============ 消息入口 ============


@yinmei_router.post("/msg")
async def receive_message(data: MsgInput):
    hub = get_hub()
    traceid = str(uuid.uuid4())
    hub.process_message(traceid, data.msg, data.uid, data.username)
    return {"status": "成功", "traceid": traceid}


@yinmei_router.get("/chat")
async def chat(
    text: str = Query(None),
    uid: str = Query("0"),
    username: str = Query("anonymous"),
    callback: str = Query(None),
):
    hub = get_hub()
    traceid = str(uuid.uuid4())
    if not text:
        return {"traceid": traceid, "status": "值为空"}
    hub.process_message(traceid, text, uid, username)
    return {"traceid": traceid, "status": "成功", "content": text}


# ============ 指令 ============


@yinmei_router.get("/cmd")
async def execute_command(cmd: str = Query(...)):
    hub = get_hub()
    traceid = str(uuid.uuid4())
    hub.process_message(traceid, cmd, "0", "http_cmd")
    return {"status": "成功"}


# ============ TTS 说话 ============


@yinmei_router.post("/say")
async def tts_say(data: SayInput):
    hub = get_hub()
    if hub._tts_callback:
        from threading import Thread

        Thread(target=hub._tts_callback, args=(data.text,), daemon=True).start()
    return {"status": "成功"}


# ============ 表情 ============


@yinmei_router.post("/emote")
async def trigger_emote(data: EmoteInput):
    hub = get_hub()
    if hub._emote_callback:
        from threading import Thread

        Thread(target=hub._emote_callback, args=(data.text,), daemon=True).start()
    return {"status": "成功"}


# ============ 唱歌 ============


@yinmei_router.get("/sing")
async def sing(songname: str = Query(...), username: str = Query("所有人")):
    hub = get_hub()
    hub.process_message(str(uuid.uuid4()), f"唱歌{songname}", "0", username)
    return {"status": "成功"}


# ============ 绘画 ============


@yinmei_router.get("/draw")
async def draw(drawname: str = Query(...), drawcontent: str = Query(""), username: str = Query("所有人")):
    data = get_data()
    data.DrawQueueList.put(
        {
            "traceid": str(uuid.uuid4()),
            "prompt": drawname,
            "drawcontent": drawcontent,
            "username": username,
            "isExtend": False,
        }
    )
    return {"status": "成功"}


# ============ 场景 ============


@yinmei_router.get("/scene")
async def change_scene(scenename: str = Query(...)):
    hub = get_hub()
    hub.change_scene(scenename)
    return {"status": "成功"}


# ============ 歌单 ============


@yinmei_router.get("/songlist")
async def songlist(callback: str = Query(None)):
    import json

    data = get_data()
    songs = []
    now = data.SongNowName
    if now:
        songs.append({"songname": f"'{now.get('username', '')}'点播《{now.get('songname', '')}》"})
    for item in list(data.SongMenuList.queue):
        songs.append({"songname": f"'{item.get('username', '')}'点播《{item.get('songname', '')}》"})
    return {"status": "成功", "content": songs}


# ============ 聊天回复流 ============


@yinmei_router.get("/chatreply")
async def chatreply(callback: str = Query(None)):
    data = get_data()
    if not data.ReplyTextList.empty():
        item = data.ReplyTextList.get()
        return {
            "traceid": item.get("traceid", ""),
            "chatStatus": item.get("chatStatus", ""),
            "status": "成功",
            "content": item.get("text", ""),
        }
    return {"status": "失败", "content": ""}


# ============ 状态 ============


@yinmei_router.get("/status")
async def status():
    data = get_data()
    return {
        "ai_name": data.Ai_Name,
        "enabled": data.yinmei_enabled,
        "is_ai_ready": data.is_ai_ready,
        "is_tts_ready": data.is_tts_ready,
        "is_singing": data.is_singing,
        "is_drawing": data.is_drawing,
        "is_dance": data.is_dance,
        "is_SearchImg": data.is_SearchImg,
        "is_SearchText": data.is_SearchText,
        "is_creating_song": data.is_creating_song,
        "question_queue": data.QuestionList.qsize(),
        "answer_queue": data.AnswerList.qsize(),
        "song_queue": data.SongQueueList.qsize(),
        "song_menu_queue": data.SongMenuList.qsize(),
        "draw_queue": data.DrawQueueList.qsize(),
        "dance_queue": data.DanceQueueList.qsize(),
        "search_img_queue": data.SearchImgList.qsize(),
        "search_text_queue": data.SearchTextList.qsize(),
        "obs_connected": data.obs_switch,
    }


# ============ Live2D 控制 (供吟美内部 + 前端桥接) ============

# 队列用于跨进程 Live2D 命令传递
_live2d_cmd_queue = []


def get_live2d_commands():
    """前端轮询获取待执行的 Live2D 命令"""
    global _live2d_cmd_queue
    cmds = list(_live2d_cmd_queue)
    _live2d_cmd_queue.clear()
    return cmds


def live2d_set_emotion(emotion: str):
    _live2d_cmd_queue.append({"type": "emotion", "value": emotion})


def live2d_set_state(state: str):
    _live2d_cmd_queue.append({"type": "state", "value": state})


def live2d_set_mouth(params: dict):
    _live2d_cmd_queue.append({"type": "mouth", "value": params})


def live2d_trigger_action(action: str):
    _live2d_cmd_queue.append({"type": "action", "value": action})


@yinmei_router.get("/live2d/commands")
async def get_commands():
    data = get_data()
    cmds = get_live2d_commands()
    return {"status": "成功", "enabled": data.yinmei_enabled, "commands": cmds}


@yinmei_router.get("/live2d/emotion")
async def set_emotion(emotion: str = Query(...)):
    live2d_set_emotion(emotion)
    return {"status": "成功"}


@yinmei_router.get("/live2d/state")
async def set_state(state: str = Query("idle")):
    live2d_set_state(state)
    return {"status": "成功"}


@yinmei_router.post("/live2d/mouth")
async def set_mouth(data: dict):
    live2d_set_mouth(data)
    return {"status": "成功"}


@yinmei_router.get("/live2d/action")
async def action(action: str = Query(...)):
    live2d_trigger_action(action)
    return {"status": "成功"}


# ============ B站弹幕 ============


@yinmei_router.get("/bilibili/start")
async def bilibili_start():
    hub = get_hub()
    hub.start_bilibili()
    return {"status": "成功"}


# ============ 自动摇摆 ============


@yinmei_router.get("/swing/start")
async def swing_start():
    hub = get_hub()
    hub.on_tts_start()
    return {"status": "成功"}


@yinmei_router.get("/swing/stop")
async def swing_stop():
    hub = get_hub()
    hub.on_tts_end()
    return {"status": "成功"}


# ============ 主开关 ============


@yinmei_router.get("/toggle")
async def toggle_power(on: bool = Query(...)):
    hub = get_hub()
    if on:
        hub.enable()
        return {"status": "成功", "enabled": True}
    else:
        hub.disable()
        return {"status": "成功", "enabled": False}
