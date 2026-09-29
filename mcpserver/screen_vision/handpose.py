"""Local hand reading: what is *in* Jia's hand, not just where his hand is.

MoveNet gives a skeleton but no objects, so "drinking" and "holding a phone"
were the same reading - the code said so itself ("MoveNet cannot tell which")
and guessed from wrist height. A generic COCO detector is not the answer either:
cell phone and cup are small objects, which is precisely where those detectors
are weakest (NanoDet-Plus reports 0.107 AP on the small bucket), and they cost
four times as much as this.

Two Apache-2.0 models from OpenCV Zoo answer it directly and cheaply
(~10ms together on this machine, less than the YuNet detector already running):

* ``palm_detector.onnx`` - MediaPipe palm detection (2016 SSD anchors);
* ``hand_landmark.onnx`` - MediaPipe 21 hand landmarks.

The postprocessing below is a faithful port of the official OpenCV Zoo
implementation (``mp_palmdet.py`` / ``mp_handpose.py``), including the anchor
table, which is irregular enough that it ships as model data rather than as a
formula. Everything here is local: no frame leaves the machine, and only derived
angles are handed on.
"""

from __future__ import annotations

import json
import logging
import math
import os
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger("screen_vision.handpose")

try:
    import numpy as np
except ImportError:  # Optional until a local camera feature is requested.
    np = None  # type: ignore[assignment]

try:
    import cv2
except ImportError:  # Optional: the module reports itself unavailable instead.
    cv2 = None  # type: ignore[assignment]

# Weights ship alongside the other camera models; the anchors are model data.
PALM_MODEL = "palm_detector.onnx"
HAND_MODEL = "hand_landmark.onnx"
ANCHOR_FILE = "palm_anchors.json"

PALM_INPUT = 192
HAND_INPUT = 224

# Official defaults: 0.8 for the fp32 model (0.49 for the quantized one, which
# does not load on onnxruntime 1.20 at all - see the note in the module doc).
PALM_SCORE_THRESHOLD = float(os.getenv("MIYA_HAND_PALM_SCORE", "0.80"))
HAND_CONFIDENCE_THRESHOLD = float(os.getenv("MIYA_HAND_CONFIDENCE", "0.80"))
PALM_NMS_THRESHOLD = float(os.getenv("MIYA_HAND_NMS", "0.30"))
MAX_HANDS = int(os.getenv("MIYA_HAND_MAX", "2"))

# MediaPipe landmark indices, named so the geometry below reads as anatomy.
WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20

# One entry per finger: (mcp, pip, tip) for the four fingers, thumb handled apart.
FINGER_CHAINS = {
    "index": (INDEX_MCP, INDEX_PIP, INDEX_TIP),
    "middle": (MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP),
    "ring": (RING_MCP, RING_PIP, RING_TIP),
    "pinky": (PINKY_MCP, PINKY_PIP, PINKY_TIP),
}

_session_cache: dict[str, Any] = {}
_session_lock = threading.Lock()
# Sentinel for "the anchor table could not be loaded". Not ``None`` (that means
# "not tried yet") and not a falsy array, because an ndarray's truth value is
# ambiguous and would raise instead of reporting the feature as unavailable.
_ANCHORS_MISSING = "unavailable"
_anchor_cache: Any = None
_anchor_lock = threading.Lock()


def _model_dir() -> Path:
    configured = os.getenv("MIYA_CAMERA_MODEL_DIR", "").strip()
    return Path(configured).expanduser() if configured else Path(__file__).resolve().parents[2] / "models" / "camera_vision"


def _session(filename: str):
    """One cached ONNX session per model file."""
    if np is None:
        raise RuntimeError("本地手部识别需要 numpy")
    path = _model_dir() / filename
    if not path.is_file():
        raise FileNotFoundError(f"缺少本地模型: {path.name}")
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise RuntimeError("未安装 onnxruntime") from exc
    key = str(path.resolve())
    with _session_lock:
        if key not in _session_cache:
            _session_cache[key] = ort.InferenceSession(key, providers=["CPUExecutionProvider"])
        return _session_cache[key]


