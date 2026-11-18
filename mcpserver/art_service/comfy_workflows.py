"""Search and submit the user's saved ComfyUI workflows."""

import asyncio
import re
from pathlib import PurePosixPath
from urllib.parse import quote

MEDIA_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".mp4", ".mov", ".mkv", ".webm",
    ".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac",
}


def relative_media_path(value):
    value = str(value).replace("\\", "/")
    path = PurePosixPath(value)
    if not value or path.is_absolute() or any(part in ("..", ".") for part in value.split("/")) or ":" in value:
        raise ValueError("素材名必须是 ComfyUI input 内的相对路径")
    if path.suffix.lower() not in MEDIA_EXTENSIONS:
        raise ValueError("只支持图片、视频和音频素材")
    return path.as_posix()


_SEARCH_ALIASES = {
    "画图": ("图片", "文生图", "动漫", "图像"),
    "绘图": ("图片", "文生图", "动漫", "图像"),
    "动漫": ("动漫", "图片生成"),
    "视频": ("视频", "H3", "动作"),
    "换人": ("人物替换", "角色替换", "换头"),
    "换脸": ("人物替换", "换头", "脸部"),
    "动作迁移": ("动作迁移", "Wan", "H3"),
    "人物替换": ("人物替换", "角色替换", "换头"),
    "超分": ("超分", "放大", "4K", "清晰度"),
    "修复": ("修复", "再生", "清晰度", "精修"),
    "音频": ("音频", "语音", "口型"),
}
_FRONTEND_TYPES = {"Note", "MarkdownNote", "Reroute", "Reroute (rgthree)"}
_SEED_CONTROLS = {"fixed", "increment", "decrement", "randomize"}
_NEGATIVE_WORDS = ("negative", "uncond", "负面", "负向")
_POSITIVE_WORDS = ("positive", "正面", "正向")
_IMAGE_CLASSES = {"loadimage", "loadimagegoohai"}
_VIDEO_CLASSES = {"vhs_loadvideo", "loadvideo", "h3consolereferenceclip"}
_AUDIO_CLASSES = {"loadaudio", "loadaudiooutput", "h3consolereferenceclip"}


def _safe_workflow_path(value):
    path = PurePosixPath(str(value or "").replace("\\", "/"))
    if path.is_absolute() or not path.parts or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError("workflow_path 必须来自 ComfyUI 工作流搜索结果")
    if path.suffix.lower() != ".json":
        raise ValueError("只支持 ComfyUI JSON 工作流")
    return path.as_posix()


async def _catalog(client):
    data = await client.get("/h3_console/workflow-hub/catalog")
    data.raise_for_status()
    items = data.json().get("items", [])
    if not isinstance(items, list):
        raise ValueError("ComfyUI 工作流目录格式无效")
    return items


def _rank(item, query):
    label = str(item.get("label") or "")
    category = str(item.get("category") or "")
    path = str(item.get("path") or "")
    text = f"{label} {category} {path}".casefold()
    query = query.strip().casefold()
    if not query:
        return 10 if item.get("favorite") else 0
    if query in text:
        return 100 + len(query)
    terms = []
    for token in re.findall(r"[a-z0-9]+|[\u3400-\u9fff]+", query):
        if token.isascii():
            terms.append(token)
        elif len(token) > 2:
            terms.extend(token[index : index + 2] for index in range(len(token) - 1))
        else:
            terms.append(token)
    terms.extend(alias for key, aliases in _SEARCH_ALIASES.items() if key in query for alias in aliases)
    score = sum(8 + len(term) for term in set(terms) if term.casefold() in text)
    if item.get("favorite") and score:
        score += 2
    return score


def search_workflows(items, query="", limit=6):
    limit = min(8, max(1, int(limit)))
    ranked = [(_rank(item, query), item) for item in items]
    ranked = [(score, item) for score, item in ranked if score > 0]
    ranked.sort(key=lambda pair: (-pair[0], not pair[1].get("favorite"), str(pair[1].get("label", "")).casefold()))
    return [
        {
            "workflow_path": item["path"],
            "name": item.get("label", PurePosixPath(item["path"]).stem),
            "category": item.get("category", ""),
            "source": item.get("source", ""),
            "favorite": bool(item.get("favorite")),
        }
        for _, item in ranked[:limit]
    ]


