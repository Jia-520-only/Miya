"""
绘画模块 - Stable Diffusion 集成
"""

import base64
import io
import logging
import random
import time
from threading import Thread

import requests
from PIL import Image

from plugins.yinmei.tools import singleton, StringUtil
from plugins.yinmei.core import SharedData
from plugins.yinmei.core.obs_controller import OBSController
from plugins.yinmei.core.nsfw_filter import NSFWFilter

logger = logging.getLogger(__name__)


@singleton
class DrawEngine:
    """Stable Diffusion 绘画引擎"""

    def __init__(self):
        self._data = SharedData()
        self._obs = OBSController()
        self._nsfw = NSFWFilter()

    def check_draw(self):
        if not self._data.DrawQueueList.empty() and self._data.is_drawing == 3:
            item = self._data.DrawQueueList.get()
            logger.info(f"启动绘画: {item}")
            Thread(
                target=self._draw,
                args=(item["prompt"], item["drawcontent"], item["username"], item.get("isExtend", False)),
                daemon=True,
            ).start()

    def _draw(self, prompt: str, drawcontent: str, username: str, is_extend: bool):
        self._data.is_drawing = 1
        draw_name = prompt
        steps = 35
        sampler = "DPM++ SDE Karras"
        seed = -1
        cfg_scale = 7
        negative_prompt = ""
        json_prompt = ""

        try:
            if is_extend:
                json_prompt = self._get_civitai_prompt(prompt, 0, 50)
                if json_prompt:
                    logger.info(f"绘画扩展提示词: {json_prompt}")

            if json_prompt:
                prompt_text = f"(({prompt},{drawcontent}))," + json_prompt["prompt"] + f",<lora:{prompt}>"
                negative_prompt = StringUtil.isNone(json_prompt.get("negativePrompt", ""))
                cfg_scale = json_prompt.get("cfgScale", 7)
                steps = json_prompt.get("steps", 35)
                sampler = json_prompt.get("sampler", "DPM++ SDE Karras")
            else:
                prompt_text = f"{prompt},{drawcontent}" + f"<lora:{prompt}>"
                negative_prompt = self._data.nsfw_filter_en

            payload = {
                "prompt": prompt_text,
                "negative_prompt": negative_prompt,
                "hr_checkpoint_name": "realvisxlV30Turbo_v30TurboBakedvae",
                "refiner_checkpoint": "realvisxlV30Turbo_v30TurboBakedvae",
                "sampler_index": sampler,
                "steps": steps,
                "cfg_scale": cfg_scale,
                "seed": seed,
                "width": self._data.draw_width,
                "height": self._data.draw_height,
            }
            logger.info(f"绘画参数: {payload}")

            Thread(target=self._watch_progress, args=(draw_name, username), daemon=True).start()

            resp = requests.post(f"{self._data.draw_url}/sdapi/v1/txt2img", json=payload, timeout=(5, 60))
            self._data.is_drawing = 2
            r = resp.json()
            if r.get("error"):
                logger.info(f"绘画错误: {r}")
                return

            imgb64 = r["images"][0]
            status, nsfw = self._nsfw.check(imgb64, draw_name, username, 3, "绘画", self._data.nsfw_limit)
            if status != 1:
                return

            img = Image.open(io.BytesIO(base64.b64decode(imgb64)))
            img = img.resize((self._data.draw_width, self._data.draw_height), Image.LANCZOS)
            timestamp = int(time.time())
            path = f"{self._data.draw_physical_folder}{draw_name}_{username}_{nsfw}_{timestamp}.jpg"
            img.save(path)
            self._obs.show_image("绘画图片", path)

        except Exception:
            logger.exception("【绘画】异常")
        finally:
            self._data.is_drawing = 3

    def _watch_progress(self, prompt: str, username: str):
        while self._data.is_drawing == 1:
            try:
                resp = requests.get(f"{self._data.draw_url}/sdapi/v1/progress", timeout=(5, 60))
                r = resp.json()
                imgb64 = r.get("current_image", "")
                if imgb64:
                    p = round(r["progress"] * 100, 2)
                    if p > self._data.nsfw_progress_limit:
                        status, nsfw_check = self._nsfw.check(
                            imgb64, prompt, username, 1, "绘画进度", self._data.nsfw_progress_nsfw_limit
                        )
                        if status in (-1, 0):
                            continue
                        self._obs.show_text("状态提示", f"{self._data.Ai_Name}正在绘图《{prompt}》,进度{p}%")
                    img = Image.open(io.BytesIO(base64.b64decode(imgb64)))
                    img = img.resize((self._data.draw_width, self._data.draw_height), Image.LANCZOS)
                    timestamp = int(time.time())
                    path = f"{self._data.draw_physical_folder}{prompt}_{username}_progress_{timestamp}.jpg"
                    img.save(path)
                    self._obs.show_image("绘画图片", path)
            except Exception:
                pass
            time.sleep(1)

    def _get_civitai_prompt(self, query: str, offset: int, limit: int) -> dict:
        url = "http://meilisearch-v1-6.civitai.com/multi-search"
        headers = {"Authorization": "Bearer 102312c2b83ea0ef9ac32e7858f742721bbfd7319a957272e746f84fd1e974af"}
        payload = {
            "queries": [
                {
                    "indexUid": "images_v6",
                    "q": query,
                    "limit": limit,
                    "offset": offset,
                    "filter": ["nsfwLevel=1"],
                    "facets": ["aspectRatio", "baseModel", "tagNames", "user.username"],
                    "attributesToHighlight": [],
                    "highlightPreTag": "__ais-highlight__",
                    "highlightPostTag": "__/ais-highlight__",
                }
            ]
        }
        try:
            resp = requests.post(
                url,
                headers=headers,
                json=payload,
                verify=False,
                timeout=60,
                proxies=self._data.draw_proxies or {"http": None, "https": None},
            )
            r = resp.json()
            hits = [h for h in r["results"][0].get("hits", []) if h.get("generationProcess") == "txt2img"]
            if not hits:
                return {}
            count = min(len(hits), limit if limit > 0 else len(hits))
            if count > 0:
                h = hits[random.randrange(0, count)]
                meta = h["meta"]
                return {
                    "prompt": StringUtil.filter(StringUtil.isNone(meta.get("prompt", "")), self._data.nsfw_filter_en),
                    "negativePrompt": StringUtil.isNone(meta.get("negativePrompt", "")),
                    "cfgScale": meta.get("cfgScale", 7),
                    "steps": meta.get("steps", 35),
                    "sampler": StringUtil.isNone(meta.get("sampler", "DPM++ SDE Karras")),
                    "seed": meta.get("seed", -1),
                }
        except Exception:
            logger.exception("C站提示词获取异常")
        return {}

    def msg_deal(self, traceid: str, query: str, uid: str, username: str) -> bool:
        text = ["画画", "画一个", "画一下", "画个"]
        is_contain = StringUtil.has_string_reg_list(f"^{text}", query)
        if is_contain is not None:
            num = StringUtil.is_index_contain_string(text, query)
            q = query[num:].strip()
            if q:
                self._data.DrawQueueList.put(
                    {
                        "traceid": traceid,
                        "prompt": q,
                        "drawcontent": "",
                        "username": username,
                        "isExtend": True,
                    }
                )
            return True
        return False
