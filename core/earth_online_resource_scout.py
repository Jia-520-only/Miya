"""地球online 收益中枢 — 开放许可资源发现器。

弥娅自己去公开授权源找"能合法卖的虚拟资源"，规则驱动地判定授权，不需要模型猜测。

设计边界 (与 v21/v22 数字资源工坊一致):
  * 只收录能**确定性判定**为可合法转售的公开资源:
      - CC0 / 公有领域 (PD / PDM)  → 自动核验并进入可售资源库
      - CC BY / CC BY-SA / CC BY-ND → 只入库为待核验候选 (需要署名 / 相同方式共享 / 不得修改)
  * 明确拒绝: 非商业 (NC) 许可、免版税素材库原样转售 (Unsplash / Pexels / Pixabay 等)、
    "保留所有权利"、聚合站，以及任何命中风险信号的资源。
  * 只做"找到并整理入库"：不下载文件、不上传、不发布、不交易。

数据源全部是带公开许可过滤的官方 API (无需 API Key):
  openverse  — Openverse API，`license=cc0,pdm` 过滤的图片
  gutenberg  — Project Gutenberg 官方 OPDS 检索 (公版书)
  met_museum — 大都会艺术博物馆 Open Access (CC0, `isPublicDomain=true`)

配置: config/qq_config.yaml → earth_online.earning_scout
"""

from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from urllib.parse import quote, urlparse

logger = logging.getLogger(__name__)

# 对外声明的范围 (写进工具/接口返回，让佳随时看得见弥娅的边界)
SCOPE_NOTE = (
    "只收录 CC0、公有领域和需署名的开放许可；非商业许可与免版税素材库原样转售一律拒绝，"
    "未知许可不入库。只找到并整理，不下载、不发布、不交易。"
)

DEFAULT_PROVIDERS: Tuple[str, ...] = ("openverse", "gutenberg", "met_museum")

DEFAULT_QUERIES: Dict[str, List[str]] = {
    "openverse": [
        "vintage botanical illustration",
        "public domain vintage poster",
        "antique map",
    ],
    "gutenberg": [
        "fairy tales",
        "classic literature",
        "poetry",
    ],
    "met_museum": [
        "ukiyo-e",
        "botanical still life",
        "landscape painting",
    ],
}

# ── 授权判定规则 (确定性，不依赖模型) ──────────────────────────────

# 许可家族 → (判定, license_type, 说明)
LICENSE_FAMILY_VERDICTS: Dict[str, Tuple[str, str, str]] = {
    "cc0": ("auto_verified", "public_domain", "CC0 1.0 公有领域贡献，可商用、可转售、无需署名"),
    "pdm": ("auto_verified", "public_domain", "公有领域标记，可商用、可转售"),
    "by": ("manual", "open_license", "CC BY 开放许可：可转售，但必须保留原作者署名"),
    "by-sa": ("manual", "open_license", "CC BY-SA 开放许可：可转售，需署名并以相同许可共享"),
    "by-nd": ("manual", "open_license", "CC BY-ND：只允许原样转售，不得修改后销售"),
    "by-nc": ("blocked", "unknown", "非商业许可 (NC)：不能用于任何销售"),
    "forbidden": ("blocked", "unknown", "许可明确禁止转售或为商业素材库内容"),
    "unknown": ("skipped", "unknown", "许可无法确定性判定，不进入可售资源库"),
}

# 命中即拒绝的许可措辞
_FORBIDDEN_LICENSE_MARKERS = (
    "all-rights-reserved",
    "allrightsreserved",
    "arr",
    "fair-use",
    "fairuse",
    "noncommercial",
    "non-commercial",
    "editorial-use-only",
    "rights-managed",
)

# 命中即拒绝的来源域名 (免版税素材库不允许原样转售；聚合站来源不可追溯)
BLOCKED_SOURCE_DOMAINS: Dict[str, str] = {
    "unsplash.com": "Unsplash 许可禁止原样转售未修改素材",
    "pexels.com": "Pexels 许可禁止原样转售未修改素材",
    "pixabay.com": "Pixabay 许可禁止原样转售未修改素材",
    "freepik.com": "Freepik 免费许可禁止转售原始素材",
    "shutterstock.com": "商业素材库，未购买转售授权",
    "istockphoto.com": "商业素材库，未购买转售授权",
    "gettyimages.com": "商业素材库，未购买转售授权",
    "stock.adobe.com": "商业素材库，未购买转售授权",
    "dreamstime.com": "商业素材库，未购买转售授权",
    "alamy.com": "商业素材库，未购买转售授权",
    "pinterest.com": "聚合站，原始来源与授权不可追溯",
}