async def _get_workflow(client, path, items):
    path = _safe_workflow_path(path)
    if path not in {str(item.get("path")) for item in items}:
        raise ValueError("请先通过 search_workflows 搜索，再使用结果中的 workflow_path")
    response = await client.get("/h3_console/workflow-hub/load", params={"path": path})
    response.raise_for_status()
    payload = response.json()
    workflow = payload.get("workflow")
    if not isinstance(workflow, dict) or not isinstance(workflow.get("nodes"), list):
        raise ValueError("所选文件不是可识别的 ComfyUI 画布工作流")
    item = next(entry for entry in items if entry.get("path") == path)
    return path, workflow, item


async def _node_schemas(client, workflow):
    classes = {
        str(node.get("type") or "")
        for node in workflow.get("nodes", [])
        if node.get("type") not in _FRONTEND_TYPES and not str(node.get("type", "")).startswith("Reroute")
    }
    schemas = {}
    semaphore = asyncio.Semaphore(12)

    async def get_info(node_class):
        async with semaphore:
            response = await client.get(f"/object_info/{quote(node_class, safe='')}")
            response.raise_for_status()
            result = response.json()
            return node_class, result.get(node_class)

    for node_class, schema in await asyncio.gather(*(get_info(name) for name in classes)):
        if schema:
            schemas[node_class] = schema
    return schemas


def _widget_values(node):
    named = node.get("widgets_values_named")
    if isinstance(named, dict):
        return named
    values = node.get("widgets_values", [])
    if isinstance(values, dict):
        return values
    if not isinstance(values, list):
        return {}
    result = {}
    index = 0
    for entry in node.get("inputs", []):
        widget = entry.get("widget")
        if not isinstance(widget, dict) or not widget.get("name"):
            continue
        name = widget["name"]
        if index >= len(values):
            break
        result[name] = values[index]
        index += 1
        if name == "seed" and index < len(values) and values[index] in _SEED_CONTROLS:
            index += 1
    return result


def _title(node):
    properties = node.get("properties") or {}
    return str(node.get("title") or properties.get("Node name for S&R") or "")


def _prompt_role(*values):
    text = " ".join(str(value or "") for value in values).casefold()
    if any(word in text for word in _NEGATIVE_WORDS):
        return "negative"
    if any(word in text for word in _POSITIVE_WORDS):
        return "positive"
    return ""


def _prompt_fields(workflow):
    nodes = {str(node["id"]): node for node in workflow.get("nodes", []) if "id" in node}
    links = {link[0]: link for link in workflow.get("links", []) if isinstance(link, list) and len(link) >= 6}
    fields = {}
    for node in nodes.values():
        node_type = str(node.get("type") or "")
        values = _widget_values(node)
        title = _title(node)
        for entry in node.get("inputs", []):
            field = str(entry.get("name") or "")
            if field in ("prompt", "positive_prompt", "negative_prompt"):
                role = _prompt_role(field, title)
                if not role and field != "negative_prompt":
                    role = "positive"
                if role:
                    link_id = entry.get("link")
                    source = nodes.get(str(links[link_id][1])) if link_id in links else None
                    source_values = _widget_values(source) if source else {}
                    source_field = next(
                        (
                            str(source_entry.get("name") or "")
                            for source_entry in (source or {}).get("inputs", [])
                            if source_entry.get("widget")
                            and source_entry.get("name") in ("text", "value")
                            and source_entry.get("name") in source_values
                        ),
                        None,
                    )
                    if source_field and str(source.get("type", "")).startswith("PrimitiveString"):
                        fields[f"{source['id']}.{source_field}"] = role
                    elif link_id is None:
                        fields[f"{node['id']}.{field}"] = role
                continue
            if field not in ("text", "value") or field not in values:
                continue
            is_text_node = node_type.startswith("PrimitiveString") or node_type in {
                "CLIPTextEncode", "CLIPTextEncodeFlux", "TextEncodeQwenImage", "TextEncodeQwenImageEdit",
            }
            if not is_text_node:
                continue
            role = _prompt_role(title, field)
            link_id = entry.get("link")
            if link_id is not None and link_id in links:
                source = nodes.get(str(links[link_id][1]))
                if source is not None:
                    source_type = str(source.get("type") or "")
                    if source_type.startswith("PrimitiveString"):
                        source_values = _widget_values(source)
                        source_field = next(
                            (
                                str(source_entry.get("name") or "")
                                for source_entry in source.get("inputs", [])
                                if source_entry.get("widget")
                                and source_entry.get("name") in ("text", "value")
                                and source_entry.get("name") in source_values
                            ),
                            None,
                        )
                        if source_field:
                            role = _prompt_role(_title(source), title, field) or role or "positive"
                            fields[f"{source['id']}.{source_field}"] = role
                    continue
            if not role and field == "text" and node_type.startswith("CLIPTextEncode"):
                role = "positive"
            if not role and node_type.startswith("PrimitiveString") and any(word in title.casefold() for word in ("prompt", "描述", "正面", "正向")):
                role = "positive"
            if role:
                fields[f"{node['id']}.{field}"] = role
    return fields


