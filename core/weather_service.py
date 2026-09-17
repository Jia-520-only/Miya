"""Truthful, non-persistent weather queries shared by Miya's tools and Earth Online."""

from __future__ import annotations

import copy
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import httpx

from config.config_utils import get_api_key

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 600
_CACHE: Dict[tuple[str, bool, int], tuple[float, Dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()


def _to_float(value: Any) -> Optional[float]:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _weather_icon(text: str) -> str:
    if any(token in text for token in ("晴", "阳光")):
        return "☼"
    if any(token in text for token in ("雨", "雪", "雷")):
        return "≋"
    return "◌"


def _resolved_location(payload: Dict[str, Any], requested: str) -> Dict[str, str]:
    return {
        "id": str(payload.get("id") or ""),
        "name": str(payload.get("name") or requested),
        "country": str(payload.get("country") or ""),
        "path": str(payload.get("path") or payload.get("name") or requested),
        "timezone": str(payload.get("timezone") or ""),
        "timezone_offset": str(payload.get("timezone_offset") or ""),
    }


def _base_result(location: str, include_forecast: bool, forecast_days: int) -> Dict[str, Any]:
    now = datetime.now().astimezone()
    return {
        "requested_location": location,
        "resolved_location": {},
        "city": "",
        "provider": "seniverse",
        "source": "seniverse",
        "source_status": "unavailable",
        "resolution_status": "unresolved",
        "captured_at": "",
        "served_at": now.isoformat(),
        "expires_at": "",
        "is_stale": True,
        "from_cache": False,
        "weather": "未同步",
        "weather_icon": "?",
        "temperature": None,
        "condition_code": "",
        "humidity": None,
        "wind": "",
        "forecast_requested": include_forecast,
        "forecast_status": "not_requested" if not include_forecast else "unavailable",
        "forecast_days": forecast_days,
        "forecast": [],
    }


def query_weather(
    location: str,
    *,
    include_forecast: bool = True,
    forecast_days: int = 3,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Query a location without mutating Earth Online settings or persisted world state."""
    requested = str(location or "").strip()[:160]
    days = max(1, min(7, int(forecast_days or 3)))
    result = _base_result(requested, bool(include_forecast), days)
    if not requested:
        result["source_status"] = "needs_location"
        return result

    cache_key = (requested.casefold(), bool(include_forecast), days)
    if not force_refresh:
        with _CACHE_LOCK:
            cached = _CACHE.get(cache_key)
        if cached and time.monotonic() - cached[0] < _CACHE_TTL_SECONDS:
            result = copy.deepcopy(cached[1])
            result["from_cache"] = True
            result["served_at"] = datetime.now().astimezone().isoformat()
            return result

    api_key = get_api_key("SENIVERSE_API_KEY") or get_api_key("WEATHER_API_KEY")
    if not api_key:
        result["source_status"] = "not_configured"
        return result

    now = datetime.now().astimezone()
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(
                "https://api.seniverse.com/v3/weather/now.json",
                params={"key": api_key, "location": requested, "language": "zh-Hans", "unit": "c"},
            )
            response.raise_for_status()
            payload = response.json()
            current_result = (payload.get("results") or [])[0]
            current = current_result.get("now") or {}
            location_data = current_result.get("location") or {}
            resolved = _resolved_location(location_data, requested)
            weather_text = str(current.get("text") or "未知")
            direction = str(current.get("wind_direction") or "").strip()
            scale = str(current.get("wind_scale") or "").strip()
            wind = " ".join(part for part in (direction, f"{scale}级" if scale else "") if part)
            captured_at = str(current_result.get("last_update") or now.isoformat())
            result.update({
                "resolved_location": resolved,
                "city": resolved["name"],
                "source_status": "ok",
                "resolution_status": "provider_resolved",
                "captured_at": captured_at,
                "expires_at": (now + timedelta(seconds=_CACHE_TTL_SECONDS)).isoformat(),
                "is_stale": False,
                "weather": weather_text,
                "weather_icon": _weather_icon(weather_text),
                "temperature": _to_float(current.get("temperature")),
                "condition_code": str(current.get("code") or ""),
                "humidity": _to_float(current.get("humidity")),
                "wind": wind,
            })

            if include_forecast:
                try:
                    forecast_response = client.get(
                        "https://api.seniverse.com/v3/weather/daily.json",
                        params={
                            "key": api_key,
                            "location": resolved.get("id") or requested,
                            "language": "zh-Hans",
                            "unit": "c",
                            "start": 0,
                            "days": days,
                        },
                    )
                    forecast_response.raise_for_status()
                    forecast_payload = forecast_response.json()
                    daily_result = (forecast_payload.get("results") or [])[0]
                    daily_items = daily_result.get("daily") or []
                    result["forecast"] = [
                        {
                            "date": str(item.get("date") or ""),
                            "text_day": str(item.get("text_day") or "未知"),
                            "text_night": str(item.get("text_night") or "未知"),
                            "high": _to_float(item.get("high")),
                            "low": _to_float(item.get("low")),
                            "rainfall": _to_float(item.get("rainfall")),
                            "precip": _to_float(item.get("precip")),
                            "humidity": _to_float(item.get("humidity")),
                            "wind_direction": str(item.get("wind_direction") or ""),
                            "wind_scale": str(item.get("wind_scale") or ""),
                        }
                        for item in daily_items[:days]
                    ]
                    result["forecast_status"] = "ok" if result["forecast"] else "unavailable"
                except Exception as exc:
                    logger.warning("[Weather] 天气预报查询失败 (%s): %s", requested, exc)
                    result["forecast_status"] = "error"
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        logger.warning("[Weather] 天气响应无法解析 (%s): %s", requested, exc)
        result["source_status"] = "not_found"
    except httpx.HTTPStatusError as exc:
        logger.warning("[Weather] 天气服务 HTTP 错误 (%s): %s", requested, exc.response.status_code)
        result["source_status"] = "not_found" if exc.response.status_code in {400, 404} else "error"
    except Exception as exc:
        logger.warning("[Weather] 天气查询失败 (%s): %s", requested, exc)
        result["source_status"] = "error"

    if result["source_status"] == "ok":
        with _CACHE_LOCK:
            expired = [key for key, cached in _CACHE.items() if time.monotonic() - cached[0] >= _CACHE_TTL_SECONDS]
            for key in expired:
                _CACHE.pop(key, None)
            while len(_CACHE) >= 256:
                _CACHE.pop(next(iter(_CACHE)))
            _CACHE[cache_key] = (time.monotonic(), copy.deepcopy(result))
    return result


def format_weather_report(data: Dict[str, Any]) -> str:
    """Render a provenance-aware result for LLM tools without inventing missing fields."""
    status = str(data.get("source_status") or "unavailable")
    requested = str(data.get("requested_location") or "未提供地点")
    if status != "ok":
        labels = {
            "needs_location": "没有提供查询地点",
            "not_configured": "尚未配置心知天气 API Key",
            "not_found": "天气服务没有解析到这个地点，请补充省份或国家",
            "error": "天气服务暂时不可用",
        }
        return f"【{requested}】{labels.get(status, '天气暂未同步')}（状态: {status}；未使用模拟数据）"

    resolved = data.get("resolved_location") or {}
    resolved_path = str(resolved.get("path") or resolved.get("name") or data.get("city") or requested)
    lines = [
        f"【天气查询】请求地点: {requested}",
        f"服务解析地点: {resolved_path}",
        f"当前: {data.get('weather') or '未知'} · {data.get('temperature') if data.get('temperature') is not None else '未知'}°C",
    ]
    details = []
    if data.get("humidity") is not None:
        details.append(f"湿度 {data['humidity']}%")
    if data.get("wind"):
        details.append(f"风况 {data['wind']}")
    if details:
        lines.append(" · ".join(details))
    forecast = data.get("forecast") or []
    if forecast:
        lines.append("未来天气:")
        for day in forecast:
            low = day.get("low") if day.get("low") is not None else "未知"
            high = day.get("high") if day.get("high") is not None else "未知"
            temperature = f"{low}~{high}°C"
            lines.append(f"- {day.get('date', '')}: {day.get('text_day', '未知')} / {day.get('text_night', '未知')} · {temperature}")
    elif data.get("forecast_requested") and data.get("forecast_status") != "ok":
        lines.append("未来天气: 此次未取得预报数据")
    cache_label = " · 10 分钟缓存" if data.get("from_cache") else ""
    lines.append(f"数据源: 心知天气 · 观测时间: {data.get('captured_at') or '未知'}{cache_label}")
    lines.append("本次仅查询，不会修改默认天气地点、当前位置或地点档案。")
    return "\n".join(lines)
