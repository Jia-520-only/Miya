"""Local ONNX camera inference for Miya Vision.

The camera boundary is intentionally small: callers provide one data URL,
inference happens in-process, and only derived values leave this module.
Identity enrollment stores normalized embeddings, never image bytes.

Face detection prefers ``cv2.FaceDetectorYN`` when OpenCV exposes it, because
that is the upstream post-processing for YuNet; the hand-rolled decoder below is
a NumPy fallback for environments without it and mirrors the same math
(sigmoid scores plus log-scale box deltas over stride priors).
"""

from __future__ import annotations

import base64
import binascii
import io
import json
import logging
import math
import os
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any

try:
    import numpy as np
except ImportError:  # Optional until a local camera feature is requested.
    np = None  # type: ignore[assignment]

try:
    from PIL import Image
except ImportError:  # Optional until a local camera feature is requested.
    Image = None  # type: ignore[assignment]

logger = logging.getLogger("screen_vision.local_camera")

FEATURE_MODELS = {
    "face_detection": "face_detector.onnx",
    "identity": "face_embedder.onnx",
    "emotion": "emotion_classifier.onnx",
    "pose": "pose_estimator.onnx",
}
# FER+ (emotion-ferplus-8) output order, which is *not* the FER2013 order:
# neutral, happiness, surprise, sadness, anger, disgust, fear, contempt.
# The tuple below previously read (中性, 开心, 悲伤, 惊讶, 恐惧, 厌恶, 愤怒, 轻蔑),
# which swaps surprise/sadness and anger/fear - Miya called a surprised face sad
# and an angry one frightened. The order lives in the model catalog so it can be
# corrected without touching code; this tuple is only the fallback.
EMOTION_LABELS_FALLBACK = ("中性", "开心", "惊讶", "悲伤", "愤怒", "厌恶", "恐惧", "轻蔑")
_EMOTION_LABELS_CACHE: tuple[str, ...] | None = None


def _emotion_labels() -> tuple[str, ...]:
    """Emotion label order for the loaded FER+ model, from the model catalog."""
    global _EMOTION_LABELS_CACHE
    if _EMOTION_LABELS_CACHE is not None:
        return _EMOTION_LABELS_CACHE
    labels: tuple[str, ...] = ()
    try:
        catalog = json.loads((_model_dir() / "model_catalog.json").read_text(encoding="utf-8"))
        node = ((catalog.get("models") or {}).get(FEATURE_MODELS["emotion"]) or {}).get("labels")
        values = node.get("values") if isinstance(node, dict) else node
        if isinstance(values, list):
            labels = tuple(str(item) for item in values if str(item).strip())
    except Exception:  # noqa: BLE001 - a missing catalog must not break emotion
        logger.debug("[local_camera] 读取表情标签配置失败，使用内置顺序", exc_info=True)
    if len(labels) != 8:
        labels = EMOTION_LABELS_FALLBACK
    _EMOTION_LABELS_CACHE = labels
    return labels


# Kept as a module-level name: it is part of this module's published surface.
EMOTION_LABELS = EMOTION_LABELS_FALLBACK
IDENTITY_THRESHOLD = float(os.getenv("MIYA_CAMERA_IDENTITY_THRESHOLD", "0.48"))
FACE_SCORE_THRESHOLD = float(os.getenv("MIYA_CAMERA_FACE_SCORE", "0.55"))
# A frame whose mean luminance is this low carries no usable signal; a virtual
# camera that is registered but never fed produces exactly this.
BLANK_FRAME_MEAN = float(os.getenv("MIYA_CAMERA_BLANK_MEAN", "4.0"))
DECODE_MAX_PIXELS = int(os.getenv("MIYA_CAMERA_DECODE_MAX_PIXELS", str(4096 * 4096)))
BASELINE_FEATURES = {
    "motion": {
        "available": True,
        "mode": "browser_frame_delta",
        "description": "浏览器端低分辨率帧差；不上传、不保存原始帧",
    },
    "action": {
        "available": True,
        "mode": "movenet_keypoint_temporal_heuristic",
        "description": "基于本地姿态关键点的短时序动作分类；只保留关键点，不保存原始帧",
    },
}
_session_cache: dict[str, Any] = {}
_session_lock = threading.Lock()
_detector_cache: dict[tuple[int, int, float], Any] = {}
# Reentrant: the detection path holds it across both the lookup and the detect.
_detector_lock = threading.RLock()
_identity_lock = threading.Lock()
_face_backend: str = "unknown"

# The order YuNet reports its five facial landmarks in. This is the person's own
# left/right, which is *not* the order this module used to assume: it read the
# pair as (left_eye, right_eye), which flips the sign of the eye-line tilt and
# therefore mirrored both the spoken "头向左歪" and Live2D's ParamAngleZ.
# Nose and mouth corners are unaffected by the swap.
YUNET_KEYPOINT_ORDER = ("right_eye", "left_eye", "nose", "right_mouth", "left_mouth")


def _model_dir() -> Path:
    configured = os.getenv("MIYA_CAMERA_MODEL_DIR", "").strip()
    return Path(configured).expanduser() if configured else Path(__file__).resolve().parents[2] / "models" / "camera_vision"


def _identity_dir() -> Path:
    configured = os.getenv("MIYA_CAMERA_IDENTITY_DIR", "").strip()
    return Path(configured).expanduser() if configured else Path(__file__).resolve().parents[2] / "data" / "camera_identities"


def _onnxruntime():
    try:
        import onnxruntime as ort
    except ImportError:
        return None
    return ort


def _session(feature: str):
    if np is None or Image is None:
        raise RuntimeError("本地摄像头需要 numpy 和 Pillow")
    path = _model_dir() / FEATURE_MODELS[feature]
    if not path.is_file():
        raise FileNotFoundError(f"缺少本地模型: {path.name}")
    ort = _onnxruntime()
    if ort is None:
        raise RuntimeError("未安装 onnxruntime")
    key = str(path.resolve())
    with _session_lock:
        if key not in _session_cache:
            _session_cache[key] = ort.InferenceSession(key, providers=["CPUExecutionProvider"])
        return _session_cache[key]


def _decode_image(data_url: str) -> Image.Image:
    if Image is None:
        raise RuntimeError("本地摄像头需要 Pillow")
    header, separator, payload = str(data_url or "").partition(",")
    mime = header.removeprefix("data:").split(";", 1)[0].lower()
    if not separator or ";base64" not in header or mime not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError("缺少有效的摄像头画面，只接受 JPEG、PNG 或 WebP base64 图片。")
    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("摄像头画面编码无效。") from exc
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("摄像头画面过大。")
    try:
        image = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as exc:
        raise ValueError("摄像头画面无法解码。") from exc
    if image.width * image.height > DECODE_MAX_PIXELS:
        raise ValueError("摄像头画面分辨率过大。")
    return image


def frame_luminance(image: Image.Image | None) -> float | None:
    """Mean luminance of one frame, used to spot cameras that never deliver."""
    if image is None or np is None:
        return None
    try:
        small = image.convert("L").resize((32, 24), Image.Resampling.BILINEAR)
    except Exception:
        return None
    return round(float(np.asarray(small, dtype=np.float32).mean()), 3)


def _input_size(session, default: tuple[int, int]) -> tuple[int, int]:
    shape = session.get_inputs()[0].shape
    if len(shape) >= 4 and isinstance(shape[-1], int) and isinstance(shape[-2], int):
        return int(shape[-1]), int(shape[-2])
    return default


def _tensor(image: Image.Image, session, default_size: tuple[int, int], *, gray=False,
            scale=1 / 128.0, mean=127.5, bgr=False) -> np.ndarray:
    width, height = _input_size(session, default_size)
    width = max(1, min(int(width), 8192))
    height = max(1, min(int(height), 8192))
    converted = image.convert("L" if gray else "RGB").resize((width, height), Image.Resampling.BILINEAR)
    array = np.asarray(converted, dtype=np.float32)
    if gray:
        array = array[None, :, :]
    elif bgr:
        array = array[:, :, ::-1].transpose(2, 0, 1)
    else:
        array = array.transpose(2, 0, 1)
    return (array - mean).astype(np.float32)[None, ...] * scale


def _run(session, tensor: np.ndarray) -> list[np.ndarray]:
    return session.run(None, {session.get_inputs()[0].name: tensor})


