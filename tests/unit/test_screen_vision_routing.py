"""Vision routing tests: hybrid deepening and cloud-quota degradation."""

from __future__ import annotations

import asyncio
import json

import pytest

from mcpserver.screen_vision import service as vision_service
from mcpserver.screen_vision.service import ScreenVisionService

_LOCAL_OK = {
    "status": "success",
    "message": "本地姿态分析完成；动作线索：敲键盘或操作鼠标（置信度 0.70）。",
    "source": "camera_local",
    "persisted": False,
    "faces": 0,
    "observations": [{"action": {"kind": "typing", "label": "敲键盘或操作鼠标", "confidence": 0.7}}],
}


@pytest.fixture(autouse=True)
def _clear_cloud_cooldown():
    """Cloud state is module-global; never leak it between tests."""
    vision_service._note_cloud_success()
    yield
    vision_service._note_cloud_success()


def _local_ready(monkeypatch, service, result=None):
    monkeypatch.setattr(service, "_camera_analysis_mode", lambda: "hybrid")
    monkeypatch.setattr("mcpserver.screen_vision.service.discover_local_camera_capabilities", lambda: {
        "status": "ready",
        "features": {"face_detection": {"available": True}, "identity": {"available": True},
                     "emotion": {"available": True}, "pose": {"available": True}},
    })
    monkeypatch.setattr("mcpserver.screen_vision.service.analyze_local_frame",
                        lambda *_args, **_kwargs: dict(result or _LOCAL_OK))


def test_hybrid_keeps_local_result_for_boilerplate_companion_query(monkeypatch):
    """The companion loop's own prompt must not spend a cloud call."""
    service = ScreenVisionService()
    _local_ready(monkeypatch, service)

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("boilerplate companion frames must stay local")

    monkeypatch.setattr(service, "_analyze_with_miya_vision", fail_if_called)
    result = json.loads(asyncio.run(service.handle_handoff({
        "tool_name": "look_me",
        "image_data": "data:image/jpeg;base64,ZmFrZQ==",
        "query": "请观察我当前的画面，描述可见的姿态、动作和环境。",
        "local_only": False,
    })))

    assert result["source"] == "camera_local"


def test_hybrid_deepens_with_cloud_when_a_semantic_question_is_asked(monkeypatch):
    service = ScreenVisionService()
    _local_ready(monkeypatch, service)
    monkeypatch.setattr("mcpserver.screen_vision.service.compress_screenshot_data_url",
                        lambda image, **_kwargs: image)
    captured = {}

    async def fake_analyze(query, image_url):
        captured["query"] = query
        return "桌上有一杯没喝完的咖啡。"

    monkeypatch.setattr(service, "_analyze_with_miya_vision", fake_analyze)
    result = json.loads(asyncio.run(service.handle_handoff({
        "tool_name": "look_me",
        "image_data": "data:image/jpeg;base64,ZmFrZQ==",
        "query": "看看我桌上有什么，我是不是该休息了？",
        "local_only": False,
    })))

    assert result["source"] == "camera_local_and_cloud"
    assert result["sources"] == ["camera_local", "camera_cloud"]
    assert "桌上有一杯没喝完的咖啡。" in result["message"]
    # The local geometry must be handed to the model as grounding.
    assert "本地模型已经给出这些几何线索" in captured["query"]


def test_hybrid_keeps_local_when_cloud_deepening_fails(monkeypatch):
    """A failed cloud leg must never lose the local observation."""
    service = ScreenVisionService()
    _local_ready(monkeypatch, service)
    monkeypatch.setattr("mcpserver.screen_vision.service.compress_screenshot_data_url",
                        lambda image, **_kwargs: image)

    async def boom(*_args, **_kwargs):
        raise RuntimeError("视觉 LLM 返回 429: 余额不足")

    monkeypatch.setattr(service, "_analyze_with_miya_vision", boom)
    result = json.loads(asyncio.run(service.handle_handoff({
        "tool_name": "look_me",
        "image_data": "data:image/jpeg;base64,ZmFrZQ==",
        "query": "看看我桌上有什么东西？",
        "local_only": False,
    })))

    assert result["status"] == "success"
    assert result["source"] == "camera_local"
    assert "429" in result["cloud_skipped"]


def test_quota_failure_arms_a_cooldown_and_degrades_without_uploading(monkeypatch):
    service = ScreenVisionService()
    monkeypatch.setattr(service, "_camera_analysis_mode", lambda: "cloud")
    vision_service._note_cloud_failure(429, '{"error":{"code":"1113","message":"余额不足"}}')

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("a provider in cooldown must not be called again")

    monkeypatch.setattr(service, "_analyze_with_miya_vision", fail_if_called)
    result = json.loads(asyncio.run(service.handle_handoff({
        "tool_name": "look_me",
        "image_data": "data:image/jpeg;base64,ZmFrZQ==",
        "query": "看看我在做什么",
    })))

    assert result["status"] == "partial"
    assert result["source"] == "camera_local_degraded"
    assert "没有上传画面" in result["message"]


def test_transient_cloud_error_does_not_arm_the_cooldown():
    vision_service._note_cloud_failure(500, "internal error")
    blocked, _reason = vision_service._cloud_blocked()
    assert blocked is False


def test_cloud_success_clears_a_previous_cooldown():
    vision_service._note_cloud_failure(402, "no credit")
    assert vision_service._cloud_blocked()[0] is True
    vision_service._note_cloud_success()
    assert vision_service._cloud_blocked()[0] is False


def test_blank_camera_frame_is_reported_as_a_device_problem(monkeypatch):
    """A virtual camera returning black must not be read as an empty room."""
    import io

    from PIL import Image

    from mcpserver.screen_vision import local_camera

    buffer = io.BytesIO()
    Image.new("RGB", (320, 240), (0, 0, 0)).save(buffer, format="JPEG")
    import base64

    data_url = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()

    result = local_camera.analyze_local_frame(data_url, identity=False, pose=False)
    assert result["status"] == "error"
    assert result["blank_frame"] is True
    assert "全黑" in result["message"]


def test_low_confidence_skeleton_is_not_labelled_as_an_action():
    from mcpserver.screen_vision import local_camera

    noisy = {"keypoints": [{"x": 0.5, "y": 0.5, "confidence": 0.12} for _ in range(17)]}
    result = local_camera.classify_pose_action([noisy] * 4, noisy)
    assert result["kind"] == "low_confidence"
    assert result["confidence"] == 0.0
    # The reason must read like a sentence, not like a log line.
    assert "说不准" in result["evidence"]


def test_usable_skeleton_still_reaches_the_action_classifier():
    from mcpserver.screen_vision import local_camera

    strong = {"keypoints": [{"x": 0.5, "y": 0.5, "confidence": 0.9} for _ in range(17)]}
    result = local_camera.classify_pose_action([strong] * 4, strong)
    assert result["kind"] != "unknown"


def test_wave_detection_does_not_raise_on_adjacent_pairs():
    """Regression: zip(strict=True) over xs and xs[1:] aborted wave detection."""
    from mcpserver.screen_vision import local_camera

    def pose(x: float) -> dict:
        points = [{"x": 0.5, "y": 0.5, "confidence": 0.9} for _ in range(17)]
        points[5].update(x=0.4, y=0.5)
        points[6].update(x=0.6, y=0.5)
        points[9].update(x=x, y=0.3)
        points[10].update(x=0.7, y=0.6)
        return {"keypoints": points}

    history = [pose(x) for x in (0.32, 0.55, 0.34, 0.57)]
    result = local_camera.classify_pose_action(history, pose(0.33))
    assert result["kind"] == "wave"
