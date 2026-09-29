"""Vision model routing: candidate ordering, health memory, and rotation."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from mcpserver.screen_vision import service as vision_service
from mcpserver.screen_vision.service import (
    IMAGE_CAPABILITIES,
    ScreenVisionService,
    _image_failed_models,
    _is_image_model,
    _note_image_model_result,
    _vision_health_snapshot,
)


@pytest.fixture(autouse=True)
def _clean_health_memory():
    """Provider health is process-global; never leak it between tests."""
    with vision_service._cloud_lock:
        vision_service._image_failed.clear()
        vision_service._image_ok.clear()
    vision_service._note_cloud_success()
    yield
    with vision_service._cloud_lock:
        vision_service._image_failed.clear()
        vision_service._image_ok.clear()
    vision_service._note_cloud_success()


# --- capability detection --------------------------------------------------


def test_a_model_labelled_multimodal_counts_as_able_to_see():
    """The DeepSeek route reads images but is not typed `vision`."""
    assert _is_image_model({"capabilities": ["multimodal", "simple_chat"]}) is True
    assert _is_image_model({"capabilities": ["image_description"]}) is True
    assert _is_image_model({"type": "vision"}) is True
    assert _is_image_model({"capabilities": ["simple_chat", "code_analysis"]}) is False
    assert _is_image_model({}) is False
    # These three labels are what the config actually uses.
    assert set(IMAGE_CAPABILITIES) == {"vision_understanding", "image_description", "multimodal"}


# --- candidate chain -------------------------------------------------------


def test_candidate_chain_follows_configured_priority():
    service = ScreenVisionService()
    candidates = service._vision_candidates()
    keys = [item[0] for item in candidates]
    assert keys, "至少应该有一个候选视觉模型"
    # The configured active vision model must come first.
    repo_root = Path(__file__).resolve().parents[2]
    cfg = json.loads((repo_root / "config" / "multi_model_config.json").read_text(encoding="utf-8"))
    assert keys[0] == cfg["vision_preferences"]["active_vision"]
    # A "@pointer" in the preferences must not leak in as a model name.
    assert all(not key.startswith("@") for key in keys)


def test_candidate_chain_honours_the_configured_fallback_order(monkeypatch, tmp_path):
    service = ScreenVisionService()
    monkeypatch.setattr(vision_service, "_healthy_vision_models", lambda: None)
    monkeypatch.setattr(vision_service, "_image_failed_models", lambda: {})
    monkeypatch.setattr(service, "_resolve_vision_model", service._resolve_vision_model)
    keys = [item[0] for item in service._vision_candidates()]
    assert keys[0] == "kimi_k2_vision"
    assert "deepseek_v4_flash_official" in keys, "跨供应商兜底必须进入候选链"


def test_a_model_that_failed_is_rotated_out(monkeypatch):
    service = ScreenVisionService()
    first = service._vision_candidates()[0][0]
    _note_image_model_result(first, ok=False)
    keys = [item[0] for item in service._vision_candidates()]
    assert first not in keys
    assert keys, "换掉坏模型之后仍然要有可用的候选"


def test_a_model_that_recovered_comes_back(monkeypatch):
    service = ScreenVisionService()
    first = service._vision_candidates()[0][0]
    _note_image_model_result(first, ok=False)
    assert first not in [item[0] for item in service._vision_candidates()]
    _note_image_model_result(first, ok=True)
    assert first in [item[0] for item in service._vision_candidates()]


def test_failure_memory_expires_so_a_topped_up_key_recovers(monkeypatch):
    service = ScreenVisionService()
    first = service._vision_candidates()[0][0]
    _note_image_model_result(first, ok=False)
    # Age the failure past its memory window.
    with vision_service._cloud_lock:
        vision_service._image_failed[first] = 1.0
    assert _image_failed_models() == {}
    assert first in [item[0] for item in service._vision_candidates()]


def test_candidates_are_excluded_while_the_global_route_is_cooling_down():
    """The global cooldown is a separate, stronger signal than one bad model."""
    vision_service._note_cloud_failure(429, "balance")
    blocked, _reason = vision_service._cloud_blocked()
    assert blocked is True
    vision_service._note_cloud_success()


# --- rotation on real calls ------------------------------------------------


@pytest.fixture()
def _fake_candidates(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(ScreenVisionService, "_vision_candidates", lambda self: [
        ("dead_provider", "key-1", "https://dead.example/v1", "dead-model"),
        ("live_provider", "key-2", "https://live.example/v1", "live-model"),
    ])
    return calls


def test_a_dead_provider_rotates_to_the_next_one(monkeypatch, _fake_candidates):
    import httpx

    class _Response:
        def __init__(self, status: int, body: dict, text: str = "") -> None:
            self.status_code = status
            self._body = body
            self.text = text or json.dumps(body)

        def json(self):
            return self._body

    async def fake_post(self, url, **_kwargs):
        _fake_candidates.append(url)
        if "dead.example" in url:
            return _Response(429, {"error": {"message": "suspended due to insufficient balance"}})
        return _Response(200, {"choices": [{"message": {"content": "看到桌上有一个杯子和键盘。"}}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    service = ScreenVisionService()
    text = asyncio.run(service._analyze_with_miya_vision_sources("看看桌上有什么", [("画面", "data:image/jpeg;base64,ZmFrZQ==")]))

    assert text == "看到桌上有一个杯子和键盘。"
    assert len(_fake_candidates) == 2
    assert "dead.example" in _fake_candidates[0] and "live.example" in _fake_candidates[1]
    # The dead provider is remembered so the next request skips it.
    assert "dead_provider" in _vision_health_snapshot()["failed_models"]


def test_one_provider_failing_does_not_cool_down_the_whole_route(monkeypatch, _fake_candidates):
    """A single 429 must rotate, not block every later vision request."""
    import httpx

    class _Response:
        def __init__(self, status: int, body: dict, text: str = "") -> None:
            self.status_code = status
            self._body = body
            self.text = text or json.dumps(body)

        def json(self):
            return self._body

    async def fake_post(self, url, **_kwargs):
        _fake_candidates.append(url)
        if "dead.example" in url:
            return _Response(429, {"error": {"message": "insufficient balance"}})
        return _Response(200, {"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    service = ScreenVisionService()
    asyncio.run(service._analyze_with_miya_vision_sources("q", [("画面", "data:image/jpeg;base64,ZmFrZQ==")]))

    blocked, _reason = vision_service._cloud_blocked()
    assert blocked is False, "单个模型失败不应该把整条云路线冷却"


def test_an_empty_reply_is_treated_as_a_failure_and_rotates(monkeypatch, _fake_candidates):
    import httpx

    class _Response:
        def __init__(self, status: int, body: dict) -> None:
            self.status_code = status
            self._body = body
            self.text = json.dumps(body)

        def json(self):
            return self._body

    async def fake_post(self, url, **_kwargs):
        _fake_candidates.append(url)
        if "dead.example" in url:
            return _Response(200, {"choices": [{"message": {"content": "   "}}]})
        return _Response(200, {"choices": [{"message": {"content": "第二个模型答的"}}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    service = ScreenVisionService()
    text = asyncio.run(service._analyze_with_miya_vision_sources("q", [("画面", "data:image/jpeg;base64,ZmFrZQ==")]))
    assert text == "第二个模型答的"
    assert "dead_provider" in _vision_health_snapshot()["failed_models"]


def test_all_providers_failing_reports_a_real_reason(monkeypatch):
    import httpx

    monkeypatch.setattr(ScreenVisionService, "_vision_candidates", lambda self: [
        ("a", "k", "https://a.example/v1", "m"),
        ("b", "k", "https://b.example/v1", "m"),
    ])

    class _Response:
        status_code = 402
        text = "no credit"

        def json(self):
            return {}

    async def fake_post(self, *_args, **_kwargs):
        return _Response()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    service = ScreenVisionService()
    with pytest.raises(RuntimeError) as excinfo:
        asyncio.run(service._analyze_with_miya_vision_sources("q", [("画面", "data:image/jpeg;base64,ZmFrZQ==")]))
    message = str(excinfo.value)
    assert "所有视觉模型都不可用" in message
    assert "402" in message
    # Only after every candidate failed does the route cool down.
    assert vision_service._cloud_blocked()[0] is True


# --- health reporting ------------------------------------------------------


def test_vision_health_tool_lists_candidates_and_state():
    service = ScreenVisionService()
    payload = json.loads(service._vision_health({}))
    assert payload["status"] == "success"
    assert payload["candidates"]
    assert "health" in payload
    assert set(payload["candidates"][0]) == {"key", "model", "base_url"}
    # Secrets must never appear in a health report.
    assert "key-" not in json.dumps(payload)


def test_vision_health_lists_the_whole_chain_by_default():
    """A missing limit must mean "everything", not an empty slice."""
    service = ScreenVisionService()
    full = json.loads(service._vision_health({}))["candidates"]
    limited = json.loads(service._vision_health({"limit": 1}))["candidates"]
    assert len(full) > len(limited)
    assert len(full) == len(service._vision_candidates())
    assert limited == full[:1]
