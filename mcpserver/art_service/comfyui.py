"""弥娅的本地 ComfyUI 工作台：提示词助手、绘图和视频任务。"""

import asyncio
import json
import mimetypes
import secrets
import uuid
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import httpx

from core.path_resolver import get_config_dir, get_data_dir


WORKFLOWS = {
    "image": {
        "description": "Illustrious XL 动漫绘图，默认 768×1024；prompt 使用英文标签。",
        "family": "Illustrious XL",
        "parameters": {
            "prompt": ("6", "text"),
            "negative_prompt": ("7", "text"),
            "width": ("5", "width"),
            "height": ("5", "height"),
            "num_images": ("5", "batch_size"),
            "seed": ("3", "seed"),
            "steps": ("3", "steps"),
            "cfg": ("3", "cfg"),
            "checkpoint": ("4", "ckpt_name"),
        },
    },
    "video": {
        "description": "H3 W6A8 图生视频，默认 288×512、5秒、4步、静音。先上传 first_frame；可先绘图再上传绘图结果。prompt 使用中文动作与镜头描述。",
        "family": "MiniMax H3 视频生成",
        "parameters": {
            "prompt": ("1", "prompt"),
            "width": ("1", "width"),
            "height": ("1", "height"),
            "seed": ("1", "seed"),
            "seconds": ("1", "seconds"),
            "audio_mode": ("1", "audio_mode"),
            "first_frame": ("10", "image"),
            "last_frame": ("3", "last_frame"),
            "finish_mode": ("5", "finish_mode"),
            **{f"image_{i}": ("3", f"image_{i}") for i in range(1, 6)},
            **{f"video_{i}": ("3", f"video_{i}") for i in range(1, 3)},
            **{f"audio_{i}": ("3", f"audio_{i}") for i in range(1, 4)},
        },
    },
}
MEDIA_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".gif",
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".wav",
    ".mp3",
    ".flac",
    ".m4a",
    ".ogg",
    ".aac",
}


def relative_media_path(value):
    value = str(value).replace("\\", "/")
    path = Path(value)
    if not value or path.is_absolute() or path.drive or any(p in ("..", ".") for p in value.split("/")) or ":" in value:
        raise ValueError("素材名必须是 ComfyUI input 内的相对路径")
    if path.suffix.lower() not in MEDIA_EXTENSIONS:
        raise ValueError("只支持图片、视频和音频素材")
    return path.as_posix()