def _anchors():
    """The 2016 palm anchors, loaded once as model data."""
    global _anchor_cache
    if _anchor_cache is not None:
        return _anchor_cache
    with _anchor_lock:
        if _anchor_cache is not None:
            return _anchor_cache
        try:
            payload = json.loads((_model_dir() / ANCHOR_FILE).read_text(encoding="utf-8"))
            xs = np.asarray(payload["x"], dtype=np.float32)
            ys = np.asarray(payload["y"], dtype=np.float32)
            if xs.shape != ys.shape or xs.shape[0] != 2016:
                raise ValueError(f"anchor 数量不对: {xs.shape}")
            _anchor_cache = np.stack([xs, ys], axis=1)
        except Exception:  # noqa: BLE001 - a missing anchor file disables the feature
            logger.warning("[handpose] 无法读取 palm anchor 表，手部识别不可用", exc_info=True)
            _anchor_cache = _ANCHORS_MISSING
        return _anchor_cache


def available() -> bool:
    """Whether hand reading can run at all on this install."""
    if np is None or cv2 is None:
        return False
    anchors = _anchors()
    if anchors is _ANCHORS_MISSING or anchors is None:
        return False
    if not (_model_dir() / PALM_MODEL).is_file() or not (_model_dir() / HAND_MODEL).is_file():
        return False
    try:
        _session(PALM_MODEL)
        _session(HAND_MODEL)
    except Exception:  # noqa: BLE001
        return False
    return True


def capabilities() -> dict[str, Any]:
    """Diagnostics for the panel, mirroring ``discover_local_camera_capabilities``."""
    directory = _model_dir()
    return {
        "available": available(),
        "models": {PALM_MODEL: (directory / PALM_MODEL).is_file(),
                   HAND_MODEL: (directory / HAND_MODEL).is_file(),
                   ANCHOR_FILE: (directory / ANCHOR_FILE).is_file()},
        "palm_score_threshold": PALM_SCORE_THRESHOLD,
        "hand_confidence_threshold": HAND_CONFIDENCE_THRESHOLD,
        "message": "本地手部识别已就绪（手掌检测 + 21 点手部关键点）。"
        if available() else "本地手部模型不完整，手部识别暂不参与活动判断。",
    }


# --- palm detection --------------------------------------------------------


def _letterbox_palm(image):
    """Pad to a 192x192 square with the same centred padding the model expects."""
    pad_bias = np.array([0.0, 0.0])
    height, width = image.shape[:2]
    ratio = min(PALM_INPUT / height, PALM_INPUT / width)
    if height != PALM_INPUT or width != PALM_INPUT:
        ratio_size = (np.array([height, width]) * ratio).astype(np.int32)
        resized = cv2.resize(image, (ratio_size[1], ratio_size[0]))
        pad_h = PALM_INPUT - ratio_size[0]
        pad_w = PALM_INPUT - ratio_size[1]
        pad_bias[0] = left = pad_w // 2
        pad_bias[1] = top = pad_h // 2
        resized = cv2.copyMakeBorder(resized, top, pad_h - top, left, pad_w - left,
                                     cv2.BORDER_CONSTANT, value=(0, 0, 0))
    else:
        resized = image
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    return rgb[np.newaxis, :, :, :], (pad_bias / ratio).astype(np.int32)


def _nms(boxes, scores, score_threshold: float, nms_threshold: float, top_k: int = 5000):
    """Greedy NMS in the same shape OpenCV's ``dnn.NMSBoxes`` returns."""
    keep: list[int] = []
    order = [int(i) for i in np.argsort(-scores) if scores[i] >= score_threshold][:top_k]
    while order:
        best = order.pop(0)
        keep.append(best)
        kept = []
        for candidate in order:
            x1 = max(boxes[best][0], boxes[candidate][0])
            y1 = max(boxes[best][1], boxes[candidate][1])
            x2 = min(boxes[best][2], boxes[candidate][2])
            y2 = min(boxes[best][3], boxes[candidate][3])
            inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
            area_best = max(0.0, boxes[best][2] - boxes[best][0]) * max(0.0, boxes[best][3] - boxes[best][1])
            area_cand = max(0.0, boxes[candidate][2] - boxes[candidate][0]) * max(0.0, boxes[candidate][3] - boxes[candidate][1])
            union = area_best + area_cand - inter
            if union <= 0 or inter / union < nms_threshold:
                kept.append(candidate)
        order = kept
    return np.asarray(keep, dtype=int)


