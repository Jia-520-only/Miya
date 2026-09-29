import asyncio
import json
from pathlib import Path

import pytest

from mcpserver.screen_vision.service import ScreenVisionService
from mcpserver.screen_vision import local_camera
from core.vision_context import VisionContextStore, record_camera_observation
# Import the real module object: the service reaches camera control through
# ``core.camera_control``, so a separately loaded copy would not be patched and
# the test would silently read the developer's live control file instead.
from core import camera_control


@pytest.fixture(autouse=True)
def _no_live_camera_inventory(monkeypatch):
    """Keep capture-index selection independent of the developer's hardware.

    The camera manager remembers which indices really deliver frames, so without
    this a machine with a working second camera would change which index these
    tests exercise.
    """
    from mcpserver.screen_vision import camera_manager

    # The service uses the module-level singleton, so patch that instance.
    monkeypatch.setattr(camera_manager.get_camera_manager(), "usable_indices", lambda: [])


@pytest.fixture(autouse=True)
def _fresh_adaptive_state():
    """Learned mouth/pose state must not leak between tests."""
    local_camera.reset_adaptive_state()
    yield
    local_camera.reset_adaptive_state()


def _pose(*, left_wrist=(0.3, 0.6), right_wrist=(0.7, 0.6), nose=(0.5, 0.35)):
    # Every joint is confident: a realistic skeleton. The local classifier now
    # refuses to name an action from a mostly-unconfident skeleton, so fixtures
    # that assert a specific action must supply a usable one.
    points = [{"x": 0.5, "y": 0.5, "confidence": 0.9} for _ in range(17)]
    points[0].update(x=nose[0], y=nose[1])
    points[5].update(x=0.4, y=0.5)
    points[6].update(x=0.6, y=0.5)
    points[9].update(x=left_wrist[0], y=left_wrist[1])
    points[10].update(x=right_wrist[0], y=right_wrist[1])
    return {"keypoints": points}


def _body_pose(*, sitting=False, left_wrist=(0.3, 0.6), right_wrist=(0.7, 0.6), ankle_gap=0.28):
    pose = _pose(left_wrist=left_wrist, right_wrist=right_wrist)
    points = pose["keypoints"]
    points[5].update(x=0.4, y=0.36)
    points[6].update(x=0.6, y=0.36)
    hip_y = 0.57 if sitting else 0.52
    knee_y = 0.60 if sitting else 0.76
    points[11].update(x=0.44, y=hip_y)
    points[12].update(x=0.56, y=hip_y)
    points[13].update(x=0.40, y=knee_y)
    points[14].update(x=0.60, y=knee_y)
    points[15].update(x=0.44 - ankle_gap / 2, y=0.88)
    points[16].update(x=0.56 + ankle_gap / 2, y=0.88)
    return pose


def _frame_with_face(size: tuple[int, int] = (640, 480)):
    """A real image, so normalized face boxes must be converted to pixels."""
    from PIL import Image

    return Image.new("RGB", size, (140, 140, 140))


def _normalized_face(**overrides):
    """A YuNet-shaped detection: normalized [0,1] box plus 5 landmarks.

    Deliberately normalized, because that is what ``_detect_faces`` returns - and
    feeding those values to ``int()`` is what produced a 0x0 crop.
    """
    face = {"x": 0.35, "y": 0.20, "width": 0.30, "height": 0.40, "score": 0.95,
            "keypoints": [
                {"x": 0.60, "y": 0.30},   # right eye
                {"x": 0.40, "y": 0.30},   # left eye
                {"x": 0.50, "y": 0.40},   # nose
                {"x": 0.59, "y": 0.52},   # right mouth corner
                {"x": 0.41, "y": 0.52},   # left mouth corner
            ]}
    face.update(overrides)
    return face


def test_normalized_face_box_is_converted_to_pixels():
    """Regression: a normalized box fed to int() collapsed to a 0x0 crop.

    That empty crop was handed to the identity and emotion models, so both
    answered a constant - which is what "本地模型识别不准" actually was.
    """
    face = _normalized_face()
    crop = local_camera._face_crop(_frame_with_face(), face)
    # A 0.30 x 0.40 box on 640x480 is ~192x192 plus the margin.
    assert crop.width > 100 and crop.height > 100
    assert crop.width < 640 and crop.height < 480