def _domain_of(value: Any) -> str:
    try:
        host = urlparse(str(value or "").strip()).hostname or ""
    except ValueError:
        return ""
    return host.lower().rstrip(".")


def _normalise_license_text(value: Any) -> str:
    """把任意许可文本压成可判定的小写短串 (CC BY-NC-SA 4.0 → cc-by-nc-sa-4.0)。"""
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = text.replace("creative commons", " ").replace("license", " ")
    text = re.sub(r"[^a-z0-9.+-]+", "-", text)
    return re.sub(r"-{2,}", "-", text).strip("-")


def _license_family(token: str) -> str:
    """许可家族判定 (纯字符串规则，可单测)。"""
    compact = token.replace(".", "-")
    if not compact:
        return "unknown"
    if any(marker in compact for marker in _FORBIDDEN_LICENSE_MARKERS):
        return "forbidden"
    if re.match(r"^(cc-)?(cc0|zero)(-|$)", compact) or compact.startswith("cc0"):
        return "cc0"
    if (
        "public-domain" in compact
        or "publicdomain" in compact
        or "no-known-copyright" in compact
        or compact in {"pd", "pdm", "public"}
        or compact.startswith("pdm-")
    ):
        return "pdm"
    if re.match(r"^(cc-)?(by-nc|nc)", compact):
        return "by-nc"
    if re.match(r"^(cc-)?(by-nd|nd)", compact):
        return "by-nd"
    if re.match(r"^(cc-)?by-sa", compact):
        return "by-sa"
    if re.match(r"^(cc-)?by(-|$)", compact):
        return "by"
    return "unknown"


def _blocked_domain_reason(candidate: Dict[str, Any]) -> str:
    for key in ("source_url", "landing_url", "license_url"):
        domain = _domain_of(candidate.get(key))
        if not domain:
            continue
        for blocked, reason in BLOCKED_SOURCE_DOMAINS.items():
            if domain == blocked or domain.endswith("." + blocked):
                return reason
    return ""


def classify_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """对一个候选资源给出确定性判定。

    返回 ``{"verdict": auto_verified|manual|blocked|skipped, "license_type": ..., "reason": ...}``。
    """
    candidate = candidate if isinstance(candidate, dict) else {}
    domain_reason = _blocked_domain_reason(candidate)
    if domain_reason:
        return {
            "verdict": "blocked",
            "license_family": "forbidden",
            "license_type": "unknown",
            "reason": domain_reason,
        }
    token = _normalise_license_text(candidate.get("license_text"))
    family = _license_family(token)
    verdict, license_type, reason = LICENSE_FAMILY_VERDICTS[family]
    return {
        "verdict": verdict,
        "license_family": family,
        "license_type": license_type,
        "reason": reason,
    }


def build_rights_note(candidate: Dict[str, Any], decision: Dict[str, Any]) -> str:
    """把授权依据写成可追溯的说明 (来源 / 许可 / 作者 / 抓取时间)。"""
    parts: List[str] = [str(decision.get("reason") or "")]
    license_url = str(candidate.get("license_url") or "").strip()
    license_text = str(candidate.get("license_text") or "").strip()
    if license_url:
        parts.append(f"许可: {license_url}")
    elif license_text:
        parts.append(f"许可: {license_text}")
    if candidate.get("creator"):
        parts.append(f"作者: {candidate['creator']}")
    if candidate.get("source_name"):
        parts.append(f"来源: {candidate['source_name']}")
    if candidate.get("extra_note"):
        parts.append(str(candidate["extra_note"]))
    if decision.get("verdict") == "manual":
        parts.append("需人工确认署名/共享方式后才能标记授权已核验")
    parts.append(f"抓取日期: {datetime.now().date().isoformat()}")
    return " · ".join(part for part in parts if part)[:3000]


# ── 公开数据源 (全部无需 API Key，且自带许可字段) ────────────────────


# 代码内置的公开 API 域名：这些 URL 全部由本模块常量拼装，不接受用户传入主机名，
# 所以只做字面校验即可 (代理 fake-ip 模式下公开域名会被解析成 198.18.x.x)。
TRUSTED_API_HOSTS: Tuple[str, ...] = (
    "api.openverse.org",
    "www.gutenberg.org",
    "collectionapi.metmuseum.org",
)


