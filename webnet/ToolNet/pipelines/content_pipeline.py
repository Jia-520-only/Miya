"""
内容自动检测管线 — 消息预处理层，所有配置从 config 读取
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from config.config_utils import get_pipeline_config, get_text

logger = logging.getLogger(__name__)


class ContentPipeline:
    def __init__(self):
        self._detectors: List[Dict[str, Any]] = []

    def register(self, name: str, detect_func, process_func=None, priority: int = 0):
        self._detectors.append(
            {
                "name": name,
                "detect": detect_func,
                "process": process_func,
                "priority": priority,
            }
        )
        self._detectors.sort(key=lambda x: x["priority"], reverse=True)

    async def detect_and_process(self, text: str) -> List[Dict[str, str]]:
        results = []
        cfg = get_pipeline_config()
        if not cfg.get("enabled", True):
            return results

        enabled = get_text("pipelines", "enabled_pipelines", default=["bilibili", "arxiv", "github"])
        pipeline_header = get_text("pipelines", "messages", "pipeline_header", default="[{source} 检测]")

        for detector in self._detectors:
            if detector["name"] not in enabled:
                continue
            try:
                detect_fn = detector["detect"]
                if callable(detect_fn) and asyncio.iscoroutinefunction(detect_fn):
                    detections = await detect_fn(text)
                else:
                    detections = detect_fn(text)
                if detections and detector["process"]:
                    for item in detections:
                        try:
                            card = await detector["process"](item)
                            if card:
                                results.append(
                                    {
                                        "source": detector["name"],
                                        "content": f"{pipeline_header.format(source=detector['name'])}\n{card}",
                                    }
                                )
                        except Exception as e:
                            logger.warning(f"[Pipeline] {detector['name']} 处理失败: {e}")
            except Exception as e:
                logger.warning(f"[Pipeline] {detector['name']} 检测失败: {e}")
        return results


_pipeline: Optional[ContentPipeline] = None


def get_pipeline() -> ContentPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = ContentPipeline()
        _register_default_detectors(_pipeline)
    return _pipeline


def _register_default_detectors(pipeline: ContentPipeline) -> None:
    cfg = get_pipeline_config()
    detectors_cfg = cfg.get("detectors", {})

    # ── B站 ──
    bili_cfg = detectors_cfg.get("bilibili", {})
    if bili_cfg.get("enabled", True):

        async def detect_bilibili(text: str) -> list:
            try:
                from webnet.ToolNet.tools.bilibili.parser import extract_all_from_message

                return await extract_all_from_message(text)
            except Exception:
                return []

        async def process_bilibili(bvid: str) -> Optional[str]:
            try:
                from webnet.ToolNet.tools.bilibili.bilibili_video import BilibiliVideoTool

                tool = BilibiliVideoTool()

                class FakeCtx:
                    pass

                result = await tool.execute(FakeCtx(), args={"video_id": bvid, "action": "card"})
                return result if result and "失败" not in result else None
            except Exception:
                return None

        pipeline.register("bilibili", detect_bilibili, process_bilibili, priority=bili_cfg.get("priority", 10))

    # ── arXiv ──
    arxiv_cfg = detectors_cfg.get("arxiv", {})
    if arxiv_cfg.get("enabled", True):

        def detect_arxiv(text: str) -> list:
            import re

            return list(set(re.findall(r"(?:arxiv\.org/abs/|arxiv:\s*)(\d{4}\.\d{4,}(?:v\d+)?)", text, re.IGNORECASE)))

        async def process_arxiv(paper_id: str) -> Optional[str]:
            try:
                from webnet.ToolNet.tools.network.arxiv_search import ArxivSearchTool

                tool = ArxivSearchTool()

                class FakeCtx:
                    pass

                result = await tool.execute(FakeCtx(), args={"query": paper_id, "max_results": 1})
                return result if result else None
            except Exception:
                return None

        pipeline.register("arxiv", detect_arxiv, process_arxiv, priority=arxiv_cfg.get("priority", 8))

    # ── GitHub ──
    gh_cfg = detectors_cfg.get("github", {})
    if gh_cfg.get("enabled", True):

        def detect_github(text: str) -> list:
            try:
                from webnet.ToolNet.tools.network.github_repo import GithubAutoDetect

                url_repos = GithubAutoDetect.detect(text)
                owner_repos = GithubAutoDetect.detect_owner_repo(text)
                all_repos = []
                seen = set()
                for owner, repo in url_repos + owner_repos:
                    key = f"{owner}/{repo}".lower()
                    if key not in seen:
                        seen.add(key)
                        all_repos.append(f"{owner}/{repo}")
                return all_repos[:3]
            except Exception:
                return []

        async def process_github(repo_id: str) -> Optional[str]:
            try:
                from webnet.ToolNet.tools.network.github_repo import GithubRepoTool

                tool = GithubRepoTool()

                class FakeCtx:
                    pass

                result = await tool.execute(FakeCtx(), args={"repo_id": repo_id})
                return result if result and "失败" not in result else None
            except Exception:
                return None

        pipeline.register("github", detect_github, process_github, priority=gh_cfg.get("priority", 5))

    logger.info("[Pipeline] 默认检测器注册完成")
