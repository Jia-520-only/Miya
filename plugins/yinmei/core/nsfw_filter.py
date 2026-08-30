"""
鉴黄过滤模块
"""

import base64
import io
import logging
import time

import requests
from PIL import Image

from plugins.yinmei.tools import singleton, StringUtil
from plugins.yinmei.core import SharedData

logger = logging.getLogger(__name__)


@singleton
class NSFWFilter:
    """图片/文字鉴黄过滤"""

    def __init__(self):
        self._data = SharedData()

    def _nsfw_api(self, imgb64: str) -> dict:
        headers = {"Content-Type": "application/json"}
        body = {
            "image_loader": "yahoo",
            "model_weights": "data/open_nsfw-weights.npy",
            "input_type": "BASE64_JPEG",
            "input_image": imgb64,
        }
        resp = requests.post(
            url=f"{self._data.nsfw_server}/input",
            headers=headers,
            json=body,
            verify=False,
            timeout=(5, 10),
        )
        return resp.json()

    def check(self, imgb64: str, prompt: str, username: str, retry_count: int, source: str, limit: float) -> tuple:
        """鉴黄检测 返回 (status, nsfw_score) 1=通过 0=禁止 -1=异常"""
        try:
            self._data.nsfw_lock.acquire()
            result = self._nsfw_api(imgb64)
        except Exception:
            logger.exception(f"《{prompt}》【{source}】鉴黄异常")
            return -1, -1
        finally:
            self._data.nsfw_lock.release()

        logger.info(f"《{prompt}》【{source}】鉴黄结果: {result}")
        status = result.get("status", "失败")
        nsfw = result.get("nsfw", -1)

        if status == "失败":
            retry_count -= 1
            if retry_count > 0:
                return self.check(imgb64, prompt, username, retry_count, source, limit)
            return -1, -1

        if status == "成功":
            try:
                if nsfw > limit:
                    logger.info(f"《{prompt}》发现黄图 nsfw={nsfw}")
                    img = Image.open(io.BytesIO(base64.b64decode(imgb64)))
                    timestamp = int(time.time())
                    img.save(f"./porn/{prompt}_{username}_porn_{nsfw}_{timestamp}.jpg")
                    return 0, nsfw
                return 1, nsfw
            except Exception:
                logger.exception(f"《{prompt}》【{source}】鉴黄处理异常")
                return -1, nsfw
        return -1, nsfw

    def filter_text(self, text: str) -> str:
        """过滤非法字符"""
        if self._data.nsfw_filter_ch:
            return StringUtil.filter(text, self._data.nsfw_filter_ch)
        return text