def _fetch_public_bytes(url: str, accept: str, timeout: int = 20) -> bytes:
    """通过地球online 既有的公开地址抓取器取数据 (逐跳校验，拒绝内网地址)。"""
    from core.earth_online_store import EarthOnlineStore

    host = _domain_of(url)
    if host not in TRUSTED_API_HOSTS:
        raise ValueError(f"资源发现器不允许访问非内置数据源: {host or url}")
    return EarthOnlineStore.fetch_public_document(
        url, accept=accept, timeout=timeout, trusted_hosts=TRUSTED_API_HOSTS
    )


def _fetch_json(url: str, timeout: int = 20) -> Any:
    return json.loads(_fetch_public_bytes(url, "application/json", timeout).decode("utf-8", "replace"))


def _search_openverse(query: str, limit: int) -> List[Dict[str, Any]]:
    payload = _fetch_json(
        "https://api.openverse.org/v1/images/?q="
        + quote(str(query))
        + "&license=cc0,pdm&page_size="
        + str(max(1, min(20, int(limit))))
    )
    items = payload.get("results") if isinstance(payload, dict) else None
    results: List[Dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        landing = str(item.get("foreign_landing_url") or "").strip()
        file_url = str(item.get("url") or "").strip()
        if not title or not (landing or file_url):
            continue
        license_text = f"{item.get('license') or ''} {item.get('license_version') or ''}".strip()
        results.append({
            "title": title[:200],
            "source_url": landing or file_url,
            "landing_url": landing,
            "source_name": f"Openverse/{item.get('source') or item.get('provider') or 'open'}",
            "license_text": license_text,
            "license_url": str(item.get("license_url") or "").strip(),
            "content_uri": file_url,
            "creator": str(item.get("creator") or "").strip(),
            "extra_note": f"检索词「{query}」",
        })
    return results


def _is_opds_stat_line(text: str) -> bool:
    """Project Gutenberg OPDS 的 <content> 有时是统计行 (如 "39907 downloads") 而非作者。"""
    value = str(text or "").strip()
    if not value:
        return True
    return bool(re.match(r"^[\d,.\s]+\s*(downloads?|reads?|views?|pages?)$", value, re.IGNORECASE))


def _search_gutenberg(query: str, limit: int) -> List[Dict[str, Any]]:
    """Project Gutenberg 官方 OPDS 检索。

    之前用的是 Gutendex 第三方镜像，单次检索要 54-100 秒且经常超时，无法放进后台巡检；
    官方 OPDS 检索通常在 0.5-2 秒返回，且版权判定同样是公版。
    """
    payload = _fetch_public_bytes(
        "https://www.gutenberg.org/ebooks/search.opds/?query=" + quote(str(query)),
        "application/atom+xml, application/xml, text/xml",
        timeout=20,
    )
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError("Project Gutenberg 返回了无法解析的检索结果") from exc
    cap = max(1, min(20, int(limit)))
    results: List[Dict[str, Any]] = []
    for node in root.iter():
        if len(results) >= cap:
            break
        tag = node.tag.rsplit("}", 1)[-1].lower() if isinstance(node.tag, str) else ""
        if tag != "entry":
            continue
        title, book_id, creator = "", "", ""
        for child in list(node):
            child_tag = child.tag.rsplit("}", 1)[-1].lower() if isinstance(child.tag, str) else ""
            if child_tag == "title":
                title = str(child.text or "").strip()
            elif child_tag == "id":
                matched = re.search(r"/ebooks/(\d+)(?:\.opds)?/?$", str(child.text or "").strip())
                if matched:
                    book_id = matched.group(1)
            elif child_tag == "content":
                text = str(child.text or "").strip()
                # 有的条目 <content> 放的是"39907 downloads"这类统计，不是作者名。
                if text and not _is_opds_stat_line(text):
                    creator = creator or text
            elif child_tag == "author":
                for sub in list(child):
                    sub_tag = sub.tag.rsplit("}", 1)[-1].lower() if isinstance(sub.tag, str) else ""
                    if sub_tag == "name" and str(sub.text or "").strip():
                        creator = str(sub.text).strip()
        if not title or not book_id:
            continue  # 导航型条目 (Subjects / Bookshelves) 没有书号
        results.append({
            "title": title[:200],
            "source_url": f"https://www.gutenberg.org/ebooks/{book_id}",
            "landing_url": f"https://www.gutenberg.org/ebooks/{book_id}",
            "source_name": "Project Gutenberg",
            "license_text": "public domain",
            "license_url": "https://www.gutenberg.org/policy/license.html",
            "content_uri": f"https://www.gutenberg.org/ebooks/{book_id}.epub3.images",
            "creator": creator,
            "extra_note": "公版文本；转售时请移除 Project Gutenberg 头信息与商标",
        })
    return results


def _search_met_museum(query: str, limit: int) -> List[Dict[str, Any]]:
    payload = _fetch_json(
        "https://collectionapi.metmuseum.org/public/collection/v1/search?hasImages=true&q=" + quote(str(query))
    )
    object_ids = payload.get("objectIDs") if isinstance(payload, dict) else None
    candidates_ids = [str(value) for value in (object_ids or []) if str(value).isdigit()]
    # 每个检索词最多回查少量对象详情，避免把远端打爆。
    lookups = max(1, min(5, int(limit)))
    results: List[Dict[str, Any]] = []
    for object_id in candidates_ids:
        if len(results) >= max(1, min(20, int(limit))) or lookups <= 0:
            break
        lookups -= 1
        try:
            obj = _fetch_json(
                f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{object_id}", timeout=20
            )
        except Exception as exc:  # 单个对象失败不影响整轮
            logger.debug("[ResourceScout] Met 对象 %s 读取失败: %s", object_id, exc)
            continue
        if not isinstance(obj, dict) or not obj.get("isPublicDomain"):
            continue
        title = str(obj.get("title") or "").strip()
        image = str(obj.get("primaryImage") or "").strip()
        if not title or not image:
            continue
        results.append({
            "title": title[:200],
            "source_url": str(obj.get("objectURL") or f"https://www.metmuseum.org/art/collection/search/{object_id}"),
            "landing_url": str(obj.get("objectURL") or ""),
            "source_name": "The Met Open Access",
            "license_text": "CC0 1.0",
            "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "content_uri": image,
            "creator": str(obj.get("artistDisplayName") or "").strip(),
            "extra_note": f"大都会博物馆 Open Access · {obj.get('objectDate') or ''} · {obj.get('medium') or ''}".strip(" ·"),
        })
    return results


PROVIDER_FETCHERS: Dict[str, Callable[[str, int], List[Dict[str, Any]]]] = {
    "openverse": _search_openverse,
    "gutenberg": _search_gutenberg,
    "met_museum": _search_met_museum,
}

PROVIDER_LABELS: Dict[str, str] = {
    "openverse": "Openverse (CC0 / 公有领域图片)",
    "gutenberg": "Project Gutenberg (公版书)",
    "met_museum": "大都会博物馆 Open Access (CC0 馆藏)",
}


# ── 配置 ────────────────────────────────────────────────


def _bounded_int(raw: Dict[str, Any], key: str, default: int, low: int, high: int) -> int:
    try:
        value = int(raw.get(key, default) or default)
    except (TypeError, ValueError):
        value = default
    return max(low, min(high, value))


def normalise_scout_config(raw: Any) -> Dict[str, Any]:
    """把配置节收敛成带兜底的内部结构 (未知数据源会被剔除并报告)。"""
    raw = raw if isinstance(raw, dict) else {}
    requested = raw.get("providers")
    if not isinstance(requested, list) or not requested:
        requested = list(DEFAULT_PROVIDERS)
    providers: List[str] = []
    dropped: List[str] = []
    for value in requested:
        key = str(value or "").strip().lower()
        if not key:
            continue
        if key in PROVIDER_FETCHERS:
            if key not in providers:
                providers.append(key)
        elif key not in dropped:
            dropped.append(key)
    if not providers:
        providers = list(DEFAULT_PROVIDERS)
    queries_raw = raw.get("queries") if isinstance(raw.get("queries"), dict) else {}
    queries: Dict[str, List[str]] = {}
    for provider in providers:
        values = queries_raw.get(provider)
        if not isinstance(values, list) or not values:
            values = DEFAULT_QUERIES.get(provider, [])
        queries[provider] = [str(value).strip() for value in values if str(value).strip()][:5]
    return {
        "enabled": bool(raw.get("enabled", True)),
        "auto_verify": bool(raw.get("auto_verify", True)),
        "max_per_cycle": _bounded_int(raw, "max_per_cycle", 2, 1, 20),
        "daily_cap": _bounded_int(raw, "daily_cap", 12, 1, 200),
        "per_query": _bounded_int(raw, "per_query", 4, 1, 20),
        "providers": providers,
        "dropped_providers": dropped,
        "queries": queries,
    }


def load_scout_config() -> Dict[str, Any]:
    from config.config_utils import get_qq_config

    return normalise_scout_config(get_qq_config("earth_online", "earning_scout", default={}) or {})


def provider_catalog() -> List[Dict[str, str]]:
    """给前台/工具用的数据源清单。"""
    return [{"key": key, "label": PROVIDER_LABELS.get(key, key)} for key in DEFAULT_PROVIDERS]


# ── 主流程 ──────────────────────────────────────────────


def _rotated_providers(providers: Sequence[str]) -> List[str]:
    """按时间轮换数据源顺序，让每个源都能轮到有限的新增额度。"""
    ordered = list(providers)
    if len(ordered) < 2:
        return ordered
    now = datetime.now()
    offset = (now.toordinal() * 24 + now.hour) % len(ordered)
    return ordered[offset:] + ordered[:offset]


def _title_key(title: str) -> str:
    return re.sub(r"\W+", "", str(title or "").lower())[:80]


def scout_open_resources(
    store: Any,
    *,
    query: str = "",
    provider: str = "",
    limit: int = 0,
    respect_limits: bool = True,
    config: Optional[Dict[str, Any]] = None,
    fetchers: Optional[Dict[str, Callable[[str, int], List[Dict[str, Any]]]]] = None,
) -> Dict[str, Any]:
    """去找开放许可资源并把可合法转售的部分入库。

    ``respect_limits=True`` (后台巡检用) 时遵守开关、单轮上限和每日上限；
    手动调用 (弥娅工具 / 接口) 可以指定 query / provider / limit。
    """
    started_at = datetime.now().isoformat()
    settings = config if isinstance(config, dict) else load_scout_config()
    if fetchers is not None and not isinstance(fetchers, dict):
        raise TypeError("fetchers 必须是 {数据源: 取回函数} 映射")
    registry = fetchers if isinstance(fetchers, dict) else PROVIDER_FETCHERS
    result: Dict[str, Any] = {
        "success": True,
        "enabled": bool(settings.get("enabled", True)),
        "started_at": started_at,
        "finished_at": started_at,
        "created": [],
        "created_count": 0,
        "auto_verified_count": 0,
        "pending_count": 0,
        "blocked": [],
        "blocked_count": 0,
        "skipped_license_count": 0,
        "skipped_duplicate_count": 0,
        "errors": [],
        "providers": {},
        "auto_verify": bool(settings.get("auto_verify", True)),
        "daily_used": 0,
        "daily_cap": int(settings.get("daily_cap", 0) or 0),
        "dropped_providers": list(settings.get("dropped_providers") or []),
        "scope": SCOPE_NOTE,
    }
    if not result["enabled"]:
        result["skipped"] = "disabled"
        result["message"] = "资源发现器未启用 (earth_online.earning_scout.enabled)"
        return result

    available = [key for key in (settings.get("providers") or DEFAULT_PROVIDERS) if key in registry]
    asked_provider = str(provider or "").strip().lower()
    if asked_provider:
        if asked_provider not in registry:
            result["success"] = False
            result["skipped"] = "unknown_provider"
            result["message"] = f"未知数据源: {asked_provider}"
            return result
        available = [asked_provider]
    elif respect_limits:
        available = _rotated_providers(available)
    if not available:
        result["success"] = False
        result["skipped"] = "no_provider"
        result["message"] = "没有可用的资源数据源"
        return result

    # 每日上限 (含人工收录，避免后台把资源库刷爆)
    if respect_limits:
        today = datetime.now().date().isoformat()
        try:
            used = int(store.count_digital_resources_created_since(today) or 0)
        except Exception as exc:
            logger.debug("[ResourceScout] 每日用量统计失败: %s", exc)
            used = 0
        result["daily_used"] = used
        if used >= result["daily_cap"]:
            result["skipped"] = "daily_cap"
            result["message"] = f"今日新增资源已达上限 {result['daily_cap']} 条"
            return result

    budget = max(1, min(20, int(limit or 0))) if limit else int(settings.get("max_per_cycle", 2) or 2)
    if respect_limits:
        budget = min(budget, max(0, int(result["daily_cap"]) - int(result["daily_used"])))
    per_query = max(1, min(20, int(limit or settings.get("per_query", 4) or 4)))
    # 后台巡检每个数据源只跑 1 个检索词，避免把一轮巡检拖成一个长请求队列；
    # 手动调用 (弥娅工具 / 前台) 才允许一次跑完配置里的前 3 个主题。
    query_budget = 1 if respect_limits else 3

    queries = settings.get("queries") if isinstance(settings.get("queries"), dict) else {}
    known = store.list_digital_resources()
    existing_urls = {str(item.get("source_url") or "").strip() for item in known}
    existing_titles = {_title_key(item.get("title")) for item in known}

    for key in available:
        result["providers"][key] = {"queries": 0, "candidates": 0, "created": 0, "blocked": 0}
        if budget <= 0:
            break
        provider_queries = [str(query).strip()] if str(query or "").strip() else list(queries.get(key) or [])
        if not provider_queries:
            continue
        for search_term in provider_queries[:query_budget]:
            if budget <= 0:
                break
            result["providers"][key]["queries"] += 1
            try:
                candidates = registry[key](search_term, per_query) or []
            except Exception as exc:
                result["errors"].append({"provider": key, "query": search_term, "error": str(exc)[:300]})
                logger.debug("[ResourceScout] %s 检索失败 (%s): %s", key, search_term, exc)
                continue
            for candidate in candidates:
                if budget <= 0:
                    break
                if not isinstance(candidate, dict):
                    continue
                result["providers"][key]["candidates"] += 1
                decision = classify_candidate(candidate)
                verdict = decision.get("verdict")
                if verdict == "blocked":
                    result["blocked_count"] += 1
                    result["providers"][key]["blocked"] += 1
                    if len(result["blocked"]) < 10:
                        result["blocked"].append({
                            "title": str(candidate.get("title") or "")[:160],
                            "reason": decision.get("reason") or "",
                        })
                    continue
                if verdict == "skipped":
                    result["skipped_license_count"] += 1
                    continue
                source_url = str(candidate.get("source_url") or "").strip()
                title_key = _title_key(candidate.get("title"))
                if (source_url and source_url in existing_urls) or (title_key and title_key in existing_titles):
                    result["skipped_duplicate_count"] += 1
                    continue
                payload = {
                    "title": str(candidate.get("title") or "").strip()[:200],
                    "source_url": source_url,
                    "source_name": str(candidate.get("source_name") or "")[:200],
                    "license_type": decision.get("license_type") or "unknown",
                    "rights_status": "pending",
                    "rights_note": build_rights_note(candidate, decision),
                    "content_uri": str(candidate.get("content_uri") or "")[:1000],
                }
                if not payload["title"]:
                    continue
                try:
                    created = store.create_digital_resource(payload)
                except Exception as exc:
                    result["errors"].append({"provider": key, "query": search_term, "error": str(exc)[:300]})
                    continue
                budget -= 1
                if source_url:
                    existing_urls.add(source_url)
                if title_key:
                    existing_titles.add(title_key)
                item = {
                    "id": int(created.get("id") or 0),
                    "title": created.get("title") or payload["title"],
                    "license_type": created.get("license_type") or payload["license_type"],
                    "rights_status": created.get("rights_status") or "pending",
                    "status": created.get("status") or "candidate",
                    "source_name": created.get("source_name") or payload["source_name"],
                }
                if verdict == "auto_verified" and result["auto_verify"]:
                    try:
                        updated = store.update_digital_resource(
                            int(item["id"]), {"rights_status": "verified", "status": "approved"}
                        )
                        if updated:
                            item["rights_status"] = updated.get("rights_status") or "verified"
                            item["status"] = updated.get("status") or "approved"
                            result["auto_verified_count"] += 1
                    except Exception as exc:
                        result["errors"].append({
                            "provider": key, "query": search_term,
                            "error": f"自动核验未通过: {str(exc)[:200]}",
                        })
                if item["status"] != "approved":
                    result["pending_count"] += 1
                result["created"].append(item)
                result["created_count"] += 1
                result["providers"][key]["created"] += 1

    result["finished_at"] = datetime.now().isoformat()
    if result["created_count"]:
        try:
            store.log_activity(
                "earning", "▣",
                f"资源发现器新增 {result['created_count']} 条开放许可资源",
                f"自动核验 {result['auto_verified_count']} 条 · 待核验 {result['pending_count']} 条 · 拒绝 {result['blocked_count']} 条",
            )
        except Exception as exc:
            logger.debug("[ResourceScout] 动态写入失败: %s", exc)
    return result
