"""Local ONNX camera inference for Miya Vision.

The camera boundary is intentionally small: callers provide one data URL,
inference happens in-process, and only derived values leave this module.
Identity enrollment stores normalized embeddings, never image bytes.
"""

from __future__ import annotations

import base64
import binascii
import io
import json
import logging
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
EMOTION_LABELS = ("中性", "开心", "悲伤", "惊讶", "恐惧", "厌恶", "愤怒", "轻蔑")
IDENTITY_THRESHOLD = float(os.getenv("MIYA_CAMERA_IDENTITY_THRESHOLD", "0.48"))
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
_identity_lock = threading.Lock()


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
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as exc:
        raise ValueError("摄像头画面无法解码。") from exc


def _input_size(session, default: tuple[int, int]) -> tuple[int, int]:
    shape = session.get_inputs()[0].shape
    if len(shape) >= 4 and isinstance(shape[-1], int) and isinstance(shape[-2], int):
        return int(shape[-1]), int(shape[-2])
    return default


def _tensor(image: Image.Image, session, default_size: tuple[int, int], *, gray=False,
            scale=1 / 128.0, mean=127.5, bgr=False) -> np.ndarray:
    width, height = _input_size(session, default_size)
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


def _detect_faces(image: Image.Image) -> list[dict[str, float]]:
    session = _session("face_detection")
    width, height = _input_size(session, (320, 320))
    resized = image.resize((width, height), Image.Resampling.BILINEAR)
    array = np.asarray(resized, dtype=np.float32)[:, :, ::-1].transpose(2, 0, 1)[None, ...]
    faces: list[dict[str, float]] = []
    scale_x, scale_y = image.width / width, image.height / height
    outputs = _run(session, array)
    # The OpenCV Zoo YuNet export exposes three separate stride heads rather
    # than the post-processed [x,y,w,h,landmarks,score] matrix.
    if len(outputs) >= 12:
        for head, stride in zip((0, 1, 2), (8, 16, 32)):
            cls = np.asarray(outputs[head]).reshape(-1)
            obj = np.asarray(outputs[3 + head]).reshape(-1)
            boxes = np.asarray(outputs[6 + head]).reshape((-1, 4))
            grid = int(round(np.sqrt(len(cls))))
            for index, (class_score, object_score) in enumerate(zip(cls, obj)):
                score = float(class_score * object_score)
                if score < 0.55 or grid <= 0:
                    continue
                row, column = divmod(index, grid)
                cx, cy = (column + 0.5) * stride, (row + 0.5) * stride
                left, top, right, bottom = map(float, boxes[index])
                # YuNet bbox heads are distance deltas in stride units.
                if max(abs(left), abs(top), abs(right), abs(bottom)) < 8:
                    left, top, right, bottom = left * stride, top * stride, right * stride, bottom * stride
                x, y = cx - abs(left), cy - abs(top)
                box_w, box_h = abs(left) + abs(right), abs(top) + abs(bottom)
                faces.append({"x": max(0.0, x * scale_x), "y": max(0.0, y * scale_y),
                              "width": min(float(image.width), box_w * scale_x),
                              "height": min(float(image.height), box_h * scale_y), "score": score})
    else:
        output = np.asarray(outputs[0])
        raw = output.reshape((-1, output.shape[-1]))
        for row in raw:
            if row.size < 5:
                continue
            score = float(row[14] if row.size >= 15 else row[4])
            if score < 0.55:
                continue
            x, y, box_w, box_h = map(float, row[:4])
            if box_w <= 1.0 and box_h <= 1.0:
                x, box_w = x * width, box_w * width
                y, box_h = y * height, box_h * height
            faces.append({"x": max(0.0, x * scale_x), "y": max(0.0, y * scale_y),
                          "width": min(float(image.width), box_w * scale_x),
                          "height": min(float(image.height), box_h * scale_y), "score": score})
    return sorted(faces, key=lambda face: face["score"], reverse=True)


def _face_crop(image: Image.Image, face: dict[str, float]) -> Image.Image:
    left, top = int(face["x"]), int(face["y"])
    right, bottom = int(face["x"] + face["width"]), int(face["y"] + face["height"])
    padding = int(max(face["width"], face["height"]) * 0.12)
    return image.crop((max(0, left - padding), max(0, top - padding),
                       min(image.width, right + padding), min(image.height, bottom + padding)))


def _embedding(face_image: Image.Image) -> list[float]:
    session = _session("identity")
    output = np.asarray(_run(session, _tensor(face_image, session, (112, 112), bgr=True))[0]).reshape(-1)
    norm = float(np.linalg.norm(output))
    if norm == 0 or not np.isfinite(norm):
        raise RuntimeError("人脸特征模型返回了无效向量")
    return (output / norm).astype(np.float32).tolist()


