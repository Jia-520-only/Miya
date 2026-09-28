import asyncio

from core import image_vision_router as router


def _set_mode(monkeypatch, mode):
    monkeypatch.setattr(
        "config.config_utils.get_qq_config",
        lambda *_path, default=None: mode if _path[-1] == "vision_mode" else default,
    )


def test_invalid_route_fails_closed_to_local(monkeypatch):
    _set_mode(monkeypatch, "not-a-route")
    assert router.image_vision_mode() == "local"


def test_local_route_never_calls_cloud(monkeypatch):
    _set_mode(monkeypatch, "local")
    monkeypatch.setattr(
        router,
        "_analyze_local_ocr",
        lambda _data: {"success": True, "has_text": True, "description": "本地 OCR：你好"},
    )

    async def fail_cloud(*_args, **_kwargs):
        raise AssertionError("local route must not call cloud vision")

    monkeypatch.setattr("core.multi_vision_analyzer.analyze_image_multi_model", fail_cloud)
    result = asyncio.run(router.analyze_image_with_route(b"image"))

    assert result["description"] == "本地 OCR：你好"


def test_cloud_route_skips_local_ocr(monkeypatch):
    _set_mode(monkeypatch, "cloud")
    monkeypatch.setattr(
        router,
        "_analyze_local_ocr",
        lambda _data: (_ for _ in ()).throw(AssertionError("cloud route must skip local OCR")),
    )

    class FakeResult:
        def to_context_dict(self):
            return {"success": True, "description": "云端描述", "provider": "siliconflow"}

    async def fake_cloud(*_args, **_kwargs):
        return FakeResult()

    monkeypatch.setattr("core.multi_vision_analyzer.analyze_image_multi_model", fake_cloud)
    result = asyncio.run(router.analyze_image_with_route(b"image"))

    assert result["description"] == "云端描述"
    assert result["source"] == "image_cloud_vision"


def test_hybrid_route_uses_cloud_only_after_local_failure(monkeypatch):
    _set_mode(monkeypatch, "hybrid")
    monkeypatch.setattr(
        router,
        "_analyze_local_ocr",
        lambda _data: {"success": False, "has_text": False, "description": "本地 OCR 不可用"},
    )

    class FakeResult:
        def to_context_dict(self):
            return {"success": True, "description": "云端补充", "provider": "cloud"}

    async def fake_cloud(*_args, **_kwargs):
        return FakeResult()

    monkeypatch.setattr("core.multi_vision_analyzer.analyze_image_multi_model", fake_cloud)
    result = asyncio.run(router.analyze_image_with_route(b"image"))

    assert result["description"] == "云端补充"
    assert result["source"] == "image_cloud_vision"


def test_cloud_image_route_ignores_screen_ocr_mode(monkeypatch):
    """Chat images must remain cloud multimodal even when screen OCR is local."""
    _set_mode(monkeypatch, "local")
    monkeypatch.setattr(
        router,
        "_analyze_local_ocr",
        lambda _data: (_ for _ in ()).throw(AssertionError("chat images must skip screen OCR")),
    )

    class FakeResult:
        def to_context_dict(self):
            return {"success": True, "description": "云端图片描述", "provider": "cloud"}

    async def fake_cloud(*_args, **_kwargs):
        return FakeResult()

    monkeypatch.setattr("core.multi_vision_analyzer.analyze_image_multi_model", fake_cloud)
    result = asyncio.run(router.analyze_cloud_image(b"image"))

    assert result["description"] == "云端图片描述"
    assert result["source"] == "image_cloud_vision"
