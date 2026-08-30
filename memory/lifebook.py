"""
LifeBook - 多视角日记系统

职责：
- 自动实时记录对话关键信息
- 多视角输出：lover/user/共同视角
- 按年/月组织文件，方便检索
- 自动生成周/月/年总结
"""

import json
import logging
from calendar import monthrange
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class LifeBook:
    """LifeBook 日记管理器 - 多视角实时日记系统"""

    def __init__(self, base_dir: Optional[str] = None):
        self._config = self._load_config()

        actual_base_dir = base_dir or self._config.get("base_dir", "data/lifebook")
        self.base_dir = Path(actual_base_dir)

        self.lover_dir = self.base_dir / "lover"
        self.user_dir = self.base_dir / "user"
        self.together_dir = self.base_dir / "together"

        for d in [self.lover_dir, self.user_dir, self.together_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self._index_file = self.base_dir / "index.json"
        self._index: Dict[str, Dict] = self._load_index()

        buffer_size = self._config.get("buffer_max_size", 100)
        self._buffer: deque = deque(maxlen=buffer_size)

        perspective_names = self._config.get("perspective_name", {})
        self._lover_name = perspective_names.get("lover", "弥娅")
        self._user_name = perspective_names.get("user", "佳")

    def _load_config(self) -> Dict:
        """从 text_config.json 加载配置"""
        try:
            config_path = Path(__file__).parent.parent / "config" / "text_config.json"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f).get("lifebook", {})
        except Exception as e:
            logger.warning(f"[LifeBook] 加载配置失败: {e}")
        return {}

    def _get_config_value(self, key: str, default=None):
        """获取配置值"""
        return self._config.get(key, default)

    def _load_index(self) -> Dict[str, Dict]:
        """加载日记索引"""
        if self._index_file.exists():
            try:
                with open(self._index_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"[LifeBook] 加载索引失败: {e}")
        return {}

    def _save_index(self):
        """保存日记索引"""
        try:
            with open(self._index_file, "w", encoding="utf-8") as f:
                json.dump(self._index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[LifeBook] 保存索引失败: {e}")

    def _get_date_key(self, dt: Optional[datetime] = None) -> str:
        """获取日期键 (YYYY-MM-DD)"""
        return (dt or datetime.now()).strftime("%Y-%m-%d")

    def _get_year_month(self, dt: Optional[datetime] = None) -> tuple:
        """获取年份和月份"""
        dt = dt or datetime.now()
        return dt.year, dt.strftime("%m")

    def _get_daily_file(self, date_key: str, perspective: str = "lover") -> Path:
        """获取每日日记文件路径（按年/月组织）"""
        year, month = self._get_year_month(datetime.strptime(date_key, "%Y-%m-%d"))

        dir_map = {
            "lover": self.lover_dir / str(year) / month,
            "user": self.user_dir / str(year) / month,
            "together": self.together_dir / str(year) / month,
        }
        target_dir = dir_map.get(perspective, self.lover_dir / str(year) / month)
        target_dir.mkdir(parents=True, exist_ok=True)

        return target_dir / f"{date_key}.md"

    def _get_period_file(self, period: str, perspective: str = "lover") -> Path:
        """获取周期总结文件路径"""
        now = datetime.now()
        year = now.year

        file_org = self._get_config_value("file_organization")
        summaries_folder = file_org.get("summaries_folder", "summaries") if file_org else "summaries"

        dir_map = {
            "lover": self.lover_dir / summaries_folder,
            "user": self.user_dir / summaries_folder,
            "together": self.together_dir / summaries_folder,
        }
        base_dir = dir_map.get(perspective, self.lover_dir / summaries_folder)

        if period == "week":
            week_num = now.isocalendar()[1]
            weekly_pattern = file_org.get("weekly_filename_pattern") if file_org else "W{week:02d}.md"
            file_path = base_dir / f"{year}" / weekly_pattern.format(week=week_num)
        elif period == "month":
            month_str = now.strftime("%m")
            monthly_pattern = file_org.get("monthly_filename_pattern") if file_org else "{month}.md"
            file_path = base_dir / f"{year}" / monthly_pattern.format(month=month_str)
        elif period == "year":
            yearly_pattern = file_org.get("yearly_filename_pattern") if file_org else "{year}.md"
            file_path = base_dir / yearly_pattern.format(year=year)
        else:
            file_path = base_dir / f"{year}" / f"{period}.md"

        file_path.parent.mkdir(parents=True, exist_ok=True)
        return file_path

    # ==================== 实时记录 API ====================

    async def record_interaction(
        self,
        user_message: str,
        lover_response: str,
        topics: Optional[List[str]] = None,
        emotion: str = None,
    ):
        """实时记录一次交互"""
        if emotion is None:
            emotion = self._get_config_value("default_emotion", "平静")

        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_message": user_message,
            "lover_response": lover_response,
            "topics": topics or [],
            "emotion": emotion,
        }

        self._buffer.append(entry)

        date_key = self._get_date_key()
        await self._append_together_entry(date_key, entry)
        await self._append_lover_auto_thought(user_message, lover_response, emotion, date_key)

        await self._extract_and_record_user_facts(user_message)

        if date_key not in self._index:
            self._index[date_key] = {
                "together_count": 0,
                "user_count": 0,
                "lover_count": 0,
            }
        self._index[date_key]["together_count"] = self._index[date_key].get("together_count", 0) + 1
        self._save_index()

        logger.debug(f"[LifeBook] 实时记录: user={user_message[:20]}..., lover={lover_response[:20]}...")

    async def _append_lover_auto_thought(self, user_message: str, lover_response: str, emotion: str, date_key: str):
        """自动记录弥娅视角简短心理活动（不依赖 AI）"""
        thought = self._get_config_value("auto_thought_template", "")
        if not thought:
            thought = "佳说「{user}」，我回答了他。感觉{emotion}。"
        thought = thought.format(
            user=user_message[:60],
            emotion=emotion,
        )
        await self.record_lover_thought(thought, context="对话中")

    async def _extract_and_record_user_facts(self, user_message: str):
        """从用户消息中自动提取并记录重要事实"""
        import re

        extraction_config = self._config.get("user_fact_extraction", {})
        patterns = extraction_config.get("patterns", {})
        ignore_patterns = extraction_config.get("ignore_patterns", [])
        min_length = extraction_config.get("min_content_length", 5)

        if len(user_message) < min_length:
            return

        for pattern_config in ignore_patterns:
            if re.match(pattern_config, user_message):
                return

        for category, pattern_list in patterns.items():
            for pattern_config in pattern_list:
                pattern = pattern_config.get("pattern", "")
                category_name = pattern_config.get("category", category)
                pattern_config.get("field", "")

                match = re.search(pattern, user_message)
                if match:
                    fact = match.group(0)
                    await self.record_user_fact(fact, category_name)
                    logger.debug(f"[LifeBook] 提取用户事实: {fact[:30]}...")
                    return

    async def _append_together_entry(self, date_key: str, entry: Dict):
        """追加到共同视角日记（直接写入）"""
        together_file = self._get_daily_file(date_key, "together")

        time_str = datetime.fromisoformat(entry["timestamp"]).strftime("%H:%M")

        content_md = f"""
### {time_str}

**user说**: {entry["user_message"]}

**我说**: {entry["lover_response"]}

*情感: {entry["emotion"]}*
"""
        if entry["topics"]:
            content_md += f"\n*话题: {', '.join(entry['topics'])}*"

        content_md += "\n"

        if together_file.exists():
            existing = together_file.read_text(encoding="utf-8")
            if f"# {date_key} 我们的日记" not in existing:
                content = f"# {date_key} 我们的日记\n\n> 这一天，我们共同度过。\n\n{content_md}"
            else:
                content = existing + content_md
        else:
            content = f"# {date_key} 我们的日记\n\n> 这一天，我们共同度过。\n\n{content_md}"

        together_file.write_text(content, encoding="utf-8")

    async def record_user_fact(self, fact: str, category: str = "other"):
        """记录关于user的重要事实（直接写入）"""
        date_key = self._get_date_key()
        user_file = self._get_daily_file(date_key, "user")

        entry_md = f"""
---
### {category}

{fact}

*记录于: {datetime.now().strftime("%H:%M")}*
"""

        if user_file.exists():
            existing = user_file.read_text(encoding="utf-8")
            if f"# {date_key} user的日记" not in existing:
                content = f"# {date_key} user的日记\n\n> 记录关于user的点点滴滴。\n\n{entry_md}"
            else:
                content = existing + entry_md
        else:
            content = f"# {date_key} user的日记\n\n> 记录关于user的点点滴滴。\n\n{entry_md}"

        user_file.write_text(content, encoding="utf-8")

        if date_key not in self._index:
            self._index[date_key] = {
                "together_count": 0,
                "user_count": 0,
                "lover_count": 0,
            }
        self._index[date_key]["user_count"] = self._index[date_key].get("user_count", 0) + 1
        self._save_index()

        logger.info(f"[LifeBook] 记录用户事实: {fact[:30]}...")

    async def record_lover_thought(self, thought: str, context: str = ""):
        """记录lover的思考/感受（直接写入）"""
        date_key = self._get_date_key()
        lover_file = self._get_daily_file(date_key, "lover")

        entry_md = f"""
---
### {datetime.now().strftime("%H:%M")}

{thought}
"""
        if context:
            entry_md += f"\n*情境: {context}*"

        if lover_file.exists():
            existing = lover_file.read_text(encoding="utf-8")
            if f"# {date_key} 我的日记" not in existing:
                content = f"# {date_key} 我的日记\n\n> 作为lover，我的思考与感受。\n\n{entry_md}"
            else:
                content = existing + entry_md
        else:
            content = f"# {date_key} 我的日记\n\n> 作为lover，我的思考与感受。\n\n{entry_md}"

        lover_file.write_text(content, encoding="utf-8")

        if date_key not in self._index:
            self._index[date_key] = {
                "together_count": 0,
                "user_count": 0,
                "lover_count": 0,
            }
        self._index[date_key]["lover_count"] = self._index[date_key].get("lover_count", 0) + 1
        self._save_index()

        logger.debug(f"[LifeBook] 记录lover思考: {thought[:30]}...")

    def flush_all(self):
        """强制刷新所有缓冲内容到磁盘（现在直接写入，保留兼容接口）"""
        pass

    # ==================== 周期总结生成 ====================

    async def generate_daily_summary(self, date_key: Optional[str] = None):
        """生成每日总结"""
        date_key = date_key or self._get_date_key()

        together_file = self._get_daily_file(date_key, "together")
        if not together_file.exists():
            return None

        together_content = together_file.read_text(encoding="utf-8")
        if not together_content:
            return None

        try:
            summary = await self._call_ai_summary(
                template_key="daily",
                content=together_content[:1000],
                perspective="lover",
            )

            lover_file = self._get_daily_file(date_key, "lover")

            # 如果文件不存在，先创建
            if not lover_file.exists():
                year, month = self._get_year_month(datetime.strptime(date_key, "%Y-%m-%d"))
                initial_content = f"""# {date_key} 我的日记

> 作为lover，我的思考与感受。

"""
                lover_file.parent.mkdir(parents=True, exist_ok=True)
                lover_file.write_text(initial_content, encoding="utf-8")

            # 追加总结
            existing = lover_file.read_text(encoding="utf-8")
            summary_md = f"\n---\n## 🌙 每日总结\n\n{summary}\n"
            lover_file.write_text(existing + summary_md, encoding="utf-8")

            logger.info(f"[LifeBook] 每日总结已生成: {date_key}")
            return summary
        except Exception as e:
            logger.warning(f"[LifeBook] 生成每日总结失败: {e}")
            return None

    async def generate_weekly_summary(self):
        """生成每周总结"""
        now = datetime.now()
        year = now.year
        week_num = now.isocalendar()[1]

        start_of_week = now - timedelta(days=now.weekday())
        dates = [(start_of_week + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

        contents = []
        for date_key in dates:
            together_file = self._get_daily_file(date_key, "together")
            if together_file.exists():
                contents.append(together_file.read_text(encoding="utf-8"))

        if not contents:
            logger.info(f"[LifeBook] 第{week_num}周无内容，跳过总结")
            return None

        combined_content = "\n\n---\n\n".join(contents)[:1500]

        try:
            summary = await self._call_ai_summary(
                template_key="weekly",
                content=combined_content,
                perspective="lover",
                extra={"week": week_num},
            )

            week_file = self._get_period_file("week", "lover")

            content = f"""# {year} 第{week_num}周总结

> 这一周，我们共同度过的时光。

{summary}

---
*记录于 {datetime.now().strftime("%Y-%m-%d %H:%M")}*
"""
            week_file.write_text(content, encoding="utf-8")

            logger.info(f"[LifeBook] 周总结已生成: {year} W{week_num:02d}")
            return str(week_file)
        except Exception as e:
            logger.warning(f"[LifeBook] 生成周总结失败: {e}")
            return None

    async def generate_monthly_summary(self):
        """生成每月总结"""
        now = datetime.now()
        year = now.year
        month = now.strftime("%m")

        _, days_in_month = monthrange(year, int(month))
        dates = [f"{year}-{month}-{day:02d}" for day in range(1, days_in_month + 1)]

        contents = []
        for date_key in dates:
            if date_key > now.strftime("%Y-%m-%d"):
                break
            together_file = self._get_daily_file(date_key, "together")
            if together_file.exists():
                contents.append(f"## {date_key}\n{together_file.read_text(encoding='utf-8')[:300]}")

        if not contents:
            logger.info(f"[LifeBook] {year}-{month} 无内容，跳过总结")
            return None

        combined_content = "\n\n".join(contents)[:2000]

        try:
            summary = await self._call_ai_summary(
                template_key="monthly",
                content=combined_content,
                perspective="lover",
                extra={"year": year, "month": int(month)},
            )

            month_file = self._get_period_file("month", "lover")

            content = f"""# {year}年{month}月总结

> 这一个月的点点滴滴。

{summary}

---
*记录于 {datetime.now().strftime("%Y-%m-%d %H:%M")}*
"""
            month_file.write_text(content, encoding="utf-8")

            logger.info(f"[LifeBook] 月总结已生成: {year}-{month}")
            return str(month_file)
        except Exception as e:
            logger.warning(f"[LifeBook] 生成月总结失败: {e}")
            return None

    async def _call_ai_summary(
        self,
        template_key: str,
        content: str,
        perspective: str = "lover",
        extra: Optional[Dict] = None,
    ) -> str:
        """调用 AI 生成总结"""
        from core.ai_client import AIClientFactory
        from core.model_pool_manager import get_model_pool

        model_pool = get_model_pool()
        if not model_pool:
            return "（AI 不可用）"

        # 从multi_model_config.json读取系统默认模型配置
        multi_config = model_pool._config
        ai_client_config = multi_config.get("system_defaults", {})
        model_id = ai_client_config.get("soul_model", "deepseek_v4_flash_official")

        model_cfg = model_pool._models.get(model_id)
        if not model_cfg:
            return "（模型不可用）"

        try:
            provider_val = getattr(model_cfg.provider, "value", None) or str(model_cfg.provider)

            client = AIClientFactory.create_client(
                provider=provider_val,
                api_key=model_cfg.api_key or "",
                model=model_cfg.name,
                base_url=model_cfg.base_url or "",
            )

            if not client:
                return "（客户端不可用）"

            templates = self._get_config_value("summary_templates")
            template = ""
            if templates:
                template = templates.get(template_key, "")

            template = template.format(content=content, **extra) if extra else template.format(content=content)

            system_prompt = self._get_config_value("system_prompt") or _load_lifebook_summary_prompt()

            summary = await client.chat_with_system_prompt(
                system_prompt=system_prompt,
                user_message=template,
                tools=None,
                tool_choice="none",
            )

            return summary or "（生成失败）"
        except Exception as e:
            logger.warning(f"[LifeBook] AI 调用失败: {e}")
            return f"（生成失败: {e}）"

    # ==================== 检索接口 ====================

    def get_entry(self, date_key: str, perspective: str = "lover") -> Optional[str]:
        """获取指定日期的日记内容"""
        daily_file = self._get_daily_file(date_key, perspective)
        if daily_file.exists():
            return daily_file.read_text(encoding="utf-8")
        return None

    def get_period_summary(self, period: str, perspective: str = "lover") -> Optional[str]:
        """获取周期总结"""
        period_file = self._get_period_file(period, perspective)
        if period_file.exists():
            return period_file.read_text(encoding="utf-8")
        return None

    def list_entries(self, perspective: str = "lover", year: Optional[int] = None, limit: int = None) -> List[Dict]:
        """列出日记条目"""
        if limit is None:
            list_limit_config = self._get_config_value("list_limit")
            limit = list_limit_config if list_limit_config is not None else 30

        dir_map = {
            "lover": self.lover_dir,
            "user": self.user_dir,
            "together": self.together_dir,
        }
        target_dir = dir_map.get(perspective, self.lover_dir)

        results = []

        if year:
            year_dir = target_dir / str(year)
            if year_dir.exists():
                for month_dir in sorted(year_dir.iterdir(), reverse=True):
                    if month_dir.is_dir():
                        md_files = sorted(month_dir.glob("*.md"), reverse=True)[:limit]
                        for f in md_files:
                            results.append({"date": f.stem, "file": str(f)})
                            if len(results) >= limit:
                                break
        else:
            for year_dir in sorted(target_dir.iterdir(), reverse=True):
                if year_dir.is_dir() and year_dir.name.isdigit():
                    for month_dir in sorted(year_dir.iterdir(), reverse=True):
                        if month_dir.is_dir():
                            md_files = sorted(month_dir.glob("*.md"), reverse=True)[:limit]
                            for f in md_files:
                                results.append({"date": f.stem, "file": str(f)})
                                if len(results) >= limit:
                                    break
                if len(results) >= limit:
                    break

        return results[:limit]

    def search(self, keyword: str, perspective: str = "lover") -> List[Dict]:
        """搜索日记内容"""
        search_limit_config = self._get_config_value("search_limit")
        limit = search_limit_config if search_limit_config is not None else 20

        dir_map = {
            "lover": self.lover_dir,
            "user": self.user_dir,
            "together": self.together_dir,
        }
        target_dir = dir_map.get(perspective, self.lover_dir)

        results = []
        keyword_lower = keyword.lower()

        for year_dir in target_dir.rglob("*"):
            if year_dir.is_file() and year_dir.suffix == ".md":
                try:
                    content = year_dir.read_text(encoding="utf-8")
                    if keyword_lower in content.lower():
                        results.append(
                            {
                                "date": year_dir.stem,
                                "file": str(year_dir),
                                "preview": content[:200] + "...",
                            }
                        )
                except:
                    pass

        return results[:limit]

    def get_index(self) -> Dict:
        """获取索引"""
        return self._index

    async def append_session(
        self,
        session_id: str,
        platform: str,
        messages: List[Dict],
        summary: str = "",
        emotion: str = "平静",
        topics: Optional[List[str]] = None,
    ) -> str:
        """
        追加会话到日记（兼容旧接口）

        Args:
            session_id: 会话ID
            platform: 平台 (qq/terminal/web)
            messages: 对话消息列表
            summary: 会话摘要
            emotion: 情感基调
            topics: 话题列表

        Returns:
            日期键
        """
        date_key = self._get_date_key()

        user_msg = ""
        for msg in messages:
            if msg.get("role") == "user":
                user_msg = msg.get("content", "")
            elif msg.get("role") == "assistant":
                lover_msg = msg.get("content", "")
                if user_msg:
                    await self.record_interaction(user_msg, lover_msg, topics, emotion)
                    user_msg = ""

        self.flush_all()

        # 生成每日总结
        await self.generate_daily_summary(date_key)

        logger.info(f"[LifeBook] 会话已追加: {date_key}")
        return date_key


def _load_lifebook_summary_prompt() -> str:
    try:
        import json as _json

        config_path = Path(__file__).parent.parent / "config" / "text_config.json"
        with open(config_path, "r", encoding="utf-8") as _f:
            _cfg = _json.load(_f)
        return (
            _cfg.get("prompt_templates", {})
            .get("lifebook", {})
            .get("summary_system_prompt", "你是一个温暖的AI伴侣，请用第一人称写总结。")
        )
    except Exception:
        return "你是一个温暖的AI伴侣，请用第一人称写总结。"


# 全局单例
_lifebook: Optional[LifeBook] = None


def get_lifebook() -> LifeBook:
    """获取 LifeBook 单例"""
    global _lifebook
    if _lifebook is None:
        _lifebook = LifeBook()
    return _lifebook