def _emotion(face_image: Image.Image) -> dict[str, Any]:
    session = _session("emotion")
    output = np.asarray(_run(session, _tensor(face_image, session, (48, 48), gray=True, scale=1 / 255.0, mean=0))[0]).reshape(-1)
    shifted = output - np.max(output)
    probabilities = np.exp(shifted) / np.maximum(np.exp(shifted).sum(), 1e-8)
    index = int(np.argmax(probabilities))
    label = EMOTION_LABELS[index] if index < len(EMOTION_LABELS) else f"类别 {index + 1}"
    return {"label": label, "confidence": round(float(probabilities[index]), 4),
            "distribution": [round(float(x), 4) for x in probabilities]}


def _pose(image: Image.Image) -> dict[str, Any]:
    session = _session("pose")
    # The verified MoveNet conversion uses NHWC uint/int32 pixels, unlike the
    # NCHW float tensors used by the face models above.
    shape = session.get_inputs()[0].shape
    height = int(shape[1]) if isinstance(shape[1], int) else 192
    width = int(shape[2]) if isinstance(shape[2], int) else 192
    converted = image.resize((width, height), Image.Resampling.BILINEAR)
    tensor = np.asarray(converted, dtype=np.int32)[None, ...]
    output = np.asarray(_run(session, tensor)[0]).reshape((-1, 3))
    return {"keypoints": [{"x": round(float(point[1]), 5), "y": round(float(point[0]), 5),
                            "confidence": round(float(point[2]), 4)} for point in output]}


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


def classify_pose_action(pose_history: list[dict[str, Any]] | None, current_pose: dict[str, Any]) -> dict[str, Any]:
    """Classify a small set of observable actions without a cloud call.

    MoveNet supplies a stable 17-point skeleton but no temporal action label.
    This deliberately conservative classifier uses at most the last 12 derived
    skeletons.  It is a cheap local fallback, not a claim of full activity
    recognition or intent inference.
    """
    history = [item for item in (pose_history or []) if isinstance(item, (dict, list))][-11:]
    sequence = history + [current_pose]
    valid = sum(1 for item in sequence if _keypoint(item, 5) or _keypoint(item, 6))
    if valid < 1:
        return {"label": "未识别", "confidence": 0.0, "kind": "unknown", "evidence": "关键点不足"}

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

    latest = sequence[-1]
    left_shoulder, right_shoulder = point(5, latest), point(6, latest)
    left_wrist, right_wrist = point(9, latest), point(10, latest)
    nose = point(0, latest)
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
        deltas = [b - a for a, b in zip(xs, xs[1:]) if abs(b - a) >= 0.018]
        changes = sum(1 for a, b in zip(deltas, deltas[1:]) if a * b < 0)
        span = max(xs) - min(xs)
        if changes >= 2 and span >= 0.08:
            wave_scores.append(min(0.95, 0.60 + changes * 0.07 + span * 0.5))
    if wave_scores:
        return {"label": "挥手", "confidence": round(max(wave_scores), 3), "kind": "wave", "evidence": "手腕横向往返"}

    # Clapping is a short convergence event: hands were apart and are now
    # close together above the hips. It needs both wrists, so it degrades
    # quietly when the camera only sees one arm.
    current_gap = wrist_gap(latest)
    previous_gaps = [gap for item in sequence[:-1] if (gap := wrist_gap(item)) is not None]
    if current_gap is not None and current_gap <= 0.14 and any(gap >= 0.20 for gap in previous_gaps[-5:]):
        return {"label": "鼓掌", "confidence": 0.78, "kind": "clap", "evidence": "双手快速靠拢"}

    if raised:
        label = "双手举起" if len(raised) > 1 else f"{raised[0]}举起"
        return {"label": label, "confidence": round(min(0.92, 0.68 + 0.06 * len(raised)), 3), "kind": "raised_hand", "evidence": "手腕高于肩部"}

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
            return {"label": "坐下", "confidence": 0.76, "kind": "sit_down", "evidence": "髋部与膝部高度收拢"}
        if current_posture == "standing" and "sitting" in prior_postures[-4:]:
            return {"label": "起身", "confidence": 0.76, "kind": "stand_up", "evidence": "髋部重新高于膝部"}

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
    switches = sum(1 for left, right in zip(walk_states, walk_states[1:]) if left != right)
    if len(walk_states) >= 5 and switches >= 2:
        return {"label": "走动", "confidence": round(min(0.88, 0.62 + switches * 0.05), 3), "kind": "walk", "evidence": "双脚交替移动"}

    if current_posture == "sitting":
        return {"label": "坐着", "confidence": 0.70, "kind": "sitting", "evidence": "髋部与膝部高度接近"}
    if current_posture == "standing":
        return {"label": "站立", "confidence": 0.70, "kind": "standing", "evidence": "膝部明显低于髋部"}

    # Head nod: vertical nose movement with comparatively little horizontal drift.
    noses = [p for item in sequence if (p := point(0, item)) and p[2] >= 0.30]
    if len(noses) >= 4:
        y_span = max(p[1] for p in noses) - min(p[1] for p in noses)
        x_span = max(p[0] for p in noses) - min(p[0] for p in noses)
        if y_span >= 0.09 and x_span <= max(0.12, y_span * 1.4):
            return {"label": "点头或低头", "confidence": round(min(0.86, 0.57 + y_span), 3), "kind": "nod", "evidence": "头部上下变化"}

    # Large hip displacement is a useful, privacy-preserving cue for body movement.
    hips = []
    for item in sequence:
        candidates = [p for p in (point(11, item), point(12, item)) if p and p[2] >= 0.25]
        if candidates:
            hips.append((sum(p[0] for p in candidates) / len(candidates), sum(p[1] for p in candidates) / len(candidates)))
    if len(hips) >= 3:
        displacement = max(((x - hips[0][0]) ** 2 + (y - hips[0][1]) ** 2) ** 0.5 for x, y in hips)
        if displacement >= 0.10:
            return {"label": "身体移动", "confidence": round(min(0.82, 0.52 + displacement), 3), "kind": "body_motion", "evidence": "髋部位置变化"}

    return {"label": "姿态稳定", "confidence": 0.62, "kind": "still", "evidence": "关键点变化较小"}


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
        "privacy": "local_only" if face_ready else "frame_delta_local_only",
        "message": "本地人脸、身份、表情、姿态与短时序动作识别已就绪。" if model_ready else "本地模型尚未完整安装；仅已安装的能力可用，不会回退到云端。",
    }


