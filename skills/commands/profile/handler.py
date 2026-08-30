"""
/profile (别名: /p, /me, /侧写) — 查看用户或群聊的认知侧写

默认模式：渲染侧写 Markdown 为精美卡片图片
-t 模式：纯文本输出
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List

from config.config_utils import get_text_message

logger = logging.getLogger(__name__)


async def execute(args: List[str], context: Any) -> str:
    is_group = False
    target_id = ""
    use_render = True

    for arg in args:
        stripped = arg.strip()
        lower = stripped.lower()
        if lower in ("g", "group", "群"):
            is_group = True
        elif lower in ("-t", "--text", "text"):
            use_render = False
        elif lower in ("-r", "--render", "render"):
            use_render = True
        elif stripped.isdigit():
            if context.check_permission("superadmin"):
                target_id = stripped

    if is_group:
        entity_type = "group"
        entity_id = target_id or str(context.group_id)
        if not entity_id or entity_id == "0":
            return get_text_message("cognitive_memory", "group_profile_private")
    else:
        entity_type = "user"
        entity_id = target_id or str(context.sender_id)

    try:
        from utils.render import render_profile_to_image, get_profile_image_path
        from memory.profile_storage import ProfileStorage

        storage = ProfileStorage("data/cognitive/profiles")
        profile = await storage.load(entity_type, entity_id)

        if not profile:
            try:
                from webnet.ToolNet.tools.cognitive.profile_storage import get_profile_storage

                cognitive_storage = get_profile_storage()
                profile = await cognitive_storage.read_profile(entity_type, entity_id)
                if profile:
                    await storage.save(entity_type, entity_id, profile)
                    observations = await cognitive_storage.get_observations(entity_type, entity_id, limit=5)
                    if observations:
                        obs_text = "\n".join(f"- {o['observation']}" for o in observations)
                        profile = f"{profile}\n\n## 近期观察\n{obs_text}"
                        await storage.save(entity_type, entity_id, profile)
            except Exception as exc:
                logger.debug(f"从旧存储迁移侧写失败: {exc}")

        if profile:
            if use_render:
                try:
                    output_path = await render_profile_to_image(
                        entity_type,
                        entity_id,
                        profile,
                    )
                    if output_path:
                        abs_path = str(output_path.absolute()).replace("\\", "/")
                        return f"[CQ:image,file=file:///{abs_path}]"
                except Exception as exc:
                    logger.warning(f"侧写渲染失败，回退文本模式: {exc}")

            type_label = "用户" if entity_type == "user" else "群聊"
            return f"【{type_label}侧写】ID: {entity_id}\n{profile}"

        try:
            from webnet.ToolNet.tools.cognitive.profile_storage import get_profile_storage

            cognitive_storage = get_profile_storage()
            observations = await cognitive_storage.get_observations(entity_type, entity_id, limit=5)
            if observations:
                type_label = "用户" if entity_type == "user" else "群聊"
                header = get_text_message("cognitive_memory", "preliminary_header", type=type_label)
                obs_text = "\n".join(f"- {o.get('observation', str(o))}" for o in observations)
                footer = get_text_message("cognitive_memory", "preliminary_footer")
                return f"{header}\n{obs_text}\n\n{footer}"
        except Exception as exc:
            logger.debug(f"获取侧写原始观察失败: {exc}")

    except Exception as exc:
        logger.warning(f"获取侧写失败: {exc}")

    type_label = "用户" if entity_type == "user" else "群聊"
    return get_text_message("cognitive_memory", "profile_empty", type=type_label)