def _sigmoid(value: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(value, dtype=np.float32), -60.0, 60.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def _letterbox(image: Image.Image, size: tuple[int, int]) -> tuple[Any, float, int, int]:
    """Resize with preserved aspect ratio and symmetric padding.

    YuNet and MoveNet are both trained on square inputs. Stretching a 16:9
    webcam frame into a square distorts faces and skeletons, so pad instead.
    """
    target_w, target_h = int(size[0]), int(size[1])
    canvas = Image.new("RGB", (target_w, target_h), (0, 0, 0))
    if image.width < 1 or image.height < 1:
        return canvas, 1.0, 0, 0
    ratio = min(target_w / image.width, target_h / image.height)
    new_w = max(1, int(round(image.width * ratio)))
    new_h = max(1, int(round(image.height * ratio)))
    offset_x = (target_w - new_w) // 2
    offset_y = (target_h - new_h) // 2
    canvas.paste(image.resize((new_w, new_h), Image.Resampling.BILINEAR), (offset_x, offset_y))
    return canvas, ratio, offset_x, offset_y


def _nms_faces(faces: list[dict[str, Any]], iou_threshold: float = 0.45) -> list[dict[str, Any]]:
    """Drop overlapping detections, keeping the highest-scoring box.

    YuNet's stride heads report the same face once per neighbouring anchor, so a
    decoder without this step inflates the face count and makes "how many people
    are there" meaningless.
    """
    if len(faces) <= 1:
        return list(faces)
    ordered = sorted(faces, key=lambda face: float(face.get("score") or 0.0), reverse=True)
    kept: list[dict[str, Any]] = []
    for candidate in ordered:
        cx, cy = float(candidate["x"]), float(candidate["y"])
        cw, ch = float(candidate["width"]), float(candidate["height"])
        c_right, c_bottom = cx + cw, cy + ch
        duplicate = False
        for existing in kept:
            ex, ey = float(existing["x"]), float(existing["y"])
            ew, eh = float(existing["width"]), float(existing["height"])
            e_right, e_bottom = ex + ew, ey + eh
            inter_w = max(0.0, min(c_right, e_right) - max(cx, ex))
            inter_h = max(0.0, min(c_bottom, e_bottom) - max(cy, ey))
            intersection = inter_w * inter_h
            if intersection <= 0.0:
                continue
            union = cw * ch + ew * eh - intersection
            if union > 0.0 and intersection / union >= iou_threshold:
                duplicate = True
                break
        if not duplicate:
            kept.append(candidate)
    return kept


def _decode_yunet_heads(
    outputs: list[np.ndarray],
    threshold: float,
    canvas_size: tuple[int, int] | None = None,
) -> list[dict[str, Any]]:
    """NumPy fallback for the YuNet stride heads.

    The export exposes classification, objectness, box deltas and keypoint
    deltas per stride. Scores are raw logits and the box heads are distances in
    stride units from the anchor centre; both are transformed explicitly here.

    Coordinates are normalized against ``canvas_size`` - the letterboxed input
    the model actually saw - rather than a hard-coded 640, which silently
    mis-scaled every box whenever the session input size differed.
    """
    if len(outputs) < 12:
        return []
    canvas_width = float((canvas_size or (640, 640))[0]) or 640.0
    canvas_height = float((canvas_size or (640, 640))[1]) or 640.0
    faces: list[dict[str, Any]] = []
    for head, stride in enumerate((8, 16, 32)):
        scores = _sigmoid(outputs[head]).reshape(-1) * _sigmoid(outputs[3 + head]).reshape(-1)
        boxes = np.asarray(outputs[6 + head], dtype=np.float32).reshape((-1, 4))
        keypoints = np.asarray(outputs[9 + head], dtype=np.float32).reshape((-1, 10))
        grid = int(round(math.sqrt(scores.size)))
        if grid <= 0 or boxes.shape[0] != scores.size:
            continue
        for index in np.nonzero(scores >= threshold)[0]:
            row, column = divmod(int(index), grid)
            center_x = (column + 0.5) * stride
            center_y = (row + 0.5) * stride
            left, top, right, bottom = (value * stride for value in boxes[index])
            x = center_x - left
            y = center_y - top
            width = left + right
            height = top + bottom
            if width <= 1.0 or height <= 1.0:
                continue
            points = []
            for offset in range(0, 10, 2):
                points.append({
                    "x": round(float((center_x + keypoints[index][offset] * stride) / canvas_width), 5),
                    "y": round(float((center_y + keypoints[index][offset + 1] * stride) / canvas_height), 5),
                })
            faces.append({
                "x": round(float(x / canvas_width), 5), "y": round(float(y / canvas_height), 5),
                "width": round(float(width / canvas_width), 5), "height": round(float(height / canvas_height), 5),
                "score": round(float(scores[index]), 4), "keypoints": points,
            })
    return _nms_faces(faces)


def _yunet_detector(image: Image.Image, threshold: float):
    """A reusable ``cv2.FaceDetectorYN`` for one input size and threshold.

    YuNet's post-processing is exposed by OpenCV, and building the detector costs
    30-70ms - per frame that was pure waste. ``FaceDetectorYN`` is stateful, so it
    is cached per (size, threshold) and guarded by a lock rather than shared
    freely across threads.
    """
    import cv2

    key = (int(image.width), int(image.height), round(float(threshold), 4))
    with _detector_lock:
        detector = _detector_cache.get(key)
        if detector is None:
            model_path = str(_model_dir() / FEATURE_MODELS["face_detection"])
            detector = cv2.FaceDetectorYN.create(model_path, "", (key[0], key[1]), key[2], 0.3, 5000)
            detector.setInputSize((key[0], key[1]))
            _detector_cache[key] = detector
        return detector


def _detect_faces_opencv(image: Image.Image, threshold: float) -> list[dict[str, Any]] | None:
    """Upstream YuNet post-processing; ``None`` means OpenCV cannot do it."""
    try:
        import cv2
    except ImportError:
        return None
    if not hasattr(cv2, "FaceDetectorYN"):
        return None
    frame = np.asarray(image, dtype=np.uint8)[:, :, ::-1].copy()
    try:
        with _detector_lock:
            detector = _yunet_detector(image, threshold)
            _, raw = detector.detect(frame)
    except Exception as exc:  # noqa: BLE001 - any OpenCV failure must fall back
        logger.info("[local_camera] OpenCV FaceDetectorYN 不可用，回退 NumPy 解码: %s", exc)
        return None
    faces: list[dict[str, Any]] = []
    if raw is None:
        return faces
    for row in np.asarray(raw):
        if row.size < 15:
            continue
        score = float(row[-1])
        if score < threshold:
            continue
        x, y, width, height = (float(value) for value in row[:4])
        # YuNet emits its five landmarks in a fixed order. Recorded verbatim so
        # the order stays a property of the detector, and interpreted in exactly
        # one place (``expression_signals``).
        points = [
            {"x": round(float(row[4 + offset]) / image.width, 5),
             "y": round(float(row[5 + offset]) / image.height, 5)}
            for offset in range(0, 10, 2)
        ]
        faces.append({
            "x": round(x / image.width, 5), "y": round(y / image.height, 5),
            "width": round(width / image.width, 5), "height": round(height / image.height, 5),
            "score": round(score, 4), "keypoints": points,
        })
    return faces


def _detect_faces(image: Image.Image, threshold: float | None = None) -> list[dict[str, Any]]:
    """Detect faces with normalized [0,1] boxes plus 5 facial landmarks."""
    global _face_backend
    cutoff = FACE_SCORE_THRESHOLD if threshold is None else float(threshold)
    opencv_faces = _detect_faces_opencv(image, cutoff)
    if opencv_faces is not None:
        _face_backend = "opencv_yunet"
        return sorted(opencv_faces, key=lambda face: face["score"], reverse=True)

    session = _session("face_detection")
    width, height = _input_size(session, (640, 640))
    canvas, _ratio, _offset_x, _offset_y = _letterbox(image, (width, height))
    array = np.asarray(canvas, dtype=np.float32)[:, :, ::-1].transpose(2, 0, 1)[None, ...]
    outputs = _run(session, array)
    _face_backend = "onnx_yunet_heads"
    return sorted(_decode_yunet_heads(outputs, cutoff, (width, height)),
                  key=lambda face: face["score"], reverse=True)


def _face_box_pixels(image: Image.Image, face: dict[str, Any]) -> tuple[int, int, int, int] | None:
    """Turn a normalized ``[0,1]`` face box into pixel bounds.

    ``_detect_faces`` documents and returns normalized coordinates; this is the
    single place that converts them back into pixels. It used to ``int()`` the
    normalized values directly, which floors every one of them to ``0`` and
    yields a 0x0 crop - so the identity and emotion models were fed a black
    square and answered a constant. Keeping the conversion in one function, with
    the empty-box case handled explicitly, is what stops that from returning.
    """
    width, height = int(image.width), int(image.height)
    if width <= 0 or height <= 0:
        return None
    try:
        x = float(face["x"])
        y = float(face["y"])
        box_w = float(face["width"])
        box_h = float(face["height"])
    except (KeyError, TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in (x, y, box_w, box_h)):
        return None
    if box_w <= 0.0 or box_h <= 0.0:
        return None
    left = int(round(x * width))
    top = int(round(y * height))
    right = int(round((x + box_w) * width))
    bottom = int(round((y + box_h) * height))
    if right <= left or bottom <= top:
        return None
    # A little margin around the box, in pixels, so the chin and forehead are
    # not clipped off a landmark-based crop.
    padding = int(round(max(box_w, box_h) * max(width, height) * 0.12))
    return (max(0, left - padding), max(0, top - padding),
            min(width, right + padding), min(height, bottom + padding))


def _face_crop(image: Image.Image, face: dict[str, Any]) -> Image.Image:
    """Crop one face out of a frame, in pixel space.

    Raises ``ValueError`` when the box carries no usable area, so a malformed
    detection fails loudly here instead of silently feeding the models a black
    image. Callers that treat a face as optional catch it.
    """
    bounds = _face_box_pixels(image, face)
    if bounds is None:
        raise ValueError("人脸框无效（归一化坐标无法换算为像素区域）")
    left, top, right, bottom = bounds
    crop = image.crop((left, top, right, bottom))
    if crop.width <= 0 or crop.height <= 0:
        raise ValueError("人脸裁剪结果为空")
    return crop


# Canonical 112x112 landmark template for SFace, expressed as ratios of the
# 112x112 input so the transform is resolution independent. SFace was trained on
# faces aligned with ``cv2.FaceRecognizerSF.alignCrop``; feeding it an
# axis-aligned rectangle instead measurably lowers similarity, so the five
# YuNet landmarks are used to build the same similarity transform here.
SFACE_TEMPLATE_112 = np.array([
    [38.2946, 51.6963],   # right eye (the person's right, image left)
    [73.5318, 51.5014],   # left eye
    [56.0252, 71.7366],   # nose tip
    [41.5493, 92.3655],   # right mouth corner
    [70.7299, 92.2041],   # left mouth corner
], dtype=np.float32) if np is not None else None  # type: ignore[union-attr]


def _align_face(
    image: Image.Image,
    face: dict[str, Any],
    size: tuple[int, int],
) -> Image.Image | None:
    """Align a face with its five landmarks and resize to ``size``.

    Returns ``None`` when the landmarks are missing or degenerate, so the caller
    can fall back to the plain crop rather than to a wrong transform.
    """
    if np is None or Image is None:
        return None
    points = [point for point in (face.get("keypoints") or []) if isinstance(point, dict)]
    if len(points) < 5:
        return None
    try:
        source = np.array(
            [[float(point["x"]) * image.width, float(point["y"]) * image.height] for point in points[:5]],
            dtype=np.float32,
        )
    except (KeyError, TypeError, ValueError):
        return None
    # SFace's own alignment is a similarity fit between this face and the
    # template; refuse a degenerate fit rather than stretching a bad detection.
    if not np.all(np.isfinite(source)):
        return None
    if float(np.linalg.norm(source[0] - source[1])) < 1.0:
        return None
    if SFACE_TEMPLATE_112 is None:
        return None
    try:
        import cv2
    except ImportError:
        return None
    target = SFACE_TEMPLATE_112.astype(np.float32).copy()
    if size != (112, 112):
        scale = np.array([size[0] / 112.0, size[1] / 112.0], dtype=np.float32)
        target = target * scale
    try:
        matrix, _inliers = cv2.estimateAffinePartial2D(source, target, method=cv2.LMEDS)
        if matrix is None:
            return None
        warp = np.asarray(matrix, dtype=np.float32)
    except Exception:  # noqa: BLE001 - alignment is an enhancement, not a requirement
        logger.debug("[local_camera] 人脸对齐失败，回退到矩形裁剪", exc_info=True)
        return None
    if not np.all(np.isfinite(warp)):
        return None
    # Reject a transform that collapses or explodes the face: a sane similarity
    # fit keeps the scale within a normal range for a detected face.
    scale = float(np.sqrt(abs(warp[0, 0] * warp[1, 1] - warp[0, 1] * warp[1, 0])))
    if not 0.05 <= scale <= 20.0:
        return None
    try:
        frame = np.asarray(image.convert("RGB"), dtype=np.uint8)
        aligned = cv2.warpAffine(frame, warp, (int(size[0]), int(size[1])),
                                 flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    except Exception:  # noqa: BLE001
        logger.debug("[local_camera] 人脸对齐仿射变换失败", exc_info=True)
        return None
    return Image.fromarray(aligned, mode="RGB")


def _embedding(
    face_image: Image.Image,
    *,
    face: dict[str, Any] | None = None,
    image: Image.Image | None = None,
) -> list[float]:
    """SFace embedding of one face.

    Prefers the 5-point aligned crop SFace was trained on and falls back to the
    supplied crop when landmarks are unavailable.
    """
    session = _session("identity")
    prepared = face_image
    if face is not None and image is not None:
        aligned = _align_face(image, face, (112, 112))
        if aligned is not None:
            prepared = aligned
    output = np.asarray(_run(session, _tensor(prepared, session, (112, 112), bgr=True))[0]).reshape(-1)
    norm = float(np.linalg.norm(output))
    if norm == 0 or not np.isfinite(norm):
        raise RuntimeError("人脸特征模型返回了无效向量")
    return (output / norm).astype(np.float32).tolist()


def _emotion(face_image: Image.Image) -> dict[str, Any]:
    session = _session("emotion")
    output = np.asarray(_run(session, _tensor(face_image, session, (64, 64), gray=True, scale=1 / 255.0, mean=0))[0]).reshape(-1)
    shifted = output - np.max(output)
    probabilities = np.exp(shifted) / np.maximum(np.exp(shifted).sum(), 1e-8)
    index = int(np.argmax(probabilities))
    labels = _emotion_labels()
    label = labels[index] if index < len(labels) else f"类别 {index + 1}"
    return {"label": label, "confidence": round(float(probabilities[index]), 4),
            "distribution": [round(float(x), 4) for x in probabilities]}


def _keypoints_from_bgr(frame: Any) -> list[dict[str, Any]]:
    """MoveNet keypoints for a raw BGR frame (an OpenCV array).

    MoveNet is square-input, but webcam frames are commonly 16:9 or 4:3. The
    persistent reader used to resize those frames directly to a square, which
    stretched the body horizontally and made temporal action geometry unstable.
    Keep the aspect ratio with centred padding, then map the returned points
    back to the original frame coordinates.
    """
    session = _session("pose")
    shape = session.get_inputs()[0].shape
    height = int(shape[1]) if isinstance(shape[1], int) else 192
    width = int(shape[2]) if isinstance(shape[2], int) else 192
    try:
        import cv2
    except ImportError:
        return []
    source = np.asarray(frame)
    if source.ndim != 3 or source.shape[2] < 3:
        return []
    source_height, source_width = source.shape[:2]
    if source_height < 1 or source_width < 1:
        return []
    scale = min(width / source_width, height / source_height)
    resized_width = max(1, int(round(source_width * scale)))
    resized_height = max(1, int(round(source_height * scale)))
    resized = cv2.resize(source[:, :, :3], (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
    canvas = np.zeros((height, width, 3), dtype=resized.dtype)
    offset_x = (width - resized_width) // 2
    offset_y = (height - resized_height) // 2
    canvas[offset_y:offset_y + resized_height, offset_x:offset_x + resized_width] = resized
    # MoveNet expects RGB; the reader and the one-shot capture both hand over BGR.
    tensor = np.asarray(canvas[:, :, ::-1], dtype=np.int32)[None, ...]
    output = np.asarray(_run(session, tensor)[0]).reshape((-1, 3))
    points: list[dict[str, Any]] = []
    for point in output:
        canvas_x = float(point[1]) * width
        canvas_y = float(point[0]) * height
        source_x = (canvas_x - offset_x) / scale / source_width
        source_y = (canvas_y - offset_y) / scale / source_height
        points.append({
            "x": round(float(source_x), 5),
            "y": round(float(source_y), 5),
            "confidence": round(float(point[2]), 4),
        })
    return points


def _pose(image: Image.Image) -> dict[str, Any]:
    """MoveNet keypoints for a PIL frame, preserving its aspect ratio."""
    frame = np.asarray(image.convert("RGB"), dtype=np.uint8)[:, :, ::-1]
    return {"keypoints": _keypoints_from_bgr(frame)}


def _keypoint(pose: dict[str, Any] | None, index: int) -> tuple[float, float, float] | None:
    """Return one MoveNet point, tolerating incomplete client-side history."""
    points = (pose or {}).get("keypoints", pose if isinstance(pose, list) else [])
    if not isinstance(points, list) or index >= len(points):
        return None
    point = points[index]
    if not isinstance(point, dict):
        return None
    try:
        return float(point["x"]), float(point["y"]), float(point.get("confidence", 0.0))
    except (KeyError, TypeError, ValueError):
        return None


def pose_quality(pose: dict[str, Any] | None) -> dict[str, Any]:
    """Summarize how trustworthy one skeleton is.

    A frame with almost no confident joints must not be reported as a reliable
    posture; callers need this to avoid claiming "still" from noise.
    """
    points = (pose or {}).get("keypoints", pose if isinstance(pose, list) else [])
    if not isinstance(points, list) or not points:
        return {"confident": 0, "total": 0, "mean_confidence": 0.0, "max_confidence": 0.0, "usable": False}
    confidences = []
    for point in points:
        try:
            confidences.append(float(point.get("confidence", 0.0)))
        except (AttributeError, TypeError, ValueError):
            confidences.append(0.0)
    confident = sum(1 for value in confidences if value >= 0.30)
    return {
        "confident": confident,
        "total": len(confidences),
        "mean_confidence": round(sum(confidences) / len(confidences), 4),
        "max_confidence": round(max(confidences), 4),
        # Walk/bend/typing heuristics need a real skeleton, not one noisy joint.
        "usable": confident >= 5 and max(confidences) >= 0.40,
    }


def _wrist_motion(sequence: list[Any], index: int) -> float:
    """Peak-to-peak horizontal travel of one wrist across the sample window."""
    xs = [point[0] for item in sequence if (point := _keypoint(item, index)) and point[2] >= 0.30]
    if len(xs) < 3:
        return 0.0
    return max(xs) - min(xs)


# --- pose sequence ---------------------------------------------------------
#
# Every temporal branch in ``classify_pose_action`` needs several samples over a
# few seconds (typing >=3, wave >=4, walk >=5). The caller-supplied
# ``pose_history`` only ever came from the browser, so the backend's own
# autonomous loop - the one that actually watches all day - passed nothing and
# could therefore only ever report a static posture. The buffer below accumulates
# keypoints from whichever capture path has frames, at its own fixed cadence, so
# the temporal reader has real history regardless of who is asking and how often.
POSE_SEQUENCE_SAMPLE_SECONDS = float(os.getenv("MIYA_CAMERA_POSE_SAMPLE_SECONDS", "1.0"))
POSE_SEQUENCE_WINDOW_SECONDS = float(os.getenv("MIYA_CAMERA_POSE_WINDOW_SECONDS", "240"))
POSE_SEQUENCE_MAX_SAMPLES = int(os.getenv("MIYA_CAMERA_POSE_MAX_SAMPLES", "240"))


class PoseSequenceBuffer:
    """Bounded, time-stamped keypoint history for the temporal action reader."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._samples: dict[Any, list[tuple[float, dict[str, Any]]]] = {}
        self._last_sample: dict[Any, float] = {}

    def _prune_locked(self, key: Any, now: float) -> list[tuple[float, dict[str, Any]]]:
        cutoff = now - POSE_SEQUENCE_WINDOW_SECONDS
        kept = [item for item in self._samples.get(key, []) if item[0] >= cutoff]
        if len(kept) > POSE_SEQUENCE_MAX_SAMPLES:
            kept = kept[-POSE_SEQUENCE_MAX_SAMPLES:]
        self._samples[key] = kept
        return kept

    def record(self, pose: dict[str, Any] | None, *, key: Any = -1,
               at: float | None = None, force: bool = False) -> bool:
        """Store one pose, at most once per sampling interval.

        Returns whether it was stored, so a caller can report sampling rate.
        """
        points = (pose or {}).get("keypoints") if isinstance(pose, dict) else None
        if not points:
            return False
        now = time.time() if at is None else float(at)
        with self._lock:
            last = self._last_sample.get(key, 0.0)
            if not force and last and (now - last) < POSE_SEQUENCE_SAMPLE_SECONDS:
                return False
            self._prune_locked(key, now)
            self._samples[key].append((now, pose))
            self._last_sample[key] = now
            return True

    def due(self, *, key: Any = -1, at: float | None = None) -> bool:
        """Whether the sampling interval has elapsed for this camera."""
        now = time.time() if at is None else float(at)
        with self._lock:
            last = self._last_sample.get(key, 0.0)
            return not last or (now - last) >= POSE_SEQUENCE_SAMPLE_SECONDS

    def history(self, *, key: Any = -1, limit: int = 11) -> list[dict[str, Any]]:
        """The most recent poses, oldest first, excluding nothing."""
        now = time.time()
        with self._lock:
            kept = self._prune_locked(key, now)
        return [pose for _at, pose in kept[-max(1, int(limit)):]]

    def clear(self, *, key: Any | None = None) -> None:
        with self._lock:
            if key is None:
                self._samples.clear()
                self._last_sample.clear()
            else:
                self._samples.pop(key, None)
                self._last_sample.pop(key, None)

    def describe(self) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            return {
                "cameras": {str(key): len(self._prune_locked(key, now)) for key in list(self._samples)},
                "sample_seconds": POSE_SEQUENCE_SAMPLE_SECONDS,
                "window_seconds": POSE_SEQUENCE_WINDOW_SECONDS,
            }


_pose_sequence = PoseSequenceBuffer()


def observe_frame_pose(frame: Any, *, key: Any = -1, at: float | None = None) -> bool:
    """Sample one raw camera frame into the shared pose sequence.

    Called from the persistent capture loop, which runs at ~20Hz - far denser
    than the once-per-30s observation, and that density is the point. Rate
    limited internally, and any failure is swallowed: pose sampling is an
    enhancement to the observation, never a reason for it to fail.
    """
    if np is None or frame is None:
        return False
    now = time.time() if at is None else float(at)
    if not _pose_sequence.due(key=key, at=now):
        return False
    try:
        pose = {"keypoints": _keypoints_from_bgr(frame)}
    except Exception:  # noqa: BLE001 - sampling must never break the reader loop
        logger.debug("[local_camera] 姿态采样失败", exc_info=True)
        return False
    return _pose_sequence.record(pose, key=key, at=now, force=True)


def pose_sequence_status() -> dict[str, Any]:
    """Diagnostics for the shared pose history."""
    return _pose_sequence.describe()


def classify_pose_action(
    pose_history: list[dict[str, Any]] | None,
    current_pose: dict[str, Any],
    *,
    pose_key: Any = -1,
) -> dict[str, Any]:
    """Classify what Jia appears to be doing, from a short skeleton history.

    MoveNet supplies a stable 17-point skeleton but no temporal action label, so
    this layer is a conservative geometric/temporal reader. It reports an
    *activity* with evidence rather than pretending to know intent, and it names
    the reader's own limit in plain language when the skeleton is too noisy to
    support any conclusion.

    When the caller supplies no history, the shared sequence filled by the
    capture path is used instead - without it the temporal branches could never
    fire on the autonomous observation loop.
    """
    supplied = [item for item in (pose_history or []) if isinstance(item, (dict, list))]
    history = (supplied if supplied else _pose_sequence.history(key=pose_key))[-11:]
    sequence = history + [current_pose]

    def point(index: int, item: dict[str, Any] | list[dict[str, Any]]) -> tuple[float, float, float] | None:
        return _keypoint(item, index)

    def midpoint(*points: tuple[float, float, float] | None) -> tuple[float, float] | None:
        usable = [item for item in points if item and item[2] >= 0.30]
        if not usable:
            return None
        return (sum(item[0] for item in usable) / len(usable), sum(item[1] for item in usable) / len(usable))

    def wrist_gap(item: dict[str, Any] | list[dict[str, Any]]) -> float | None:
        left, right = point(9, item), point(10, item)
        if not left or not right or left[2] < 0.30 or right[2] < 0.30:
            return None
        return ((left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2) ** 0.5

    quality = pose_quality(current_pose)
    if not quality["usable"]:
        # Explain the limit like a person would, not like a log line.
        return {
            "label": "看不清",
            "confidence": 0.0,
            "kind": "low_confidence",
            "evidence": "这个角度只能认出你一点点轮廓，暂时说不准你在做什么",
            "detail": f"{quality['confident']}/{quality['total']} 个关节可用",
        }

    latest = sequence[-1]
    left_shoulder, right_shoulder = point(5, latest), point(6, latest)
    left_wrist, right_wrist = point(9, latest), point(10, latest)
    shoulder_y = [p[1] for p in (left_shoulder, right_shoulder) if p and p[2] >= 0.25]
    shoulder_level = sum(shoulder_y) / len(shoulder_y) if shoulder_y else None

    raised = []
    if shoulder_level is not None:
        for wrist, side in ((left_wrist, "左手"), (right_wrist, "右手")):
            if wrist and wrist[2] >= 0.30 and wrist[1] < shoulder_level - 0.12:
                raised.append(side)

    # A wave is a raised wrist changing horizontal direction over several samples.
    wave_scores: list[float] = []
    for wrist_index in (9, 10):
        xs = [p[0] for item in sequence if (p := point(wrist_index, item)) and p[2] >= 0.30]
        if len(xs) < 4:
            continue
        # Adjacent-pair zips are intentionally shorter by one element; strict=True
        # would raise here and break wave detection entirely.
        deltas = [b - a for a, b in zip(xs, xs[1:], strict=False) if abs(b - a) >= 0.018]
        changes = sum(1 for a, b in zip(deltas, deltas[1:], strict=False) if a * b < 0)
        span = max(xs) - min(xs)
        if changes >= 2 and span >= 0.08:
            wave_scores.append(min(0.95, 0.60 + changes * 0.07 + span * 0.5))
    if wave_scores:
        return {"label": "在跟你挥手", "confidence": round(max(wave_scores), 3), "kind": "wave",
                "evidence": "手腕在横向来回摆动"}

    # Clapping is a short convergence event: hands were apart and are now
    # close together above the hips. It needs both wrists, so it degrades
    # quietly when the camera only sees one arm.
    current_gap = wrist_gap(latest)
    previous_gaps = [gap for item in sequence[:-1] if (gap := wrist_gap(item)) is not None]
    if current_gap is not None and current_gap <= 0.14 and any(gap >= 0.20 for gap in previous_gaps[-5:]):
        return {"label": "在鼓掌", "confidence": 0.78, "kind": "clap", "evidence": "双手从分开快速合拢"}

    # A stretch reaches both arms upward, but so does a two-handed raise. The
    # distinguishing cue is the outward opening of the hands, not the raise.
    if len(raised) > 1 and left_wrist and right_wrist and shoulder_level is not None:
        reach = shoulder_level - min(left_wrist[1], right_wrist[1])
        span = abs(left_wrist[0] - right_wrist[0])
        if reach >= 0.28 and span >= 0.26:
            return {"label": "在伸懒腰", "confidence": 0.76, "kind": "stretch", "evidence": "双臂高举并向两侧张开"}

    # A hand up near the face is either a phone or a cup; MoveNet cannot tell
    # which, so the label stays honest about the ambiguity.
    nose = point(0, latest)
    if nose and nose[2] >= 0.30:
        for wrist in (left_wrist, right_wrist):
            if not wrist or wrist[2] < 0.30:
                continue
            distance = ((wrist[0] - nose[0]) ** 2 + (wrist[1] - nose[1]) ** 2) ** 0.5
            if distance <= 0.12:
                elevated = shoulder_level is not None and wrist[1] < shoulder_level
                return {
                    "label": "在看手机" if elevated else "在喝水或吃东西",
                    "confidence": 0.7,
                    "kind": "phone" if elevated else "drink",
                    "evidence": "手举到脸前" + ("，位置偏高" if elevated else "，位置低于肩"),
                }

    if raised:
        label = "双手都举起来了" if len(raised) > 1 else f"{raised[0]}举起来了"
        return {"label": label, "confidence": round(min(0.92, 0.68 + 0.06 * len(raised)), 3),
                "kind": "raised_hand", "evidence": "手腕高于肩膀"}

    def posture(item: dict[str, Any] | list[dict[str, Any]]) -> str | None:
        shoulders = midpoint(point(5, item), point(6, item))
        hips = midpoint(point(11, item), point(12, item))
        knees = midpoint(point(13, item), point(14, item))
        if not shoulders or not hips or not knees:
            return None
        hip_to_knee = knees[1] - hips[1]
        # MoveNet coordinates grow downwards. A standing body has the knees
        # clearly below the hips; while seated, the two levels converge.
        if hip_to_knee >= 0.12 and hips[1] - shoulders[1] >= 0.08:
            return "standing"
        if hip_to_knee <= 0.07 and hips[1] - shoulders[1] >= 0.08:
            return "sitting"
        return None

    postures = [state for item in sequence if (state := posture(item))]
    current_posture = posture(latest)
    if current_posture:
        prior_postures = postures[:-1]
        if current_posture == "sitting" and "standing" in prior_postures[-4:]:
            return {"label": "刚坐下了", "confidence": 0.78, "kind": "sit_down", "evidence": "身体从站立变为坐姿"}
        if current_posture == "standing" and "sitting" in prior_postures[-4:]:
            return {"label": "刚站起来了", "confidence": 0.78, "kind": "stand_up", "evidence": "身体从坐姿变为站立"}

    # Walking produces alternating ankle offsets around the hip center. This
    # uses derived skeleton geometry only and needs a few frames to avoid
    # labelling a single step or camera shake as walking.
    walk_states: list[int] = []
    for item in sequence:
        hips = midpoint(point(11, item), point(12, item))
        left_ankle, right_ankle = point(15, item), point(16, item)
        if not hips or not left_ankle or not right_ankle or left_ankle[2] < 0.30 or right_ankle[2] < 0.30:
            continue
        separation = left_ankle[0] - right_ankle[0]
        if abs(separation) >= 0.07:
            walk_states.append(1 if separation > 0 else -1)
    switches = sum(1 for left, right in zip(walk_states, walk_states[1:], strict=False) if left != right)
    if len(walk_states) >= 5 and switches >= 2:
        return {"label": "在走动", "confidence": round(min(0.88, 0.62 + switches * 0.05), 3),
                "kind": "walk", "evidence": "双腿在交替迈步"}

    # Hands low and close to the body, moving a little but not going anywhere:
    # that is the posture of working at a keyboard. The window matters more than
    # any single frame, which is why this branch needs several samples.
    if shoulder_level is not None and len(sequence) >= 3:
        hands_present = [wrist for wrist in (left_wrist, right_wrist) if wrist and wrist[2] >= 0.30]
        hands_low = bool(hands_present) and all(wrist[1] >= shoulder_level - 0.02 for wrist in hands_present)
        bilateral = left_wrist is not None and right_wrist is not None and left_wrist[2] >= 0.30 and right_wrist[2] >= 0.30
        if hands_low and bilateral and current_posture in {"sitting", None}:
            travel = max(_wrist_motion(sequence, 9), _wrist_motion(sequence, 10))
            # Only real hand travel counts as working. A hand merely resting on
            # the desk or the mouse must not be reported as typing.
            if travel >= 0.018:
                return {"label": "在打键盘或动鼠标", "confidence": round(min(0.82, 0.60 + travel * 2.0), 3),
                        "kind": "typing", "evidence": "双手放在桌面高度，小幅往复移动"}

    # Torso leaning away from the vertical, with the head above the hips,
    # is the shape of settling back into the chair.
    if current_posture == "sitting" and shoulder_level is not None:
        hips = midpoint(point(11, latest), point(12, latest))
        shoulders = midpoint(left_shoulder, right_shoulder)
        if hips and shoulders:
            torso_height = hips[1] - shoulders[1]
            if torso_height <= 0.12 and raised == []:
                return {"label": "靠在椅背上", "confidence": 0.66, "kind": "lean_back",
                        "evidence": "肩膀离髋部很近，身体向后靠"}

    if current_posture == "sitting":
        return {"label": "坐着", "confidence": 0.70, "kind": "sitting", "evidence": "髋部与膝部高度接近"}
    if current_posture == "standing":
        return {"label": "站着", "confidence": 0.70, "kind": "standing", "evidence": "膝部明显低于髋部"}

    # Head nod: vertical nose movement with comparatively little horizontal drift.
    noses = [p for item in sequence if (p := point(0, item)) and p[2] >= 0.30]
    if len(noses) >= 4:
        y_span = max(p[1] for p in noses) - min(p[1] for p in noses)
        x_span = max(p[0] for p in noses) - min(p[0] for p in noses)
        if y_span >= 0.09 and x_span <= max(0.12, y_span * 1.4):
            return {"label": "在点头或低头", "confidence": round(min(0.86, 0.57 + y_span), 3),
                    "kind": "nod", "evidence": "头部上下移动"}

    # Large hip displacement is a useful, privacy-preserving cue for body movement.
    hips = []
    for item in sequence:
        candidates = [p for p in (point(11, item), point(12, item)) if p and p[2] >= 0.25]
        if candidates:
            hips.append((sum(p[0] for p in candidates) / len(candidates), sum(p[1] for p in candidates) / len(candidates)))
    if len(hips) >= 3:
        displacement = max(((x - hips[0][0]) ** 2 + (y - hips[0][1]) ** 2) ** 0.5 for x, y in hips)
        if displacement >= 0.10:
            return {"label": "在动身体", "confidence": round(min(0.82, 0.52 + displacement), 3),
                    "kind": "body_motion", "evidence": "髋部位置有明显变化"}

    return {"label": "安静地待着", "confidence": 0.62, "kind": "still", "evidence": "关键点变化很小"}
def _identity_file() -> Path:
    return _identity_dir() / "identities.json"


def _read_identities() -> list[dict[str, Any]]:
    path = _identity_file()
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        logger.warning("身份库无法读取，将按空库处理: %s", path)
        return []


def _write_identities(identities: list[dict[str, Any]]) -> None:
    directory = _identity_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = _identity_file()
    fd, temp_name = tempfile.mkstemp(prefix="identities-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(identities, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(temp_name, 0o600)
        except OSError:
            pass
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _match_identity(embedding: list[float], identities: list[dict[str, Any]]) -> dict[str, Any] | None:
    if np is None:
        raise RuntimeError("本地身份匹配需要 numpy")
    vector = np.asarray(embedding, dtype=np.float32)
    best: tuple[float, dict[str, Any]] | None = None
    for identity in identities:
        candidate = np.asarray(identity.get("embedding", []), dtype=np.float32)
        if candidate.shape != vector.shape:
            continue
        score = float(np.dot(vector, candidate))
        if best is None or score > best[0]:
            best = (score, identity)
    if best is None or best[0] < IDENTITY_THRESHOLD:
        return None
    return {"id": best[1]["id"], "name": best[1]["name"], "similarity": round(best[0], 4)}


def face_signals(faces: list[dict[str, Any]], image: Image.Image | None = None) -> dict[str, Any]:
    """Derive presence-relevant geometry from raw detections."""
    if not faces:
        return {"count": 0, "largest_ratio": 0.0, "best_score": 0.0, "centered": False}
    best = max(faces, key=lambda face: float(face.get("width", 0)) * float(face.get("height", 0)))
    ratio = float(best.get("width", 0)) * float(best.get("height", 0))
    center_x = float(best.get("x", 0)) + float(best.get("width", 0)) / 2
    center_y = float(best.get("y", 0)) + float(best.get("height", 0)) / 2
    return {
        "count": len(faces),
        "largest_ratio": round(ratio, 4),
        "best_score": round(float(best.get("score", 0.0)), 4),
        "center": [round(center_x, 4), round(center_y, 4)],
        "centered": abs(center_x - 0.5) <= 0.28,
        "landmarks": bool(best.get("keypoints")),
        "aspect": round(float(best.get("width", 0)) / max(float(best.get("height", 1e-6)), 1e-6), 3),
    }


# --- interpretable expression geometry -------------------------------------
#
# YuNet yields exactly five facial landmarks (both eyes, nose tip, both mouth
# corners). That is not enough to score emotion, but it *is* enough to measure
# a few things honestly: how wide the mouth is, how open the jaw looks, whether
# the head is turned, and which way it is tilted. These are ratios of the face's
# own box, so they survive the user leaning toward or away from the camera.

# Whether the mouth is open is now judged against the person's own resting
# baseline (see ``_MouthBaseline`` below) rather than against a fixed number:
# the corner height this ratio measures varies by face and by posture, so a
# constant calibrated on synthetic proportions stayed permanently exceeded on a
# real face. This value is kept only as the reference the rig geometry uses
# before a baseline exists, and as the documented closed-mouth starting point.
MOUTH_OPEN_RATIO = float(os.getenv("MIYA_FACE_MOUTH_OPEN", "1.15"))


def reset_adaptive_state() -> None:
    """Drop the learned baselines.

    The mouth reference and the pose sequence are process-local learning, so a
    fresh camera, a different person at the desk, or one test after another must
    be able to start from nothing rather than inherit stale samples.
    """
    _mouth_baseline.clear()
    _pose_sequence.clear()
# How far the nose may drift off the eye midpoint, in inter-eye units, before
# the head counts as turned.
HEAD_TURN_OFFSET_RATIO = float(os.getenv("MIYA_FACE_HEAD_TURN", "0.14"))
HEAD_TILT_DEGREES = float(os.getenv("MIYA_FACE_HEAD_TILT", "7.0"))
# Share of the lower face that is much darker than the rest: an open mouth.
MOUTH_DARK_RATIO = float(os.getenv("MIYA_FACE_MOUTH_DARK", "0.10"))
# Mouth width over inter-eye distance at or above which the mouth counts as
# stretched. A neutral closed mouth measures near 0.90.
MOUTH_WIDE_RATIO = float(os.getenv("MIYA_FACE_MOUTH_WIDE", "1.05"))


def _distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    return ((float(a["x"]) - float(b["x"])) ** 2 + (float(a["y"]) - float(b["y"])) ** 2) ** 0.5


def _dark_fraction(face_image: Image.Image | None) -> float | None:
    """Fraction of the lower face that is much darker than its surroundings.

    An open mouth reads as a dark patch against skin, which is a far more
    robust cue than any expression classifier we have locally.
    """
    if face_image is None or np is None:
        return None
    try:
        height = face_image.height
        lower = np.asarray(face_image.crop((0, int(height * 0.55), face_image.width, height))
                           .convert("L"), dtype=np.float32)
    except Exception:
        return None
    if lower.size == 0:
        return None
    median = float(np.median(lower))
    if median <= 1.0:
        return None
    return round(float((lower < median * 0.62).mean()), 4)


def expression_signals(
    face: dict[str, Any] | None,
    face_image: Image.Image | None = None,
) -> dict[str, Any]:
    """Interpretable expression cues from the five available landmarks."""
    points = (face or {}).get("keypoints") or []
    if len(points) < 5:
        return {"available": False, "reason": "人脸关键点不足（需要 5 点）"}
    # Named by YuNet's documented order, not by positional assumption. Getting
    # this backwards flipped the eye-line tilt sign, which mirrored both the
    # spoken tilt direction and Live2D's head roll.
    landmarks = dict(zip(YUNET_KEYPOINT_ORDER, points[:5], strict=True))
    left_eye = landmarks["left_eye"]
    right_eye = landmarks["right_eye"]
    nose = landmarks["nose"]
    left_mouth = landmarks["left_mouth"]
    right_mouth = landmarks["right_mouth"]
    try:
        for point in (left_eye, right_eye, nose, left_mouth, right_mouth):
            float(point["x"])
            float(point["y"])
    except (KeyError, TypeError, ValueError):
        return {"available": False, "reason": "人脸关键点格式无效"}
    width = max(float((face or {}).get("width") or 0.0), 1e-6)
    eye_distance = max(_distance(left_eye, right_eye), 1e-6)
    mouth_width = _distance(left_mouth, right_mouth)
    # How far the mouth corners sit below the eye line, in inter-eye units. This
    # is a pure "how open is the jaw" measure: it does not mix in mouth width,
    # which is why it is used instead of the nose-to-corner distance.
    eye_line_y = (float(left_eye["y"]) + float(right_eye["y"])) / 2
    mouth_drop = ((float(left_mouth["y"]) - eye_line_y) + (float(right_mouth["y"]) - eye_line_y)) / 2
    mouth_open_ratio = mouth_drop / eye_distance
    # Frontal faces keep the eyes spanning a stable share of the detection box;
    # a turned head makes the box wider than the projected eye distance.
    eye_share = eye_distance / width
    # Image-space tilt: y grows downward, so a positive angle means the person's
    # left eye sits lower, i.e. the head leans toward their left, which is the
    # viewer's right. `describe_expression` and the rig both read this sign.
    tilt = math.degrees(math.atan2(
        float(left_eye["y"]) - float(right_eye["y"]),
        max(abs(float(left_eye["x"]) - float(right_eye["x"])), 1e-6),
    ))
    # Horizontal offset of the nose between the eyes indicates a turned head.
    nose_offset = (float(nose["x"]) - (float(left_eye["x"]) + float(right_eye["x"])) / 2) / eye_distance

    signals: dict[str, Any] = {
        "available": True,
        "mouth_open_ratio": round(mouth_open_ratio, 4),
        "mouth_width_ratio": round(mouth_width / eye_distance, 4),
        "nose_offset_ratio": round(nose_offset, 4),
        "head_tilt_degrees": round(tilt, 2),
        "eye_span_ratio": round(eye_share, 4),
        # Mouth corners spread as the jaw drops, which is what Live2D's
        # MouthFunnel / ParamMouthForm expect for a natural open mouth.
        "mouth_wide": (mouth_width / eye_distance) >= MOUTH_WIDE_RATIO,
        "head_turned": abs(nose_offset) >= HEAD_TURN_OFFSET_RATIO,
        "head_tilted": abs(tilt) >= HEAD_TILT_DEGREES,
    }

    # Openness is judged against this face's own resting ratio once enough
    # readings exist; the fixed constant only applies as a last-resort ceiling.
    resting = _mouth_baseline.resting()
    threshold = max(resting * (1.0 + MOUTH_OPEN_MARGIN), 0.0) if resting else MOUTH_OPEN_CEILING
    signals["mouth_open"] = mouth_open_ratio >= threshold
    signals["mouth_baseline_ratio"] = round(resting, 4) if resting else None
    signals["mouth_open_threshold"] = round(threshold, 4)

    dark = _dark_fraction(face_image)
    if dark is not None:
        signals["lower_face_dark_ratio"] = dark
        # An open mouth usually shows a dark cavity; combine both cues.
        signals["mouth_likely_open"] = bool(signals["mouth_open"] or dark >= MOUTH_DARK_RATIO)
    else:
        signals["mouth_likely_open"] = bool(signals["mouth_open"])
    # Only a reading the baseline itself considers closed may update it, so an
    # open mouth cannot drag its own reference upward.
    if not signals["mouth_open"] or resting is None:
        _mouth_baseline.observe(mouth_open_ratio)
    return signals


def describe_expression(signals: dict[str, Any] | None) -> str:
    """One plain sentence about the face, or an empty string if nothing holds."""
    if not signals or not signals.get("available"):
        return ""
    bits: list[str] = []
    if signals.get("mouth_likely_open"):
        bits.append("嘴是张着的")
    if signals.get("head_tilted"):
        # Positive tilt means the person's left eye sits lower than the right,
        # i.e. their head leans to their own left. Described from the viewer's
        # side, that is "to the right", which is what a person watching them
        # (and Miya, looking through the same camera) actually sees.
        direction = "向右" if float(signals.get("head_tilt_degrees") or 0) > 0 else "向左"
        bits.append(f"头{direction}歪着")
    if signals.get("head_turned"):
        bits.append("脸有点转向侧面")
    return "，".join(bits)


# --- rig parameters --------------------------------------------------------
#
# The conversion from measurement to Live2D parameter lives here, next to the
# measurement and its thresholds, so there is exactly one copy of it. The
# desktop frontend only applies what it is given.

# Closed-mouth value of mouth_open_ratio; the baseline the jaw opens from.
RIG_MOUTH_CLOSED = float(os.getenv("MIYA_RIG_MOUTH_CLOSED", "0.90"))
# Jaw drop above baseline that counts as fully open.
RIG_MOUTH_OPEN_SPAN = float(os.getenv("MIYA_RIG_MOUTH_OPEN_SPAN", "0.45"))
RIG_MOUTH_NEUTRAL_WIDTH = float(os.getenv("MIYA_RIG_MOUTH_NEUTRAL_WIDTH", "0.90"))
RIG_MOUTH_WIDTH_SPAN = float(os.getenv("MIYA_RIG_MOUTH_WIDTH_SPAN", "0.25"))
# Degrees of eye-line tilt that map to full head roll.
RIG_TILT_FULL_SCALE = float(os.getenv("MIYA_RIG_TILT_SCALE", "20"))
# Nose offset that maps to full head yaw.
RIG_YAW_FULL_SCALE = float(os.getenv("MIYA_RIG_YAW_SCALE", "0.20"))


def _clamp(value: float, low: float, high: float) -> float:
    if value != value:  # NaN
        return 0.0
    return max(low, min(high, value))


def rig_parameters(signals: dict[str, Any] | None) -> dict[str, float]:
    """Convert measured geometry into additive Live2D parameter offsets.

    Additive by design: Miya's emotion channel and her talking mouth write these
    same parameters, so overwriting them would stop her talking whenever Jia's
    face is visible.

    Only the parameters this measurement can honestly justify are produced.
    Eyebrows and eyelids are absent because YuNet provides no landmarks for
    them - inventing them would be exactly the fake confidence this layer exists
    to avoid.
    """
    if not signals or not signals.get("available"):
        return {}
    # Prefer the same baseline the open/closed decision used, so the jaw cannot
    # report half-open for a face whose mouth is judged shut.
    closed_reference = signals.get("mouth_baseline_ratio")
    if closed_reference is None:
        closed_reference = RIG_MOUTH_CLOSED
    open_amount = _clamp(
        (float(signals.get("mouth_open_ratio") or 0.0) - float(closed_reference)) / RIG_MOUTH_OPEN_SPAN, 0.0, 1.0)
    wide = _clamp(
        (float(signals.get("mouth_width_ratio") or 0.0) - RIG_MOUTH_NEUTRAL_WIDTH) / RIG_MOUTH_WIDTH_SPAN, -1.0, 1.0)
    # Negated: a positive measured tilt means the person's head leans toward the
    # viewer's right, which is a negative roll for Live2D's ParamAngleZ.
    roll = _clamp(-float(signals.get("head_tilt_degrees") or 0.0) / RIG_TILT_FULL_SCALE, -1.0, 1.0)
    yaw = _clamp(float(signals.get("nose_offset_ratio") or 0.0) / RIG_YAW_FULL_SCALE, -1.0, 1.0)
    return {
        "JawOpen": round(open_amount * 0.55, 4),
        "ParamMouthOpenY": round(open_amount * 0.5, 4),
        # A stretched mouth rounds (funnel); a narrow one flattens.
        "MouthFunnel": round(wide * 0.35, 4) if wide > 0 else 0.0,
        "ParamMouthForm": round(-wide * 0.25, 4),
        "ParamAngleZ": round(roll * 22, 4),
        "ParamBodyAngleZ": round(roll * 6, 4),
        "ParamAngleX": round(yaw * 14, 4),
        "ParamBodyAngleX": round(yaw * 5, 4),
    }


def _emotion_is_stuck(sample: dict[str, Any]) -> bool:
    """Flag an expression model that answers the same thing every single time.

    A classifier with no contrast is worse than no classifier: it produces
    confident-looking labels that carry no information. Detecting that is what
    stops it from being quoted as if it meant something.
    """
    label = str(sample.get("label") or "")
    confidence = float(sample.get("confidence") or 0.0)
    with _emotion_probe_lock:
        if label != _emotion_probe["label"]:
            _emotion_probe["label"] = label
            _emotion_probe["same_count"] = 1
            _emotion_probe["distinct"] = min(8, int(_emotion_probe["distinct"]) + 1)
            return False
        _emotion_probe["same_count"] = int(_emotion_probe["same_count"]) + 1
        # Only declare it stuck once we have seen a run of identical answers.
        return int(_emotion_probe["same_count"]) >= 12 and int(_emotion_probe["distinct"]) <= 1 and confidence >= 0.5


def expression_model_status() -> dict[str, Any]:
    with _emotion_probe_lock:
        return {
            "distinct_labels_seen": int(_emotion_probe["distinct"]),
            "identical_run": int(_emotion_probe["same_count"]),
            "stuck": bool(int(_emotion_probe["distinct"]) <= 1 and int(_emotion_probe["same_count"]) >= 12),
        }


_emotion_probe_lock = threading.Lock()
_emotion_probe = {"label": "", "same_count": 0, "distinct": 0}


# --- mouth baseline --------------------------------------------------------
#
# A fixed "mouth drop / inter-eye distance" threshold cannot work across people
# and postures: the two corners sit at different heights on different faces, and
# leaning toward the camera changes the ratio on its own. The original constant
# was calibrated on synthetic proportions, so on a real face it stayed over the
# line almost permanently - 8 of 10 recorded summaries said "嘴微张".
#
# The robust comparison is against the same person's own resting face, which is
# what the baseline below keeps: a slow-moving high quantile of recent readings
# that ignores the moment being judged.
MOUTH_BASELINE_MIN_SAMPLES = int(os.getenv("MIYA_FACE_BASELINE_MIN", "40"))
# Fraction of the baseline the jaw must open beyond before "open" is claimed.
MOUTH_OPEN_MARGIN = float(os.getenv("MIYA_FACE_MOUTH_MARGIN", "0.10"))
# Hard ceiling: even without a baseline, an extreme ratio is an open mouth.
MOUTH_OPEN_CEILING = float(os.getenv("MIYA_FACE_MOUTH_CEILING", "1.45"))
# Cap on stored samples; the window is long on purpose (one reading ~30s).
MOUTH_BASELINE_WINDOW = int(os.getenv("MIYA_FACE_BASELINE_WINDOW", "240"))


class _MouthBaseline:
    """Recent closed-mouth reference for one face, in inter-eye units."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._samples: list[float] = []

    def clear(self) -> None:
        with self._lock:
            self._samples.clear()

    def observe(self, ratio: float) -> None:
        if not math.isfinite(ratio) or ratio <= 0.0:
            return
        with self._lock:
            self._samples.append(float(ratio))
            if len(self._samples) > MOUTH_BASELINE_WINDOW:
                del self._samples[: len(self._samples) - MOUTH_BASELINE_WINDOW]

    def resting(self) -> float | None:
        """The person's resting ratio, or ``None`` until enough is seen.

        A high quantile rather than the median: whether a mouth is open is
        decided against how *closed* this face gets, and the median of a person
        who talks a lot would drift upward with them.
        """
        with self._lock:
            if len(self._samples) < MOUTH_BASELINE_MIN_SAMPLES:
                return None
            ordered = sorted(self._samples)
        index = min(len(ordered) - 1, int(round(0.15 * (len(ordered) - 1))))
        return float(ordered[index])

    def describe(self) -> dict[str, Any]:
        resting = self.resting()
        with self._lock:
            count = len(self._samples)
        return {"samples": count, "resting_ratio": resting}


_mouth_baseline = _MouthBaseline()


def mouth_baseline_status() -> dict[str, Any]:
    """Diagnostics: how settled the resting-mouth baseline is."""
    status = _mouth_baseline.describe()
    status.update({"min_samples": MOUTH_BASELINE_MIN_SAMPLES, "margin": MOUTH_OPEN_MARGIN,
                   "ceiling": MOUTH_OPEN_CEILING})
    return status


def discover_local_camera_capabilities() -> dict[str, Any]:
    runtime_available = np is not None and Image is not None and _onnxruntime() is not None
    features: dict[str, dict[str, Any]] = {}
    for feature, filename in FEATURE_MODELS.items():
        path = _model_dir() / filename
        features[feature] = {"available": runtime_available and path.is_file(), "model": filename, "path": str(path)}
    face_ready = all(features[name]["available"] for name in ("face_detection", "identity"))
    model_ready = face_ready and features["emotion"]["available"] and features["pose"]["available"]
    return {
        # Browser-side frame delta and the action protocol remain available
        # even when the optional ONNX runtime has not been installed.
        "status": "ready" if model_ready else "partial",
        "runtime": "onnxruntime" if runtime_available else "missing", "model_dir": str(_model_dir()),
        "features": features, "baseline": BASELINE_FEATURES, "identity_count": len(_read_identities()),
        "face_backend": _face_backend,
        "face_score_threshold": FACE_SCORE_THRESHOLD,
        "blank_frame_mean": BLANK_FRAME_MEAN,
        # Adaptive state, so "why did it say the mouth was open / why is the
        # action still 安静地待着" can be answered from the panel instead of by
        # guessing which threshold fired.
        "mouth_baseline": mouth_baseline_status(),
        "pose_sequence": pose_sequence_status(),
        "privacy": "local_only" if face_ready else "frame_delta_local_only",
        "message": "本地人脸、身份、表情、姿态与短时序动作识别已就绪。" if model_ready else "本地模型尚未完整安装；仅已安装的能力可用，不会回退到云端。",
    }


def local_only_error() -> dict[str, Any]:
    capabilities = discover_local_camera_capabilities()
    return {"status": "unavailable", "message": capabilities["message"], "capabilities": capabilities, "persisted": False}


def mark_vision_result(result: dict[str, Any]) -> dict[str, Any]:
    """Tag a result that came from real pixels, so fusion can trust it.

    A result whose device merely failed to open also has ``status: error``; it
    must not be mistaken for "the camera delivered a black frame".
    """
    result["vision_analyzed"] = True
    return result


def analyze_local_frame(
    image_data: str,
    *,
    identity=True,
    emotion=False,
    pose=False,
    faces: bool | None = None,
    pose_history: list[dict[str, Any]] | None = None,
    pose_key: Any = -1,
    hands: bool = True,
) -> dict[str, Any]:
    image = _decode_image(image_data)
    luminance = frame_luminance(image)
    if luminance is not None and luminance < BLANK_FRAME_MEAN:
        return mark_vision_result({
            "status": "error",
            "source": "camera_local",
            "persisted": False,
            "faces": 0,
            "observations": [],
            "luminance": luminance,
            "blank_frame": True,
            "message": "摄像头返回的是全黑画面：设备可能被其它程序占用、被隐私开关关闭，或没有程序在向虚拟摄像头推流。",
        })
    # Pose-only companion ticks should not require a face detector. This keeps
    # the action path useful for a partial silhouette or a back-facing pose.
    # `faces=True` asks for detection purely to measure expression geometry,
    # which is how the rig follows Jia without also matching identity.
    detect_faces = bool(faces) if faces is not None else bool(identity or emotion)
    faces_found = _detect_faces(image) if detect_faces else []
    result: dict[str, Any] = mark_vision_result({"status": "success", "source": "camera_local", "persisted": False,
                                                 "faces": len(faces_found), "observations": [], "luminance": luminance})
    if not faces_found and not pose:
        result["message"] = "没看到你的脸，这次也没法看姿态。"
        return result
    # A crop that cannot be produced is reported, never silently replaced by a
    # black square: that is what made identity and emotion answer a constant.
    face_image: Image.Image | None = None
    if faces_found:
        try:
            face_image = _face_crop(image, faces_found[0])
        except ValueError as exc:
            logger.info("[local_camera] 人脸裁剪失败，跳过身份与表情: %s", exc)
            result["face_crop_error"] = str(exc)
    observation: dict[str, Any] = {"box": faces_found[0]} if faces_found else {}
    if faces_found:
        observation["face_signals"] = face_signals(faces_found, image)
        # Interpretable geometry, available even when the emotion model is not.
        expression = expression_signals(faces_found[0], face_image)
        if expression.get("available"):
            observation["expression"] = expression
            # Ready-to-apply rig parameters, so the conversion exists in exactly
            # one place: next to the measurement and its thresholds.
            observation["rig"] = rig_parameters(expression)
            spoken = describe_expression(expression)
            if spoken:
                observation["expression_text"] = spoken
    if face_image is not None and identity:
        embedding = _embedding(face_image, face=faces_found[0], image=image)
        enrolled = _read_identities()
        if not enrolled:
            # Saying "未知" when nobody was ever enrolled reads as a failure and
            # hides the real next step, which is enrolling an identity.
            observation["identity"] = {"name": "未登记", "similarity": 0.0, "reason": "identity_store_empty"}
        else:
            observation["identity"] = _match_identity(embedding, enrolled) or {"name": "未知", "similarity": 0.0}
    if face_image is not None and emotion:
        sample = _emotion(face_image)
        # A classifier that answers identically every time is not evidence.
        if _emotion_is_stuck(sample):
            sample["uninformative"] = True
            sample["reason"] = "这个表情模型目前对每一帧都给出同一个答案，不能当作表情线索"
        observation["emotion"] = sample
    if pose:
        observation["pose"] = _pose(image)
        observation["pose_quality"] = pose_quality(observation["pose"])
        # Feed this reading back into the shared sequence as well, so whichever
        # path has frames keeps the history dense.
        _pose_sequence.record(observation["pose"], key=pose_key)
        observation["action"] = classify_pose_action(
            pose_history,
            observation["pose"],
            pose_key=pose_key,
        )
    if hands:
        # What is *in* his hand, which the skeleton cannot say. Failure here is
        # reported and then ignored: hand reading is an extra sense, and losing it
        # must never break an observation that already worked without it.
        try:
            from .handpose import describe_hands, read_hands

            reading = read_hands(np.asarray(image)[:, :, ::-1].copy())
        except Exception as exc:  # noqa: BLE001
            logger.debug("[local_camera] 手部识别失败: %s", exc)
            reading = {"available": False, "reason": f"手部识别失败: {type(exc).__name__}", "hands": []}
        if reading.get("available") and reading.get("count"):
            observation["hands"] = reading
            spoken_hands = describe_hands(reading)
            if spoken_hands:
                observation["hand_text"] = spoken_hands
    result["observations"].append(observation)
    result["message"] = _natural_message(
        observation,
        faces=len(faces_found),
        camera_count=int(result.get("camera_count") or 1),
    )
    result["detail"] = build_detail_fields(observation)
    return result


def _natural_message(observation: dict[str, Any], *, faces: int, camera_count: int = 1) -> str:
    """Describe this frame the way a companion would, not the way a log would.

    Numeric confidence and landmark counts stay in the structured fields; a
    person being watched should hear what was noticed, plus an honest sentence
    when the camera simply could not tell.
    """
    identity = observation.get("identity") or {}
    action = observation.get("action") or {}
    quality = observation.get("pose_quality") or {}
    signals = observation.get("face_signals") or {}

    parts: list[str] = []
    if faces and identity.get("name") and identity["name"] not in {"未知", "未登记"}:
        parts.append(f"看到{identity['name']}在画面里")
    elif faces:
        parts.append("看清你的脸了")
        if quality.get("usable") and action.get("kind") not in {"low_confidence", "unknown", ""}:
            parts[-1] = "看到你了"

    if camera_count > 1:
        parts.append(f"（{camera_count} 个摄像头一起看）")

    kind = str(action.get("kind") or "")
    if kind == "low_confidence":
        parts.append("这个角度只看清你一点轮廓，暂时说不准你在做什么")
    elif kind and kind != "unknown":
        parts.append(str(action.get("label") or ""))
    elif faces:
        parts.append("看起来在安静地待着")
    elif quality.get("usable"):
        parts.append("看到你的身影，但没看清脸")
    else:
        parts.append("没有看清你在做什么")

    # Interpretable face geometry beats a classifier that may be guessing.
    expression_text = str(observation.get("expression_text") or "")
    if expression_text:
        parts.append(expression_text)

    # What his hands are doing is the one thing the skeleton cannot report, and it
    # is what tells apart the activities that used to look identical.
    hand_text = str(observation.get("hand_text") or "")
    if hand_text:
        parts.append(hand_text)

    emotion = observation.get("emotion") or {}
    if emotion.get("uninformative"):
        # Say the honest thing rather than quoting a constant label.
        if expression_text:
            parts.append("表情模型这次不可信，就不猜了")
    elif emotion.get("label") and float(emotion.get("confidence") or 0) >= 0.5 and emotion["label"] != "中性":
        parts.append(f"表情看着有点{emotion['label']}")

    if faces and not signals.get("centered"):
        parts.append("你有点偏出画面了，可以往中间坐一点")

    body = "，".join(part for part in parts if part)
    return f"{body}。" if body else "弥娅看着你，但还说不清你在做什么。"


def build_detail_fields(observation: dict[str, Any]) -> dict[str, Any]:
    """Structured, machine-readable view of one observation, for diagnostics."""
    action = observation.get("action") or {}
    quality = observation.get("pose_quality") or {}
    return {
        "action_kind": action.get("kind"),
        "action_label": action.get("label"),
        "action_confidence": action.get("confidence"),
        "action_evidence": action.get("evidence"),
        "landmarks_usable": quality.get("confident"),
        "landmarks_total": quality.get("total"),
        "pose_usable": quality.get("usable"),
    }


def enroll_identity(image_data: str, name: str) -> dict[str, Any]:
    clean_name = " ".join(str(name or "").split())[:80]
    if not clean_name:
        return {"status": "error", "message": "身份名称不能为空。", "persisted": False}
    image = _decode_image(image_data)
    faces = _detect_faces(image)
    if not faces:
        return {"status": "error", "message": "没有可靠检测到人脸，未登记。", "persisted": False}
    embedding = _embedding(_face_crop(image, faces[0]), face=faces[0], image=image)
    record = {"id": uuid.uuid4().hex, "name": clean_name, "embedding": embedding, "created_at": int(time.time())}
    with _identity_lock:
        identities = [item for item in _read_identities() if item.get("name") != clean_name]
        identities.append(record)
        _write_identities(identities)
    return {"status": "success", "id": record["id"], "name": clean_name, "persisted": True, "stored": "embedding_only"}


def list_identities() -> dict[str, Any]:
    return {"status": "success", "identities": [{"id": x.get("id"), "name": x.get("name"), "created_at": x.get("created_at")} for x in _read_identities()]}


def delete_identity(identity_id: str) -> dict[str, Any]:
    with _identity_lock:
        identities = _read_identities()
        remaining = [item for item in identities if item.get("id") != identity_id]
        if len(remaining) == len(identities):
            return {"status": "error", "message": "未找到该本地身份。"}
        _write_identities(remaining)
    return {"status": "success", "deleted": identity_id, "persisted": True}