def test_face_crop_rejects_a_box_it_cannot_convert():
    """A box that cannot yield a real area must fail loudly, not silently."""
    degenerate = _normalized_face(x=0.5, y=0.5, width=0.0, height=0.0)
    with pytest.raises(ValueError):
        local_camera._face_crop(_frame_with_face(), degenerate)
    with pytest.raises(ValueError):
        local_camera._face_crop(_frame_with_face(), {"x": "bad", "y": 0.2, "width": 0.3, "height": 0.4})


def test_two_different_frames_do_not_yield_the_same_face_crop():
    """The old bug made every frame crop to the same empty image."""
    from PIL import Image

    left_frame = Image.new("RGB", (640, 480), (10, 10, 10))
    right_frame = Image.new("RGB", (640, 480), (250, 250, 250))
    face = _normalized_face()
    assert local_camera._face_crop(left_frame, face).tobytes() \
        != local_camera._face_crop(right_frame, face).tobytes()


def test_analysis_reports_a_crop_failure_instead_of_feeding_a_black_image(monkeypatch):
    monkeypatch.setattr(local_camera, "_decode_image", lambda _d: _frame_with_face())
    monkeypatch.setattr(local_camera, "frame_luminance", lambda _i: 90.0)
    monkeypatch.setattr(local_camera, "_detect_faces",
                        lambda _i, threshold=None: [_normalized_face(width=0.0, height=0.0)])

    def must_not_run(*_args, **_kwargs):
        raise AssertionError("身份/表情模型不能拿到无效裁剪")

    monkeypatch.setattr(local_camera, "_embedding", must_not_run)
    monkeypatch.setattr(local_camera, "_emotion", must_not_run)

    result = local_camera.analyze_local_frame(
        "data:image/jpeg;base64,ZmFrZQ==", identity=True, emotion=True, pose=False
    )
    assert "face_crop_error" in result
    assert "identity" not in result["observations"][0]
    assert "emotion" not in result["observations"][0]


def test_autonomous_analysis_uses_the_shared_pose_sequence(monkeypatch):
    """The backend path must supply temporal history it never sent before.

    Without it every temporal branch in the classifier was unreachable, so the
    observation loop could only ever report a static posture.
    """
    monkeypatch.setattr(local_camera, "_decode_image", lambda _d: _frame_with_face())
    monkeypatch.setattr(local_camera, "frame_luminance", lambda _i: 90.0)
    monkeypatch.setattr(local_camera, "_detect_faces", lambda _i, threshold=None: [])
    monkeypatch.setattr(local_camera, "_pose", lambda _i: _pose())

    # Stand in for the persistent reader's dense sampling.
    for offset in range(6):
        local_camera._pose_sequence.record(_pose(left_wrist=(0.30 + 0.02 * offset, 0.30)),
                                           key=0, at=1000.0 + offset, force=True)

    result = local_camera.analyze_local_frame(
        "data:image/jpeg;base64,ZmFrZQ==", identity=False, pose=True, pose_key=0
    )
    action = result["observations"][0]["action"]
    # A history was available, so this is not the "no skeleton" bail-out.
    assert action["kind"] != "low_confidence"


def test_observe_frame_pose_is_rate_limited():
    """Sampling must be throttled by the interval, not run per frame at 20Hz."""
    import numpy as np

    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    calls: list[int] = []

    def fake_keypoints(_frame):
        calls.append(1)
        return [{"x": 0.5, "y": 0.5, "confidence": 0.9} for _ in range(17)]

    original = local_camera._keypoints_from_bgr
    local_camera._keypoints_from_bgr = fake_keypoints
    try:
        assert local_camera.observe_frame_pose(frame, key=0, at=100.0) is True
        assert local_camera.observe_frame_pose(frame, key=0, at=100.2) is False
        assert local_camera.observe_frame_pose(frame, key=0, at=100.0 + local_camera.POSE_SEQUENCE_SAMPLE_SECONDS) is True
    finally:
        local_camera._keypoints_from_bgr = original
    assert len(calls) == 2, "节流没有生效"


