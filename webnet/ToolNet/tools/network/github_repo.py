"""
GitHub 仓库信息获取工具 — 所有可配置值从 config 读取
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

import httpx

from config.config_utils import get_api_key, get_github_config, get_text_message
from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)

_GITHUB_REPO_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9_.\-]+)/([A-Za-z0-9_.\-]+)/?(?!\S*\.(?:png|jpg|jpeg|gif|svg|webp|ico)\b)[^\s]*",
    re.IGNORECASE,
)
_OWNER_REPO_PATTERN = re.compile(
    r"(?:^|\s)([A-Za-z0-9_.\-]+)/([A-Za-z0-9_.\-]+)(?:\s|$)",
)
_COMMON_WORDS = {"a", "an", "the", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of", "and", "or", "but"}


class GithubRepoTool(BaseTool):
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "github_repo",
            "description": "获取GitHub仓库信息。当用户发送GitHub仓库链接、提到owner/repo格式的仓库名、或询问某个GitHub项目时使用。自动检测消息中的GitHub链接。",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_id": {
                        "type": "string",
                        "description": "仓库标识：完整URL、owner/repo 格式、或包含GitHub链接的消息文本",
                    },
                },
                "required": ["repo_id"],
            },
        }

    async def execute(self, args: Dict, context: ToolContext) -> str:
        args = args or {}
        repo_id = args.get("repo_id", "")
        if not repo_id:
            return get_text_message("github", "repo_id_required")
        owner, repo = self._parse_repo(repo_id)
        if not owner or not repo:
            return get_text_message("github", "parse_failed", text=repo_id[:100])
        return await self._fetch_repo_info(owner, repo)

    def _parse_repo(self, text: str) -> tuple[Optional[str], Optional[str]]:
        url_match = _GITHUB_REPO_PATTERN.search(text)
        if url_match:
            return url_match.group(1), url_match.group(2).rstrip("/")
        match = _OWNER_REPO_PATTERN.search(text)
        if match:
            return match.group(1), match.group(2)
        parts = text.strip().split("/")
        if len(parts) == 2:
            return parts[0], parts[1]
        return None, None

    async def _fetch_repo_info(self, owner: str, repo: str) -> str:
        api_url = get_github_config("api_url", default="https://api.github.com")
        user_agent = get_github_config("user_agent", default="Miya-Bot/1.0")
        timeout_val = get_github_config("timeout", default=15)

        try:
            async with httpx.AsyncClient(timeout=timeout_val) as client:
                headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": user_agent}
                token = get_api_key("GITHUB_TOKEN")
                if token:
                    headers["Authorization"] = f"token {token}"

                resp = await client.get(f"{api_url}/repos/{owner}/{repo}", headers=headers)

                if resp.status_code == 404:
                    return get_text_message("github", "not_found", owner=owner, repo=repo)
                if resp.status_code == 403:
                    return get_text_message("github", "rate_limit")
                if resp.status_code != 200:
                    return get_text_message("github", "http_error", code=resp.status_code, owner=owner, repo=repo)

                data = resp.json()
                lines = [
                    get_text_message("github", "header", full_name=data.get("full_name", f"{owner}/{repo}")),
                    "",
                ]
                desc = data.get("description", "")
                if desc:
                    lines.append(desc)
                    lines.append("")

                def _fmt(key: str, count: Any) -> str:
                    try:
                        c = int(count)
                        return f"{c:,}"
                    except (ValueError, TypeError):
                        return str(count)

                lines.append(get_text_message("github", "stars", count=data.get("stargazers_count", 0)))
                lines.append(get_text_message("github", "forks", count=data.get("forks_count", 0)))
                lines.append(get_text_message("github", "watchers", count=data.get("subscribers_count", 0)))
                lines.append(get_text_message("github", "issues", count=data.get("open_issues_count", 0)))

                lang = data.get("language", "")
                if lang:
                    lines.append(get_text_message("github", "language", lang=lang))

                license_info = data.get("license")
                if license_info:
                    lines.append(get_text_message("github", "license", license=license_info.get("spdx_id", "Unknown")))

                topics = data.get("topics", [])
                if topics:
                    lines.append(get_text_message("github", "topics", topics=", ".join(topics[:8])))

                lines.append("")
                lines.append(
                    get_text_message("github", "link", url=data.get("html_url", f"https://github.com/{owner}/{repo}"))
                )

                created = data.get("created_at", "")[:10]
                updated = data.get("updated_at", "")[:10]
                if created:
                    lines.append(get_text_message("github", "created_updated", created=created, updated=updated))

                default_branch = data.get("default_branch", "")
                if default_branch:
                    lines.append(get_text_message("github", "branch", branch=default_branch))

                return "\n".join(lines)

        except httpx.TimeoutException:
            return get_text_message("github", "timeout", owner=owner, repo=repo)
        except Exception as e:
            logger.error(f"获取 GitHub 仓库信息失败: {e}")
            return f"获取仓库信息失败: {str(e)[:100]}"


class GithubAutoDetect:
    """GitHub 仓库自动检测器"""

    @staticmethod
    def detect(text: str) -> list[tuple[str, str]]:
        repos = []
        seen = set()
        for match in _GITHUB_REPO_PATTERN.finditer(text):
            owner, repo_name = match.group(1), match.group(2).rstrip("/")
            key = f"{owner}/{repo_name}".lower()
            if key not in seen:
                seen.add(key)
                repos.append((owner, repo_name))
        return repos

    @staticmethod
    def detect_owner_repo(text: str) -> list[tuple[str, str]]:
        repos = []
        seen = set()
        for match in _OWNER_REPO_PATTERN.finditer(text):
            owner, repo_name = match.group(1), match.group(2)
            if owner.lower() in _COMMON_WORDS:
                continue
            key = f"{owner}/{repo_name}".lower()
            if key not in seen:
                seen.add(key)
                repos.append((owner, repo_name))
        return repos
