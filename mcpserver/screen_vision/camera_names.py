"""Camera names for the OpenCV indices, read from DirectShow.

OpenCV addresses every camera by a bare integer index, which makes "which camera
is 0?" a question only trial and error can answer - and the answer changes when
a device is plugged in or unplugged. ffmpeg is already a declared dependency of
this project (``setup/dependencies/network.txt``), and its ``dshow`` input
enumerates the *same* DirectShow device list in the *same* order, with the
friendly names attached.

So this module answers one question: "what is index N actually called?"

Two deliberate rules:

* **Nothing here opens a camera.** ``-list_devices`` only builds the filter
  graph and tears it down; it cannot steal a device from the desktop preview or
  from a persistent reader. That is why this is the whole name-resolution
  mechanism instead of something that probes devices directly.
* **Missing ffmpeg is not an error.** A machine without ffmpeg simply gets no
  names - every caller must treat the name as optional decoration around the
  index, never as the thing that identifies the camera.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("screen_vision.camera_names")

# `-list_devices` is a cheap graph build, but a wedged driver can still hang it.
LIST_TIMEOUT_SECONDS = float(os.getenv("MIYA_FFMPEG_TIMEOUT", "20"))
# Device lists change when something is plugged in, but not often; re-reading on
# every scan would spawn a process every 45 seconds for no new information.
CACHE_SECONDS = float(os.getenv("MIYA_CAMERA_NAME_CACHE", "120"))

# ffmpeg prints one line per device, e.g.
#   [dshow @ 0000...] "Integrated Camera" (video)
#   [dshow @ 0000...]   Alternative name "@device_pnp_..."
# Only the quoted name followed by a device kind is a device; the "Alternative
# name" lines carry quotes too but no kind, which is what filters them out.
_DEVICE_LINE = re.compile(r'\]\s+"(?P<name>[^"]+)"\s+\((?P<kind>video|audio|none)\)\s*$')

_names_lock = threading.Lock()
_names_cache: list[str] = []
_names_at: float = 0.0
_last_error: str = ""
_last_attempt: float = 0.0
# A failed lookup backs off, so a machine without ffmpeg does not respawn a
# failing process on every scan.
FAILED_BACKOFF_SECONDS = float(os.getenv("MIYA_CAMERA_NAME_BACKOFF", "300"))


def _decode(raw: bytes) -> str:
    """Decode ffmpeg's console output, which is not always UTF-8 on Windows.

    Device names are user-visible text - "Xiaomi 15 Pro (Windows 虚拟摄像头)" -
    so getting the code page wrong would mangle exactly the string this module
    exists to produce.
    """
    for encoding in ("utf-8", "cp936", "mbcs"):
        try:
            text = raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
        if "\ufffd" not in text:
            return text
    return raw.decode("utf-8", errors="replace")


def _candidate_paths() -> list[str]:
    """Where an ffmpeg binary might be, best first. Never downloads one."""
    candidates: list[str] = []

    configured = os.getenv("MIYA_FFMPEG", "").strip()
    if configured:
        candidates.append(configured)

    found = shutil.which("ffmpeg")
    if found:
        candidates.append(found)

    # static-ffmpeg ships a binary inside its own package once it has been
    # fetched; the project lists it as a dependency, so on an installed machine
    # this is the normal location.
    try:
        import static_ffmpeg  # type: ignore[import-not-found]

        base = Path(static_ffmpeg.__file__).resolve().parent / "bin"
        candidates.extend(str(path) for path in sorted(base.glob("**/ffmpeg.exe")))
        candidates.extend(str(path) for path in sorted(base.glob("**/ffmpeg")))
    except Exception:  # noqa: BLE001 - an absent helper package is expected
        pass

    # pyffmpeg bundles its own copy under the package directory.
    try:
        import pyffmpeg  # type: ignore[import-not-found]

        base = Path(pyffmpeg.__file__).resolve().parent
        candidates.extend(str(path) for path in sorted(base.glob("**/ffmpeg*.exe")))
    except Exception:  # noqa: BLE001
        pass

    seen: set[str] = set()
    unique: list[str] = []
    for path in candidates:
        if not path or path in seen:
            continue
        seen.add(path)
        if Path(path).is_file():
            unique.append(path)
    return unique


def ffmpeg_path() -> str:
    """The ffmpeg binary to use, or an empty string when there is none."""
    paths = _candidate_paths()
    return paths[0] if paths else ""


def _run_list_devices(executable: str) -> list[str]:
    """Run `-list_devices` and return the video device names in index order."""
    command = [
        executable,
        "-hide_banner",
        "-list_devices", "true",
        "-f", "dshow",
        "-i", "dummy",
    ]
    creation_flags = 0
    if sys.platform == "win32":
        # No console window may flash on the user's desktop for a background scan.
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
        command,
        capture_output=True,
        timeout=LIST_TIMEOUT_SECONDS,
        creationflags=creation_flags,
        check=False,
    )
    # ffmpeg always "fails" here: "dummy" is not a real input, which is the
    # documented way to make it print the device list. The exit code is noise.
    text = _decode(completed.stderr or b"") + "\n" + _decode(completed.stdout or b"")
    names: list[str] = []
    for line in text.splitlines():
        match = _DEVICE_LINE.search(line)
        if match and match.group("kind") == "video":
            name = match.group("name").strip()
            if name:
                names.append(name)
    return names


def dshow_device_names(*, force: bool = False) -> list[str]:
    """Video device names in DirectShow (and therefore OpenCV) index order.

    Returns an empty list when ffmpeg is unavailable or the lookup fails; the
    caller keeps working with indices, just without names.
    """
    global _names_cache, _names_at, _last_error, _last_attempt

    now = time.time()
    with _names_lock:
        fresh = _names_cache and (now - _names_at) < CACHE_SECONDS
        if fresh and not force:
            return list(_names_cache)
        if not force and _last_error and (now - _last_attempt) < FAILED_BACKOFF_SECONDS:
            return list(_names_cache)
        _last_attempt = now

    executable = ffmpeg_path()
    if not executable:
        with _names_lock:
            _last_error = "没有找到 ffmpeg，无法读取摄像头名字（索引仍然可用）"
        logger.debug("[CameraNames] %s", _last_error)
        return []

    try:
        names = _run_list_devices(executable)
    except subprocess.TimeoutExpired:
        names = []
        with _names_lock:
            _last_error = f"ffmpeg 列举设备超时（{LIST_TIMEOUT_SECONDS:.0f} 秒）"
        logger.warning("[CameraNames] %s", _last_error)
        return []
    except Exception as exc:  # noqa: BLE001 - names are decoration, never fatal
        with _names_lock:
            _last_error = f"读取摄像头名字失败: {type(exc).__name__}: {exc}"
        logger.warning("[CameraNames] %s", _last_error)
        return []

    with _names_lock:
        _names_cache = names
        _names_at = time.time()
        _last_error = "" if names else "ffmpeg 没有枚举到任何视频设备"
    logger.info("[CameraNames] DirectShow 摄像头: %s", names or "（没有）")
    return list(names)


def name_for_index(index: Any, *, names: list[str] | None = None) -> str:
    """The friendly name of one camera index, or an empty string."""
    try:
        position = int(index)
    except (TypeError, ValueError):
        return ""
    if position < 0:
        return ""
    resolved = dshow_device_names() if names is None else names
    if position < len(resolved):
        return resolved[position]
    return ""


def is_virtual_name(name: str) -> bool:
    """Whether a device name looks like a software/virtual camera.

    The distinction matters for the explanation a black frame gets: a virtual
    camera is black because nothing is feeding it, while a physical one that
    stays black has a different set of causes.
    """
    lowered = str(name or "").lower()
    return any(
        marker in lowered
        for marker in ("virtual", "虚拟", "obs", "manycam", "vcam", "screen capture", "ndi")
    )


def describe() -> dict[str, Any]:
    """Diagnostics for the name lookup, for the panel and for health checks."""
    with _names_lock:
        names = list(_names_cache)
        fetched_at = _names_at
        error = _last_error
    return {
        "available": bool(ffmpeg_path()),
        "ffmpeg": ffmpeg_path(),
        "names": names,
        "fetched_at": round(fetched_at, 1),
        "error": error,
    }


def reset_cache() -> None:
    """Forget the cached names; the next lookup re-reads them."""
    global _names_cache, _names_at, _last_error, _last_attempt
    with _names_lock:
        _names_cache = []
        _names_at = 0.0
        _last_error = ""
        _last_attempt = 0.0