def test_pose_action_classifier_detects_raised_hand_and_wave():
    raised = local_camera.classify_pose_action([], _pose(left_wrist=(0.42, 0.2), right_wrist=(0.58, 0.2)))
    assert raised["kind"] == "raised_hand"
    assert "举起" in raised["label"]

    history = [_pose(left_wrist=(x, 0.3)) for x in (0.32, 0.55, 0.34, 0.57)]
    waved = local_camera.classify_pose_action(history, _pose(left_wrist=(0.33, 0.3)))
    assert waved["kind"] == "wave"
    assert "挥手" in waved["label"]


def test_pose_action_classifier_tells_a_stretch_apart_from_a_raise():
    """Arms high and opened outward is a stretch; high and together is a raise."""
    stretched = local_camera.classify_pose_action([], _pose(left_wrist=(0.16, 0.18), right_wrist=(0.84, 0.18)))
    assert stretched["kind"] == "stretch"
    assert "伸懒腰" in stretched["label"]


def test_pose_action_classifier_reports_resting_hands_not_typing():
    """Hands on the desk without travel must not be called typing."""
    still = _pose(left_wrist=(0.46, 0.56), right_wrist=(0.54, 0.56))
    result = local_camera.classify_pose_action([still] * 3, still)
    assert result["kind"] != "typing"


def test_pose_action_classifier_is_conservative_when_still():
    result = local_camera.classify_pose_action([_pose()] * 3, _pose())
    assert result["kind"] == "still"
    assert result["confidence"] < 0.7


def test_pose_action_classifier_detects_clap_and_posture_transitions():
    clapped = local_camera.classify_pose_action(
        [_body_pose(left_wrist=(0.25, 0.5), right_wrist=(0.75, 0.5))],
        _body_pose(left_wrist=(0.46, 0.5), right_wrist=(0.54, 0.5)),
    )
    assert clapped["kind"] == "clap"

    sat = local_camera.classify_pose_action([_body_pose(sitting=False)] * 3, _body_pose(sitting=True))
    assert sat["kind"] == "sit_down"
    stood = local_camera.classify_pose_action([_body_pose(sitting=True)] * 3, _body_pose(sitting=False))
    assert stood["kind"] == "stand_up"


def test_pose_action_classifier_detects_walking():
    history = [_body_pose(ankle_gap=gap) for gap in (0.30, -0.30, 0.30, -0.30, 0.30)]
    walking = local_camera.classify_pose_action(history, _body_pose(ankle_gap=-0.30))
    assert walking["kind"] == "walk"


def test_pose_only_does_not_require_face_detector(monkeypatch):
    image = object()
    monkeypatch.setattr(local_camera, "_decode_image", lambda _data: image)
    monkeypatch.setattr(local_camera, "_pose", lambda _image: _pose())
    monkeypatch.setattr(local_camera, "_detect_faces", lambda _image: (_ for _ in ()).throw(AssertionError("face detector should be skipped")))

    result = local_camera.analyze_local_frame("data:image/jpeg;base64,ZmFrZQ==", identity=False, pose=True)
    assert result["status"] == "success"
    assert result["observations"][0]["action"]["kind"] == "still"


def test_look_me_rejects_missing_camera_frame():
    service = ScreenVisionService()

    result = json.loads(asyncio.run(service.handle_handoff({"tool_name": "look_me"})))

    assert result["status"] == "error"
    assert "摄像头画面" in result["message"]


def test_look_me_analyzes_supplied_frame_without_persisting(monkeypatch):
    service = ScreenVisionService()
    captured = {}
    monkeypatch.setattr(service, "_vision_mode", lambda _source: "cloud")
    monkeypatch.setattr(service, "_camera_analysis_mode", lambda: "cloud")

    async def fake_analyze(query: str, image_url: str) -> str:
        captured["query"] = query
        captured["image_url"] = image_url
        return "画面中有人正在向镜头挥手。"

    monkeypatch.setattr(
        "mcpserver.screen_vision.service.compress_screenshot_data_url",
        lambda image_url, **_kwargs: image_url,
    )
    monkeypatch.setattr(service, "_analyze_with_miya_vision", fake_analyze)

    result = json.loads(
        asyncio.run(service.handle_handoff(
            {
                "tool_name": "look_me",
                "image_data": "data:image/jpeg;base64,ZmFrZQ==",
                "query": "看看我在做什么",
            }
        ))
    )

    assert result == {
        "status": "success",
        "message": "画面中有人正在向镜头挥手。",
        "source": "camera",
        "persisted": False,
    }
    assert captured["query"] == "看看我在做什么"
    assert captured["image_url"].startswith("data:image/jpeg;base64,")