def detect_palms(image) -> list[dict[str, Any]]:
    """Palm boxes plus the 7 palm landmarks, in original-image coordinates.

    Each result is ``[x1, y1, x2, y2, <7 landmark pairs>, score]``, the layout the
    official implementation produces and the hand model consumes.
    """
    anchors = _anchors()
    if anchors is _ANCHORS_MISSING or anchors is None:
        return []
    session = _session(PALM_MODEL)
    blob, pad_bias = _letterbox_palm(image)
    outputs = session.run(None, {session.get_inputs()[0].name: blob})
    # The exported graph returns the raw logits: scores second, deltas first.
    score = np.asarray(outputs[1])[0, :, 0].astype(np.float64)
    box_delta = np.asarray(outputs[0])[0, :, 0:4]
    landmark_delta = np.asarray(outputs[0])[0, :, 4:]
    score = 1.0 / (1.0 + np.exp(-score))

    height, width = image.shape[:2]
    scale = max(height, width)
    cxy_delta = box_delta[:, :2] / PALM_INPUT
    wh_delta = box_delta[:, 2:] / PALM_INPUT
    xy1 = (cxy_delta - wh_delta / 2 + anchors) * scale
    xy2 = (cxy_delta + wh_delta / 2 + anchors) * scale
    boxes = np.concatenate([xy1, xy2], axis=1)
    boxes -= [pad_bias[0], pad_bias[1], pad_bias[0], pad_bias[1]]

    keep = _nms(boxes, score, PALM_SCORE_THRESHOLD, PALM_NMS_THRESHOLD)
    if len(keep) == 0:
        return []
    keep = keep[:MAX_HANDS]
    selected_score = score[keep]
    selected_box = boxes[keep]

    landmarks = landmark_delta[keep].reshape(-1, 7, 2) / PALM_INPUT
    landmarks += anchors[keep][:, np.newaxis, :]
    landmarks *= scale
    landmarks -= pad_bias

    results: list[dict[str, Any]] = []
    for index in range(len(keep)):
        entry = np.concatenate([selected_box[index], landmarks[index].reshape(-1),
                                [selected_score[index]]])
        results.append({
            # x1, y1, x2, y2 in original pixels, then 7 palm landmarks.
            "box": [float(v) for v in entry[:4]],
            "landmarks": [[float(p[0]), float(p[1])] for p in landmarks[index]],
            "score": float(selected_score[index]),
        })
    return results


# --- hand landmarks --------------------------------------------------------


def _crop_and_pad(image, box, *, for_rotation: bool):
    """Official palm-box shift/enlarge, then crop and square-pad."""
    shift_vector = np.array([0, 0] if for_rotation else [0, -0.4]) * (box[1] - box[0])
    box = box + shift_vector
    center = np.sum(box, axis=0) / 2
    wh = box[1] - box[0]
    half = wh * (4 if for_rotation else 3) / 2
    box = np.array([center - half, center + half]).astype(np.int32)
    box[:, 0] = np.clip(box[:, 0], 0, image.shape[1])
    box[:, 1] = np.clip(box[:, 1], 0, image.shape[0])
    crop = image[box[0][1]:box[1][1], box[0][0]:box[1][0], :]
    if crop.size == 0:
        return None, None, None
    side = int(np.linalg.norm(crop.shape[:2]) if for_rotation else max(crop.shape[:2]))
    pad_h = side - crop.shape[0]
    pad_w = side - crop.shape[1]
    left, top = pad_w // 2, pad_h // 2
    crop = cv2.copyMakeBorder(crop, top, pad_h - top, left, pad_w - left,
                              cv2.BORDER_CONSTANT, value=(0, 0, 0))
    return crop, box, box[0] - [left, top]


