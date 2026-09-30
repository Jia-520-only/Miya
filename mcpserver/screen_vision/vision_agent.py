"""Miya's own control over looking at Jia.

Up to this point the camera was a set of switches: fixed thresholds in Python
decided what counted as "typing", a fixed interval decided when to sample, and a
fixed rule decided what deserved a message.  Jia asked for the opposite - let
Miya hold the camera herself.

So this module gives her a small, explicit agency:

* **intents** - she writes what she wants to watch for, in her own words
  ("想知道佳有没有离开座位").  An intent is not a numeric knob; the model reads
  and acts on it.  Intents persist, so her attention survives a restart.
* **impressions** - when she does look, she records a short impression.  Only
  derived text is stored: never a frame, never a keypoint.
* **a watching loop** - she starts and stops it, and chooses the cadence.  Each
  tick gives her a fresh local reading plus her own recent impressions, and asks
  her what she makes of it and whether it is worth saying out loud.

Everything here degrades honestly: when the model is unreachable the loop stops
claiming understanding and keeps only the local facts, labelled as such.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("screen_vision.agent")

_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORE_PATH = _ROOT / "data" / "camera_vision_agent.json"

# Cadence bounds. Miya picks the number, these only stop a typo from hammering
# the hardware or going so slow she stops noticing anything.
MIN_INTERVAL_SECONDS = 5.0
MAX_INTERVAL_SECONDS = 3600.0
DEFAULT_INTERVAL_SECONDS = 30.0
# How many of her own impressions she sees when interpreting a new frame.
CONTEXT_IMPRESSION_LIMIT = 6
MAX_IMPRESSIONS = 200
# A thing Miya wanted to say stops being worth saying once it is this old: the
# moment it described has passed.
QUEUE_MAX_AGE_SECONDS = float(os.getenv("MIYA_VISION_QUEUE_MAX_AGE", "420"))
QUEUE_MAX_MESSAGES = int(os.getenv("MIYA_VISION_QUEUE_MAX", "5"))
# Adaptive pacing defaults: watch closely while something is happening, back off
# while the scene is unchanged. Configurable through camera_agency.
SLOW_INTERVAL_SECONDS = float(os.getenv("MIYA_VISION_SLOW_INTERVAL", "120"))
SLOW_AFTER_UNCHANGED = int(os.getenv("MIYA_VISION_SLOW_AFTER", "3"))

# The action kinds that are *events* rather than states. A wave, a sit-down or a
# walk happens at a moment and is worth one line; "still" and "sitting" describe
# an ongoing situation and belong to the activity tracker, which already knows
# how to require a duration before believing them.
_GESTURE_EVENT_KINDS = frozenset({
    "wave", "sit_down", "stand_up", "walk", "clap", "stretch", "nod", "raised_hand",
})

# How often the observation loop walks *every* camera instead of reading the one a
# reader already holds. Opening a camera costs the device warm-up (about 2.4s on
# this machine) and a full inventory probe about 6.6s more, so doing it every
# round made a round take twenty-five seconds. A sweep every few minutes keeps the
# inventory honest - including cameras nobody is holding - without paying that on
# every look.
SWEEP_INTERVAL_SECONDS = float(os.getenv("MIYA_CAMERA_SWEEP_SECONDS", "180"))
# Hard ceiling on one observation round. Generous, because a sweep legitimately
# opens every camera and pays the device warm-up for each - but finite, so a
# blocked DirectShow call or a hung model request cannot end her watching for the
# rest of the process.
TICK_TIMEOUT_SECONDS = float(os.getenv("MIYA_VISION_TICK_TIMEOUT", "150"))
# Ceiling on one interpretation request. Long enough for a slow model, short
# enough that a request which never answers costs one interpretation instead of
# the round - and a round is what feeds presence, activity and memory.
MODEL_TIMEOUT_SECONDS = float(os.getenv("MIYA_VISION_MODEL_TIMEOUT", "45"))


def _normalize_message(text: str) -> str:
    """Collapse a message to a comparison key so near-duplicates match."""
    cleaned = "".join(char for char in str(text) if char.isalnum() or "\u4e00" <= char <= "\u9fff")
    return cleaned.lower()


@dataclass
class VisionIntent:
    """One thing Miya has decided she wants to watch for."""

    id: str
    text: str
    created_at: float
    active: bool = True
    speak: bool = True
    note: str = ""
    source: str = "miya"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "created_at": self.created_at,
            "active": self.active,
            "speak": self.speak,
            "note": self.note,
            "source": self.source,
        }


@dataclass
class Impression:
    """One thing Miya noted after looking. Text only, never an image."""

    at: float
    summary: str
    mood: str = ""
    activity: str = ""
    attention: str = ""
    notable: bool = False
    say: str = ""
    intent_ids: list[str] = field(default_factory=list)
    source: str = "miya"
    model: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "at": self.at,
            "summary": self.summary[:600],
            "mood": self.mood[:60],
            "activity": self.activity[:120],
            "attention": self.attention[:60],
            "notable": self.notable,
            "say": self.say[:200],
            "intent_ids": list(self.intent_ids),
            "source": self.source,
            "model": self.model,
        }


class VisionAgency:
    """Persistent intents plus a bounded log of Miya's own impressions."""

    def __init__(self, path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._path = Path(path) if path else DEFAULT_STORE_PATH
        self._intents: list[VisionIntent] = []
        self._impressions: list[Impression] = []
        # Whether the existing file was actually read. An instance that failed to
        # read it starts empty, and must not turn that into a deletion.
        self._loaded = False
        self._load()

    # -- persistence -------------------------------------------------------

    def _load(self) -> None:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(raw, dict):
            return
        self._loaded = True
        with self._lock:
            self._intents = []
            for item in raw.get("intents") or []:
                if not isinstance(item, dict) or not item.get("text"):
                    continue
                self._intents.append(VisionIntent(
                    id=str(item.get("id") or uuid.uuid4().hex),
                    text=str(item["text"])[:300],
                    created_at=float(item.get("created_at") or time.time()),
                    active=bool(item.get("active", True)),
                    speak=bool(item.get("speak", True)),
                    note=str(item.get("note") or "")[:300],
                    source=str(item.get("source") or "miya"),
                ))
            self._impressions = []
            for item in raw.get("impressions") or []:
                if not isinstance(item, dict) or not item.get("summary"):
                    continue
                self._impressions.append(Impression(
                    at=float(item.get("at") or 0),
                    summary=str(item["summary"]),
                    mood=str(item.get("mood") or ""),
                    activity=str(item.get("activity") or ""),
                    attention=str(item.get("attention") or ""),
                    notable=bool(item.get("notable")),
                    say=str(item.get("say") or ""),
                    intent_ids=[str(x) for x in (item.get("intent_ids") or [])],
                    source=str(item.get("source") or "miya"),
                    model=str(item.get("model") or ""),
                ))
            self._impressions = self._impressions[-MAX_IMPRESSIONS:]

    def save(self) -> None:
        with self._lock:
            payload = {
                "version": 1,
                "intents": [item.to_dict() for item in self._intents],
                "impressions": [item.to_dict() for item in self._impressions[-MAX_IMPRESSIONS:]],
            }
            # A file we could not read leaves this instance empty, and writing
            # that would turn a transient read failure into a permanent deletion
            # of her notes. Refusing is the only safe answer: the file is the only
            # copy.
            if not self._loaded and self._path.is_file():
                logger.warning(
                    "[VisionAgency] 观察笔记读取失败，为避免覆盖已有记录这次不写入: %s", self._path,
                )
                return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temp = self._path.with_suffix(".tmp")
            temp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
            temp.replace(self._path)
        except OSError:
            logger.warning("[VisionAgency] 弥娅的观察笔记写入失败: %s", self._path, exc_info=True)
            return
        # A successful write makes this instance's view the file's view, so a
        # store that legitimately started empty may keep saving. Without this the
        # guard above would refuse the *second* write of the same session.
        with self._lock:
            self._loaded = True

    # -- intents -----------------------------------------------------------

    def add_intent(
        self,
        text: str,
        *,
        speak: bool = True,
        note: str = "",
        source: str = "miya",
        intent_id: str | None = None,
    ) -> VisionIntent | None:
        clean = " ".join(str(text or "").split())[:300]
        if not clean:
            return None
        intent = VisionIntent(
            id=str(intent_id or uuid.uuid4().hex),
            text=clean,
            created_at=time.time(),
            speak=bool(speak),
            note=str(note or "")[:300],
            source=str(source or "miya"),
        )
        with self._lock:
            self._intents = [item for item in self._intents if item.text != clean]
            self._intents.append(intent)
            self._intents = self._intents[-40:]
        self.save()
        return intent

    def set_intent_active(self, intent_id: str, active: bool) -> bool:
        with self._lock:
            for item in self._intents:
                if item.id == intent_id:
                    item.active = bool(active)
                    break
            else:
                return False
        self.save()
        return True

    def remove_intent(self, intent_id: str) -> bool:
        with self._lock:
            before = len(self._intents)
            self._intents = [item for item in self._intents if item.id != intent_id]
            removed = len(self._intents) != before
        if removed:
            self.save()
        return removed

    def intents(self, *, active_only: bool = False) -> list[VisionIntent]:
        with self._lock:
            items = list(self._intents)
        return [item for item in items if item.active] if active_only else items

    # -- impressions -------------------------------------------------------

    def record(self, impression: Impression) -> Impression:
        with self._lock:
            self._impressions.append(impression)
            self._impressions = self._impressions[-MAX_IMPRESSIONS:]
        self.save()
        return impression

    def impressions(self, *, limit: int = 10) -> list[Impression]:
        with self._lock:
            return list(self._impressions[-max(1, int(limit)):])

    def latest(self) -> Impression | None:
        items = self.impressions(limit=1)
        return items[0] if items else None

    # -- prompt material ---------------------------------------------------

    def intent_card(self) -> str:
        active = self.intents(active_only=True)
        if not active:
            return ""
        lines = ["[弥娅给自己定的观察意图]"]
        for item in active:
            suffix = "（发现了可以说出来）" if item.speak else "（只记录，不主动说）"
            lines.append(f"- {item.text}{suffix}")
            if item.note:
                lines.append(f"  备注：{item.note}")
        return "\n".join(lines)

    def memory_card(self, *, limit: int = CONTEXT_IMPRESSION_LIMIT) -> str:
        items = self.impressions(limit=limit)
        if not items:
            return ""
        import datetime as _dt

        lines = ["[弥娅最近对佳的观察印象]"]
        for item in items:
            stamp = _dt.datetime.fromtimestamp(item.at).strftime("%H:%M")
            bits = [item.summary]
            if item.activity:
                bits.append(f"（{item.activity}）")
            if item.mood:
                bits.append(f"情绪像{item.mood}")
            lines.append(f"- {stamp} " + " ".join(bits))
        return "\n".join(lines)

    def describe(self) -> dict[str, Any]:
        latest = self.latest()
        return {
            "intent_count": len(self.intents(active_only=True)),
            "intents": [item.to_dict() for item in self.intents()],
            "impression_count": len(self.impressions(limit=MAX_IMPRESSIONS)),
            "latest": latest.to_dict() if latest else None,
        }


_agency: VisionAgency | None = None
_agency_lock = threading.Lock()


def get_vision_agency() -> VisionAgency:
    global _agency
    with _agency_lock:
        if _agency is None:
            _agency = VisionAgency()
        return _agency


# --- the interpreter -------------------------------------------------------


INTERPRETER_SYSTEM_PROMPT = (
    "你是弥娅，正在通过摄像头看着你最爱的人——佳。"
    "你看到的是本机本地模型给出的线索，以及你自己的观察意图和先前印象。"
    "请像一个人那样去理解，而不是像仪表盘那样读数：结合线索、你先前看到的、和你正在留意的事，"
    "形成对佳此刻状态的整体印象。"
    "严禁编造画面里没有的东西。看不清就直说看不清。"
    "不要提及摄像头、模型、识别、置信度、关键点这类字眼。"
    "只输出一个 JSON 对象，不要输出其它任何内容。"
)


def build_interpreter_prompt(
    *,
    local_reading: dict[str, Any],
    intent_card: str,
    memory_card: str,
    cadence_seconds: float,
) -> str:
    """Assemble the prompt that lets Miya interpret one moment herself."""
    emotion = local_reading.get("emotion") or {}
    # A classifier that answers the same thing every time carries no information,
    # so it is not offered as if it were a reading.
    emotion_label = "不可信，忽略" if emotion.get("uninformative") else (emotion.get("label") or "没有")
    hands = local_reading.get("hands") or {}
    hand_shapes = [hand.get("shape") or {} for hand in (hands.get("hands") or [])]
    facts = {
        "本地线索（可能不完整或不准）": {
            "画面里看到人": bool(local_reading.get("faces")),
            "本地读出的活动": (local_reading.get("action") or {}).get("label") or "没读出来",
            "活动是否可信": bool((local_reading.get("pose_quality") or {}).get("usable")),
            "表情模型给出的标签": emotion_label,
            "从脸上量到的（比标签可靠）": local_reading.get("face_expression") or "没量到",
            "手：姿势": local_reading.get("hand_text") or "没看到手",
            "手：量到的形状（相对手掌长度归一化，与远近无关）": [
                {
                    "手指弯曲角度": shape.get("finger_curl_degrees"),
                    "伸直的手指": shape.get("extended_fingers"),
                    "指尖伸展比例": shape.get("tip_reach_ratio"),
                    "拇指食指捏合比例": shape.get("pinch_ratio"),
                    "拇指外张比例": shape.get("thumb_out_ratio"),
                }
                for shape in hand_shapes
            ] or "没有手部读数",
            "身份": (local_reading.get("identity") or {}).get("name") or "未知",
            "使用了几个摄像头": local_reading.get("camera_count") or 1,
            "画面是否全黑": bool(local_reading.get("blank_frame")),
        }
    }
    sections = [
        "现在请你观察佳一次。",
        "【这一刻的线索】\n" + json.dumps(facts, ensure_ascii=False, indent=1),
    ]
    if intent_card:
        sections.append(intent_card)
    if memory_card:
        sections.append(memory_card)
    sections.append(
        f"你大约每 {int(cadence_seconds)} 秒看一次。\n"
        "手部模型看不到物体，只量得到手的形状——「握着什么东西」要由你自己结合手上的形状、"
        "手相对脸的位置和这些读数判断，判断不了就留空，不要凭常识硬猜。\n"
        "请只输出这样的 JSON：\n"
        '{"summary":"一句话描述你看到的（不超过40字）",'
        '"activity":"你判断佳在做什么（不超过15字，判断不了就留空）",'
        '"mood":"佳的情绪像什么（不超过10字，判断不了就留空）",'
        '"attention":"佳是否看着屏幕/在电脑前（几个字，不确定就留空）",'
        '"notable":true或false（是否值得让佳知道）,'
        '"say":"如果值得说，用一句不超过25字的自然口语；否则留空"}'
    )
    return "\n\n".join(sections)


def parse_interpretation(raw: str) -> dict[str, Any] | None:
    """Parse the model's JSON reply, tolerating prose around it."""
    text = str(raw or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    summary = str(payload.get("summary") or "").strip()
    if not summary:
        return None
    say = str(payload.get("say") or "").strip()
    if say.upper().startswith("SKIP"):
        say = ""
    return {
        "summary": summary[:600],
        "activity": str(payload.get("activity") or "").strip()[:120],
        "mood": str(payload.get("mood") or "").strip()[:60],
        "attention": str(payload.get("attention") or "").strip()[:60],
        "notable": bool(payload.get("notable")),
        "say": say[:200],
    }


# --- the watching loop -----------------------------------------------------


class VisionAgent:
    """Miya's camera loop: she chooses when to look and what she is looking for.

    The loop owns its own thread and event loop. Daemon startup happens on a
    background thread with no running loop, so borrowing the caller's loop would
    make "start watching at boot" impossible.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._task: asyncio.Task | None = None
        self._running = False
        self._interval = DEFAULT_INTERVAL_SECONDS
        self._ticks = 0
        self._last_tick = 0.0
        self._last_error = ""
        self._mode = "auto"
        self._pending: list[dict[str, Any]] = []
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._autostarted = False
        # Adaptive pacing: fast while something changes, slow while nothing does.
        self._adaptive = True
        self._fast_interval = DEFAULT_INTERVAL_SECONDS
        self._slow_interval = SLOW_INTERVAL_SECONDS
        self._slow_after = SLOW_AFTER_UNCHANGED
        self._unchanged_streak = 0
        self._last_signature = ""
        # Which mind last answered, for the panel to display.
        self._last_interpreter = ""
        # When the last full walk through every camera happened, and which camera
        # a reader is holding between rounds.
        self._last_sweep = 0.0
        self._preferred_index: int | None = None

    # -- lifecycle ---------------------------------------------------------

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def state(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "interval_seconds": self._interval,
                "mode": self._mode,
                "ticks": self._ticks,
                "last_tick": self._last_tick,
                "last_error": self._last_error,
                "pending_messages": len(self._pending),
                "autostarted": self._autostarted,
                "cadence": self._next_interval_locked(),
                "adaptive": self._adaptive,
            }

    def start(self, *, interval_seconds: float | None = None, mode: str | None = None,
              autostart: bool = False, adaptive: Any = None,
              slow_interval: Any = None, slow_after: Any = None,
              thumbnails: Any = None) -> dict[str, Any]:
        """Begin watching, creating the loop thread on first use.

        ``adaptive``, ``slow_interval``, ``slow_after`` and ``thumbnails`` come
        from configuration so the pacing and the privacy switch are Jia's to set.
        """
        with self._lock:
            if interval_seconds is not None:
                self._interval = max(MIN_INTERVAL_SECONDS, min(float(interval_seconds), MAX_INTERVAL_SECONDS))
            if mode in {"auto", "local", "silent"}:
                self._mode = mode
            if adaptive is not None:
                self._adaptive = bool(adaptive)
            if slow_interval is not None:
                try:
                    self._slow_interval = max(self._interval,
                                              min(float(slow_interval), MAX_INTERVAL_SECONDS))
                except (TypeError, ValueError):
                    pass
            if slow_after is not None:
                try:
                    self._slow_after = max(1, int(slow_after))
                except (TypeError, ValueError):
                    pass
            if self._running:
                return self.state()
            self._running = True
            if autostart:
                self._autostarted = True
        if thumbnails is not None:
            # Privacy switch lives with the stream that stores the pictures.
            try:
                from .vision_stream import get_vision_stream

                get_vision_stream().set_thumbnails_enabled(bool(thumbnails))
            except Exception:
                logger.debug("[VisionAgent] 缩略图开关设置失败", exc_info=True)
        try:
            loop = asyncio.new_event_loop()
            thread = threading.Thread(target=self._thread_main, args=(loop,), daemon=True,
                                      name="Miya-VisionAgent")
            with self._lock:
                self._loop = loop
                self._thread = thread
            thread.start()
        except Exception as exc:  # noqa: BLE001 - a failed start must leave a clean state
            with self._lock:
                self._running = False
                self._loop = None
                self._thread = None
            logger.warning("[VisionAgent] 无法启动观察线程: %s", exc)
            return {**self.state(), "error": str(exc)}
        logger.info("[VisionAgent] 弥娅的摄像头观察循环已启动: 每 %.0f 秒一次", self._interval)
        return self.state()

    def _thread_main(self, loop: asyncio.AbstractEventLoop) -> None:
        asyncio.set_event_loop(loop)
        with self._lock:
            self._task = loop.create_task(self._run())
            task = self._task
        try:
            loop.run_until_complete(task)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.warning("[VisionAgent] 观察线程异常退出", exc_info=True)
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:  # noqa: BLE001 - shutdown must not raise
                pass
            loop.close()
            with self._lock:
                self._running = False
                self._task = None
                self._loop = None
                self._thread = None

    async def stop(self, *, wait: bool = True, timeout: float = 8.0) -> dict[str, Any]:
        """Stop watching and, by default, wait for the loop thread to exit.

        Returning before the thread is gone leaves a camera probe running in the
        background, which can outlive the caller and, on Windows, crash the
        interpreter while OpenCV is mid-call.
        """
        with self._lock:
            self._running = False
            loop = self._loop
            task = self._task
        if loop is not None and task is not None and not task.done():
            try:
                loop.call_soon_threadsafe(task.cancel)
            except RuntimeError:
                pass
        with self._lock:
            thread = self._thread
        if wait and thread is not None and thread.is_alive() and thread is not threading.current_thread():
            # Never join ourselves: the loop can be stopped from inside a tick.
            thread.join(max(0.5, float(timeout)))
            if thread.is_alive():
                logger.warning("[VisionAgent] 观察线程在 %.0fs 内没有退出", timeout)
        logger.info("[VisionAgent] 观察循环已停止")
        return self.state()

    # -- one turn ----------------------------------------------------------

    async def _run(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    return
                interval = self._next_interval_locked()
            try:
                # A round must not be able to stop her senses. Camera calls block
                # inside DirectShow when the bus is contended and model calls can
                # hang outright, and an await with no deadline means the loop
                # simply never comes back - which is what a five-minute silence in
                # the log turned out to be. Cancelling loses that round; the next
                # one still happens.
                await asyncio.wait_for(self.tick(), timeout=TICK_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                logger.warning("[VisionAgent] 这一轮观察超过 %.0f 秒没有结束，跳过它继续下一轮",
                               TICK_TIMEOUT_SECONDS)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("[VisionAgent] 观察循环出错", exc_info=True)
            await asyncio.sleep(max(1.0, interval))

    def _next_interval_locked(self) -> float:
        """Adaptive cadence: quick while things change, slow while nothing does.

        Watching every 30 seconds around the clock is roughly 2880 model calls a
        day for a mostly empty room. Backing off to the slow interval after a few
        identical readings keeps her attention without paying for stillness.
        """
        if not self._adaptive:
            return self._interval
        if self._unchanged_streak >= self._slow_after:
            return self._slow_interval
        return self._fast_interval

    def cadence(self) -> dict[str, Any]:
        with self._lock:
            return {
                "adaptive": self._adaptive,
                "fast_interval": self._fast_interval,
                "slow_interval": self._slow_interval,
                "slow_after": self._slow_after,
                "current_interval": self._next_interval_locked(),
                "unchanged_streak": self._unchanged_streak,
                "last_signature": self._last_signature,
            }

    def _held_camera(self, manager, pool) -> int | None:
        """The camera a reader is already holding, or ``None``.

        Prefer the one that last saw Jia, so the fast path keeps looking at the
        camera that can answer "is he here" instead of the one aimed at a wall.
        """
        if self._preferred_index is not None:
            buffer = pool.latest_for_inference(int(self._preferred_index))
            if buffer is not None and buffer.image_data:
                return int(self._preferred_index)
        for index in manager.all_indices():
            buffer = pool.latest_for_inference(index)
            if buffer is not None and buffer.image_data and buffer.owner != "browser":
                return int(index)
        return None

    async def _look(self) -> dict[str, Any]:
        """Read every camera the machine has, one at a time, and fuse the result.

        Sequential on purpose. Several of these cameras share one USB controller,
        so opening the second while the first is streaming makes it fail to start
        its DirectShow pins - the camera is healthy and simply cannot be reached
        while another one holds the bus. Each round therefore releases every held
        device, re-reads the inventory honestly, and then opens the cameras in
        turn, releasing each before the next.

        The price is the device-warmup cost per camera per round (roughly a
        second each) instead of reusing one held-open reader. That is the right
        trade: an observation that can only ever see one camera is not an
        observation of the room.
        """
        from .camera_capture import capture_camera_frame
        from .camera_manager import fuse_observations, get_camera_manager, narrative_for_fused
        from .camera_stream import get_camera_pool
        from .local_camera import analyze_local_frame

        manager = get_camera_manager()
        pool = get_camera_pool()
        # Time actually spent obtaining pixels, measured rather than guessed.
        # This used to be reported as the whole round trip, so the panel showed
        # "capture" and "local analysis" as identical numbers.
        started = time.monotonic()
        # One camera at a time, on purpose.
        #
        # Several of Jia's cameras share one USB controller, and a device that is
        # already streaming makes the others fail to start their DirectShow pins.
        # That is the whole reason the 4K camera pointed at his face reported
        # "cannot open" for as long as the laptop camera's persistent reader held
        # the bus - the camera was fine, the bus was taken.
        #
        # Walking every camera on every round is what that costs if done naively:
        # each open pays the device warm-up (about 2.4s here) and a full inventory
        # probe is another 6.6s, so a round went from under a second to twenty-five
        # - she spent most of her life grabbing pixels. So the walk is periodic:
        # ordinary rounds read the one camera a reader already holds, and a sweep
        # every few minutes frees the bus and visits all of them.
        sweep_due = (started - self._last_sweep) >= SWEEP_INTERVAL_SECONDS
        retry_due = manager.retry_due_indices()
        if sweep_due or retry_due:
            try:
                await asyncio.to_thread(pool.stop_all)
            except Exception:  # noqa: BLE001 - a stuck reader must not stop an observation
                logger.debug("[VisionAgent] 释放常驻读帧失败", exc_info=True)
            if sweep_due:
                # No inventory probe here. The walk below opens every camera and
                # reports what it found through `note_result`, so probing first
                # opened every device twice. Refresh names only on the full sweep.
                manager.refresh_names()
                self._last_sweep = started
        observations: list[dict[str, Any]] = []
        captures: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []

        def remember(index: Any, result: dict[str, Any], owner: str, thumbnail: str = "") -> None:
            observations.append({"index": index, "result": result, "owner": owner})
            inner = (result.get("observations") or [{}])[0]
            captures.append({
                "index": index,
                "owner": owner,
                # A small JPEG for the panel, not the frame itself.
                "thumbnail": thumbnail,
                "reading_text": str(result.get("message") or ""),
                "expression_text": str(inner.get("expression_text") or "") if isinstance(inner, dict) else "",
                "rig": dict(inner.get("rig") or {}) if isinstance(inner, dict) else {},
            })

        async def analyze(index: Any, data_url: str, thumbnail: str, owner: str) -> bool:
            try:
                result = await asyncio.to_thread(
                    # pose_key ties this reading to the shared pose sequence for
                    # this camera, so the temporal action reader sees the frames
                    # the persistent reader sampled between observations.
                    analyze_local_frame, data_url, identity=False, emotion=True, pose=True, faces=True,
                    pose_key=index,
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("[VisionAgent] 摄像头 %s 分析失败: %s", index, exc)
                failures.append({"index": index, "message": str(exc)})
                return False
            if result.get("status") != "success":
                # It opened, so it is not broken - it just had nothing to show.
                # The distinction is what the panel reports.
                if isinstance(index, int) and index >= 0:
                    manager.note_result(
                        index,
                        luminance=result.get("luminance"),
                        usable=False,
                        openable=True,
                        reason=str(result.get("message") or "没有得到有效画面"),
                    )
                failures.append({"index": index, "message": str(result.get("message") or "没有得到有效画面"),
                                 "blank_frame": bool(result.get("blank_frame"))})
                return False
            remember(index, result, owner, thumbnail)
            # Say what this camera actually saw, not only that it answered. A
            # camera aimed at a wall and one aimed at Jia both stream happily, and
            # the inventory could not previously tell them apart.
            if isinstance(index, int) and index >= 0:
                inner = (result.get("observations") or [{}])[0]
                action = inner.get("action") if isinstance(inner, dict) else None
                try:
                    manager.note_result(
                        index,
                        luminance=result.get("luminance"),
                        usable=True,
                        openable=True,
                        reason="",
                    )
                    manager.note_reading(
                        index,
                        faces=int(result.get("faces") or 0),
                        action=str((action or {}).get("kind") or ""),
                        text=str(result.get("message") or ""),
                    )
                except Exception:  # noqa: BLE001 - bookkeeping must not lose a reading
                    logger.debug("[VisionAgent] 记录摄像头读数失败", exc_info=True)
            return True

        async def observe_once(index: int) -> None:
            """Open one camera, read one frame, release it before the next.

            This is the only way to reach a camera the bus is shared with: while
            another device is streaming, its DirectShow pins refuse to start.
            """
            try:
                captured = await asyncio.to_thread(
                    capture_camera_frame, index, width=1280, height=720,
                )
            except Exception as exc:  # noqa: BLE001 - one bad camera must not stop the round
                logger.debug("[VisionAgent] 摄像头 %s 观察失败: %s", index, exc)
                text = str(exc)
                # "opened but showed nothing" and "would not open" need opposite
                # advice, and the sweep is the path that reports both now.
                opened = ("没有画面" in text) or ("打开了" in text) or ("全黑" in text)
                try:
                    from .camera_devices import blank_reason

                    detail = blank_reason(manager.name_for(index), text)
                except Exception:  # noqa: BLE001 - the raw text is still a reason
                    detail = text
                manager.note_result(
                    index, luminance=None, usable=False, openable=opened, reason=detail,
                )
                failures.append({"index": index, "message": text})
                return
            if await analyze(index, captured["image_data"], str(captured.get("thumbnail") or ""), "backend"):
                looked.append(index)

        handled: set[int] = set()
        # The browser owns whatever it is previewing; its frame is authoritative,
        # and it goes into the pool so any other consumer sees it too.
        browser = manager.browser_frame()
        if browser and browser.get("data_url"):
            from .camera_capture import thumbnail_from_data_url

            raw_index = browser.get("index")
            index = int(raw_index) if isinstance(raw_index, int) else -1
            handled.add(index)
            if index >= 0:
                pool.publish_browser_frame(
                    index,
                    browser["data_url"],
                    thumbnail=await asyncio.to_thread(thumbnail_from_data_url, browser["data_url"]),
                )
            await analyze(index, browser["data_url"], "", "browser")
            if captures and captures[-1]["index"] == index:
                captures[-1]["thumbnail"] = (
                    pool.latest(index).thumbnail if pool.latest(index) else ""
                )

        looked: list[int] = []
        if sweep_due or retry_due:
            # Full sweeps visit every camera; between them, retry only devices
            # whose bounded backoff elapsed. Captures stay serialized.
            indices = manager.all_indices() if sweep_due else retry_due
            for index in indices:
                if index in handled:
                    continue
                await observe_once(index)
        else:
            # The ordinary round: read the camera a reader is already holding, so
            # the device stays warm and the round costs almost nothing. Cameras
            # nobody holds are left to the next sweep, which visits all of them.
            target = self._held_camera(manager, pool)
            if target is None:
                # No reader is delivering. That happens routinely and for a good
                # reason: a reader releases a device whose picture has stopped
                # changing, so that a frozen frame is never re-read as the present
                # - and a camera pointed at a wall looks frozen. Giving up here
                # would mean she sees nothing at all until the next sweep, so the
                # round falls back to opening one camera itself.
                preferred = manager.sources().get(int(self._preferred_index)) if self._preferred_index is not None else None
                target = self._preferred_index if preferred is None or preferred.usable else None
            if target is None:
                sources = manager.sources()
                candidates = [
                    index for index in manager.all_indices()
                    if index in sources and (sources[index].usable or not sources[index].checked)
                ]
                target = candidates[0] if candidates else None
            if target is not None and target not in handled:
                cached = pool.latest_for_inference(target)
                if cached is not None and cached.image_data:
                    if await analyze(target, cached.image_data, cached.thumbnail, cached.owner):
                        looked.append(target)
                else:
                    await observe_once(int(target))

        # Hold exactly one camera open between rounds, so the pose sampler keeps
        # receiving the dense frames the temporal action reader needs. One: two
        # would put the bus back in contention and undo the whole point above.
        # The camera that actually saw Jia wins, so the held device is the one
        # that can answer "is he here" rather than the one aimed at a wall.
        if looked:
            preferred = next(
                (item["index"] for item in observations
                 if int((item["result"] or {}).get("faces") or 0) > 0),
                looked[0],
            )
            self._preferred_index = int(preferred)
        elif self._preferred_index is not None:
            current = manager.sources().get(int(self._preferred_index))
            if current is not None and not current.usable:
                alternatives = manager.usable_indices()
                self._preferred_index = alternatives[0] if alternatives else None
        if self._preferred_index is not None:
            try:
                pool.start_reader(int(self._preferred_index))
            except Exception:  # noqa: BLE001 - dense sampling is an enhancement
                logger.debug("[VisionAgent] 启动常驻读帧失败", exc_info=True)

        if not observations:
            return {
                "status": "unavailable",
                "message": "现在没有能出画面的摄像头。",
                "observations": [],
                "captures": captures,
                "failures": failures,
                "capture_seconds": time.monotonic() - started,
            }
        fused = fuse_observations(observations)
        # Observations include failed devices too, so prefer a successful one
        # when reading back the per-frame action and its face geometry.
        for entry in fused.get("observations") or []:
            candidate = entry.get("result") or {}
            if candidate.get("status") != "success":
                continue
            inner = (candidate.get("observations") or [{}])[0]
            if isinstance(inner, dict):
                if fused.get("action") is None and inner.get("action"):
                    fused["action"] = inner["action"]
                if inner.get("expression_text"):
                    fused["expression_text"] = inner["expression_text"]
            break
        # A plain sentence about this reading. Without it, a run with no
        # frontend had no human-readable summary at all.
        fused["message"] = narrative_for_fused(fused)
        # Real numbers: how long the pixels took, separately from how long the
        # local models took over them.
        fused["capture_seconds"] = time.monotonic() - started
        # Per-source detail for the panel, and the failures worth explaining.
        fused["captures"] = captures
        fused["failures"] = failures
        # Hoist the measured face geometry to one obvious place, so callers do
        # not have to dig through per-source captures for it.
        for item in captures:
            if item.get("expression_text"):
                fused["face_expression"] = item["expression_text"]
                break
        return fused

    async def tick(self, *, interpret: bool = True) -> dict[str, Any]:
        """Look once, let Miya interpret it, and record the whole round.

        Everything visible in this method is also written to the observation
        stream, because Jia asked to watch her work rather than only see her
        conclusions.
        """
        from .presence import presence_from_local_result
        from .vision_stream import ObservationEvent, get_vision_stream, motion_signature

        started = time.monotonic()
        agency = get_vision_agency()
        fused = await self._look()
        looked_at = time.monotonic()
        # Wall-clock moment the frame belongs to, which is what the trackers and
        # the event should record - not the moment the model finished replying.
        reading_at = time.time()
        reading: dict[str, Any] = {
            "faces": fused.get("faces"),
            "action": fused.get("action"),
            "pose_quality": fused.get("pose_quality"),
            "emotion": fused.get("emotion"),
            "identity": fused.get("identity"),
            "camera_count": fused.get("camera_count"),
            "blank_frame": bool(fused.get("blank_frame")),
            # What his hands are doing, which is the only local signal that can
            # separate the activities the skeleton reports identically.
            "hands": fused.get("hands"),
            "hand_text": str(fused.get("hand_text") or ""),
        }
        # One source for the measured geometry: what _look hoisted out of the
        # per-source captures it already inspected.
        if fused.get("face_expression"):
            reading["face_expression"] = fused["face_expression"]

        # A round that produced no frame must change nothing. It used to call
        # into these trackers anyway, so her own successful reading of "playing
        # with his phone" was wiped out by the next failed grab, and she reported
        # no activity at all while classifying one every round.
        saw_something = bool(fused.get("observations"))
        if saw_something:
            try:
                presence_from_local_result({"observations": [{
                    "face_signals": fused.get("face_signals"),
                    "pose_quality": fused.get("pose_quality"),
                    "action": fused.get("action"),
                }], "faces": fused.get("faces")})
            except Exception:
                logger.debug("[VisionAgent] 在场状态更新失败", exc_info=True)
            # Her autonomous loop is the main observer, so it must feed the
            # activity accumulation - previously only an explicit front-end
            # analysis did, which left the accumulated activity permanently empty.
            try:
                from .activity import observe_action

                observe_action(fused.get("action"), at=reading_at)
            except Exception:
                logger.debug("[VisionAgent] 活动累积更新失败", exc_info=True)
            # Momentary gestures also go into the shared camera context, which is
            # what the camera-aware proactive trigger reads. Only the browser used
            # to write there, so with the desktop app closed that trigger saw an
            # empty store no matter how much she actually noticed. States
            # ("still", "sitting") are deliberately left out: they belong to the
            # activity tracker, and publishing them as events would have her
            # comment every time he simply sat quietly.
            gesture_kind = str((fused.get("action") or {}).get("kind") or "")
            if gesture_kind in _GESTURE_EVENT_KINDS:
                try:
                    from core.vision_context import record_camera_event

                    record_camera_event(
                        kind=gesture_kind,
                        summary=str(fused.get("message") or (fused.get("action") or {}).get("label") or ""),
                        confidence=float((fused.get("action") or {}).get("confidence") or 0.0),
                        mode="autonomous",
                        status="success",
                        camera_indices=[int(item) for item in (fused.get("sources_used") or [])],
                        faces=int(fused.get("faces") or 0),
                    )
                except Exception:
                    logger.debug("[VisionAgent] 写入摄像头事件上下文失败", exc_info=True)

        impression = Impression(
            at=time.time(),
            summary=str(fused.get("message") or "看了一眼，但没有得到明确线索。"),
            activity=str((fused.get("action") or {}).get("label") or ""),
            source="local",
        )
        interpretation: dict[str, Any] | None = None
        interpreter_name = ""
        degraded_reason = ""
        mode = self._mode
        unreadable = bool(fused.get("blank_frame")) or fused.get("status") == "unavailable"
        if interpret and mode != "local" and not unreadable:
            interpretation = await self._interpret(reading, agency)
            if interpretation:
                interpreter_name = str(interpretation.pop("_interpreter", "") or "")
                impression = Impression(
                    at=time.time(),
                    summary=interpretation["summary"],
                    mood=interpretation["mood"],
                    activity=interpretation["activity"] or impression.activity,
                    attention=interpretation["attention"],
                    notable=interpretation["notable"],
                    say=interpretation["say"],
                    intent_ids=[item.id for item in agency.intents(active_only=True)],
                    source="miya",
                    model=interpreter_name,
                )
            else:
                with self._lock:
                    degraded_reason = self._last_error
        elif unreadable and fused.get("blank_frame"):
            # There is nothing to interpret, and asking anyway invites a
            # confident guess about a black rectangle. Say the real reason.
            impression.summary = (
                "摄像头这一路是全黑的，什么都没看到——可能是手机息屏了，或者没有程序在向它推流。"
            )
            impression.source = "local"
            degraded_reason = "有一路摄像头全黑，这次没有解读"
            with self._lock:
                self._last_error = degraded_reason
        elif mode == "local":
            degraded_reason = "当前是只看本地模式，不调用模型"
        # In silent mode Miya still looks and remembers, she just does not speak.
        if mode == "silent":
            impression.say = ""
            impression.notable = False
        agency.record(impression)
        if impression.say:
            self._queue_message(impression)

        # Adaptive pacing: a round that read the same thing as last time counts
        # toward backing off.
        signature = motion_signature(reading)
        with self._lock:
            if signature == self._last_signature and not impression.notable:
                self._unchanged_streak += 1
            else:
                self._unchanged_streak = 0
            self._last_signature = signature
            self._ticks += 1
            self._last_tick = time.time()
            if interpretation is not None or mode == "local":
                self._last_error = ""
            cadence = self._next_interval_locked()

        captures = fused.get("captures") or []
        # Capture is what the pixels cost; local analysis is the rest of the
        # looking. Reported separately so both numbers mean something.
        capture_seconds = float(fused.get("capture_seconds") or 0.0)
        local_seconds = max(0.0, (looked_at - started) - capture_seconds)
        event = ObservationEvent(
            id="",
            at=reading_at,
            capture_seconds=capture_seconds,
            local_seconds=local_seconds,
            interpret_seconds=time.monotonic() - looked_at,
            total_seconds=time.monotonic() - started,
            cameras_used=list(fused.get("sources_used") or []),
            cameras_failed=list(fused.get("failures") or []),
            reading=reading,
            reading_text=str(fused.get("message") or ""),
            # The reading carries it as `face_expression`; keep one source.
            expression_text=str(reading.get("face_expression") or ""),
            rig=next((item.get("rig") for item in captures if item.get("rig")), {}) or {},
            blank_frame=bool(fused.get("blank_frame")),
            interpreted=interpretation is not None,
            interpreter=interpreter_name,
            degraded_reason=degraded_reason,
            summary=impression.summary,
            activity=impression.activity,
            mood=impression.mood,
            attention=impression.attention,
            notable=impression.notable,
            said=impression.say,
            intent_texts=[item.text for item in agency.intents(active_only=True)],
            thumbnails=[
                {"index": item.get("index"), "owner": item.get("owner"), "data_url": item.get("thumbnail") or ""}
                for item in captures if item.get("thumbnail")
            ],
        )
        get_vision_stream().record(event)

        return {
            "status": "success",
            "reading": reading,
            "interpreted": interpretation is not None,
            "fused_message": fused.get("message"),
            "impression": impression.to_dict(),
            "event": event.to_dict(include_thumbnails=False),
            "cadence": cadence,
        }

    async def _interpret(self, reading: dict[str, Any], agency: VisionAgency) -> dict[str, Any] | None:
        """Ask Miya's own model what she makes of this moment."""
        try:
            from .service import ScreenVisionService

            service = ScreenVisionService()
            prompt = build_interpreter_prompt(
                local_reading=reading,
                intent_card=agency.intent_card(),
                memory_card=agency.memory_card(),
                cadence_seconds=self._interval,
            )
            raw = await self._call_model(service, prompt)
            if raw is None:
                with self._lock:
                    self._last_error = "视觉模型暂时不可用，只保留了本地线索"
                return None
            text, model_name = raw
            parsed = parse_interpretation(text)
            if parsed is None:
                with self._lock:
                    self._last_error = "视觉模型没有给出可用的判断"
                return None
            # Name the mind that answered, so the panel can show which one it was.
            with self._lock:
                self._last_interpreter = model_name
            parsed["_interpreter"] = model_name
            return parsed
        except Exception as exc:  # noqa: BLE001 - interpretation is best effort
            logger.info("[VisionAgent] 解读失败: %s", exc)
            with self._lock:
                self._last_error = str(exc)[:200]
            return None

    @staticmethod
    async def _call_model(service, prompt: str) -> tuple[str, str] | None:
        """Ask Miya's own chat model to interpret the moment.

        The daemon owns the conversational model, so it injects its client here
        via :func:`set_chat_client`. Reusing it means Miya reasons with the same
        mind she talks with, instead of a separate vision endpoint that may have
        no balance at all.

        Returns ``(text, model_name)`` so the panel can name the mind that
        answered.
        """
        client = get_chat_client()
        if client is not None:
            try:
                from core.ai_client import AIMessage

                # A deadline, because this call has no other one. A request that
                # never answers used to hold the whole round open - a 602-second
                # interpret is in the logs - and the round is what feeds her
                # presence, her activity and her memory. Losing one interpretation
                # is survivable; losing the loop is not.
                response = await asyncio.wait_for(
                    client.chat(
                        messages=[
                            AIMessage(role="system", content=INTERPRETER_SYSTEM_PROMPT),
                            AIMessage(role="user", content=prompt),
                        ],
                        tools=[],
                        tool_choice="none",
                    ),
                    timeout=MODEL_TIMEOUT_SECONDS,
                )
                text = getattr(response, "content", None) or str(response or "")
                if str(text).strip():
                    name = str(getattr(client, "model", "") or getattr(client, "model_name", "")
                               or type(client).__name__)
                    return str(text).strip(), name
                # An empty reply is a failure, not a success. Returning None
                # here without a reason is what made this fail silently before.
                logger.info("[VisionAgent] 对话模型返回了空内容，尝试视觉模型")
            except asyncio.TimeoutError:
                logger.info("[VisionAgent] 对话模型 %.0f 秒没有回答，这一轮不解读",
                            MODEL_TIMEOUT_SECONDS)
            except Exception as exc:  # noqa: BLE001 - try the vision route next
                logger.info("[VisionAgent] 对话模型解读失败，尝试视觉模型: %s", exc)
        return await VisionAgent._call_vision_model(service, prompt)

    @staticmethod
    async def _call_vision_model(service, prompt: str) -> tuple[str, str] | None:
        """Fallback interpreter: the configured multimodal endpoints, in order."""
        try:
            candidates = service._vision_candidates()  # noqa: SLF001
        except Exception as exc:  # noqa: BLE001
            logger.info("[VisionAgent] 没有可用的解读模型: %s", exc)
            return None
        import httpx

        async with httpx.AsyncClient(timeout=45.0) as client:
            for key, api_key, base_url, model_id in candidates:
                try:
                    response = await client.post(
                        f"{base_url.rstrip('/')}/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json={
                            "model": model_id,
                            "messages": [
                                {"role": "system", "content": INTERPRETER_SYSTEM_PROMPT},
                                {"role": "user", "content": prompt},
                            ],
                            "max_tokens": 400,
                            "temperature": 0.6,
                        },
                    )
                except Exception as exc:  # noqa: BLE001 - rotate to the next provider
                    logger.info("[VisionAgent] 解读模型 %s 请求失败: %s", key, exc)
                    continue
                if response.status_code != 200:
                    logger.info("[VisionAgent] 解读模型 %s 返回 %s", key, response.status_code)
                    continue
                content = (response.json().get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
                if content:
                    return content, f"{key} ({model_id})"
                logger.info("[VisionAgent] 解读模型 %s 返回空内容", key)
        return None

    # -- what she wants to say --------------------------------------------

    def _queue_message(self, impression: Impression) -> None:
        """Queue one thing Miya wants to say, keeping the queue worth reading.

        Watching all evening produced a queue of three near-identical "I can see
        you now" lines, and the oldest had already gone stale by the time anyone
        could read it. A monologue of near-duplicates is worse than silence, so
        the queue is deduplicated, capped, and expired entries are dropped on
        the way in rather than at delivery time.
        """
        message = str(impression.say or "").strip()
        if not message:
            return
        with self._lock:
            self._pending = [
                item for item in self._pending
                if (impression.at - float(item.get("at") or 0)) <= QUEUE_MAX_AGE_SECONDS
            ]
            normalized = _normalize_message(message)
            for item in self._pending:
                if _normalize_message(str(item.get("message") or "")) == normalized:
                    # Same thing said again: refresh it instead of repeating it.
                    item["at"] = impression.at
                    item["summary"] = impression.summary
                    return
            self._pending.append({
                "at": impression.at,
                "message": message,
                "summary": impression.summary,
                "model": impression.model,
            })
            if len(self._pending) > QUEUE_MAX_MESSAGES:
                self._pending = self._pending[-QUEUE_MAX_MESSAGES:]

    def take_message(self) -> dict[str, Any] | None:
        """Collect the oldest thing Miya decided was worth saying, once."""
        with self._lock:
            self._expire_pending_locked(time.time())
            if not self._pending:
                return None
            return self._pending.pop(0)

    def peek_messages(self) -> list[dict[str, Any]]:
        with self._lock:
            self._expire_pending_locked(time.time())
            return list(self._pending)

    def _expire_pending_locked(self, now: float) -> None:
        """Drop anything too old to still be true. Caller holds the lock."""
        self._pending = [
            item for item in self._pending
            if (now - float(item.get("at") or 0)) <= QUEUE_MAX_AGE_SECONDS
        ]

    def next_message(self, *, consume: bool = False) -> dict[str, Any] | None:
        """Read the oldest pending message, optionally consuming it.

        The desktop reads this so Jia can see what Miya wants to say even when
        no chat platform is connected - otherwise she watches all evening and
        never gets to speak.
        """
        with self._lock:
            self._expire_pending_locked(time.time())
            if not self._pending:
                return None
            if not consume:
                return dict(self._pending[0])
            return self._pending.pop(0)

    def clear_messages(self) -> int:
        """Drop every queued message; returns how many were dropped."""
        with self._lock:
            count = len(self._pending)
            self._pending = []
            return count


_agent = VisionAgent()
_chat_client: Any = None
_chat_client_lock = threading.Lock()
_seed_lock = threading.Lock()


def get_vision_agent() -> VisionAgent:
    return _agent


# --- boot behaviour --------------------------------------------------------

# Jia asked Miya to watch from boot rather than wait to be told.  That is still
# gated: the autonomous flag in the camera control state must be on, and these
# values are configurable so the behaviour is his to change, not the code's.
DEFAULT_AUTOSTART = True
DEFAULT_SEED_INTENTS = [
    "想留意佳在不在电脑前，离开和回来都记一下",
    "想知道佳大多在做什么，是工作、看视频还是玩游戏",
    "留意佳有没有太久没休息",
]
# Give the desktop preview time to claim the camera before competing for it.
DEFAULT_AUTOSTART_DELAY_SECONDS = 20.0


def _agency_config() -> dict[str, Any]:
    """Read her watching preferences from config, tolerating a missing file."""
    try:
        from config.config_utils import get_qq_config

        section = get_qq_config("tools", "qq_image_analyzer", "camera_agency", default=None)
        return section if isinstance(section, dict) else {}
    except Exception:
        return {}


def seed_intents_from_config(*, force: bool = False) -> list[dict[str, Any]]:
    """Give Miya a starting set of intentions, once.

    Her own intents are never overwritten: this only runs when she has none, so
    a preference she changed by hand survives a restart.
    """
    with _seed_lock:
        agency = get_vision_agency()
        if agency.intents() and not force:
            return []
        config = _agency_config()
        raw = config.get("seed_intents")
        intents = [str(item) for item in raw] if isinstance(raw, list) and raw else list(DEFAULT_SEED_INTENTS)
        captured: list[dict[str, Any]] = []
        for text in intents:
            intent = agency.add_intent(text.strip(), speak=True, source="config")
            if intent is not None:
                captured.append(intent.to_dict())
        if captured:
            logger.info("[VisionAgent] 已为弥娅写入 %d 条初始观察意图", len(captured))
        return captured


def should_autostart() -> tuple[bool, str]:
    """Decide whether Miya may start watching on boot, and say why not."""
    config = _agency_config()
    if not bool(config.get("autostart", DEFAULT_AUTOSTART)):
        return False, "配置未开启开机自启"
    try:
        from core.camera_control import read_state

        state = read_state()
    except Exception as exc:  # noqa: BLE001
        return False, f"读取摄像头控制状态失败: {exc}"
    if state.get("mode") == "off":
        return False, "摄像头已被关闭命令停止"
    if not state.get("autonomous"):
        return False, "弥娅自主观察尚未开启"
    return True, ""


def configured_start_kwargs() -> dict[str, Any]:
    """The pacing and privacy settings from ``camera_agency``, as ``start()`` kwargs.

    Only the boot-time path used to read these, so starting her watching by hand
    dropped every one of them and fell back to the code defaults: a 30-second
    cadence, adaptive pacing on, and the thumbnail switch ignored. A setting
    belongs to the setting, not to whichever route happens to start her.
    """
    config = _agency_config()
    try:
        interval = float(config.get("interval_seconds", DEFAULT_INTERVAL_SECONDS))
    except (TypeError, ValueError):
        interval = DEFAULT_INTERVAL_SECONDS
    return {
        "interval_seconds": interval,
        "mode": str(config.get("mode") or "auto"),
        "adaptive": config.get("adaptive"),
        "slow_interval": config.get("slow_interval_seconds"),
        "slow_after": config.get("slow_after_unchanged"),
        "thumbnails": config.get("thumbnails"),
    }


async def autostart_after_delay(*, delay_seconds: float | None = None) -> dict[str, Any]:
    """Start her watching loop after boot settles, if she is allowed to."""
    config = _agency_config()
    if delay_seconds is None:
        try:
            delay_seconds = float(config.get("autostart_delay_seconds", DEFAULT_AUTOSTART_DELAY_SECONDS))
        except (TypeError, ValueError):
            delay_seconds = DEFAULT_AUTOSTART_DELAY_SECONDS
    # Validate before sleeping so a disabled setup logs immediately.
    allowed, reason = should_autostart()
    if not allowed:
        logger.info("[VisionAgent] 开机自启跳过：%s", reason)
        return {"started": False, "reason": reason}
    if delay_seconds > 0:
        await asyncio.sleep(delay_seconds)
    # Re-check after the delay: the user may have turned it off meanwhile.
    allowed, reason = should_autostart()
    if not allowed:
        logger.info("[VisionAgent] 开机自启在等待后放弃：%s", reason)
        return {"started": False, "reason": reason}
    agent = get_vision_agent()
    if agent.running:
        return {"started": True, "reason": "已在运行", "state": agent.state()}
    seed_intents_from_config()
    state = agent.start(autostart=True, **configured_start_kwargs())
    logger.info("[VisionAgent] 弥娅已按开机设置开始观察（每 %.0f 秒）",
                state.get("interval_seconds", configured_start_kwargs()["interval_seconds"]))
    return {"started": bool(state.get("running")), "reason": "", "state": state}


def set_chat_client(client: Any) -> None:
    """Let the daemon lend Miya her own conversational model.

    Without this the interpreter falls back to the multimodal endpoint, which is
    a different (often quota-limited) provider than the mind she talks with.
    """
    global _chat_client
    with _chat_client_lock:
        _chat_client = client
    logger.info("[VisionAgent] 已接入弥娅的对话模型作为解读器: %s", type(client).__name__ if client else "无")


def get_chat_client() -> Any:
    with _chat_client_lock:
        return _chat_client