def test_look_me_rejects_invalid_image_payload():
    service = ScreenVisionService()

    result = json.loads(asyncio.run(service.handle_handoff({
        "tool_name": "look_me",
        "image_data": "data:image/svg+xml;base64,not-an-image",
    })))

    assert result["status"] == "error"
    assert "JPEG" in result["message"]


def test_camera_look_captures_without_frontend_and_never_persists(monkeypatch):
    service = ScreenVisionService()
    captured = {}

    async def fake_look_me(call):
        captured.update(call)
        return json.dumps({"status": "success", "message": "本地动作：挥手", "persisted": False})

    monkeypatch.setattr(
        "mcpserver.screen_vision.camera_capture.capture_camera_frame",
        lambda index, **kwargs: {
            "image_data": "data:image/jpeg;base64,ZmFrZQ==",
            "width": 640,
            "height": 480,
            "camera_index": index,
        },
    )
    monkeypatch.setattr(service, "_look_me", fake_look_me)

    result = json.loads(asyncio.run(service.handle_handoff({
        "tool_name": "camera_look",
        "query": "我在做什么？",
    })))

    assert result["status"] == "success"
    assert result["source"] == "camera_terminal"
    assert result["capture"]["camera_index"] == 0
    assert result["persisted"] is False
    assert captured["image_data"].startswith("data:image/jpeg")
    assert captured["local_only"] is True


def test_camera_look_cloud_requires_explicit_opt_in(monkeypatch):
    service = ScreenVisionService()
    captured = {}

    async def fake_look_me(call):
        captured.update(call)
        return json.dumps({"status": "success", "message": "云端描述", "persisted": False})

    monkeypatch.setattr(
        "mcpserver.screen_vision.camera_capture.capture_camera_frame",
        lambda index, **kwargs: {
            "image_data": "data:image/jpeg;base64,ZmFrZQ==",
            "width": 640,
            "height": 480,
            "camera_index": index,
        },
    )
    monkeypatch.setattr(service, "_look_me", fake_look_me)

    asyncio.run(service.handle_handoff({
        "tool_name": "camera_look",
        "local_only": False,
    }))

    assert captured["local_only"] is False


def test_look_both_labels_screen_and_camera_sources(monkeypatch):
    from types import SimpleNamespace

    service = ScreenVisionService()
    captured = {}
    monkeypatch.setattr(service, "_vision_mode", lambda _source: "cloud")
    monkeypatch.setattr(
        "mcpserver.screen_vision.service.get_screenshot_provider",
        lambda: SimpleNamespace(capture_data_url=lambda: SimpleNamespace(data_url="data:image/png;base64,c2NyZWVu")),
    )
    monkeypatch.setattr(
        "mcpserver.screen_vision.service.compress_screenshot_data_url",
        lambda image, **_kwargs: image,
    )

    async def fake_analyze(query, sources):
        captured["query"] = query
        captured["sources"] = sources
        return "屏幕上是聊天窗口，摄像头中是你。"

    monkeypatch.setattr(service, "_analyze_with_miya_vision_sources", fake_analyze)
    result = json.loads(asyncio.run(service.handle_handoff({
        "tool_name": "look_both",
        "image_data": "data:image/jpeg;base64,Y2FtZXJh",
        "query": "帮我看看",
    })))

    assert result["status"] == "success"
    assert result["sources"] == ["screen", "camera"]
    assert captured["query"] == "帮我看看"
    assert captured["sources"] == [
        ("屏幕截图", "data:image/png;base64,c2NyZWVu"),
        ("摄像头画面（用户本人）", "data:image/jpeg;base64,Y2FtZXJh"),
    ]


def test_look_both_does_not_capture_or_upload_in_local_only_mode(monkeypatch):
    service = ScreenVisionService()

    def fail_if_captured():
        raise AssertionError("screen capture must not run in local-only mode")

    monkeypatch.setattr("mcpserver.screen_vision.service.get_screenshot_provider", fail_if_captured)
    result = json.loads(asyncio.run(service.handle_handoff({
        "tool_name": "look_both",
        "image_data": "data:image/jpeg;base64,Y2FtZXJh",
        "local_only": True,
    })))

    assert result["status"] == "partial"
    assert result["source"] == "screen_and_camera_local"
    assert result["persisted"] is False