def _schema_inputs(schema):
    inputs = schema.get("input", {})
    return {name for section in ("required", "optional") for name in (inputs.get(section) or {})}


def _describe_inputs(workflow, schemas, limit=48):
    rows = []
    for node in workflow.get("nodes", []):
        if int(node.get("mode", 0)) != 0:
            continue
        node_id = str(node.get("id", ""))
        node_class = str(node.get("type") or "")
        accepted = _schema_inputs(schemas.get(node_class) or {})
        values = _widget_values(node)
        schema_inputs = schemas.get(node_class, {}).get("input", {})
        for entry in node.get("inputs", []):
            widget = entry.get("widget")
            name = str(entry.get("name") or (widget or {}).get("name") or "")
            if not widget or name not in accepted:
                continue
            value = values.get(name)
            if isinstance(value, str) and len(value) > 80:
                value = value[:77] + "..."
            if name in ("image", "video", "audio") or name.startswith(("image_", "video_", "audio_")):
                kind = "media"
            elif isinstance(value, bool):
                kind = "boolean"
            elif isinstance(value, int | float):
                kind = "number"
            elif isinstance(value, str):
                kind = "string"
            else:
                kind = "value"
            row = {"key": f"{node_id}.{name}", "node": _title(node) or node_class, "type": kind, "value": value}
            info = next(
                (section[name] for section in (schema_inputs.get("required", {}), schema_inputs.get("optional", {})) if name in section),
                None,
            )
            if isinstance(info, list) and len(info) > 1 and isinstance(info[1], dict):
                options = info[1]
                for key in ("min", "max", "step"):
                    if key in options:
                        row[key] = options[key]
                if isinstance(info[0], list):
                    row["choices"] = info[0]
            rows.append(row)
            if len(rows) >= limit:
                return rows
    return rows


def _input_default(info):
    if not isinstance(info, list) or not info:
        return None
    options = info[1] if len(info) > 1 and isinstance(info[1], dict) else {}
    if "default" in options:
        return options["default"]
    first = info[0]
    if isinstance(first, list):
        return first[0] if first else None
    return first


def _prepare_widgets(node, schema):
    accepted = _schema_inputs(schema)
    values = _widget_values(node)
    for section in ("required", "optional"):
        for name, info in (schema.get("input", {}).get(section) or {}).items():
            if name not in values:
                default = _input_default(info)
                if default is not None:
                    values[name] = default
    return accepted, values


def _resolve_link(link_id, links, nodes, seen=None):
    link = links.get(link_id)
    if link is None:
        raise ValueError(f"工作流连线 {link_id} 不完整")
    node_id, slot = str(link[1]), int(link[2])
    node = nodes.get(node_id)
    if node is None:
        raise ValueError(f"工作流节点 {node_id} 不存在")
    if str(node.get("type", "")).startswith("Reroute"):
        seen = set() if seen is None else seen
        if node_id in seen:
            raise ValueError("工作流 Reroute 连线形成循环")
        seen.add(node_id)
        source = next((item for item in node.get("inputs", []) if item.get("link") is not None), None)
        if source is None:
            raise ValueError("工作流 Reroute 没有输入连线")
        return _resolve_link(source["link"], links, nodes, seen)
    return [node_id, slot]


def _media_value(node_class, field, value):
    lowered = node_class.casefold()
    is_media = (
        ("image" in lowered and field in ("image", "image_name"))
        or ("video" in lowered and field in ("video", "video_name"))
        or ("audio" in lowered and field in ("audio", "audio_name"))
        or ("h3consoleassets" in lowered and field.startswith(("image_", "video_", "audio_", "last_frame")))
    )
    if not is_media or not isinstance(value, str) or value in ("", "__none__"):
        return value
    path = relative_media_path(value)
    if PurePosixPath(path).suffix.lower() not in MEDIA_EXTENSIONS:
        raise ValueError(f"工作流素材格式无效：{field}")
    return path


