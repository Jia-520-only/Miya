import asyncio
import json
import shutil
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from mcpserver.art_service.comfyui import ComfyUIWorkshop
from mcpserver.art_service.service import ArtService


@pytest.fixture
def workshop(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "providers.json").write_text(
        json.dumps(
            {
                "providers": {
                    "comfyui": {
                        "enabled": True,
                        "base_url": "http://127.0.0.1:3198",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    shutil.copytree(
        Path(__file__).resolve().parents[1] / "config/artnet/comfyui_workflows", config / "comfyui_workflows"
    )
    return ComfyUIWorkshop(config_dir=config, data_dir=tmp_path / "output")


def mock_client(monkeypatch, handler):
    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        "mcpserver.art_service.comfyui.httpx.AsyncClient",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handler), **kwargs),
    )


def task_record(workshop, prompt_id):
    directory = workshop.data_dir / prompt_id
    directory.mkdir(parents=True)
    (directory / "task.json").write_text(
        json.dumps({"workflow": "video", "base_url": workshop.base_url}), encoding="utf-8"
    )


def test_video_defaults_and_user_values(workshop):
    graph = workshop.build_prompt(
        "video", "镜头缓慢推进", {"first_frame": "miya/frame.png", "seconds": 12.5, "width": 352, "height": 640}
    )
    assert graph["1"]["inputs"]["width"] == 352
    assert graph["1"]["inputs"]["height"] == 640
    assert graph["1"]["inputs"]["seconds"] == 12.5
    assert graph["1"]["inputs"]["replacement_identity"] == "原版 · pro4500"
    assert graph["1"]["inputs"]["audio_mode"] == "静音 · 最快"
    assert graph["10"]["class_type"] == "LoadImage"
    assert workshop._workflow("video")["10"]["inputs"]["image"] == ""


@pytest.mark.parametrize(
    "parameters",
    [
        {"width": ["bad", 0]},
        {"width": True},
        {"first_frame": "../outside.png"},
        {"first_frame": "C:/outside.png"},
        {"first_frame": "http://remote/image.png"},
        {"first_frame": "miya/frame.png", "unknown": 1},
    ],
)
def test_reject_invalid_parameters(workshop, parameters):
    with pytest.raises(ValueError):
        workshop.build_prompt("video", "镜头缓慢推进", parameters)


def test_video_requires_first_frame(workshop):
    with pytest.raises(ValueError, match="first_frame"):
        workshop.build_prompt("video", "镜头缓慢推进", {})


def test_generate_submits_once_and_records_id(workshop, monkeypatch):
    prompt_id = str(uuid4())
    requests = []

    def handler(request):
        requests.append(request)
        data = json.loads(request.content)
        assert data["prompt"]["6"]["inputs"]["text"] == "a white cat"
        assert data["prompt"]["3"]["inputs"]["seed"] == 42
        assert data["prompt"]["8"]["inputs"]["vae"] == ["4", 2]
        return httpx.Response(200, json={"prompt_id": prompt_id})

    mock_client(monkeypatch, handler)
    result = asyncio.run(
        workshop.handle({"action": "generate", "prompt": "a white cat", "parameters_json": '{"seed":42}'})
    )
    assert result["status"] == "queued"
    assert len(requests) == 1
    assert (workshop.data_dir / prompt_id / "task.json").is_file()


def test_assistant_reuses_comfy_endpoint(workshop, monkeypatch):
    def handler(request):
        assert request.url.path == "/h3_console/cloud-chat"
        data = json.loads(request.content)
        assert data["workflow_family"] == "MiniMax H3 视频生成"
        assert data["user_message"] == "小猫眨眼"
        assert "api_key" not in data
        return httpx.Response(200, json={"action": "update_prompt", "prompt": "小猫轻轻眨眼", "negative_prompt": ""})

    mock_client(monkeypatch, handler)
    result = asyncio.run(workshop.handle({"action": "assist_prompt", "workflow": "video", "prompt": "小猫眨眼"}))
    assert result["prompt"] == "小猫轻轻眨眼"


@pytest.mark.parametrize("state", ["running", "queued", "unknown", "error", "interrupted", "no_files"])
def test_task_states(workshop, monkeypatch, state):
    prompt_id = str(uuid4())
    task_record(workshop, prompt_id)

    def handler(request):
        if request.url.path == "/queue":
            return httpx.Response(
                200,
                json={
                    "queue_running": [[0, prompt_id]] if state == "running" else [],
                    "queue_pending": [[0, prompt_id]] if state == "queued" else [],
                },
            )
        if state == "error":
            entry = {
                "status": {
                    "completed": False,
                    "status_str": "error",
                    "messages": [["execution_error", {"exception_message": "CUDA OOM", "node_type": "KSampler"}]],
                }
            }
        elif state == "interrupted":
            entry = {"status": {"messages": [["execution_interrupted", {}]]}}
        elif state == "no_files":
            entry = {"status": {"completed": True}, "outputs": {}}
        else:
            return httpx.Response(200, json={})
        return httpx.Response(200, json={prompt_id: entry})

    mock_client(monkeypatch, handler)
    result = asyncio.run(workshop.handle({"action": "get_task", "prompt_id": prompt_id, "wait_seconds": 0}))
    assert result["status"] == ("error" if state in ("interrupted", "no_files") else state)
    if state == "error":
        assert result["error"] == "CUDA OOM"


def test_native_video_and_vhs_outputs_are_saved_once(workshop, monkeypatch):
    prompt_id = str(uuid4())
    task_record(workshop, prompt_id)
    downloads = []
    descriptor = {"filename": "cat.mp4", "subfolder": "Miya", "type": "output"}

    def handler(request):
        if request.url.path == "/view":
            downloads.append(request)
            return httpx.Response(200, content=b"video-bytes")
        return httpx.Response(
            200,
            json={
                prompt_id: {
                    "status": {"completed": True},
                    "outputs": {
                        "5": {"images": [descriptor]},
                        "6": {"gifs": [descriptor]},
                        "7": {"images": [{"filename": "preview.png", "type": "temp"}]},
                    },
                }
            },
        )

    mock_client(monkeypatch, handler)
    result = asyncio.run(workshop.handle({"action": "get_task", "prompt_id": prompt_id}))
    assert result["status"] == "success"
    assert len(result["local_paths"]) == 1
    assert Path(result["local_paths"][0]).read_bytes() == b"video-bytes"
    asyncio.run(workshop.handle({"action": "get_task", "prompt_id": prompt_id}))
    assert len(downloads) == 1


def test_upload_uses_input_folder_and_unique_filename(workshop, monkeypatch, tmp_path):
    source = tmp_path / "cat.png"
    source.write_bytes(b"image-bytes")

    def handler(request):
        assert request.url.path == "/upload/image"
        assert b"image-bytes" in request.content
        assert b'filename="cat.png"' not in request.content
        return httpx.Response(200, json={"name": "unique.png", "subfolder": "miya", "type": "input"})

    mock_client(monkeypatch, handler)
    result = asyncio.run(workshop.handle({"action": "upload_media", "file_path": str(source)}))
    assert result["input_name"] == "miya/unique.png"


def test_service_dispatch_and_manifest_schema(workshop, monkeypatch):
    monkeypatch.setattr("mcpserver.art_service.service.ComfyUIWorkshop", lambda: workshop)
    result = json.loads(
        asyncio.run(ArtService().handle_handoff({"tool_name": "comfyui", "action": "describe_workflow"}))
    )
    assert result["parameters"]["checkpoint"] == "Illustrious-XL-v2.0.safetensors"

    from webnet.ToolNet.tools.mcp.mcp_adapter import _build_tool_schema

    manifest = json.loads(
        (Path(__file__).resolve().parents[1] / "mcpserver/art_service/agent-manifest.json").read_text(encoding="utf-8")
    )
    definition = next(tool for tool in manifest["capabilities"]["tools"] if tool["name"] == "comfyui")
    schema = _build_tool_schema("art_service", definition)
    assert schema["parameters"]["required"] == ["action"]


def test_remote_endpoint_is_rejected(workshop):
    config = workshop.config_dir / "providers.json"
    config.write_text(
        json.dumps({"providers": {"comfyui": {"enabled": True, "base_url": "http://example.com"}}}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="本机"):
        ComfyUIWorkshop(config_dir=workshop.config_dir)