def test_look_both_accepts_string_local_only_flag(monkeypatch):
    service = ScreenVisionService()

    async def local_result(_call):
        return json.dumps({"status": "partial", "source": "screen_and_camera_local", "persisted": False})

    monkeypatch.setattr(service, "_look_both_local", local_result)
    result = json.loads(asyncio.run(service.handle_handoff({
        "tool_name": "look_both",
        "local_only": "true",
    })))

    assert result["source"] == "screen_and_camera_local"


def test_local_look_both_combines_ocr_and_pose_without_remote(monkeypatch):
    from types import SimpleNamespace

    service = ScreenVisionService()
    monkeypatch.setattr(service, "_vision_mode", lambda _source: "local")
    monkeypatch.setattr(
        "mcpserver.screen_vision.service.get_screenshot_provider",
        lambda: SimpleNamespace(capture_data_url=lambda: SimpleNamespace(data_url="data:image/png;base64,c2NyZWVu")),
    )
    monkeypatch.setattr(
        "mcpserver.screen_vision.service.analyze_local_screen",
        lambda _image: {"status": "success", "message": "本地 OCR：聊天窗口", "source": "screen_local_ocr"},
    )
    monkeypatch.setattr("mcpserver.screen_vision.service.discover_local_camera_capabilities", lambda: {
        "features": {"pose": {"available": True}},
    })
    monkeypatch.setattr("mcpserver.screen_vision.service.analyze_local_frame", lambda *_args, **_kwargs: {
        "status": "success", "message": "本地姿态分析完成；动作线索：坐着", "source": "camera_local",
    })

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("local combined mode must not call remote vision")

    monkeypatch.setattr(service, "_analyze_with_miya_vision_sources", fail_if_called)
    result = json.loads(asyncio.run(service.handle_handoff({
        "tool_name": "look_both",
        "image_data": "data:image/jpeg;base64,Y2FtZXJh",
        "local_only": True,
    })))

    assert result["status"] == "success"
    assert "本地 OCR：聊天窗口" in result["message"]
    assert "本地姿态分析完成" in result["message"]


def test_local_only_never_falls_back_to_remote(monkeypatch):
    service = ScreenVisionService()

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("remote vision must not be called in local-only mode")

    monkeypatch.setattr(service, "_analyze_with_miya_vision", fail_if_called)
    result = json.loads(asyncio.run(service.handle_handoff({
        "tool_name": "look_me",
        "image_data": "data:image/jpeg;base64,ZmFrZQ==",
        "local_only": True,
    })))

    assert result["status"] == "unavailable"
    assert result["persisted"] is False


def test_configured_local_camera_mode_uses_onnx_without_cloud_fallback(monkeypatch):
    service = ScreenVisionService()
    monkeypatch.setattr(service, "_camera_analysis_mode", lambda: "local")
    monkeypatch.setattr("mcpserver.screen_vision.service.discover_local_camera_capabilities", lambda: {
        "status": "ready", "features": {"pose": {"available": True}},
    })
    monkeypatch.setattr("mcpserver.screen_vision.service.analyze_local_frame", lambda image, **kwargs: {
        "status": "success", "message": "本地动作：挥手", "source": "camera_local", "persisted": False,
    })

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("configured local mode must not call remote vision")

    monkeypatch.setattr(service, "_analyze_with_miya_vision", fail_if_called)
    result = json.loads(asyncio.run(service.handle_handoff({
        "tool_name": "look_me",
        "image_data": "data:image/jpeg;base64,ZmFrZQ==",
        "identity": False,
        "pose": True,
    })))

    assert result["status"] == "success"
    assert result["source"] == "camera_local"


def test_camera_analysis_mode_reads_qq_image_analyzer_config(monkeypatch):
    """The camera route is read from the unified key and its own override key."""
    service = ScreenVisionService()
    seen: list[tuple] = []

    def fake_get_qq_config(*path, default=None):
        seen.append(path)
        return "local"

    monkeypatch.setattr("config.config_utils.get_qq_config", fake_get_qq_config)

    assert service._camera_analysis_mode() == "local"
    assert ("tools", "qq_image_analyzer", "vision_mode") in seen
    assert ("tools", "qq_image_analyzer", "camera_analysis_mode") in seen


