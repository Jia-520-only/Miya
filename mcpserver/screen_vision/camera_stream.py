"""Camera frame sources, so several consumers can share one device.

Only one process can hold a camera at a time, but more than one thing needs
frames from it:

* Miya's own observation loop, which runs whether or not a window is open;
* a smooth preview in the desktop's browser, which needs real video;
* a low-rate preview of the *other* cameras, so the panel can show every angle.

The resolution is a small pool keyed by camera index. Each camera has exactly
one **owner**:

* ``browser`` - the desktop preview holds the device and pushes frames in. The
  backend must never open it, or it would steal it from the preview.
* ``backend`` - a persistent reader thread holds the device and keeps one frame
  ready. Opening once and keeping it is also what removes the multi-second
  device-warmup cost from every single observation.
* ``idle`` - nobody owns it yet; the first consumer decides.

Everything downstream asks the pool for "the latest frame of camera N" and does
not care where it came from.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("screen_vision.camera_stream")

# How stale a cached frame may be before it is not worth using.
FRAME_MAX_AGE_SECONDS = float(os.getenv("MIYA_CAMERA_FRAME_MAX_AGE", "20"))
# How long a *live* reader may go without publishing before its frame stops
# counting as current. A healthy reader publishes every ~50 ms, so this only
# fires once the device has stopped delivering - which is exactly when serving
# the last frame would have Miya re-interpret one frozen picture as the present.
READER_PUBLISH_GRACE_SECONDS = float(os.getenv("MIYA_CAMERA_PUBLISH_GRACE", "8"))
# A live sensor cannot repeat itself byte for byte; a stalled virtual camera or a
# phone whose stream died can, indefinitely. After this long of reading the same
# picture the device is not delivering, and holding it helps nobody.
FROZEN_AFTER_SECONDS = float(os.getenv("MIYA_CAMERA_FROZEN_SECONDS", "30"))
# A reader that has produced nothing for this long has lost the device.
READER_STALL_SECONDS = float(os.getenv("MIYA_CAMERA_STALL_SECONDS", "15"))
# Reader loop pacing: keep the newest frame fresh without spinning the CPU.
READER_SLEEP_SECONDS = float(os.getenv("MIYA_CAMERA_READER_SLEEP", "0.05"))
# A frame at least this old is re-read before being served to an inference call.
FRESH_FOR_INFERENCE_SECONDS = float(os.getenv("MIYA_CAMERA_FRESH_INFERENCE", "3.0"))
# Below this mean luminance the picture is black, which means the device is not
# really delivering - a sleeping phone, or another program holding it. Such a
# frame must never be treated as a usable observation.
BLANK_FRAME_MEAN = float(os.getenv("MIYA_CAMERA_BLANK_MEAN", "4.0"))
# Consecutive blank frames before the reader gives the device up so it can recover.
BLANK_STREAK_BEFORE_RELEASE = int(os.getenv("MIYA_CAMERA_BLANK_STREAK", "4"))
# How long a browser frame makes the desktop preview count as the device's owner.
#
# The preview shares a frame every 15s (cameraVision.ts FRAME_SHARE_INTERVAL_MS),
# while a frame only stays *fresh* for 30s. Gating ownership on freshness alone
# therefore announced "the browser is gone" every time two shares were missed -
# and the backend immediately opened a camera the browser was still holding. Both
# sides then read black, released, reopened, forever; that is the loop behind
# every "连续 4 次全黑，释放设备" in the log. Ownership is about who holds the
# hardware, not about how new our copy of its picture is, so it gets its own,
# much longer grace.
BROWSER_OWNERSHIP_GRACE_SECONDS = float(os.getenv("MIYA_CAMERA_BROWSER_GRACE", "90"))

OWNER_BROWSER = "browser"
OWNER_BACKEND = "backend"
OWNER_IDLE = "idle"


@dataclass
class FrameBuffer:
    """The newest frame for one camera index, plus who is feeding it."""

    index: int
    owner: str = OWNER_IDLE
    image_data: str = ""
    thumbnail: str = ""
    width: int = 0
    height: int = 0
    at: float = 0.0
    luminance: float | None = None
    error: str = ""
    reads: int = 0

    def age(self, *, now: float | None = None) -> float:
        if not self.at:
            return float("inf")
        return max(0.0, (time.time() if now is None else now) - self.at)

    def is_usable(self, *, max_age: float = FRAME_MAX_AGE_SECONDS) -> bool:
        return bool(self.image_data) and self.age() <= max_age

    @property
    def is_blank(self) -> bool:
        """A black picture means the device failed, not that nothing is there."""
        return self.luminance is not None and float(self.luminance) < BLANK_FRAME_MEAN

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "owner": self.owner,
            "width": self.width,
            "height": self.height,
            "age_seconds": None if not self.at else round(self.age(), 1),
            "luminance": None if self.luminance is None else round(float(self.luminance), 2),
            "has_frame": bool(self.image_data),
            "error": self.error,
        }


class _PersistentReader:
    """One camera kept open by a thread, always holding the newest frame."""

    def __init__(self, pool: CameraFramePool, index: int, width: int, height: int) -> None:
        self._pool = pool
        self._index = int(index)
        self._width = int(width)
        self._height = int(height)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        # Set once the reader has either produced a frame or given up, so callers
        # can wait instead of opening the same device behind its back.
        self.ready = threading.Event()
        self.opened = False

    def start(self) -> bool:
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name=f"Miya-Cam{self._index}")
        self._thread.start()
        return True

    def stop(self, *, timeout: float = 3.0) -> None:
        self._stop.set()
        self.ready.set()  # unblock anyone waiting on a reader that is going away
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(max(0.2, float(timeout)))

    def wait_ready(self, timeout: float = 4.0) -> bool:
        """Block until the reader has a frame, or until it has failed."""
        self.ready.wait(max(0.1, float(timeout)))
        return self.opened

    @property
    def alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        try:
            import cv2  # noqa: F401 - presence check only; opening happens below
        except ImportError:
            self._pool.note_error(self._index, "需要 OpenCV 才能常驻读帧")
            self.ready.set()
            return
        capture = None
        try:
            from .camera_capture import make_thumbnail, open_camera

            # Use the same backend probing as the one-shot path, so a phone camera
            # that opens on one backend and yields black frames on another is not
            # accepted as working.
            capture, backend = open_camera(
                self._index, width=self._width, height=self._height, warmup=10,
            )
            if capture is None:
                self._pool.note_error(self._index, f"无法得到画面：{backend}")
                logger.info("[CameraStream] 常驻读帧 #%s 打不开：%s", self._index, backend)
                return
            logger.info("[CameraStream] 常驻读帧 #%s 使用后端 %s", self._index, backend)
            self.opened = True
            self.ready.set()
            blank_streak = 0
            last_publish = time.monotonic()
            last_fingerprint = ""
            unchanged_since = 0.0
            while not self._stop.is_set():
                # A device that stops answering leaves this thread alive while it
                # publishes nothing, and a live thread used to be taken as proof
                # that its last frame was current. Give the device up so it can be
                # reopened cleanly instead of being held by a stuck reader.
                stalled = time.monotonic() - last_publish
                if stalled >= READER_STALL_SECONDS:
                    self._pool.note_error(
                        self._index,
                        f"读帧线程已经 {int(stalled)} 秒没有拿到画面，已释放设备等待重试",
                    )
                    logger.info("[CameraStream] 常驻读帧 #%s %s 秒没有拿到画面，释放设备",
                                self._index, int(stalled))
                    return
                ok, frame = capture.read()
                if not ok or frame is None or not getattr(frame, "size", 0):
                    time.sleep(READER_SLEEP_SECONDS)
                    continue
                luminance = self._pool._mean_luminance(frame)
                if luminance < BLANK_FRAME_MEAN:
                    blank_streak += 1
                    if blank_streak >= BLANK_STREAK_BEFORE_RELEASE:
                        # Holding a device that only yields blackness helps nobody:
                        # it starves any other program and cannot recover on its
                        # own. Give it up and let the device be reopened cleanly.
                        self._pool.note_error(self._index, "读帧线程只拿到全黑画面，已释放设备等待重试")
                        logger.info("[CameraStream] 常驻读帧 #%s 连续 %s 次全黑，释放设备",
                                    self._index, blank_streak)
                        return
                    time.sleep(READER_SLEEP_SECONDS)
                    continue
                blank_streak = 0
                # Frames are arriving, but are they *new*? A frozen stream passes
                # every other check - it is not black, it is not old, the reader is
                # alive - and that is how one picture ends up being interpreted as
                # the present over and over.
                fingerprint = _frame_fingerprint(frame)
                now_mono = time.monotonic()
                if fingerprint and fingerprint == last_fingerprint:
                    if not unchanged_since:
                        unchanged_since = now_mono
                    elif now_mono - unchanged_since >= FROZEN_AFTER_SECONDS:
                        self._pool.note_error(
                            self._index,
                            f"画面连续 {int(now_mono - unchanged_since)} 秒一模一样，"
                            "像是虚拟摄像头或手机推流卡住了，已释放设备等待重试",
                        )
                        logger.info("[CameraStream] 常驻读帧 #%s 画面 %s 秒没有变化，释放设备",
                                    self._index, int(now_mono - unchanged_since))
                        return
                else:
                    unchanged_since = 0.0
                last_fingerprint = fingerprint
                # Sample this frame's skeleton into the shared pose sequence. The
                # reader sees ~20 frames a second, while Miya's own observation
                # runs once every 30s: without this dense sampling the temporal
                # action reader never has the few seconds of history it needs, so
                # she could only ever report a static posture. Self rate-limited
                # and best-effort - it must never disturb the capture loop.
                try:
                    from .local_camera import observe_frame_pose

                    observe_frame_pose(frame, key=self._index)
                except Exception:  # noqa: BLE001
                    logger.debug("[CameraStream] 姿态采样失败", exc_info=True)
                self._pool.publish_backend_frame(
                    self._index, frame, width=frame.shape[1], height=frame.shape[0],
                    thumbnail=make_thumbnail(frame),
                )
                last_publish = now_mono
                time.sleep(READER_SLEEP_SECONDS)
        except Exception as exc:  # noqa: BLE001 - a reader must never take the process down
            logger.warning("[CameraStream] 常驻读帧 %s 异常: %s", self._index, exc)
            self._pool.note_error(self._index, str(exc))
        finally:
            # Releasing can itself throw when another process grabbed the device;
            # that must not escape and kill the thread noisily.
            self.ready.set()
            if capture is not None:
                _safe_release(capture)
            logger.info("[CameraStream] 常驻读帧 #%s 已释放设备", self._index)


def _safe_release(capture: Any) -> None:
    try:
        capture.release()
    except Exception:  # noqa: BLE001 - release failures are not actionable
        logger.debug("[CameraStream] 释放摄像头时出错", exc_info=True)


def _frame_fingerprint(frame: Any) -> str:
    """A cheap content fingerprint, so "the same picture again" is detectable.

    A physical sensor cannot repeat itself byte for byte - thermal noise alone
    changes the pixels - so an exact match on a subsample is a strong signal that
    no new picture arrived, while a genuinely live stream never collides.

    Only derived bytes are hashed; no frame is stored or sent anywhere.
    """
    try:
        import hashlib

        return hashlib.blake2b(frame[::16, ::16].tobytes(), digest_size=16).hexdigest()
    except Exception:  # noqa: BLE001 - a fingerprint must never break the reader
        return ""


class CameraFramePool:
    """Latest frame per camera, with an owner-aware, persistent backend reader."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._buffers: dict[int, FrameBuffer] = {}
        self._readers: dict[int, _PersistentReader] = {}
        # Last moment the desktop preview proved it holds each device.
        self._browser_touched: dict[int, float] = {}

    # -- buffers -----------------------------------------------------------

    def buffer(self, index: int) -> FrameBuffer:
        with self._lock:
            if index not in self._buffers:
                self._buffers[index] = FrameBuffer(index=int(index))
            return self._buffers[int(index)]

    def owner(self, index: int) -> str:
        with self._lock:
            return self._buffers.get(int(index), FrameBuffer(index=int(index))).owner

    def set_owner(self, index: int, owner: str) -> FrameBuffer:
        """Claim a camera for one side, releasing the other side if needed."""
        reader = None
        with self._lock:
            buffer = self._buffers.setdefault(int(index), FrameBuffer(index=int(index)))
            if owner != OWNER_BACKEND and buffer.owner == OWNER_BACKEND:
                reader = self._signal_reader_stop_locked(int(index))
            buffer.owner = owner
            buffer.error = ""
        if reader is not None:
            reader.stop()
        return buffer

    def note_error(self, index: int, message: str) -> None:
        with self._lock:
            buffer = self._buffers.setdefault(int(index), FrameBuffer(index=int(index)))
            buffer.error = str(message)[:200]

    # -- publishing (browser side) -----------------------------------------

    def publish_browser_frame(self, index: int, data_url: str, *, thumbnail: str = "") -> None:
        """Accept a frame handed over by the desktop preview."""
        reader = None
        with self._lock:
            buffer = self._buffers.setdefault(int(index), FrameBuffer(index=int(index)))
            buffer.owner = OWNER_BROWSER
            buffer.image_data = str(data_url)
            if thumbnail:
                buffer.thumbnail = thumbnail
            buffer.at = time.time()
            buffer.error = ""
            # Remember when the browser last proved it holds this device, so
            # ``start_reader`` keeps treating it as the owner between shares.
            self._browser_touched[index] = buffer.at
            # The preview is the authority on this camera, so stop competing.
            reader = self._signal_reader_stop_locked(int(index))
        if reader is not None:
            reader.stop()

    def browser_owns(self, index: int) -> bool:
        """Whether the desktop preview still counts as this device's owner.

        True while a frame is fresh *or* while the browser has shared one within
        the ownership grace, so a 15s share interval is never mistaken for the
        preview having let the camera go.
        """
        now = time.time()
        with self._lock:
            buffer = self._buffers.get(int(index))
            if buffer is not None and buffer.owner == OWNER_BROWSER \
                    and buffer.age(now=now) <= FRAME_MAX_AGE_SECONDS:
                return True
            touched = self._browser_touched.get(int(index))
        return bool(touched) and (now - touched) <= BROWSER_OWNERSHIP_GRACE_SECONDS

    def release_browser(self, index: int | None = None) -> None:
        """Drop browser ownership immediately after the preview stops."""
        with self._lock:
            indices = [int(index)] if index is not None else list(self._browser_touched)
            if index is None:
                indices.extend(
                    camera_index for camera_index, buffer in self._buffers.items()
                    if buffer.owner == OWNER_BROWSER and camera_index not in indices
                )
            for camera_index in indices:
                self._browser_touched.pop(camera_index, None)
                buffer = self._buffers.get(camera_index)
                if buffer is not None and buffer.owner == OWNER_BROWSER:
                    buffer.owner = OWNER_IDLE
                    buffer.image_data = ""
                    buffer.thumbnail = ""
                    buffer.at = 0.0
                    buffer.error = ""

    # -- publishing (backend side) -----------------------------------------

    def publish_backend_frame(self, index: int, frame: Any, *, width: int = 0, height: int = 0,
                              thumbnail: str = "") -> None:
        """Store a frame read by a persistent backend reader."""
        import base64

        import cv2

        # Measure brightness here. Without this a black frame was accepted as a
        # perfectly good picture, so the pool served blackness to every consumer
        # and - worse - told them nothing was wrong.
        luminance = self._mean_luminance(frame)
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 78])
        if not ok:
            return
        payload = base64.b64encode(encoded.tobytes()).decode("ascii")
        with self._lock:
            buffer = self._buffers.setdefault(int(index), FrameBuffer(index=int(index)))
            if buffer.owner == OWNER_BROWSER:
                # The preview took the device while we were reading; stand down.
                return
            buffer.owner = OWNER_BACKEND
            buffer.image_data = f"data:image/jpeg;base64,{payload}"
            if thumbnail:
                buffer.thumbnail = thumbnail
            buffer.width = int(width)
            buffer.height = int(height)
            buffer.luminance = luminance
            buffer.at = time.time()
            buffer.reads += 1
            buffer.error = ""

    @staticmethod
    def _mean_luminance(frame: Any) -> float:
        """Average brightness, sampled rather than over every pixel."""
        try:
            import numpy as np

            if frame is None or not getattr(frame, "size", 0):
                return 0.0
            if frame.ndim == 3:
                # Every 8th pixel in both directions is plenty for a mean.
                return float(np.asarray(frame[::8, ::8], dtype="float32").mean())
            return float(np.asarray(frame, dtype="float32").mean())
        except Exception:
            return 0.0

    # -- persistent readers -------------------------------------------------

    def start_reader(self, index: int, *, width: int = 1280, height: int = 720) -> bool:
        """Keep one camera open so every later read is instant."""
        # Never steal a device the preview is using. Checked through
        # ``browser_owns`` rather than a bare owner string, because ownership has
        # to outlive the freshness of the last frame the browser happened to send.
        if self.browser_owns(index):
            return False
        with self._lock:
            existing = self._readers.get(int(index))
            if existing is not None and existing.alive:
                return True
            reader = _PersistentReader(self, int(index), width, height)
            self._readers[int(index)] = reader
        reader.start()
        logger.info("[CameraStream] 开始常驻读帧 #%s", index)
        return True

    def _signal_reader_stop_locked(self, index: int) -> _PersistentReader | None:
        """Pull a reader out of the table and tell it to stop.

        Deliberately does not join: the reader needs this same lock to publish
        frames, so joining while holding it would deadlock. Callers join after
        releasing the lock.
        """
        reader = self._readers.pop(int(index), None)
        if reader is not None:
            reader._stop.set()
        return reader

    def stop_reader(self, index: int) -> None:
        with self._lock:
            reader = self._signal_reader_stop_locked(int(index))
        if reader is not None:
            reader.stop()

    def stop_all(self) -> None:
        with self._lock:
            readers = [self._signal_reader_stop_locked(index) for index in list(self._readers)]
        for reader in readers:
            if reader is not None:
                reader.stop()

    # -- serving consumers --------------------------------------------------

    def reader(self, index: int) -> _PersistentReader | None:
        """The live reader for one camera, if there is one."""
        with self._lock:
            return self._readers.get(int(index))

    def latest(self, index: int, *, max_age: float = FRAME_MAX_AGE_SECONDS) -> FrameBuffer | None:
        with self._lock:
            buffer = self._buffers.get(int(index))
            if buffer is None or not buffer.is_usable(max_age=max_age):
                return None
            return buffer

    def latest_for_inference(self, index: int) -> FrameBuffer | None:
        """A frame good enough to base an observation on.

        A held-open reader publishes continuously, so while it is alive *and still
        publishing* its frame is current and must not be rejected for age: the age
        limit (20s) is shorter than the observation interval (30s), and applying it
        to a healthy reader made every round reopen the device - while fighting the
        reader for it.

        "Alive" is not enough, though. A reader blocked in ``read()``, or one whose
        device stopped delivering, stays alive while its last frame gets older and
        older; serving that frame is how one frozen picture was interpreted as the
        present again and again, thirty seconds apart. So liveness here means
        *published just now*, with the same grace the reader gives itself.
        """
        with self._lock:
            buffer = self._buffers.get(int(index))
            if buffer is None or not buffer.image_data or buffer.is_blank:
                return None
            reader = self._readers.get(int(index))
            max_age = FRAME_MAX_AGE_SECONDS
            if reader is not None and reader.alive:
                max_age = READER_PUBLISH_GRACE_SECONDS
            return buffer if buffer.age() <= max_age else None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {index: buffer.to_dict() for index, buffer in sorted(self._buffers.items())}

    def describe(self) -> dict[str, Any]:
        with self._lock:
            buffers = {index: buffer.to_dict() for index, buffer in sorted(self._buffers.items())}
        return {
            "sources": buffers,
            "browser_owned": sorted(i for i, b in buffers.items() if b["owner"] == OWNER_BROWSER),
            "backend_owned": sorted(i for i, b in buffers.items() if b["owner"] == OWNER_BACKEND),
            "readers_running": sorted(i for i, r in self._readers.items() if r.alive),
        }


_pool = CameraFramePool()


def get_camera_pool() -> CameraFramePool:
    return _pool
