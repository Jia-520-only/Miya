"""
禁漫天堂下载工具（基于 jmcomic 库）

- 按关键词搜索本子，或直接指定 album_id 下载整本
- 自动处理图片解密、域名更新（jmcomic 库内置，域名失效会自动刷新）
- 可选依赖: pip install jmcomic（未安装时给出安装提示）
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)

_JM_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "data" / "downloads" / "jmcomic"
_MIYA_ROOT = _JM_DIR.parent.parent.parent  # .../Miya/data/downloads/jmcomic → .../Miya


def _run_sync(func, *args, **kwargs):
    import asyncio

    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, lambda: func(*args, **kwargs))


class JmcomicDownloadTool(BaseTool):
    """禁漫天堂整本下载工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "jmcomic_download",
            "description": (
                "禁漫天堂(JMComic)本子搜索与整本下载。"
                "给出 album_id 直接下载；给出 query 则搜索后下载最热门的第一个结果并列出其余候选。"
                "下载后返回本地目录路径，图片自动解密拼接。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "album_id": {
                        "type": "string",
                        "description": "本子 ID（从资源搜索结果的 jmcomic 链接 /photo/{id}/ 中提取）。与 query 二选一",
                    },
                    "query": {
                        "type": "string",
                        "description": "搜索关键词（搜索后自动下载第一个结果）。与 album_id 二选一",
                    },
                    "save_dir": {
                        "type": "string",
                        "description": "保存目录，默认 data/downloads/jmcomic/",
                    },
                },
                "required": [],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        album_id = (args.get("album_id") or "").strip()
        query = (args.get("query") or "").strip()
        save_dir = (args.get("save_dir") or "").strip()

        if not album_id and not query:
            return "❌ 请提供 album_id 或 query"

        save_path = _JM_DIR
        if save_dir:
            p = Path(save_dir)
            # 相对路径基于项目根（避免 data/downloads 重复拼接）
            save_path = p if p.is_absolute() else _MIYA_ROOT / save_dir

        try:
            import jmcomic
        except ImportError:
            return "❌ 未安装 jmcomic 库。请在虚拟环境执行: pip install jmcomic"

        def _work(aid: str) -> str:
            try:
                # jmcomic 库日志降噪
                logging.getLogger("jmcomic").setLevel(logging.WARNING)

                option = jmcomic.JmOption.default()
                # 指定下载根目录（dir_rule.base_dir 默认为工作目录）
                save_path.mkdir(parents=True, exist_ok=True)
                option.dir_rule.base_dir = str(save_path)
                client = option.new_jm_client()

                candidates: List[str] = []
                if query:
                    page = client.search_site(query, page=1)
                    rows = list(page.iter_id_title())[:8]
                    if not rows:
                        return f"❌ 未找到与「{query}」相关的本子"
                    aid = str(rows[0][0])
                    candidates = [f"{a} | {t[:40]}" for a, t in rows[1:]]

                detail = client.get_album_detail(aid)
                title = (getattr(detail, "title", "") or f"album-{aid}").strip()[:60]

                option.download_album(aid)

                album_dir = save_path / title if (save_path / title).exists() else save_path
                n_imgs = sum(1 for f in album_dir.rglob("*") if f.is_file()) if album_dir.exists() else 0

                lines = [f"✅ 本子下载完成\n📁 目录: {album_dir}\n🖼 图片数: {n_imgs}\n📖 ID: {aid}"]
                if candidates:
                    lines.append("\n其他候选 (可用 album_id 继续下载):")
                    lines.extend(f" - {c}" for c in candidates[:5])
                return "\n".join(lines)
            except Exception as e:
                logger.error(f"禁漫下载失败: {e}", exc_info=True)
                return f"❌ 下载失败: {str(e)[:200]}"

        return await _run_sync(_work, album_id)


def get_jmcomic_download_tool():
    return JmcomicDownloadTool()