def test_local_screen_route_uses_ocr_without_cloud_fallback(monkeypatch):
    from types import SimpleNamespace

    service = ScreenVisionService()
    monkeypatch.setattr(service, "_vision_mode", lambda _source: "local")
    monkeypatch.setattr(
        "mcpserver.screen_vision.service.get_screenshot_provider",
        lambda: SimpleNamespace(capture_data_url=lambda: SimpleNamespace(data_url="data:image/png;base64,c2NyZWVu")),
    )
    monkeypatch.setattr(
        "mcpserver.screen_vision.service.analyze_local_screen",
        lambda _image: {"status": "success", "message": "本地 OCR：设置", "source": "screen_local_ocr", "persisted": False},
    )

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("local screen mode must not call remote vision")

    monkeypatch.setattr(service, "_analyze_with_miya_vision", fail_if_called)
    result = json.loads(asyncio.run(service.handle_handoff({"tool_name": "look_screen"})))

    assert result["status"] == "success"
    assert result["source"] == "screen_local_ocr"


def test_hybrid_screen_route_uses_vision_model_and_includes_local_ocr(monkeypatch):
    from types import SimpleNamespace

    service = ScreenVisionService()
    captured = {}
    monkeypatch.setattr(service, "_vision_mode", lambda _source: "hybrid")
    monkeypatch.setattr(
        "mcpserver.screen_vision.service.get_screenshot_provider",
        lambda: SimpleNamespace(capture_data_url=lambda: SimpleNamespace(
            data_url="data:image/png;base64,c2NyZWVu", width=800, height=600, source="test",
        )),
    )
    monkeypatch.setattr(
        "mcpserver.screen_vision.service.analyze_local_screen",
        lambda _image: {"status": "success", "message": "本地 OCR：错误代码 42", "ocr_text": "错误代码 42"},
    )
    monkeypatch.setattr(
        "mcpserver.screen_vision.service.compress_screenshot_data_url",
        lambda image, **_kwargs: image,
    )

    async def fake_analyze(query, _image):
        captured["query"] = query
        return "这是一个错误窗口。"

    monkeypatch.setattr(service, "_analyze_with_miya_vision", fake_analyze)
    result = json.loads(asyncio.run(service.handle_handoff({
        "tool_name": "look_screen",
        "query": "这个报错怎么解决？",
    })))

    assert result["status"] == "success"
    assert "这个报错怎么解决？" in captured["query"]
    assert "错误代码 42" in captured["query"]


def test_unified_vision_mode_reads_from_qq_config(monkeypatch):
    service = ScreenVisionService()
    monkeypatch.setattr(
        "config.config_utils.get_qq_config",
        lambda *path, default=None: "hybrid" if path[-1] == "vision_mode" else default,
    )

    assert service._vision_mode("screen") == "hybrid"
    assert service._vision_mode("camera") == "hybrid"


def test_per_source_vision_mode_overrides_shared_route(monkeypatch):
    service = ScreenVisionService()
    overrides = {"vision_mode": "cloud", "camera_analysis_mode": "local", "screen_analysis_mode": "hybrid"}

    def fake_get_qq_config(*path, default=None):
        return overrides.get(path[-1], default)

    monkeypatch.setattr("config.config_utils.get_qq_config", fake_get_qq_config)

    assert service._vision_mode("camera") == "local"
    assert service._vision_mode("screen") == "hybrid"


def test_vision_mode_fails_closed_to_local_when_config_is_unreadable(monkeypatch):
    service = ScreenVisionService()

    def fail_config(*_path, **_kwargs):
        raise RuntimeError("yaml unavailable")

    monkeypatch.setattr("config.config_utils.get_qq_config", fail_config)

    assert service._vision_mode("screen") == "local"
    assert service._vision_mode("camera") == "local"
    assert service._vision_mode("combined") == "local"


def test_vision_mode_fails_closed_to_local_for_invalid_values(monkeypatch):
    service = ScreenVisionService()
    monkeypatch.setattr(
        "config.config_utils.get_qq_config",
        lambda *_path, **_kwargs: "unexpected-mode",
    )

    assert service._vision_mode("screen") == "local"