def build_api_prompt(workflow, schemas, prompt="", parameters=None):
    parameters = parameters or {}
    nodes = {str(node["id"]): node for node in workflow.get("nodes", []) if "id" in node}
    links = {link[0]: link for link in workflow.get("links", []) if isinstance(link, list) and len(link) >= 6}
    prompt_fields = _prompt_fields(workflow)
    result = {}
    for node_id, node in nodes.items():
        node_class = str(node.get("type") or "")
        if int(node.get("mode", 0)) != 0:
            raise ValueError(f"工作流含停用或旁路节点：{_title(node) or node_class}（{node_id}）；请先在 ComfyUI 保存为全启用版本")
        schema = schemas.get(node_class)
        if schema is None:
            if node_class in _FRONTEND_TYPES or node_class.startswith("Reroute"):
                continue
            raise ValueError(f"所选工作流需要未安装的节点：{node_class}")
        accepted, values = _prepare_widgets(node, schema)
        api_inputs = {}
        for entry in node.get("inputs", []):
            field = str(entry.get("name") or "")
            if field not in accepted:
                continue
            link_id = entry.get("link")
            if link_id is not None:
                api_inputs[field] = _resolve_link(link_id, links, nodes)
            elif field in values:
                api_inputs[field] = _media_value(node_class, field, values[field])
        widget_fields = {
            str(entry.get("name") or (entry.get("widget") or {}).get("name") or "")
            for entry in node.get("inputs", [])
            if entry.get("widget")
        }
        for key, value in parameters.items():
            node_key, separator, field = str(key).partition(".")
            if separator and node_key == node_id:
                if field not in accepted or field not in widget_fields:
                    raise ValueError(f"节点 {node_id} 不支持参数 {field}，请先调用 describe_workflow")
                api_inputs[field] = _media_value(node_class, field, value)
        for key, role in prompt_fields.items():
            target_id, field = key.split(".", 1)
            if target_id == node_id and prompt and key not in parameters and role == "positive":
                api_inputs[field] = prompt
            if target_id == node_id and "negative_prompt" in parameters and key not in parameters and role == "negative":
                api_inputs[field] = parameters["negative_prompt"]
        result[node_id] = {"class_type": node_class, "inputs": api_inputs}
    if prompt and not any(
        role == "positive" and key.split(".", 1)[0] in result and key.split(".", 1)[1] in result[key.split(".", 1)[0]]["inputs"]
        for key, role in prompt_fields.items()
    ):
        raise ValueError("这个工作流没有可识别的正向提示词输入；请用 parameters_json 指定 node_id.field")
    return result


async def inspect_workflow(client, workflow_path):
    items = await _catalog(client)
    path, workflow, item = await _get_workflow(client, workflow_path, items)
    schemas = await _node_schemas(client, workflow)
    missing = sorted({str(node.get("type")) for node in workflow.get("nodes", []) if node.get("type") not in schemas and node.get("type") not in _FRONTEND_TYPES and not str(node.get("type", "")).startswith("Reroute")})
    disabled = sum(int(node.get("mode", 0)) != 0 for node in workflow["nodes"])
    return {
        "workflow_path": path,
        "name": item.get("label", PurePosixPath(path).stem),
        "category": item.get("category", ""),
        "favorite": bool(item.get("favorite")),
        "node_count": len(workflow["nodes"]),
        "disabled_nodes": disabled,
        "missing_nodes": missing,
        "prompt_fields": [{"key": key, "role": role} for key, role in _prompt_fields(workflow).items()],
        "parameters": _describe_inputs(workflow, schemas),
        "executable": not missing and not disabled,
        "_workflow": workflow,
        "_schemas": schemas,
    }


async def submit_workflow(client, workflow_path, prompt, parameters):
    details = await inspect_workflow(client, workflow_path)
    if not details["executable"]:
        reasons = []
        if details["missing_nodes"]:
            reasons.append("未安装节点：" + ", ".join(details["missing_nodes"][:12]))
        if details["disabled_nodes"]:
            reasons.append(f"含 {details['disabled_nodes']} 个停用或旁路节点")
        raise ValueError("所选工作流暂不可执行；" + "；".join(reasons))
    graph = build_api_prompt(details["_workflow"], details["_schemas"], prompt, parameters)
    result = await client.post("/prompt", json={"prompt": graph, "client_id": "miya-art"})
    result.raise_for_status()
    payload = result.json()
    if payload.get("error") or not payload.get("prompt_id"):
        raise ValueError(f"ComfyUI 无法提交工作流：{payload.get('error') or payload.get('node_errors') or payload}")
    return details, payload
