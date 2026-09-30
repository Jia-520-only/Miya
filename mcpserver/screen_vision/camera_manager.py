"""Automatic multi-camera discovery and fusion for Miya Vision.

Jia asked for one thing plainly: do not make me pick a camera, just use as many
as you can see.  A phone used as a webcam also drops to black frames whenever
its screen sleeps, so "which cameras work" is not a fact to establish once - it
is a state to keep re-checking.

This module therefore does three jobs:

1. keep a live inventory of every OpenCV camera index that can actually deliver
   pixels, re-probing the ones that are currently dark;
2. expose that inventory to the backend capture paths and the desktop UI;
3. fuse per-camera observations into one picture of what Jia is doing, without
   ever claiming more than the pixels support.
"""

from __future__ import annotations

import logging
import os
import hashlib
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from . import camera_devices
from .camera_devices import DARK_FRAME_MEAN, MAX_INDEX, preferred_camera_index

_INITIAL_DEVICE_DISCOVERY = camera_devices.list_camera_devices
# Retained as a compatibility patch point for callers that replaced this name.
list_camera_devices = _INITIAL_DEVICE_DISCOVERY

# Compatibility seam for integrations that historically replaced
# ``camera_manager.list_camera_devices`` directly. New code resolves the module
# attribute so replacing ``camera_devices.list_camera_devices`` works too.

logger = logging.getLogger("screen_vision.camera_manager")

# A dark device is usually a sleeping phone screen, not a broken camera, so it
# gets re-checked periodically instead of being dropped for the session.
RESCAN_INTERVAL_SECONDS = float(os.getenv("MIYA_CAMERA_RESCAN_SECONDS", "45"))
# Do not let a hard failure hammer the device: back off per index.
DARK_RETRY_SECONDS = float(os.getenv("MIYA_CAMERA_DARK_RETRY_SECONDS", "20"))
FAILURE_BACKOFF_SECONDS = float(os.getenv("MIYA_CAMERA_FAILURE_BACKOFF_SECONDS", "8"))
MAX_FAILURE_BACKOFF_SECONDS = float(os.getenv("MIYA_CAMERA_MAX_FAILURE_BACKOFF_SECONDS", "120"))
# A frame the desktop sent us counts as "that camera is alive" for this long.
BROWSER_FRAME_FRESH_SECONDS = float(os.getenv("MIYA_CAMERA_BROWSER_FRESH", "30"))


@dataclass
class CameraSource:
    """One physical camera index and what it last showed us."""

    index: int
    usable: bool = False
    # Whether the device could be opened at all. A camera that opens and returns
    # nothing is a different problem from one DirectShow refuses to connect, and
    # the two need opposite next steps - so they are never merged into one
    # "not usable" bucket.
    openable: bool = True
    luminance: float | None = None
    width: int = 0
    height: int = 0
    backend: str = ""
    # The DirectShow friendly name ("4K USB Camera", "Xiaomi 15 Pro (Windows
    # 虚拟摄像头)"). Empty when ffmpeg is unavailable; the index is still the key.
    name: str = ""
    reason: str = ""
    # "backend" means we opened the device ourselves; "browser" means the desktop
    # preview is holding it and only the browser can read frames from it.
    owner: str = "backend"
    last_checked: float = 0.0
    last_usable: float = 0.0
    # What this camera last actually showed. "Online" and "seeing something worth
    # looking at" are different questions: the laptop camera aimed at a wall and
    # the one looking at Jia are both perfectly usable, and the only thing that
    # separates them is what came back from the model. Without this the inventory
    # could say a camera works but never whether it was worth watching.
    last_reading_at: float = 0.0
    last_reading_text: str = ""
    last_faces: int = 0
    last_action: str = ""
    failure_count: int = 0
    last_failure_at: float = 0.0
    next_retry_at: float = 0.0
    checked: bool = False

    def label(self) -> str:
        """How this camera should be named in logs and in the panel."""
        return self.name or f"索引 {self.index}"

    def to_dict(self) -> dict[str, Any]:
        now = time.time()
        if self.usable:
            health = "online"
        elif not self.checked:
            health = "unknown"
        elif self.openable:
            health = "no_frame"
        else:
            health = "unopenable"
        normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", self.name.lower())
        stable_name = normalized or f"index-{self.index}"
        # Friendly names are stable across index shifts. Duplicate friendly names
        # are intentionally not disambiguated here: the frontend must refuse an
        # ambiguous match instead of guessing which physical camera it means.
        source_key = hashlib.sha256(stable_name.encode("utf-8")).hexdigest()[:16]
        return {
            "index": self.index,
            "source_id": f"dshow:{source_key}",
            "health": health,
            "checked": self.checked,
            "name": self.name,
            "label": self.label(),
            "usable": self.usable,
            "openable": self.openable,
            "luminance": None if self.luminance is None else round(float(self.luminance), 2),
            "width": self.width,
            "height": self.height,
            "backend": self.backend,
            "reason": self.reason,
            "owner": self.owner,
            "last_checked": round(self.last_checked, 1),
            "last_usable": round(self.last_usable, 1),
            "last_reading_at": round(self.last_reading_at, 1),
            "last_reading_text": self.last_reading_text,
            "last_faces": self.last_faces,
            "last_action": self.last_action,
            "failure_count": self.failure_count,
            "last_failure_at": round(self.last_failure_at, 1),
            "next_retry_at": round(self.next_retry_at, 1),
            "checked_age_seconds": round(max(0.0, now - self.last_checked), 1) if self.last_checked else None,
            "reading_age_seconds": round(max(0.0, now - self.last_reading_at), 1) if self.last_reading_at else None,
            "retry_in_seconds": round(max(0.0, self.next_retry_at - now), 1) if self.next_retry_at else 0.0,
            # True when this camera has ever actually recognised a person. It is
            # the answer to "is this one pointed at Jia", which the device list
            # alone cannot give.
            "sees_people": self.last_faces > 0,
        }


