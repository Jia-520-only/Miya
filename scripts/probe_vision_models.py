"""Probe every configured vision/chat endpoint and report which ones actually work."""
from __future__ import annotations

import asyncio
import base64
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from config.config_utils import get_api_key  # noqa: E402


def make_probe_image() -> str:
    """A simple drawing with unmissable content, so a model can describe it."""
    image = Image.new("RGB", (360, 240), (245, 245, 250))
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 120, 120), fill=(220, 60, 60))       # red square
    draw.ellipse((200, 60, 320, 180), fill=(60, 90, 220))         # blue circle
    draw.text((30, 180), "MIYA VISION TEST", fill=(20, 20, 20))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


PROMPT = "这张图里有几个几何图形？分别是什么颜色和形状？只回答这些。"


async def probe_vision(name: str, model: dict, image_url: str) -> dict:
    api_key = get_api_key(model.get("env_key", "")) if model.get("env_key") else ""
    if not api_key:
        return {"name": name, "ok": False, "why": f"缺少 {model.get('env_key')}"}
    base = str(model.get("base_url") or "").rstrip("/")
    target = str(model.get("name") or "")
    payload = {
        "model": target,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]}],
        "max_tokens": 200,
        "temperature": 0.2,
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
    except Exception as exc:  # noqa: BLE001
        return {"name": name, "ok": False, "why": f"{type(exc).__name__}: {exc}"}
    if response.status_code != 200:
        return {"name": name, "ok": False, "status": response.status_code, "why": response.text[:220]}
    data = response.json()
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    return {"name": name, "ok": bool(content.strip()), "model": target, "reply": content.strip()[:220]}


async def probe_chat(name: str, model: dict) -> dict:
    api_key = get_api_key(model.get("env_key", "")) if model.get("env_key") else ""
    if not api_key:
        return {"name": name, "ok": False, "why": f"缺少 {model.get('env_key')}"}
    base = str(model.get("base_url") or "").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": str(model.get("name") or ""),
                    "messages": [{"role": "user", "content": "只回答两个字：在的"}],
                    "max_tokens": 32,
                    "temperature": 0.1,
                },
            )
    except Exception as exc:  # noqa: BLE001
        return {"name": name, "ok": False, "why": f"{type(exc).__name__}: {exc}"}
    if response.status_code != 200:
        return {"name": name, "ok": False, "status": response.status_code, "why": response.text[:220]}
    data = response.json()
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    return {"name": name, "ok": bool(content.strip()), "reply": content.strip()[:60]}


async def main() -> int:
    cfg = json.loads((ROOT / "config" / "multi_model_config.json").read_text(encoding="utf-8"))
    models = cfg.get("models") or {}
    prefs = (cfg.get("vision_preferences") or {}).get("model_preferences") or {}
    print("== 视觉路线配置 ==")
    print("  primary  :", prefs.get("primary"))
    print("  secondary:", prefs.get("secondary"))
    print("  active_vision:", (cfg.get("vision_preferences") or {}).get("active_vision"))
    print("  active   :", cfg.get("active"))

    image_url = make_probe_image()
    vision_names = [k for k, v in models.items()
                    if isinstance(v, dict) and (v.get("type") == "vision"
                                                or "vision_understanding" in (v.get("capabilities") or [])
                                                or "image_description" in (v.get("capabilities") or []))]
    print("\n== 逐个实测视觉模型 ==")
    for name in vision_names:
        result = await probe_vision(name, models[name], image_url)
        flag = "可用" if result.get("ok") else "不可用"
        print(f"  [{flag}] {name} -> {models[name].get('name')}")
        if result.get("ok"):
            print(f"          回答: {result['reply']}")
        else:
            print(f"          原因: {result.get('why')}")

    print("\n== 实测对话模型（我用它来解读）==")
    for name in [n for n in ([prefs.get("primary"), prefs.get("secondary")] +
                             [cfg.get("active")] + list(models)) if isinstance(n, str)][:6]:
        model = models.get(name)
        if not isinstance(model, dict):
            continue
        if model.get("type") == "vision" or model.get("type") == "embedding":
            continue
        result = await probe_chat(name, model)
        flag = "可用" if result.get("ok") else "不可用"
        print(f"  [{flag}] {name} -> {model.get('name')}  {result.get('reply') or result.get('why')}")
    return 0


raise SystemExit(asyncio.run(main()))
