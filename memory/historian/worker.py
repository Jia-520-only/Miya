"""
弥娅认知记忆 — 后台史官 Worker

独立的 asyncio.Task，异步消费认知任务队列：
1. LLM 绝对化改写 observation
2. 正则闸门校验
3. ChromaDB 事件入库
4. 侧写合并（含历史事件注入）
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from memory.models import MemorySource

logger = logging.getLogger(__name__)

_MIN_POLL_INTERVAL_SECONDS = 0.1

_REWRITE_SYSTEM_PROMPT = """你是一个记忆改写助手。你的任务是将观察记录改写为绝对化的陈述。

规则：
1. 消灭所有代词（"他"、"她"、"它"、"这个"、"那个"、"这里"、"那里"、"今天"、"昨天"、"刚才"、"上次" 等），替换为具体的实体名称或绝对日期
2. 相对时间改为绝对时间（如"2024年1月"而不是"上个月"）
3. 保持事实准确，不添加未观察到的信息
4. 输出格式：直接输出改写后的陈述，一行一条，不要编号，不要前言后语
5. 如果原文已经足够绝对化，原样输出
6. 基于提供的上下文信息（当前消息原文、最近消息参考）进行实体消歧"""

_ABSOLUTE_GATE_PATTERNS = [
    (r"他", "代词「他」未消除"),
    (r"她", "代词「她」未消除"),
    (r"它[^科技]", "代词「它」未消除"),
    (r"这个(?!项目|系统|功能|应用|工具|软件|框架|代码|文件)", "代词「这个」未消除"),
    (r"那个", "代词「那个」未消除"),
    (r"这里", "代词「这里」未消除"),
    (r"那里", "代词「那里」未消除"),
    (r"今天", "相对时间「今天」"),
    (r"昨天", "相对时间「昨天」"),
    (r"明天", "相对时间「明天」"),
    (r"刚才", "相对时间「刚才」"),
    (r"上次", "相对时间「上次」"),
    (r"这次", "相对时间「这次」"),
    (r"下次", "相对时间「下次」"),
    (r"前几天", "相对时间「前几天」"),
    (r"过几天", "相对时间「过几天」"),
]

_PROFILE_MERGE_SYSTEM_PROMPT = """你是一个用户画像管理助手。根据新的观察记录，更新用户的 Markdown 画像文件。