class CameraManager:
    """Thread-safe, self-refreshing inventory of usable camera indices."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sources: dict[int, CameraSource] = {}
        self._last_scan = 0.0
        self._scanning = False
        self._browser_frame: dict[str, Any] | None = None

    # -- inventory ---------------------------------------------------------

    def scan(self, *, force: bool = False) -> dict[str, CameraSource]:
        """Refresh the inventory, honouring the rescan interval unless forced."""
        with self._lock:
            now = time.time()
            if not force and (now - self._last_scan) < RESCAN_INTERVAL_SECONDS:
                return dict(self._sources)
            if self._scanning:
                return dict(self._sources)
            self._scanning = True
        try:
            discover = list_camera_devices
            if discover is _INITIAL_DEVICE_DISCOVERY:
                discover = camera_devices.list_camera_devices
            report = discover(probe=True)
            with self._lock:
                previous = dict(self._sources)
            found: dict[int, CameraSource] = {}
            for item in report.get("devices") or []:
                try:
                    index = int(item.get("index"))
                except (TypeError, ValueError):
                    continue
                source = CameraSource(
                    index=index,
                    usable=bool(item.get("usable")),
                    openable=bool(item.get("available", True)),
                    luminance=item.get("luminance"),
                    width=int(item.get("width") or 0),
                    height=int(item.get("height") or 0),
                    backend=str(item.get("backend") or ""),
                    name=str(item.get("name") or ""),
                    reason=str(item.get("reason") or ""),
                    last_checked=time.time(),
                    last_usable=time.time() if item.get("usable") else 0.0,
                    checked=item.get("available") is not None,
                )
                # What a camera last showed outlives the scan that re-lists it.
                # Rebuilding the inventory from scratch wiped this every 45
                # seconds, which would have left "has this one ever seen Jia"
                # permanently blank.
                old = previous.get(index)
                if old is not None:
                    source.last_reading_at = old.last_reading_at
                    source.last_reading_text = old.last_reading_text
                    source.last_faces = old.last_faces
                    source.last_action = old.last_action
                    source.failure_count = old.failure_count
                    source.last_failure_at = old.last_failure_at
                    source.next_retry_at = old.next_retry_at
                found[index] = source
            with self._lock:
                browser = dict(self._browser_frame) if self._browser_frame else None
                self._sources = found
                self._last_scan = time.time()
            # The desktop preview holds one device, so the probe above cannot open
            # it and would report it as broken. If we have a fresh frame from the
            # browser, that camera is working - just not ours to open.
            if browser and isinstance(browser.get("index"), int):
                age = time.time() - float(browser.get("at") or 0)
                if age <= BROWSER_FRAME_FRESH_SECONDS:
                    with self._lock:
                        owner = self._sources.get(int(browser["index"]))
                        if owner is None:
                            owner = CameraSource(index=int(browser["index"]))
                            self._sources[int(browser["index"])] = owner
                        owner.usable = True
                        owner.owner = "browser"
                        owner.reason = ""
                        owner.last_usable = time.time()
            logger.info(
                "[CameraManager] 摄像头扫描完成: %s",
                "；".join(
                    f"{found[index].label()}={found[index].reason or '出画面'}"
                    if not found[index].usable else f"{found[index].label()}=出画面"
                    for index in sorted(found)
                ) or "没有发现摄像头",
            )
        except Exception:
            logger.warning("[CameraManager] 摄像头扫描失败", exc_info=True)
        finally:
            with self._lock:
                self._scanning = False
        return self.sources()

    def sources(self) -> dict[int, CameraSource]:
        with self._lock:
            return dict(self._sources)

    def usable_indices(self) -> list[int]:
        """Every index currently delivering pixels, lowest index first."""
        with self._lock:
            return sorted(index for index, source in self._sources.items() if source.usable)

    def all_indices(self) -> list[int]:
        with self._lock:
            return sorted(self._sources)

    def retry_due_indices(self, *, now: float | None = None) -> list[int]:
        """Failed devices whose backoff has elapsed and are ready to retry."""
        current = time.time() if now is None else float(now)
        with self._lock:
            return sorted(
                index for index, source in self._sources.items()
                if not source.usable
                and source.failure_count > 0
                and source.next_retry_at <= current
            )

    def sleepers(self) -> list[int]:
        """Indices that opened but delivered nothing - likely a sleeping phone."""
        with self._lock:
            return sorted(index for index, source in self._sources.items()
                          if source.checked and not source.usable and source.openable)

    def unopenable(self) -> list[int]:
        """Indices of devices DirectShow exists but refuses to open."""
        with self._lock:
            return sorted(index for index, source in self._sources.items()
                          if source.checked and not source.openable)

    def label_for(self, index: Any) -> str:
        """The friendly name of one camera, falling back to its index."""
        with self._lock:
            source = self._sources.get(int(index)) if isinstance(index, (int, float)) else None
        return source.label() if source is not None else f"索引 {index}"

    def name_for(self, index: Any) -> str:
        """The friendly name, or an empty string when it is not known.

        Callers that build an explanation use this rather than :meth:`label_for`,
        because "索引 1" is not a name and must not be treated as one.
        """
        with self._lock:
            source = self._sources.get(int(index)) if isinstance(index, (int, float)) else None
        return source.name if source is not None else ""

    def note_result(
        self,
        index: int,
        *,
        luminance: float | None,
        usable: bool,
        openable: bool | None = None,
        reason: str | None = None,
    ) -> None:
        """Let a real capture update the inventory without a full probe.

        ``openable`` and ``reason`` are optional so the callers that only know
        "did it deliver pixels" stay as they are, while the observation sweep -
        which is now the thing that refreshes the inventory - can report the same
        detail a probe would have.
        """
        with self._lock:
            source = self._sources.get(int(index))
            if source is None:
                source = CameraSource(index=int(index), last_checked=time.time())
                self._sources[int(index)] = source
            source.luminance = luminance
            source.checked = True
            source.usable = bool(usable)
            source.last_checked = time.time()
            if openable is not None:
                source.openable = bool(openable)
            if reason is not None:
                source.reason = str(reason)[:400]
            if usable:
                source.last_usable = time.time()
                source.failure_count = 0
                source.last_failure_at = 0.0
                source.next_retry_at = 0.0
            else:
                source.failure_count += 1
                source.last_failure_at = source.last_checked
                delay = min(
                    MAX_FAILURE_BACKOFF_SECONDS,
                    FAILURE_BACKOFF_SECONDS * (2 ** max(0, source.failure_count - 1)),
                )
                source.next_retry_at = source.last_checked + delay

    def refresh_names(self) -> list[int]:
        """Re-read the device names and return every index worth trying.

        This is the inventory refresh the observation sweep performs *instead of*
        a full probe. The sweep opens each camera itself and reports what it found
        through :meth:`note_result`, so probing first opened every device twice -
        measured at 6.6 seconds of pure duplication per sweep on this machine.

        ``_last_scan`` is moved forward as well, because the panel's polling calls
        the throttled :meth:`scan` and would otherwise repeat the probe it just
        replaced.
        """
        from .camera_names import describe as describe_names, dshow_device_names

        names = dshow_device_names()
        names_available = bool(describe_names().get("enumerated"))
        now = time.time()
        with self._lock:
            # A successful DirectShow enumeration is authoritative. Remove
            # unplugged indices now so the autonomous loop cannot keep trying
            # stale devices. If enumeration is unavailable, retain the last
            # known inventory and let capture failures update its health.
            if names_available:
                present = set(range(len(names)))
                browser = self._browser_frame
                if browser and isinstance(browser.get("index"), int):
                    if now - float(browser.get("at") or 0) <= BROWSER_FRAME_FRESH_SECONDS:
                        present.add(int(browser["index"]))
                self._sources = {
                    index: source for index, source in self._sources.items()
                    if index in present
                }
            for index, name in enumerate(names):
                source = self._sources.get(index)
                if source is None:
                    source = CameraSource(index=index, last_checked=now)
                    self._sources[index] = source
                source.name = name
            # When names cannot be read, do not invent a disappearance. The
            # inventory stays available but its labels remain index based.
            self._last_scan = now
            return sorted(self._sources)

    def note_reading(
        self,
        index: int,
        *,
        faces: int = 0,
        action: str = "",
        text: str = "",
        at: float | None = None,
    ) -> None:
        """Remember what one camera actually saw, not just that it answered.

        A camera that streams a wall and a camera looking at Jia are both
        "usable"; the difference is the only thing worth acting on, and it is not
        visible in a luminance reading. This is what lets the panel - and Miya -
        answer "which of these is pointed at him".
        """
        with self._lock:
            if int(index) < 0:
                # A negative index means "the browser's camera, which has no
                # OpenCV index of its own". Recording it as a source would put a
                # phantom entry in the inventory that every later scan tries to
                # open.
                return
            source = self._sources.get(int(index))
            if source is None:
                source = CameraSource(index=int(index))
                self._sources[int(index)] = source
            source.last_reading_at = time.time() if at is None else float(at)
            source.last_faces = int(faces or 0)
            source.last_action = str(action or "")
            source.last_reading_text = str(text or "")[:200]

    def known_indices(self) -> list[int]:
        """Candidate indices, including ones not seen in the last scan."""
        with self._lock:
            known = set(self._sources)
        if not known:
            known = set(range(MAX_INDEX))
        else:
            known.update(range(min(MAX_INDEX, max(known) + 2)))
        return sorted(known)

    def mark_dark(self, index: int, reason: str = "") -> None:
        with self._lock:
            source = self._sources.get(int(index))
            if source is not None:
                source.usable = False
                if reason:
                    source.reason = reason

    # -- browser-owned devices --------------------------------------------

    def remember_browser_frame(
        self,
        *,
        index: int | None = None,
        data_url: str = "",
        at: float | None = None,
    ) -> None:
        """Keep the most recent frame the desktop's browser sent us.

        A camera can only be opened by one process at a time. When the desktop UI
        has a live preview it *owns* that device, so a backend ``VideoCapture`` on
        the same index fails - which previously looked like "the camera is
        broken". Remembering the browser's frame lets the backend see through the
        browser's eyes instead of fighting it for the hardware.
        """
        if not data_url:
            return
        with self._lock:
            self._browser_frame = {
                "data_url": data_url,
                "index": None if index is None else int(index),
                "at": time.time() if at is None else float(at),
            }
            if index is not None and int(index) not in self._sources:
                self._sources[int(index)] = CameraSource(
                    index=int(index), usable=True, owner="browser",
                    last_checked=time.time(), last_usable=time.time(), checked=True,
                )

    def browser_frame(self, *, max_age_seconds: float = 30.0) -> dict[str, Any] | None:
        with self._lock:
            frame = dict(self._browser_frame) if self._browser_frame else None
        if not frame:
            return None
        if (time.time() - float(frame.get("at") or 0)) > max_age_seconds:
            return None
        return frame

    def describe(self) -> dict[str, Any]:
        with self._lock:
            sources = dict(self._sources)
        usable = [item for item in sources.values() if item.usable]
        sleepers = [item for item in sources.values() if item.checked and not item.usable and item.openable]
        blocked = [item for item in sources.values() if item.checked and not item.openable]
        unknown = [item for item in sources.values() if not item.checked]
        return {
            "count": len(sources),
            "usable_count": len(usable),
            "unknown_count": len(unknown),
            "unopenable_count": len(blocked),
            "usable_indices": sorted(item.index for item in usable),
            "sleeping_indices": sorted(item.index for item in sleepers),
            "unopenable_indices": sorted(item.index for item in blocked),
            "unknown_indices": sorted(item.index for item in unknown),
            "devices": [sources[index].to_dict() for index in sorted(sources)],
            # Names are handed out separately as well, so a consumer that only
            # has an index (the frame pool, the panel) can still label it.
            "names": {str(index): sources[index].name for index in sorted(sources) if sources[index].name},
            "last_scan": round(self._last_scan, 1),
            "message": self._message(usable, sleepers, blocked, unknown),
        }

    @staticmethod
    def _message(
        usable: list[CameraSource],
        sleepers: list[CameraSource],
        blocked: list[CameraSource] | None = None,
        unknown: list[CameraSource] | None = None,
    ) -> str:
        """One honest sentence about the whole inventory.

        "No picture" and "will not open" are kept apart on purpose: the first
        asks the user to start streaming, the second asks them to check USB or
        which program is holding the device. Folding them together is what made
        every camera problem look identical.
        """
        blocked = blocked or []
        unknown = unknown or []
        if not usable and not sleepers and not blocked:
            return "还没有发现任何摄像头。"

        parts: list[str] = []
        if usable:
            parts.append("正在使用 " + "、".join(item.label() for item in usable))
        else:
            parts.append("现在没有摄像头在出画面")
        for item in sleepers:
            hint = (
                "，多半是手机端没有在推流"
                if _looks_virtual(item.name)
                else "（手机息屏、或者没有程序在向它推流时会出现这种情况，亮屏后会自动接上）"
            )
            parts.append(f"{item.label()} 打开了但没有画面{hint}")
        for item in blocked:
            parts.append(f"{item.label()} 系统里有，但打不开")
        if unknown:
            parts.append(f"{len(unknown)} 台已发现、等待首次探测")
        return "；".join(parts) + "。"


def _looks_virtual(name: str) -> bool:
    from .camera_names import is_virtual_name

    return is_virtual_name(name)


_manager = CameraManager()


def get_camera_manager() -> CameraManager:
    return _manager


def resolve_capture_index(call: dict[str, Any] | None = None) -> int:
    """Pick the camera a one-shot terminal capture should use.

    An explicit index always wins. Otherwise the browser's camera is preferred
    when we have a fresh frame from it: the desktop preview holds that device,
    so a backend ``VideoCapture`` on it would either fail or steal it from the
    preview - which is what made switching cameras feel unstable.
    """
    call = call or {}
    for key in ("camera_index", "index", "device_index"):
        value = call.get(key)
        if value is None or value == "":
            continue
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            continue
    manager = get_camera_manager()
    manager.scan()
    browser = manager.browser_frame()
    if browser and isinstance(browser.get("index"), int):
        return int(browser["index"])
    usable = manager.usable_indices()
    if usable:
        return usable[0]
    return preferred_camera_index(call)


def fuse_observations(observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge per-camera observations into one picture of what Jia is doing.

    Each entry is ``{"index": int, "result": analyze_local_frame(...)}``.
    The fused result never invents a conclusion: if no camera produced a usable
    reading, it says so in plain language instead of reporting a fake posture.
    """
    usable = [item for item in observations if isinstance(item, dict) and isinstance(item.get("result"), dict)]
    if not usable:
        return {
            "status": "unknown",
            "sources_used": [],
            "faces": 0,
            "message": "现在没有能看清你的摄像头。",
        }

    faces_total = 0
    best_face: dict[str, Any] | None = None
    poses: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    emotions: list[dict[str, Any]] = []
    identities: list[dict[str, Any]] = []
    hand_readings: list[dict[str, Any]] = []
    sources: list[int] = []
    blank_indices: list[int] = []
    delivered_indices: list[int] = []

    for item in usable:
        index = item.get("index")
        result = item["result"]
        # A device that failed to open also reports "error"; only a result that
        # actually decoded pixels may be called a black frame.
        if result.get("vision_analyzed"):
            if isinstance(index, int):
                delivered_indices.append(index)
            if result.get("blank_frame") and isinstance(index, int):
                blank_indices.append(index)
        if result.get("status") not in {"success", "partial"}:
            continue
        sources.append(int(index) if isinstance(index, int) else -1)
        faces_total += int(result.get("faces") or 0)
        for observation in result.get("observations") or []:
            if not isinstance(observation, dict):
                continue
            signals = observation.get("face_signals")
            if isinstance(signals, dict):
                if best_face is None or float(signals.get("largest_ratio") or 0) > float(best_face.get("largest_ratio") or 0):
                    best_face = dict(signals)
                    best_face["from_index"] = index
            quality = observation.get("pose_quality")
            if isinstance(observation.get("pose"), dict) and isinstance(quality, dict) and quality.get("usable"):
                poses.append({"index": index, "pose": observation["pose"], "quality": quality})
            action = observation.get("action")
            if isinstance(action, dict) and action.get("kind") and action["kind"] != "unknown":
                actions.append({**action, "from_index": index})
            emotion = observation.get("emotion")
            if isinstance(emotion, dict):
                emotions.append({**emotion, "from_index": index})
            identity = observation.get("identity")
            if isinstance(identity, dict) and identity.get("name") not in {None, "", "未知", "未登记"}:
                identities.append({**identity, "from_index": index})
            # Hand readings are per-frame facts about what is in his hands, so
            # they are carried through the fusion rather than averaged away.
            hands = observation.get("hands")
            if isinstance(hands, dict) and hands.get("hands"):
                hand_readings.append({
                    "index": index,
                    "hands": list(hands.get("hands") or []),
                    "text": str(observation.get("hand_text") or ""),
                })

    # A confident action from any camera beats an unknown one from another.
    best_action = max(actions, key=lambda item: float(item.get("confidence") or 0), default=None)
    best_pose = poses[0] if poses else None
    fused: dict[str, Any] = {
        "status": "success" if (best_face or best_pose or best_action) else "partial",
        "sources_used": sorted({index for index in sources if index >= 0}),
        "camera_count": len(sources),
        "faces": faces_total,
        "face_signals": best_face,
        "pose_quality": best_pose["quality"] if best_pose else None,
        "action": best_action,
        "action_candidates": actions,
        "emotion": max(emotions, key=lambda item: float(item.get("confidence") or 0), default=None),
        "identity": identities[0] if identities else None,
        # Prefer a camera that actually saw a hand.
        "hands": ({"hands": hand_readings[0]["hands"], "available": True}
                  if hand_readings else None),
        "hand_text": hand_readings[0]["text"] if hand_readings else "",
        "blank_indices": sorted(set(blank_indices)),
        # Every camera that delivered pixels delivered nothing but black; this
        # is a device problem, not an empty room.
        "blank_frame": bool(delivered_indices and len(blank_indices) == len(delivered_indices)),
        "observations": [
            {"source_index": item.get("index"), "result": item.get("result")}
            for item in usable
        ],
    }
    return fused


