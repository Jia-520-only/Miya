import asyncio
import json
from pathlib import Path

from mcpserver.screen_vision.service import ScreenVisionService
from mcpserver.screen_vision import local_camera
from core.vision_context import VisionContextStore, record_camera_observation
import importlib.util


_CONTROL_SPEC = importlib.util.spec_from_file_location("camera_control_test", "core/camera_control.py")
camera_control = importlib.util.module_from_spec(_CONTROL_SPEC)
assert _CONTROL_SPEC.loader is not None
_CONTROL_SPEC.loader.exec_module(camera_control)


def _pose(*, left_wrist=(0.3, 0.6), right_wrist=(0.7, 0.6), nose=(0.5, 0.35)):
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


def test_pose_action_classifier_detects_raised_hand_and_wave():
    raised = local_camera.classify_pose_action([], _pose(left_wrist=(0.3, 0.2), right_wrist=(0.7, 0.2)))
    assert raised["kind"] == "raised_hand"
    assert "手" in raised["label"]

    history = [_pose(left_wrist=(x, 0.3)) for x in (0.32, 0.55, 0.34, 0.57)]
    waved = local_camera.classify_pose_action(history, _pose(left_wrist=(0.33, 0.3)))
    assert waved["kind"] == "wave"


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
    service = ScreenVisionService()
    captured = {}

    def fake_get_qq_config(*path, default=None):
        captured["path"] = path
        captured["default"] = default
        return "local"

    monkeypatch.setattr("config.config_utils.get_qq_config", fake_get_qq_config)

    assert service._camera_analysis_mode() == "local"
    assert captured == {
        "path": ("tools", "qq_image_analyzer", "vision_mode"),
        "default": "",
    }


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

    def fake_get_qq_config(*path, default=None):
        if path[-1] == "vision_mode":
            return "cloud"
        if path[-1] == "camera_analysis_mode":
            return "local"
        if path[-1] == "screen_analysis_mode":
            return "hybrid"
        return default

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
    monkeypatch.setattr(local_camera, "_decode_image", lambda _data: object())
    monkeypatch.setattr(local_camera, "_detect_faces", lambda _image: [{"x": 0, "y": 0, "width": 10, "height": 10, "score": 0.99}])
    monkeypatch.setattr(local_camera, "_face_crop", lambda image, _face: image)
    monkeypatch.setattr(local_camera, "_embedding", lambda _image: [1.0, 0.0, 0.0])

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
    monkeypatch.setattr(camera_control, "_STATE_PATH", tmp_path / "control.json")
    monkeypatch.setattr(camera_control, "_REQUEST_PATH", tmp_path / "request.json")
    monkeypatch.setattr(camera_control, "_RESULT_PATH", tmp_path / "result.json")
    service = ScreenVisionService()

    result = json.loads(asyncio.run(service.handle_handoff({
        "tool_name": "request_camera_observation",
        "query": "弥娅看看我",
    })))
    assert result["status"] == "consent_required"


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