def test_camera_capabilities_are_read_only():
    service = ScreenVisionService()

    result = json.loads(asyncio.run(service.handle_handoff({"tool_name": "camera_capabilities"})))

    assert result["status"] == "success"
    assert "features" in result["capabilities"]
    assert result["capabilities"]["baseline"]["motion"]["available"] is True
    assert result["capabilities"]["status"] in {"partial", "ready"}


def test_local_identity_store_keeps_embeddings_only(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MIYA_CAMERA_IDENTITY_DIR", str(tmp_path))
    monkeypatch.setattr(local_camera, "_decode_image", lambda _data: _frame_with_face())
    monkeypatch.setattr(local_camera, "_detect_faces", lambda _image, threshold=None: [_normalized_face()])
    monkeypatch.setattr(local_camera, "_embedding", lambda _image, **_kwargs: [1.0, 0.0, 0.0])

    result = local_camera.enroll_identity("data:image/jpeg;base64,ZmFrZQ==", "我")

    assert result["status"] == "success"
    stored = json.loads((tmp_path / "identities.json").read_text(encoding="utf-8"))
    assert stored[0]["name"] == "我"
    assert stored[0]["embedding"] == [1.0, 0.0, 0.0]
    assert "image" not in stored[0]
    assert local_camera.list_identities()["identities"][0]["name"] == "我"
    assert local_camera.delete_identity(result["id"])["status"] == "success"
    assert local_camera.list_identities()["identities"] == []


def test_local_analysis_route_does_not_call_remote(monkeypatch):
    service = ScreenVisionService()
    monkeypatch.setattr("mcpserver.screen_vision.service.discover_local_camera_capabilities", lambda: {
        "status": "ready", "features": {
            "face_detection": {"available": True}, "identity": {"available": True}, "emotion": {"available": True},
        },
    })
    monkeypatch.setattr("mcpserver.screen_vision.service.analyze_local_frame", lambda *_args, **_kwargs: {
        "status": "success", "message": "本地摄像头分析完成。", "persisted": False,
    })

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("local analysis must not call remote vision")

    monkeypatch.setattr(service, "_analyze_with_miya_vision", fail_if_called)
    result = json.loads(asyncio.run(service.handle_handoff({
        "tool_name": "camera_analyze_local",
        "image_data": "data:image/jpeg;base64,ZmFrZQ==",
        "emotion": True,
    })))

    assert result["status"] == "success"
    assert result["persisted"] is False


def test_camera_control_state_and_observation_request_are_image_free(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(camera_control, "_STATE_PATH", tmp_path / "control.json")
    monkeypatch.setattr(camera_control, "_REQUEST_PATH", tmp_path / "request.json")
    monkeypatch.setattr(camera_control, "_RESULT_PATH", tmp_path / "result.json")

    state = camera_control.write_state("companion", autonomous=True, local_only=True)
    assert state["autonomous"] is True
    assert "image" not in json.dumps(state)

    request = camera_control.request_observation("看看我是不是在挥手", local_only=True)
    loaded = camera_control.read_observation_request()
    assert loaded["request_id"] == request["request_id"]
    assert loaded["query"] == "看看我是不是在挥手"
    camera_control.publish_observation_result(request["request_id"], {"status": "success", "message": "本地动作：挥手"})
    assert camera_control.wait_for_observation_result(request["request_id"], timeout=1)["status"] == "success"


def test_autonomous_observation_requires_explicit_enable(monkeypatch, tmp_path: Path):
    # Control paths must be redirected: otherwise the test reads whatever the
    # developer's desktop last wrote and never exercises the consent branch.
    monkeypatch.setattr(camera_control, "_STATE_PATH", tmp_path / "control.json")
    monkeypatch.setattr(camera_control, "_REQUEST_PATH", tmp_path / "request.json")
    monkeypatch.setattr(camera_control, "_RESULT_PATH", tmp_path / "result.json")
    service = ScreenVisionService()

    result = json.loads(asyncio.run(service.handle_handoff({
        "tool_name": "request_camera_observation",
        "query": "弥娅看看我",
    })))
    assert result["status"] == "consent_required"


def test_autonomous_observation_runs_when_desktop_state_enables_it(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(camera_control, "_STATE_PATH", tmp_path / "control.json")
    monkeypatch.setattr(camera_control, "_REQUEST_PATH", tmp_path / "request.json")
    monkeypatch.setattr(camera_control, "_RESULT_PATH", tmp_path / "result.json")
    camera_control.write_state("companion", autonomous=True, local_only=True)
    service = ScreenVisionService()

    def fake_wait(request_id: str, _timeout: float = 25.0):
        return {"status": "success", "message": "本地动作：挥手", "request_id": request_id}

    monkeypatch.setattr(camera_control, "wait_for_observation_result", fake_wait)
    result = json.loads(asyncio.run(service.handle_handoff({
        "tool_name": "request_camera_observation",
        "query": "弥娅看看我",
    })))

    assert result["status"] == "success"
    assert result["message"] == "本地动作：挥手"


def test_vision_context_strips_image_payloads_and_builds_camera_card():
    store = VisionContextStore(max_events=20)
    event = store.add({
        "source": "camera",
        "summary": "本地动作：挥手",
        "image_data": "data:image/jpeg;base64,secret",
        "image_url": "data:image/jpeg;base64,secret",
    })
    assert "image_data" not in event
    assert "image_url" not in event
    assert "挥手" in store.build_card(source="camera")


def test_record_camera_observation_extracts_local_action_without_image():
    event = record_camera_observation({
        "status": "success",
        "observations": [{"action": {"label": "挥手", "confidence": 0.91}}],
    }, mode="local", local_only=True)
    assert event["source"] == "camera"
    assert "挥手" in event["summary"]
    assert "image_data" not in event


def test_record_camera_observation_emits_action_event_with_confidence():
    from core.vision_context import get_vision_context

    before = len(get_vision_context().recent(source="camera", limit=50))
    record_camera_observation({
        "status": "success",
        "observations": [{"action": {"kind": "wave", "label": "挥手", "confidence": 0.88}}],
    }, mode="local", local_only=True)
    events = get_vision_context().recent(source="camera", limit=50)
    assert len(events) >= before + 1
    assert any(event.get("kind") == "wave" and event.get("confidence") == 0.88 for event in events)


def test_the_inventory_remembers_which_camera_saw_a_person(monkeypatch):
    """Online and "worth watching" are different answers.

    The laptop camera aimed at a wall and the one looking at Jia both stream
    happily and report almost the same luminance; only the model knows which is
    which. The inventory used to stop at "usable", so the panel could never say
    which camera was actually pointed at him.
    """
    from mcpserver.screen_vision import camera_devices, camera_manager

    _REAL_LIST = camera_devices.list_camera_devices
    monkeypatch.setattr(
        camera_devices, "list_camera_devices",
        lambda **_kwargs: {
            "status": "success", "count": 2, "usable_count": 2, "unopenable_count": 0,
            "devices": [
                {"index": 0, "available": True, "usable": True, "name": "Integrated Camera", "luminance": 130.0},
                {"index": 2, "available": True, "usable": True, "name": "4K USB Camera", "luminance": 127.0},
            ],
        },
    )

    manager = camera_manager.CameraManager()
    manager.scan(force=True)
    manager.note_reading(2, faces=3, action="still", text="看到你在画面里")

    described = manager.describe()
    by_index = {item["index"]: item for item in described["devices"]}

    assert by_index[2]["sees_people"] is True
    assert by_index[2]["last_faces"] == 3
    assert by_index[2]["last_reading_text"] == "看到你在画面里"
    assert by_index[0]["sees_people"] is False, "没看到人的那台不该被说成看到了人"

    # A rescan re-lists the devices; what they showed must survive it.
    manager.scan(force=True)
    assert {item["index"]: item for item in manager.describe()["devices"]}[2]["sees_people"] is True
    monkeypatch.setattr(camera_devices, "list_camera_devices", _REAL_LIST)


def test_a_negative_index_never_becomes_a_phantom_camera():
    """The browser's camera has no OpenCV index; recording it must not invent one.

    A source at index -1 would enter the inventory, and every later scan would
    try to open it.
    """
    from mcpserver.screen_vision import camera_manager

    manager = camera_manager.CameraManager()
    manager.note_reading(-1, faces=1, text="浏览器那一路")

    assert manager.all_indices() == []