def narrative_for_fused(fused: dict[str, Any], *, activity: str = "", duration: float | None = None) -> str:
    """Turn a fused reading into one natural sentence, without numeric jargon."""
    from .activity import INCONCLUSIVE_KINDS

    if fused.get("status") == "unknown" or not fused.get("sources_used"):
        return "现在没有能看清你的摄像头。"

    parts: list[str] = []
    identity = fused.get("identity") or {}
    if identity.get("name"):
        parts.append(f"看到{identity['name']}")
    elif fused.get("faces"):
        parts.append("看到你在画面里")
    elif fused.get("pose_quality"):
        parts.append("看到你的身影，但没看清脸")

    camera_count = int(fused.get("camera_count") or 0)
    if camera_count > 1:
        parts.append(f"（{camera_count} 个摄像头一起看）")

    emotion = fused.get("emotion") or {}
    if emotion.get("label") and float(emotion.get("confidence") or 0) >= 0.5 and emotion["label"] != "中性":
        parts.append(f"表情看着有点{emotion['label']}")

    # Measured face geometry is a fact, not a guess, so it belongs in the
    # sentence whenever it was available.
    expression_text = str(fused.get("expression_text") or "")
    if expression_text:
        parts.append(expression_text)

    # Only a reading that actually reached a conclusion may be narrated; a
    # low-confidence result must not be read out as if it were an activity.
    readable_activity = activity if activity and activity not in INCONCLUSIVE_KINDS else ""
    if readable_activity:
        parts.append(f"像是在{readable_activity}")
        if duration and duration >= 60:
            parts.append(f"已经持续了约 {int(duration // 60)} 分钟")
    else:
        action = fused.get("action") or {}
        kind = str(action.get("kind") or "")
        if kind and kind not in INCONCLUSIVE_KINDS and action.get("label"):
            parts.append(str(action["label"]))
        elif fused.get("sources_used"):
            parts.append("这个角度还看不清你在做什么")

    body = "，".join(part for part in parts if part)
    return f"{body}。" if body else "弥娅看着你，但还说不清你在做什么。"