class ComfyUIWorkshop:
    def __init__(self, config_dir=None, data_dir=None):
        self.config_dir = Path(config_dir) if config_dir is not None else get_config_dir() / "artnet"
        self.data_dir = Path(data_dir) if data_dir is not None else get_data_dir() / "artwork" / "comfyui"
        config = json.loads((self.config_dir / "providers.json").read_text(encoding="utf-8"))["providers"]["comfyui"]
        if not config.get("enabled"):
            raise ValueError("请先在 config/artnet/providers.json 启用 comfyui")
        self.base_url = config.get("base_url", "http://127.0.0.1:8188").rstrip("/")
        parsed = urlsplit(self.base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
        ):
            raise ValueError("ComfyUI 工作台只连接本机 HTTP 服务")

    async def _json(self, client, method, path, **kwargs):
        response = await client.request(method, self.base_url + path, **kwargs)
        if response.is_error:
            raise ValueError(f"ComfyUI HTTP {response.status_code}: {response.text[:2000]}")
        data = response.json()
        if isinstance(data, dict) and data.get("error"):
            raise ValueError(f"ComfyUI: {data['error']}")
        return data

    def _workflow(self, name):
        if name not in WORKFLOWS:
            raise ValueError("workflow 请选择 image 或 video")
        return json.loads((self.config_dir / "comfyui_workflows" / f"{name}.json").read_text(encoding="utf-8"))

    def build_prompt(self, name, prompt, parameters):
        graph = self._workflow(name)
        bindings = WORKFLOWS[name]["parameters"]
        values = {"seed": secrets.randbits(63), **parameters}
        if prompt:
            values["prompt"] = prompt
        unknown = values.keys() - bindings.keys()
        if unknown:
            raise ValueError(f"不支持的参数: {', '.join(sorted(unknown))}；先用 describe_workflow 查看参数")
        for key, value in values.items():
            node, field = bindings[key]
            default = graph[node]["inputs"][field]
            if isinstance(default, bool):
                valid = isinstance(value, bool)
            elif isinstance(default, int):
                valid = isinstance(value, int) and not isinstance(value, bool)
            elif isinstance(default, float):
                valid = isinstance(value, (int, float)) and not isinstance(value, bool)
            else:
                valid = isinstance(value, str)
            if not valid:
                raise ValueError(f"参数 {key} 类型应为 {type(default).__name__}")
            if key in ("first_frame", "last_frame") or key.startswith(("image_", "video_", "audio_")):
                value = relative_media_path(value) if value != "__none__" else value
            graph[node]["inputs"][field] = value
        prompt_node, prompt_field = bindings["prompt"]
        if not graph[prompt_node]["inputs"][prompt_field].strip():
            raise ValueError("请提供 prompt")
        if name == "video" and not graph["10"]["inputs"]["image"]:
            raise ValueError(
                "视频需要 first_frame：先 upload_media 上传图片，再把返回的 input_name 放入 parameters_json"
            )
        return graph

    async def handle(self, call):
        action = str(call.get("action", "")).strip()
        name = str(call.get("workflow") or "image").strip()
        parameters = call.get("parameters_json") or "{}"
        if isinstance(parameters, str):
            parameters = json.loads(parameters)
        if not isinstance(parameters, dict):
            raise ValueError("parameters_json 必须是 JSON 对象")
        async with httpx.AsyncClient(timeout=30, trust_env=False, follow_redirects=False) as client:
            if action == "list_workflows":
                stats = await self._json(client, "GET", "/system_stats")
                return {
                    "status": "success",
                    "base_url": self.base_url,
                    "devices": stats.get("devices", []),
                    "workflows": [
                        {"name": key, "description": value["description"]} for key, value in WORKFLOWS.items()
                    ],
                    "instructions": "中文需求可先 assist_prompt；generate 只代表已提交，必须 get_task 确认完成后才能声称出图/出片。取得 local_paths 后用 send_platform_file 发送。",
                }
            if action == "describe_workflow":
                graph = self._workflow(name)
                return {
                    "status": "success",
                    "workflow": name,
                    "description": WORKFLOWS[name]["description"],
                    "parameters": {
                        key: graph[node]["inputs"][field]
                        for key, (node, field) in WORKFLOWS[name]["parameters"].items()
                    },
                }
            if action == "assist_prompt":
                self._workflow(name)
                return await self._json(
                    client,
                    "POST",
                    "/h3_console/cloud-chat",
                    json={
                        "user_message": str(call.get("prompt") or ""),
                        "mode": "generate",
                        "workflow_family": WORKFLOWS[name]["family"],
                        "workflow_task": "中文需求转英文动漫绘图标签"
                        if name == "image"
                        else "视频生成：主体、动作、镜头与光线",
                        **{
                            key: parameters[key]
                            for key in (
                                "width",
                                "height",
                                "seed",
                                "steps",
                                "cfg",
                                "current_prompt",
                                "current_negative_prompt",
                            )
                            if key in parameters
                        },
                    },
                    timeout=180,
                )
            if action == "upload_media":
                path = Path(str(call.get("file_path") or ""))
                if not path.is_absolute() or not path.is_file() or path.suffix.lower() not in MEDIA_EXTENSIONS:
                    raise ValueError("file_path 须为本机图片、视频或音频的绝对路径")
                with path.open("rb") as source:
                    result = await self._json(
                        client,
                        "POST",
                        "/upload/image",
                        files={
                            "image": (
                                uuid.uuid4().hex + path.suffix.lower(),
                                source,
                                mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                            )
                        },
                        data={"type": "input", "subfolder": "miya", "overwrite": "false"},
                        timeout=300,
                    )
                input_name = relative_media_path(f"{result.get('subfolder', '')}/{result['name']}".lstrip("/"))
                return {"status": "success", "input_name": input_name}
            if action == "generate":
                graph = self.build_prompt(name, str(call.get("prompt") or ""), parameters)
                result = await self._json(client, "POST", "/prompt", json={"prompt": graph, "client_id": "miya-art"})
                prompt_id = str(uuid.UUID(result["prompt_id"]))
                task_dir = self.data_dir / prompt_id
                task_dir.mkdir(parents=True, exist_ok=True)
                (task_dir / "task.json").write_text(
                    json.dumps(
                        {"workflow": name, "base_url": self.base_url, "prompt_id": prompt_id}, ensure_ascii=False
                    ),
                    encoding="utf-8",
                )
                return {
                    "status": "queued",
                    "prompt_id": prompt_id,
                    "workflow": name,
                    "message": "已提交；稍后用 get_task 查询，同一任务不要重复提交。",
                }
            if action == "get_task":
                deadline = asyncio.get_running_loop().time() + min(20, max(0, float(call.get("wait_seconds", 20))))
                while True:
                    result = await self.get_task(client, str(call.get("prompt_id") or ""))
                    remaining = deadline - asyncio.get_running_loop().time()
                    if result["status"] not in ("queued", "running") or remaining <= 0:
                        return result
                    await asyncio.sleep(min(2, remaining))
        raise ValueError(
            "action 请选择 list_workflows / describe_workflow / assist_prompt / upload_media / generate / get_task"
        )

    async def get_task(self, client, prompt_id):
        prompt_id = str(uuid.UUID(prompt_id))
        task_dir = self.data_dir / prompt_id
        record = task_dir / "task.json"
        if not record.is_file():
            raise ValueError("没有这个弥娅工作台任务；请使用 generate 返回的 prompt_id")
        task = json.loads(record.read_text(encoding="utf-8"))
        if task["base_url"] != self.base_url:
            raise ValueError("任务属于另一个 ComfyUI 地址，请恢复原地址后查询")
        history = await self._json(client, "GET", f"/history/{prompt_id}")
        entry = history.get(prompt_id)
        if entry is None:
            queue = await self._json(client, "GET", "/queue")
            for key, state in (("queue_running", "running"), ("queue_pending", "queued")):
                if any(item[1] == prompt_id for item in queue.get(key, [])):
                    return {"status": state, "prompt_id": prompt_id}
            return {
                "status": "unknown",
                "prompt_id": prompt_id,
                "message": "队列和历史中均未找到任务；可能重启或清除了历史。请检查 ComfyUI，不要自动重新提交。",
            }
        status = entry.get("status", {})
        for kind, details in status.get("messages", []):
            if kind in ("execution_error", "execution_interrupted"):
                return {
                    "status": "error",
                    "prompt_id": prompt_id,
                    "error": details.get("exception_message") or kind,
                    "node_type": details.get("node_type"),
                    "node_id": details.get("node_id"),
                }
        if status.get("status_str") == "error":
            return {"status": "error", "prompt_id": prompt_id, "error": "ComfyUI 执行失败，请检查本机日志"}
        if not status.get("completed"):
            return {"status": "running", "prompt_id": prompt_id}
        files = []
        seen = set()
        for output in entry.get("outputs", {}).values():
            for key in ("images", "gifs", "videos", "audio"):
                for item in output.get(key, []):
                    if not isinstance(item, dict) or not item.get("filename") or item.get("type") != "output":
                        continue
                    relative = relative_media_path(f"{item.get('subfolder', '')}/{item['filename']}".lstrip("/"))
                    if relative in seen:
                        continue
                    seen.add(relative)
                    target = (task_dir / relative).resolve()
                    if not target.is_relative_to(task_dir.resolve()):
                        raise ValueError("ComfyUI 返回了无效的输出路径")
                    params = {field: item.get(field, "") for field in ("filename", "subfolder", "type")}
                    if not target.is_file():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        partial = target.with_suffix(target.suffix + ".part")
                        async with client.stream(
                            "GET", self.base_url + "/view", params=params, timeout=300
                        ) as response:
                            response.raise_for_status()
                            with partial.open("wb") as destination:
                                async for chunk in response.aiter_bytes():
                                    destination.write(chunk)
                        partial.replace(target)
                    files.append(
                        {"local_path": target.as_posix(), "view_url": self.base_url + "/view?" + urlencode(params)}
                    )
        if not files:
            return {"status": "error", "prompt_id": prompt_id, "error": "任务已结束，但没有可交付的图片/视频/音频文件"}
        return {
            "status": "success",
            "prompt_id": prompt_id,
            "workflow": task["workflow"],
            "files": files,
            "local_paths": [item["local_path"] for item in files],
            "message": "生成完成；可用 send_platform_file 发送 local_paths 中的文件。",
        }