规则：
1. 保持 YAML frontmatter 结构（entity_type, entity_id, name, tags, updated_at, source_event_id）
2. 正文用一段连贯的 Markdown 描述该实体的特征
3. 新信息与旧信息冲突时，优先信任新信息（除非标注了来源）
4. 不要丢失历史中提到的长期稳定特征
5. 标签 (tags) 应反映最新的兴趣和特征
6. 只输出完整的 Markdown 文件内容，不要额外说明"""


def _resolve_timestamp_epoch(metadata: dict[str, Any] | None = None) -> float:
    if metadata and isinstance(metadata, dict):
        ts = metadata.get("timestamp_epoch")
        if isinstance(ts, (int, float)):
            return float(ts)
    return datetime.now(datetime.UTC).timestamp()


def _preview_text(text: str, max_len: int = 120) -> str:
    t = str(text or "").strip()
    return t[:max_len] + ("..." if len(t) > max_len else "")


class HistorianWorker:
    def __init__(
        self,
        job_queue: Any,
        vector_store: Any,
        profile_storage: Any,
        ai_client: Any,
        config_getter: Callable[[], Any],
    ) -> None:
        self._job_queue = job_queue
        self._vector_store = vector_store
        self._profile_storage = profile_storage
        self._ai_client = ai_client
        self._config_getter = config_getter
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._inflight_tasks: set[asyncio.Task[None]] = set()

    async def start(self) -> None:
        logger.info("[史官] Worker 启动中")
        config = self._config_getter()
        await self._job_queue.recover_stale(
            config.get("cognitive", {}).get("historian", {}).get("stale_job_timeout_seconds", 300.0)
        )
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("[史官] Worker 已启动")

    async def stop(self) -> None:
        logger.info("[史官] Worker 停止中")
        self._stop_event.set()
        if self._task:
            await self._task
        logger.info("[史官] Worker 已停止")

    async def _poll_loop(self) -> None:
        dispatch_count = 0
        cleanup_interval = 100
        logger.info("[史官] 轮询循环已开始")
        while not self._stop_event.is_set():
            config = self._config_getter()
            result = await self._job_queue.dequeue()
            if result:
                job_id, job = result
                task = asyncio.create_task(self._process_job_with_retry(job_id, job))
                self._inflight_tasks.add(task)
                task.add_done_callback(self._inflight_tasks.discard)
                dispatch_count += 1

                if dispatch_count % cleanup_interval == 0:
                    asyncio.create_task(self._job_queue.cleanup_failed())

            poll_interval = max(
                _MIN_POLL_INTERVAL_SECONDS,
                float(config.get("cognitive", {}).get("historian", {}).get("poll_interval_seconds", 1.0)),
            )
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=poll_interval)
                break
            except asyncio.TimeoutError:
                pass

        if self._inflight_tasks:
            logger.info("[史官] 等待 %s 个进行中任务完成", len(self._inflight_tasks))
            await asyncio.gather(*self._inflight_tasks, return_exceptions=True)
        logger.info("[史官] 轮询循环结束")

    async def _process_job_with_retry(self, job_id: str, job: dict[str, Any]) -> None:
        config = self._config_getter()
        historian_config = config.get("cognitive", {}).get("historian", {})
        max_retries = int(historian_config.get("job_max_retries", 3))

        for attempt in range(max_retries + 1):
            try:
                await self._process_job(job_id, job)
                return
            except Exception as exc:
                logger.warning(
                    "[史官] 任务处理失败: job_id=%s attempt=%s/%s err=%s",
                    job_id,
                    attempt + 1,
                    max_retries + 1,
                    exc,
                )
                if attempt < max_retries:
                    await asyncio.sleep(2.0 * (attempt + 1))
                    await self._job_queue.requeue(job_id)
                    result = await self._job_queue.dequeue()
                    if result:
                        job_id, job = result
                    else:
                        return
                else:
                    await self._job_queue.fail(job_id, error=str(exc))

    async def _process_job(self, job_id: str, job: dict[str, Any]) -> None:
        config = self._config_getter()
        historian_config = config.get("cognitive", {}).get("historian", {})

        observations = job.get("observations") or []
        memo = job.get("memo", "")
        user_id = str(job.get("user_id") or "")
        group_id = str(job.get("group_id") or "")
        sender_id = str(job.get("sender_id") or user_id)
        request_type = "private" if not group_id else "group"
        source_message = str(job.get("source_message") or "")[:800]
        recent_messages = job.get("recent_messages") or []
        _force = bool(job.get("force", False))
        timestamp_epoch = job.get("timestamp_epoch", _resolve_timestamp_epoch())

        if not observations:
            logger.info("[史官] 无 observations，跳过改写: job_id=%s", job_id)
            await self._job_queue.complete(job_id)
            return

        rewrite_max_retry = int(historian_config.get("rewrite_max_retry", 2))

        for obs_idx, obs in enumerate(observations):
            obs_text = str(obs).strip()
            if not obs_text:
                continue

            rewritten = await self._rewrite_observation(obs_text, source_message, recent_messages, rewrite_max_retry)

            event_id = f"{job_id}_{obs_idx}_{int(timestamp_epoch * 1000)}"
            timestamp_local = datetime.fromtimestamp(timestamp_epoch, tz=datetime.UTC).astimezone().isoformat()

            metadata: dict[str, Any] = {
                "user_id": user_id,
                "group_id": group_id,
                "sender_id": sender_id,
                "timestamp_utc": datetime.fromtimestamp(timestamp_epoch, tz=datetime.UTC).isoformat(),
                "timestamp_local": timestamp_local,
                "timestamp_epoch": timestamp_epoch,
                "request_type": request_type,
                "perspective": "group" if group_id else "sender",
                "is_absolute": True,
                "schema_version": "v1",
                "source": MemorySource.AUTO_EXTRACT.value,
            }

            await self._vector_store.upsert_event(event_id, rewritten, metadata)

            await self._maybe_merge_profile(rewritten, user_id, group_id, request_type, historian_config)

        if memo:
            memo_event_id = f"{job_id}_memo_{int(timestamp_epoch * 1000)}"
            timestamp_local = datetime.fromtimestamp(timestamp_epoch, tz=datetime.UTC).astimezone().isoformat()
            memo_metadata = {
                "user_id": user_id,
                "group_id": group_id,
                "sender_id": sender_id,
                "timestamp_utc": datetime.fromtimestamp(timestamp_epoch, tz=datetime.UTC).isoformat(),
                "timestamp_local": timestamp_local,
                "timestamp_epoch": timestamp_epoch,
                "request_type": request_type,
                "perspective": "group" if group_id else "sender",
                "is_absolute": True,
                "schema_version": "v1",
                "is_memo": True,
                "source": MemorySource.AUTO_EXTRACT.value,
            }
            await self._vector_store.upsert_event(memo_event_id, memo, memo_metadata)

        await self._job_queue.complete(job_id)

    async def _rewrite_observation(
        self,
        obs_text: str,
        source_message: str,
        recent_messages: list[str],
        max_retries: int,
    ) -> str:
        for attempt in range(max_retries + 1):
            user_content = f"观察记录：{obs_text}\n\n当前消息原文：{source_message}"
            if recent_messages:
                recent_text = "\n".join(str(m)[:200] for m in recent_messages[:6])
                user_content += f"\n\n最近消息参考：\n{recent_text}"
            user_content += "\n\n请输出改写后的绝对化陈述："

            messages = [
                {"role": "system", "content": _REWRITE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ]

            try:
                if hasattr(self._ai_client, "chat"):
                    result = await self._ai_client.chat(messages, temperature=0.3, max_tokens=512)
                elif callable(self._ai_client):
                    result = await self._ai_client(messages)
                else:
                    return obs_text
            except Exception as exc:
                logger.warning("[史官] LLM 改写调用失败: attempt=%s/%s err=%s", attempt + 1, max_retries + 1, exc)
                if attempt < max_retries:
                    continue
                return obs_text

            rewritten = str(result).strip() if result else obs_text
            gate_failures = []
            for pattern, label in _ABSOLUTE_GATE_PATTERNS:
                if re.search(pattern, rewritten):
                    gate_failures.append(label)

            if not gate_failures:
                logger.info("[史官] 改写成功: obs=%s → %s", _preview_text(obs_text), _preview_text(rewritten))
                return rewritten

            logger.warning(
                "[史官] 闸门校验失败: attempt=%s/%s failures=%s text=%s",
                attempt + 1,
                max_retries + 1,
                gate_failures,
                _preview_text(rewritten),
            )
            if attempt < max_retries:
                obs_text = rewritten

        return rewritten

    async def _maybe_merge_profile(
        self,
        event_text: str,
        user_id: str,
        group_id: str,
        request_type: str,
        historian_config: dict[str, Any],
    ) -> None:
        try:
            if request_type == "group" and group_id:
                await self._merge_profile("group", group_id, event_text, historian_config)
            if user_id:
                await self._merge_profile("user", user_id, event_text, historian_config)
        except Exception as exc:
            logger.debug("[史官] 侧写合并跳过: err=%s", exc)

    async def _merge_profile(
        self,
        entity_type: str,
        entity_id: str,
        event_text: str,
        historian_config: dict[str, Any],
    ) -> None:
        current_profile = await self._profile_storage.load(entity_type, entity_id)
        current_text = current_profile or ""

        history_events = []
        try:
            events = await self._vector_store.query_events(
                query_text=event_text,
                top_k=8,
                where={"entity_type": entity_type, "entity_id": entity_id} if False else None,
            )
            history_events = [e.get("document", "") for e in events if e.get("document")]
        except Exception:
            pass

        history_text = "\n\n".join(history_events[:8]) if history_events else ""

        user_content = f"实体类型: {entity_type}\n实体 ID: {entity_id}\n\n"
        user_content += f"新观察: {event_text}\n\n"
        if current_text:
            user_content += f"当前画像:\n{current_text}\n\n"
        if history_text:
            user_content += f"历史相关事件:\n{history_text}\n\n"
        user_content += "请输出更新后的完整 Markdown 画像文件："

        messages = [
            {"role": "system", "content": _PROFILE_MERGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        try:
            if hasattr(self._ai_client, "chat"):
                result = await self._ai_client.chat(messages, temperature=0.3, max_tokens=1024)
            elif callable(self._ai_client):
                result = await self._ai_client(messages)
            else:
                return
        except Exception as exc:
            logger.warning("[史官] 侧写合并 LLM 调用失败: err=%s", exc)
            return

        new_profile = str(result).strip() if result else current_text
        if not new_profile or new_profile == current_text:
            return

        await self._profile_storage.save(entity_type, entity_id, new_profile)

        metadata = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "updated_at": datetime.now(datetime.UTC).isoformat(),
        }
        try:
            await self._vector_store.upsert_profile(f"{entity_type}:{entity_id}", new_profile, metadata)
        except Exception as exc:
            logger.warning("[史官] 侧写向量写入失败: entity=%s:%s err=%s", entity_type, entity_id, exc)

        logger.info("[史官] 侧写已更新: entity=%s:%s len=%s", entity_type, entity_id, len(new_profile))