def _hand_blob(image, palm: dict[str, Any]):
    """Rotate the hand upright and cut the 224x224 blob the model expects."""
    box = np.asarray(palm["box"], dtype=np.float64).reshape(2, 2)
    crop, box, bias = _crop_and_pad(image, box, for_rotation=True)
    if crop is None:
        return None
    crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    pad_bias = np.array([0, 0], dtype=np.int32) + bias

    box = box - pad_bias
    palm_landmarks = np.asarray(palm["landmarks"], dtype=np.float64) - pad_bias
    base = palm_landmarks[0]        # palm base
    middle = palm_landmarks[2]      # middle finger base
    radians = np.pi / 2 - np.arctan2(-(middle[1] - base[1]), middle[0] - base[0])
    radians = radians - 2 * np.pi * np.floor((radians + np.pi) / (2 * np.pi))
    angle = np.rad2deg(radians)

    center = np.sum(box, axis=0) / 2
    rotation = cv2.getRotationMatrix2D(tuple(center), angle, 1.0)
    rotated = cv2.warpAffine(crop, rotation, (crop.shape[1], crop.shape[0]))

    homogeneous = np.c_[palm_landmarks, np.ones(palm_landmarks.shape[0])]
    rotated_landmarks = np.array([np.dot(homogeneous, rotation[0]),
                                  np.dot(homogeneous, rotation[1])])
    rotated_box = np.array([np.amin(rotated_landmarks, axis=1),
                            np.amax(rotated_landmarks, axis=1)])
    cut, rotated_box, _ = _crop_and_pad(rotated, rotated_box, for_rotation=False)
    if cut is None:
        return None
    blob = cv2.resize(cut, (HAND_INPUT, HAND_INPUT), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    return blob[np.newaxis, :, :, :], rotated_box, angle, rotation, pad_bias


def detect_hand(image, palm: dict[str, Any]) -> dict[str, Any] | None:
    """21 landmarks for one palm, in original-image pixel coordinates.

    Returns ``None`` when the model is not confident, which is the honest answer
    for a partly visible or fast-moving hand.
    """
    prepared = _hand_blob(image, palm)
    if prepared is None:
        return None
    blob, rotated_box, angle, rotation, pad_bias = prepared
    session = _session(HAND_MODEL)
    outputs = session.run(None, {session.get_inputs()[0].name: blob})
    landmarks, confidence, handedness, world = outputs
    confidence = float(np.asarray(confidence)[0][0])
    if confidence < HAND_CONFIDENCE_THRESHOLD:
        return None

    points = np.asarray(landmarks)[0].reshape(-1, 3).astype(np.float64)
    wh_rotated = rotated_box[1] - rotated_box[0]
    scale_factor = wh_rotated / HAND_INPUT
    points[:, :2] = (points[:, :2] - HAND_INPUT / 2) * max(scale_factor)
    points[:, 2] = points[:, 2] * max(scale_factor)

    coords_rotation = cv2.getRotationMatrix2D((0, 0), angle, 1.0)
    rotated = np.dot(points[:, :2], coords_rotation[:, :2])
    rotated = np.c_[rotated, points[:, 2]]

    rotation_component = np.array([[rotation[0][0], rotation[1][0]],
                                   [rotation[0][1], rotation[1][1]]])
    translation = np.array([rotation[0][2], rotation[1][2]])
    inverted_translation = np.array([-np.dot(rotation_component[0], translation),
                                     -np.dot(rotation_component[1], translation)])
    inverse_rotation = np.c_[rotation_component, inverted_translation]
    center = np.append(np.sum(rotated_box, axis=0) / 2, 1)
    original_center = np.array([np.dot(center, inverse_rotation[0]),
                                np.dot(center, inverse_rotation[1])])
    points[:, :2] = rotated[:, :2] + original_center + pad_bias

    height, width = image.shape[:2]
    screen = [[float(np.clip(p[0], 0, width)), float(np.clip(p[1], 0, height))]
              for p in points[:, :2]]
    handed_label = "right" if float(np.asarray(handedness)[0][0]) > 0.5 else "left"
    return {
        "landmarks": screen,
        "world": [[float(v) for v in row] for row in np.asarray(world)[0].reshape(-1, 3)],
        "confidence": round(confidence, 4),
        "handedness": handed_label,
    }


# --- geometry -------------------------------------------------------------


def _distance(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _angle(a, b, c) -> float:
    """Interior angle at ``b``, in degrees."""
    ba = (a[0] - b[0], a[1] - b[1])
    bc = (c[0] - b[0], c[1] - b[1])
    norm = math.hypot(*ba) * math.hypot(*bc)
    if norm <= 1e-9:
        return 180.0
    cosine = max(-1.0, min(1.0, (ba[0] * bc[0] + ba[1] * bc[1]) / norm))
    return math.degrees(math.acos(cosine))


def describe_hand(landmarks: list[list[float]]) -> dict[str, Any]:
    """Turn 21 points into a few honest, pose-invariant numbers.

    Everything is normalised by the palm length (wrist -> middle finger base), so
    a hand near or far from the camera reads the same. These are the quantities a
    person actually uses to tell "holding a phone" from "holding a cup": how
    curled the fingers are, how far the thumb is from the index finger, and which
    way the palm faces.
    """
    if not landmarks or len(landmarks) < 21:
        return {"available": False, "reason": "手部关键点不足（需要 21 点）"}
    points = [(float(p[0]), float(p[1])) for p in landmarks[:21]]
    palm_length = max(_distance(points[WRIST], points[MIDDLE_MCP]), 1e-6)

    curl: dict[str, float] = {}
    for name, (mcp, pip, tip) in FINGER_CHAINS.items():
        # A straight finger is ~180 degrees at the middle joint; a curled one
        # folds well under 140.
        curl[name] = round(_angle(points[mcp], points[pip], points[tip]), 1)
    extended = [name for name, angle in curl.items() if angle >= 150.0]
    curved = [name for name, angle in curl.items() if angle < 120.0]

    # How far the fingertips reach past the palm base: a fist pulls them in, an
    # open hand pushes them out. Scale-free, so distance does not matter.
    tip_reach = sum(_distance(points[WRIST], points[FINGER_CHAINS[name][2]])
                    for name in FINGER_CHAINS) / 4.0 / palm_length
    spread = sum(_distance(points[FINGER_CHAINS[name][2]], points[FINGER_CHAINS[other][2]])
                 for name, other in (("index", "pinky"), ("middle", "ring"))) / 2.0 / palm_length
    pinch = _distance(points[THUMB_TIP], points[INDEX_TIP]) / palm_length
    thumb_out = _distance(points[THUMB_TIP], points[PINKY_MCP]) / palm_length

    return {
        "available": True,
        "finger_curl_degrees": curl,
        "extended_fingers": extended,
        "curved_fingers": curved,
        "extended_count": len(extended),
        "tip_reach_ratio": round(tip_reach, 3),
        "finger_spread_ratio": round(spread, 3),
        "pinch_ratio": round(pinch, 3),
        "thumb_out_ratio": round(thumb_out, 3),
        "palm_length_px": round(palm_length, 1),
    }


# --- the reading the rest of the system consumes ---------------------------


def hand_shape_label(shape: dict[str, Any]) -> str:
    """A short, honest name for the hand's posture.

    Only shapes the landmarks actually support are named. Whether the gripped
    object is a phone, a cup or a pen is *not* claimed here: the landmarks cannot
    see objects, so that inference belongs to the interpreter, which gets the
    numbers. Guessing it in code is what produced the old
    "wrist above the shoulder, therefore a phone" rule.
    """
    if not shape or not shape.get("available"):
        return ""
    extended = int(shape.get("extended_count") or 0)
    curved = len(shape.get("curved_fingers") or [])
    if extended == 0 and curved >= 3:
        return "手握成拳"
    if extended >= 4:
        return "手掌张开"
    if float(shape.get("pinch_ratio") or 9.9) <= 0.35 and extended <= 2:
        return "拇指和食指捏在一起"
    if extended == 1:
        return "只伸出一根手指"
    if extended >= 2:
        return "半握着手"
    return "手放松着"


def describe_hands(result: dict[str, Any] | None) -> str:
    """One plain sentence for the natural-language message, or empty."""
    if not result or not result.get("available"):
        return ""
    labels = [hand_shape_label(hand.get("shape") or {}) for hand in result.get("hands") or []]
    labels = [label for label in labels if label]
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    return "两只手：" + "、".join(labels)


# --- the reading the rest of the system consumes ---------------------------


def read_hands(image) -> dict[str, Any]:
    """Every hand in one BGR frame, with its derived shape.

    Any failure returns ``available: False`` with a reason rather than raising:
    hand reading is an extra sense, and losing it must never break the camera
    loop that already worked without it.
    """
    if image is None or np is None or cv2 is None:
        return {"available": False, "reason": "本地手部识别不可用", "hands": []}
    try:
        palms = detect_palms(image)
    except Exception as exc:  # noqa: BLE001
        logger.debug("[handpose] 手掌检测失败", exc_info=True)
        return {"available": False, "reason": f"手掌检测失败: {type(exc).__name__}", "hands": []}
    hands: list[dict[str, Any]] = []
    for palm in palms:
        try:
            hand = detect_hand(image, palm)
        except Exception:  # noqa: BLE001 - one bad hand must not stop the loop
            logger.debug("[handpose] 手部关键点推理失败", exc_info=True)
            continue
        if hand is None:
            continue
        shape = describe_hand(hand["landmarks"])
        if not shape.get("available"):
            continue
        hands.append({**hand, "shape": shape, "palm_box": palm["box"], "palm_score": palm["score"]})
    return {"available": True, "hands": hands, "count": len(hands)}