def local_only_error() -> dict[str, Any]:
    capabilities = discover_local_camera_capabilities()
    return {"status": "unavailable", "message": capabilities["message"], "capabilities": capabilities, "persisted": False}


def analyze_local_frame(
    image_data: str,
    *,
    identity=True,
    emotion=False,
    pose=False,
    pose_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    image = _decode_image(image_data)
    # Pose-only companion ticks should not require a face detector. This keeps
    # the action path useful for a partial silhouette or a back-facing pose.
    faces = _detect_faces(image) if identity or emotion else []
    result: dict[str, Any] = {"status": "success", "source": "camera_local", "persisted": False,
                              "faces": len(faces), "observations": []}
    if not faces and not pose:
        result["message"] = "本地模型没有可靠检测到人脸。"
        return result
    face_image = _face_crop(image, faces[0]) if faces else None
    observation: dict[str, Any] = {"box": faces[0]} if faces else {}
    if face_image is not None and identity:
        embedding = _embedding(face_image)
        observation["identity"] = _match_identity(embedding, _read_identities()) or {"name": "未知", "similarity": 0.0}
    if face_image is not None and emotion:
        observation["emotion"] = _emotion(face_image)
    if pose:
        observation["pose"] = _pose(image)
        observation["action"] = classify_pose_action(pose_history, observation["pose"])
    result["observations"].append(observation)
    parts = ["本地摄像头分析完成"] if faces else ["本地姿态分析完成"]
    if "identity" in observation:
        parts.append(f"身份：{observation['identity'].get('name', '未知')}（相似度 {observation['identity'].get('similarity', 0):.2f}）")
    if "emotion" in observation:
        parts.append(f"表情线索：{observation['emotion']['label']}（置信度 {observation['emotion']['confidence']:.2f}）")
    if "pose" in observation:
        parts.append(f"姿态关键点：{len(observation['pose'].get('keypoints', []))} 个")
    if "action" in observation:
        action = observation["action"]
        parts.append(f"动作线索：{action.get('label', '未识别')}（置信度 {action.get('confidence', 0):.2f}）")
    result["message"] = "；".join(parts) + "。"
    return result


def enroll_identity(image_data: str, name: str) -> dict[str, Any]:
    clean_name = " ".join(str(name or "").split())[:80]
    if not clean_name:
        return {"status": "error", "message": "身份名称不能为空。", "persisted": False}
    image = _decode_image(image_data)
    faces = _detect_faces(image)
    if not faces:
        return {"status": "error", "message": "没有可靠检测到人脸，未登记。", "persisted": False}
    embedding = _embedding(_face_crop(image, faces[0]))
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
