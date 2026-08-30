"""
智能表情包管理器 v2.0
支持语义标签、自动分类、智能检索和上下文感知触发
"""

import asyncio
import hashlib
import json
import logging
import mimetypes
import os
import random
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import jieba
import jieba.analyse
import yaml

logger = logging.getLogger(__name__)


def _load_text_config() -> Dict[str, Any]:
    """加载text_config.json配置"""
    config_paths = [
        "config/text_config.json",
        os.path.join(os.path.dirname(__file__), "..", "config", "text_config.json"),
        os.path.join(os.path.dirname(__file__), "..", "..", "config", "text_config.json"),
    ]
    for path in config_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载text_config失败 {path}: {e}")
    return {}


class SemanticTagger:
    """语义标签生成器 - 从text_config.json加载关键词配置"""

    def __init__(self):
        text_config = _load_text_config()
        keyword_config = text_config.get("emoji_keyword_mapping", {})

        self.EMOTION_KEYWORDS = keyword_config.get(
            "emotion_keywords",
            {
                "开心": [
                    "开心",
                    "高兴",
                    "快乐",
                    "哈哈",
                    "笑",
                    "嘻嘻",
                    "美滋滋",
                    "happy",
                    "joy",
                ],
                "难过": ["难过", "伤心", "哭", "泪", "心痛", "sad", "cry", "失落"],
                "生气": ["生气", "愤怒", "气", "怒", "讨厌", "angry", "愤愤"],
                "惊讶": ["惊讶", "震惊", "哇", "啊", "amazing", "wow"],
                "害羞": ["害羞", "脸红", "不好意思", "羞涩", "shy", "embarrassed"],
                "可爱": ["可爱", "萌", "卡哇伊", "甜", "cute", "kawaii"],
                "得意": ["得意", "骄傲", "厉害", "棒", "赞", "proud", "牛逼"],
                "无奈": ["无奈", "无语", "汗", "囧", "尴尬", "helpless"],
                "亲亲": ["亲亲", "爱你", "喜欢", "么么哒", "love", "kiss"],
                "加油": ["加油", "努力", "冲", "fighting", "come on"],
            },
        )

        self.CONTEXT_KEYWORDS = keyword_config.get(
            "context_keywords",
            {
                "问候": [
                    "早上好",
                    "晚安",
                    "你好",
                    "早安",
                    "hi",
                    "hello",
                    "嗨",
                    "hey",
                    "在吗",
                ],
                "感谢": ["谢谢", "感谢", "谢", "thanks", "thank", "谢啦"],
                "祝福": ["祝福", "祝你", "愿你", "happy birthday", "生日快乐"],
                "道歉": ["对不起", "抱歉", "不好意思", "sorry"],
                "安慰": ["没事", "没关系", "别难过", "别伤心", "安慰"],
                "调侃": ["哈哈", "呵呵", "调皮", "傻", "笨", "调侃", "逗你"],
                "赞同": ["对", "是", "没错", "同意", "yes", "right", "对的"],
                "拒绝": ["不", "不要", "别", "no", "not", "拒绝", "不行"],
                "期待": ["期待", "希望", "想要", "想", "hope", "want"],
                "告别": ["再见", "拜拜", "下次见", "bye"],
            },
        )

        self.SCENE_KEYWORDS = keyword_config.get(
            "scene_keywords",
            {
                "工作": ["上班", "加班", "开会", "工作", "忙", "office", "work"],
                "学习": ["学习", "考试", "作业", "上课", "study", "learn"],
                "吃饭": ["吃饭", "饿了", "美食", "好吃", "eat", "food"],
                "休息": ["睡觉", "困", "累了", "休息", "sleep", "rest"],
                "游戏": ["游戏", "打游戏", "玩", "game", "play"],
                "聊天": ["聊天", "说话", "聊", "talk", "chat"],
                "天气": ["天气", "下雨", "热", "冷", "weather"],
                "节日": ["节日", "过年", "圣诞", "春节", "holiday"],
            },
        )

        self.EMOTION_MAP = text_config.get(
            "emoji_emotion_map",
            {
                "笑": "开心",
                "微笑": "开心",
                "哭": "难过",
                "泪": "难过",
                "生气": "生气",
                "愤怒": "生气",
                "惊讶": "惊讶",
                "害羞": "害羞",
                "可爱": "可爱",
                "萌": "可爱",
                "亲": "亲亲",
                "爱": "亲亲",
                "加油": "加油",
                "奋斗": "加油",
            },
        )

        self._init_jieba()

    def _init_jieba(self):
        """初始化jieba分词"""
        for keywords in self.EMOTION_KEYWORDS.values():
            for kw in keywords:
                jieba.add_word(kw)
        for keywords in self.CONTEXT_KEYWORDS.values():
            for kw in keywords:
                jieba.add_word(kw)
        for keywords in self.SCENE_KEYWORDS.values():
            for kw in keywords:
                jieba.add_word(kw)

    def extract_keywords(self, text: str, topK: int = 10) -> List[str]:
        """提取关键词"""
        try:
            keywords = jieba.analyse.extract_tags(text, topK=topK, withWeight=False)
            return keywords
        except Exception as e:
            logger.warning(f"关键词提取失败: {e}")
            words = jieba.cut(text)
            return [w for w in words if len(w) >= 2][:topK]

    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """分析情感倾向"""
        text_lower = text.lower()
        scores = defaultdict(float)

        for emotion, keywords in self.EMOTION_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    scores[emotion] += 1.0

        total = sum(scores.values()) if scores else 1.0
        return {k: v / total for k, v in scores.items()}

    def get_context_type(self, text: str) -> List[str]:
        """识别上下文类型"""
        text_lower = text.lower()
        context_types = []

        for ctx_type, keywords in self.CONTEXT_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    if ctx_type not in context_types:
                        context_types.append(ctx_type)
                    break

        return context_types

    def match_emoji_by_semantic(self, text: str, emoji_tags: Dict[str, List[str]]) -> List[Tuple[str, float]]:
        """根据语义匹配表情包"""
        text_keywords = set(self.extract_keywords(text))
        text_lower = text.lower()

        matched = []
        for emoji_path, tags in emoji_tags.items():
            score = 0.0
            tags_lower = [t.lower() for t in tags]

            for keyword in text_keywords:
                if keyword in tags_lower:
                    score += 2.0

            for tag in tags:
                if tag.lower() in text_lower:
                    score += 1.0

            if score > 0:
                matched.append((emoji_path, score))

        matched.sort(key=lambda x: x[1], reverse=True)
        return matched[:5]

    def should_send_emoji(self, text: str, probability: float = 0.3) -> Tuple[bool, Optional[str], float]:
        """
        判断是否应该发送表情包

        Returns:
            (是否发送, 建议标签, 置信度)
        """
        text_lower = text.lower()

        if len(text) < 2:
            return False, None, 0.0

        sentiment = self.analyze_sentiment(text)
        context_types = self.get_context_type(text)

        max(sentiment.values()) if sentiment else 0
        sentiment_threshold = 0.3

        need_emoji = False
        suggested_tag = None
        confidence = 0.0

        if sentiment:
            top_emotion = max(sentiment.items(), key=lambda x: x[1])
            if top_emotion[1] >= sentiment_threshold:
                need_emoji = True
                suggested_tag = top_emotion[0]
                confidence = top_emotion[1]

        if context_types and not suggested_tag:
            need_emoji = True
            suggested_tag = context_types[0]
            confidence = 0.6

        if "?" in text or "？" in text:
            need_emoji = True
            suggested_tag = suggested_tag or "惊讶"
            confidence = max(confidence, 0.5)

        if any(word in text_lower for word in ["!", "！", "~~~", "！！"]):
            need_emoji = True
            suggested_tag = suggested_tag or "开心"
            confidence = max(confidence, 0.7)

        final_decision = need_emoji and random.random() < probability

        return final_decision, suggested_tag, confidence


class SmartEmojiManager:
    """智能表情包管理器"""

    def __init__(self, config_path: str = "config/emoji_config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self.emoji_cache = {}
        self.sticker_cache = {}
        self.emoji_tags = {}
        self.usage_stats = {}
        self.semantic_tagger = SemanticTagger()
        self._init_directories()
        self._scan_resources()
        self._load_or_generate_tags()

    def _load_config(self) -> Dict:
        """加载配置文件"""
        config_paths = [
            self.config_path,
            os.path.join(os.path.dirname(__file__), "..", self.config_path),
            "./" + self.config_path,
        ]

        for path in config_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        config = yaml.safe_load(f) or {}
                        return config.get("emoji", {})
                except Exception as e:
                    logger.error(f"加载表情包配置失败 {path}: {e}")

        return {
            "resources": {
                "emoji_dir": "data/emoji",
                "stickers_dir": "data/stickers",
                "allowed_formats": [".gif", ".jpg", ".jpeg", ".png", ".webp", ".bmp"],
                "max_file_size": 5242880,
            }
        }

    def _init_directories(self):
        """初始化目录结构"""
        resources = self.config.get("resources", {})
        emoji_dir = resources.get("emoji_dir", "data/emoji")
        stickers_dir = resources.get("stickers_dir", "data/stickers")

        directories = [
            emoji_dir,
            os.path.join(emoji_dir, "custom"),
            os.path.join(emoji_dir, "miya_special"),
            os.path.join(emoji_dir, "standard"),
            os.path.join(emoji_dir, "user_uploaded"),
            stickers_dir,
            os.path.join(stickers_dir, "cute"),
            os.path.join(stickers_dir, "reaction"),
            os.path.join(stickers_dir, "seasonal"),
            os.path.join(stickers_dir, "memes"),
            "data/.emoji_backups",
        ]

        for dir_path in directories:
            os.makedirs(dir_path, exist_ok=True)

    def _scan_resources(self):
        """扫描表情包资源"""
        resources = self.config.get("resources", {})
        allowed_formats = set(resources.get("allowed_formats", []))

        emoji_dir = resources.get("emoji_dir", "data/emoji")
        self._scan_directory(emoji_dir, allowed_formats, self.emoji_cache)

        stickers_dir = resources.get("stickers_dir", "data/stickers")
        self._scan_directory(stickers_dir, allowed_formats, self.sticker_cache)

        logger.info(
            f"表情包资源扫描完成: 表情包={sum(len(v) for v in self.emoji_cache.values())}个, 贴纸={sum(len(v) for v in self.sticker_cache.values())}个"
        )

    def _scan_directory(self, base_dir: str, allowed_formats: set, cache: Dict):
        """扫描目录中的图片文件"""
        try:
            for root, _dirs, files in os.walk(base_dir):
                relative_path = os.path.relpath(root, base_dir)
                category = "root" if relative_path == "." else relative_path

                for file in files:
                    file_path = os.path.join(root, file)
                    file_ext = os.path.splitext(file)[1].lower()

                    if file_ext in allowed_formats:
                        file_info = self._get_file_info(file_path)
                        if file_info:
                            if category not in cache:
                                cache[category] = []
                            cache[category].append(file_info)
        except Exception as e:
            logger.error(f"扫描目录失败 {base_dir}: {e}")

    def _get_file_info(self, file_path: str) -> Optional[Dict]:
        """获取文件信息"""
        try:
            stat = os.stat(file_path)
            file_size = stat.st_size

            max_size = self.config.get("resources", {}).get("max_file_size", 5242880)
            if file_size > max_size:
                logger.warning(f"文件过大跳过: {file_path} ({file_size}字节)")
                return None

            file_hash = self._get_file_hash(file_path)
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                mime_type = "application/octet-stream"

            return {
                "path": file_path,
                "name": os.path.basename(file_path),
                "size": file_size,
                "hash": file_hash,
                "mime_type": mime_type,
                "extension": os.path.splitext(file_path)[1].lower(),
                "category": os.path.basename(os.path.dirname(file_path)),
                "added_time": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"获取文件信息: {file_path}: {e}")
            return None

    def _get_file_hash(self, file_path: str) -> str:
        """计算文件哈希值"""
        try:
            hasher = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            logger.error(f"计算文件哈希失败: {e}")
            return "unknown"

    def _get_tags_file_path(self) -> str:
        """获取标签文件路径"""
        backup_dir = self.config.get("resources", {}).get("backup_dir", "data/.emoji_backups")
        return os.path.join(backup_dir, "emoji_tags.json")

    def _load_or_generate_tags(self):
        """加载或生成标签"""
        tags_file = self._get_tags_file_path()

        if os.path.exists(tags_file):
            try:
                with open(tags_file, "r", encoding="utf-8") as f:
                    self.emoji_tags = json.load(f)
                logger.info(f"已加载表情包标签: {len(self.emoji_tags)}个")
            except Exception as e:
                logger.warning(f"加载标签失败: {e}")

        self._generate_tags_for_all()

    def _generate_tags_for_all(self):
        """为所有表情包生成标签"""
        logger.info("开始为表情包生成语义标签...")

        all_items = {}
        for _cat, items in self.emoji_cache.items():
            for item in items:
                all_items[item["path"]] = item
        for _cat, items in self.sticker_cache.items():
            for item in items:
                all_items[item["path"]] = item

        for path, item in all_items.items():
            if path not in self.emoji_tags:
                tags = self._generate_tags_for_emoji(item)
                self.emoji_tags[path] = tags

        self._clean_stale_tags(all_items)
        self._save_tags()
        logger.info(f"标签生成完成: {len(self.emoji_tags)}个表情包已标记")

    def _clean_stale_tags(self, valid_items: Dict[str, Dict]):
        """清理不存在的文件标签"""
        stale_paths = [p for p in self.emoji_tags if p not in valid_items]
        for path in stale_paths:
            del self.emoji_tags[path]
        if stale_paths:
            logger.info(f"清理了 {len(stale_paths)} 个不存在的文件标签")

    def _generate_tags_for_emoji(self, emoji_info: Dict) -> List[str]:
        """为单个表情包生成标签"""
        tags = []

        category = emoji_info.get("category", "")
        name = emoji_info.get("name", "")
        emoji_info.get("path", "")

        text_config = _load_text_config()
        category_tags = text_config.get(
            "emoji_category_tags",
            {
                "custom": ["自定义", "收藏", "常用"],
                "miya_special": ["弥娅", "专属", "特别"],
                "standard": ["标准", "默认", "经典"],
                "user_uploaded": ["用户上传", "分享", "收藏"],
                "cute": ["可爱", "萌", "甜"],
                "reaction": ["反应", "回应", "表情"],
                "seasonal": ["节日", "季节", "特别"],
                "memes": ["梗图", "搞笑", "网络"],
            },
        )

        default_tags = text_config.get("emoji_default_tags", ["表情包", "图片", "表情"])

        if category in category_tags:
            tags.extend(category_tags[category])
        elif category and category != "root":
            tags.append(category)

        name_without_ext = os.path.splitext(name)[0]

        if not name_without_ext.startswith("tmp") and len(name_without_ext) > 2:
            name_keywords = self.semantic_tagger.extract_keywords(name_without_ext, topK=5)
            tags.extend(name_keywords)

            for emotion, keywords in self.semantic_tagger.EMOTION_KEYWORDS.items():
                for kw in keywords:
                    if kw in name.lower():
                        if emotion not in tags:
                            tags.append(emotion)
                        break

            for ctx_type, keywords in self.semantic_tagger.CONTEXT_KEYWORDS.items():
                for kw in keywords:
                    if kw in name.lower():
                        if ctx_type not in tags:
                            tags.append(ctx_type)
                        break

        for tag in default_tags:
            if tag not in tags:
                tags.append(tag)

        tags = list(dict.fromkeys(tags))

        return tags[:10]

    def _filter_semantic_tags(self, tags: List[str]) -> List[str]:
        """过滤技术性标签，保留语义标签"""
        semantic_tags = []
        for tag in tags:
            # 过滤纯数字
            if tag.isdigit():
                continue
            # 过滤带小数点的数字
            try:
                float(tag)
                continue
            except ValueError:
                pass
            # 过滤纯技术术语
            if tag.lower() in ["kb", "mb", "gb", "px", "像素", "格式", "视觉内容"]:
                continue
            semantic_tags.append(tag)
        return semantic_tags

    async def generate_tags_with_ai(self, emoji_path: str, image_data: bytes = None) -> List[str]:
        """使用AI视觉模型生成精确的表情包标签"""
        try:
            if image_data is None:
                if not os.path.exists(emoji_path):
                    return self._generate_tags_for_emoji(
                        {
                            "path": emoji_path,
                            "name": os.path.basename(emoji_path),
                            "category": "unknown",
                        }
                    )
                with open(emoji_path, "rb") as f:
                    image_data = f.read()

            from core.multi_vision_analyzer import analyze_image_multi_model

            result = await analyze_image_multi_model(image_data, max_retries=2)

            if result and result.success and result.description:
                tags = self.semantic_tagger.extract_keywords(result.description, topK=8)
                if result.labels:
                    tags.extend(result.labels[:3])
                if result.has_text and result.text:
                    text_tags = self.semantic_tagger.extract_keywords(result.text, topK=3)
                    tags.extend(text_tags)

                emotion_map = self.semantic_tagger.EMOTION_MAP
                desc_lower = result.description.lower()
                for keyword, emotion in emotion_map.items():
                    if keyword in desc_lower and emotion not in tags:
                        tags.append(emotion)

                tags = self._filter_semantic_tags(tags)
                tags = list(dict.fromkeys(tags))
                logger.info(f"AI标签生成成功: {os.path.basename(emoji_path)} -> {tags[:5]}")
                return tags[:10]

        except Exception as e:
            logger.warning(f"AI视觉标签生成失败 {emoji_path}: {e}")

        return self._generate_tags_for_emoji(
            {
                "path": emoji_path,
                "name": os.path.basename(emoji_path),
                "category": "unknown",
            }
        )

    async def generate_ai_tags_for_all(self, batch_size: int = 5, delay: float = 1.0) -> Dict[str, int]:
        """
        为所有缺少AI标签的表情包批量生成AI标签

        Args:
            batch_size: 每批处理数量
            delay: 每个表情包处理间隔（秒），避免API限流

        Returns:
            统计信息 {'total': int, 'success': int, 'failed': int, 'skipped': int}
        """
        stats = {"total": 0, "success": 0, "failed": 0, "skipped": 0}

        all_items = {}
        for _cat, items in self.emoji_cache.items():
            for item in items:
                all_items[item["path"]] = item
        for _cat, items in self.sticker_cache.items():
            for item in items:
                all_items[item["path"]] = item

        paths_needing_tags = []
        for path, item in all_items.items():
            current_tags = self.emoji_tags.get(path, [])
            has_emotion_tag = any(
                t in current_tags
                for t in [
                    "开心",
                    "难过",
                    "生气",
                    "惊讶",
                    "害羞",
                    "可爱",
                    "加油",
                    "亲亲",
                    "得意",
                    "无奈",
                    "问候",
                    "感谢",
                    "祝福",
                    "道歉",
                    "安慰",
                    "调侃",
                    "赞同",
                    "拒绝",
                    "期待",
                    "告别",
                ]
            )
            is_meaningful = len(current_tags) >= 5 and any(
                t
                not in [
                    "misc",
                    "表情包",
                    "图片",
                    "表情",
                    "Temp",
                    "用户上传",
                    "分享",
                    "收藏",
                    "自定义",
                    "弥娅",
                    "专属",
                    "特别",
                    "标准",
                    "默认",
                    "经典",
                ]
                for t in current_tags
            )
            if not has_emotion_tag and not is_meaningful:
                paths_needing_tags.append((path, item))
            else:
                stats["skipped"] += 1

        stats["total"] = len(paths_needing_tags)
        if stats["total"] == 0:
            logger.info("所有表情包已有足够的标签，无需AI生成")
            return stats

        logger.info(f"开始批量AI标签生成: 共{stats['total']}个表情包需要处理")

        for i, (path, item) in enumerate(paths_needing_tags):
            try:
                if not os.path.exists(path):
                    stats["failed"] += 1
                    continue

                with open(path, "rb") as f:
                    image_data = f.read()

                tags = await self.generate_tags_with_ai(path, image_data)
                if tags and len(tags) > 2:
                    self.emoji_tags[path] = tags
                    stats["success"] += 1
                else:
                    stats["failed"] += 1

                if (i + 1) % batch_size == 0:
                    self._save_tags()
                    logger.info(f"进度: {i + 1}/{stats['total']} (成功:{stats['success']}, 失败:{stats['failed']})")

                if delay > 0 and i < len(paths_needing_tags) - 1:
                    await asyncio.sleep(delay)

            except Exception as e:
                logger.error(f"处理表情包失败 {path}: {e}")
                stats["failed"] += 1

        self._save_tags()
        logger.info(
            f"批量AI标签生成完成: 总计{stats['total']}, 成功{stats['success']}, 失败{stats['failed']}, 跳过{stats['skipped']}"
        )
        return stats

    def _save_tags(self):
        """保存标签"""
        try:
            tags_file = self._get_tags_file_path()
            os.makedirs(os.path.dirname(tags_file), exist_ok=True)
            with open(tags_file, "w", encoding="utf-8") as f:
                json.dump(self.emoji_tags, f, ensure_ascii=False, indent=2)
            logger.debug(f"标签已保存: {tags_file}")
        except Exception as e:
            logger.error(f"保存标签失败: {e}")

    def update_emoji_tags(self, emoji_path: str, tags: List[str]):
        """更新表情包标签"""
        if emoji_path not in self.emoji_tags:
            self.emoji_tags[emoji_path] = []

        self.emoji_tags[emoji_path] = list(set(self.emoji_tags[emoji_path] + tags))
        self._save_tags()
        logger.info(f"已更新表情包标签: {os.path.basename(emoji_path)} -> {self.emoji_tags[emoji_path]}")

    def smart_search(self, query: str, limit: int = 10) -> List[Dict]:
        """
        智能搜索表情包

        Args:
            query: 用户查询（可以是自然语言）
            limit: 返回数量限制

        Returns:
            匹配的表情包列表，按相关性排序
        """
        should_send, suggested_tag, confidence = self.semantic_tagger.should_send_emoji(query)

        keywords = self.semantic_tagger.extract_keywords(query, topK=10)
        sentiment = self.semantic_tagger.analyze_sentiment(query)
        context_types = self.semantic_tagger.get_context_type(query)

        all_items = []
        for _cat, items in self.emoji_cache.items():
            for item in items:
                item["cache_type"] = "emoji"
                all_items.append(item)
        for _cat, items in self.sticker_cache.items():
            for item in items:
                item["cache_type"] = "sticker"
                all_items.append(item)

        scored_items = []
        for item in all_items:
            path = item["path"]
            tags = self.emoji_tags.get(path, [])

            score = 0.0

            for kw in keywords:
                kw_lower = kw.lower()
                if any(kw_lower in t.lower() for t in tags):
                    score += 3.0
                if any(t.lower() in kw_lower for t in tags):
                    score += 1.5
                if kw_lower in item["name"].lower():
                    score += 2.0
                if kw_lower in item.get("category", "").lower():
                    score += 1.0

            if sentiment:
                top_emotion = max(sentiment.items(), key=lambda x: x[1])
                if top_emotion[0] in tags:
                    score += 2.0 * top_emotion[1]

            for ctx in context_types:
                if ctx in tags:
                    score += 1.5

            if suggested_tag and suggested_tag in tags:
                score += confidence * 2.0

            if score > 0:
                scored_items.append((item, score))

        scored_items.sort(key=lambda x: x[1], reverse=True)

        return [item for item, score in scored_items[:limit]]

    def get_emoji_by_context(self, text: str) -> Optional[Dict]:
        """
        根据上下文智能获取表情包（核心方法）

        这是弥娅判断是否发送表情包的主要入口
        """
        should_send, suggested_tag, confidence = self.semantic_tagger.should_send_emoji(
            text,
            probability=self.config.get("sending_strategy", {}).get("random_emoji_probability", 0.3),
        )

        if not should_send:
            return None

        search_results = self.smart_search(text, limit=5)

        if search_results:
            chosen = random.choice(search_results[: min(3, len(search_results))])
            self._record_usage(chosen)
            return chosen

        if suggested_tag:
            tag_search = self.smart_search(suggested_tag, limit=10)
            if tag_search:
                chosen = random.choice(tag_search[: min(3, len(tag_search))])
                self._record_usage(chosen)
                return chosen

        return self.get_random_emoji()

    def get_random_emoji(self, category: str = None) -> Optional[Dict]:
        """获取随机表情包"""
        try:
            if category and category in self.emoji_cache:
                emojis = self.emoji_cache[category]
            else:
                emojis = []
                for cat in self.emoji_cache.values():
                    emojis.extend(cat)

            if not emojis:
                logger.warning("没有可用的表情包")
                return None

            emoji = random.choice(emojis)
            self._record_usage(emoji)
            return emoji
        except Exception as e:
            logger.error(f"获取随机表情包失败: {e}")
            return None

    def get_random_sticker(self, category: str = None) -> Optional[Dict]:
        """获取随机贴纸"""
        try:
            if category and category in self.sticker_cache:
                stickers = self.sticker_cache[category]
            else:
                stickers = []
                for cat in self.sticker_cache.values():
                    stickers.extend(cat)

            if not stickers:
                logger.warning("没有可用的贴纸")
                return None

            sticker = random.choice(stickers)
            self._record_usage(sticker)
            return sticker
        except Exception as e:
            logger.error(f"获取随机贴纸失败: {e}")
            return None

    def search_emoji(self, keyword: str, category: str = None) -> List[Dict]:
        """搜索表情包（兼容旧接口）"""
        return self.smart_search(keyword)

    def _record_usage(self, item: Dict):
        """记录表情包使用统计"""
        try:
            item_id = f"{item['category']}/{item['name']}"

            if item_id not in self.usage_stats:
                self.usage_stats[item_id] = {
                    "count": 0,
                    "last_used": None,
                    "first_used": datetime.now().isoformat(),
                }

            self.usage_stats[item_id]["count"] += 1
            self.usage_stats[item_id]["last_used"] = datetime.now().isoformat()

            if len(self.usage_stats) % 10 == 0:
                self._save_usage_stats()
        except Exception as e:
            logger.error(f"记录使用统计失败: {e}")

    def _save_usage_stats(self):
        """保存使用统计"""
        try:
            backup_dir = self.config.get("resources", {}).get("backup_dir", "data/.emoji_backups")
            stats_file = os.path.join(backup_dir, "usage_stats.json")
            os.makedirs(os.path.dirname(stats_file), exist_ok=True)
            with open(stats_file, "w", encoding="utf-8") as f:
                json.dump(self.usage_stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存使用统计失败: {e}")

    def add_emoji(self, file_path: str, category: str = "custom", auto_tag: bool = True) -> bool:
        """添加表情包"""
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            allowed_formats = set(self.config.get("resources", {}).get("allowed_formats", []))

            if file_ext not in allowed_formats:
                logger.error(f"不支持的文件格式: {file_ext}")
                return False

            file_info = self._get_file_info(file_path)
            if not file_info:
                return False

            base_dir = self.config.get("resources", {}).get("emoji_dir", "data/emoji")
            target_dir = os.path.join(base_dir, category)
            os.makedirs(target_dir, exist_ok=True)

            target_file = os.path.join(target_dir, file_info["name"])

            if os.path.exists(target_file):
                name_part, ext = os.path.splitext(file_info["name"])
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                target_file = os.path.join(target_dir, f"{name_part}_{timestamp}{ext}")
                file_info["name"] = os.path.basename(target_file)

            import shutil

            shutil.copy2(file_path, target_file)

            if category not in self.emoji_cache:
                self.emoji_cache[category] = []

            file_info["path"] = target_file
            self.emoji_cache[category].append(file_info)

            if auto_tag:
                tags = self._generate_tags_for_emoji(file_info)
                self.emoji_tags[target_file] = tags
                self._save_tags()

            logger.info(f"添加表情包成功: {file_info['name']} -> {category}")
            return True

        except Exception as e:
            logger.error(f"添加表情包失败: {e}")
            return False

    def get_available_categories(self) -> List[str]:
        """获取可用的表情包类别"""
        categories = list(self.emoji_cache.keys()) + list(self.sticker_cache.keys())
        return sorted(set(categories))

    def get_stats(self) -> Dict:
        """获取统计信息"""
        total_emojis = sum(len(emojis) for emojis in self.emoji_cache.values())
        total_stickers = sum(len(stickers) for stickers in self.sticker_cache.values())

        return {
            "total_emojis": total_emojis,
            "total_stickers": total_stickers,
            "total_tags": len(self.emoji_tags),
            "categories": self.get_available_categories(),
            "usage_stats": len(self.usage_stats),
        }

    def analyze_message(self, text: str) -> Dict[str, Any]:
        """
        分析消息，返回完整的语义分析结果

        Returns:
            {
                'should_send': bool,
                'sentiment': dict,
                'context_type': list,
                'keywords': list,
                'suggested_tags': list,
                'confidence': float
            }
        """
        keywords = self.semantic_tagger.extract_keywords(text)
        sentiment = self.semantic_tagger.analyze_sentiment(text)
        context_types = self.semantic_tagger.get_context_type(text)
        should_send, suggested_tag, confidence = self.semantic_tagger.should_send_emoji(text)

        suggested_tags = list(sentiment.keys())[:3] if sentiment else []
        if suggested_tag and suggested_tag not in suggested_tags:
            suggested_tags.insert(0, suggested_tag)
        suggested_tags.extend(context_types[:2])

        return {
            "should_send": should_send,
            "sentiment": sentiment,
            "context_type": context_types,
            "keywords": keywords,
            "suggested_tags": suggested_tags[:5],
            "confidence": confidence,
            "original_text": text,
        }


_global_smart_emoji_manager = None


def get_smart_emoji_manager() -> SmartEmojiManager:
    """获取全局智能表情包管理器实例"""
    global _global_smart_emoji_manager
    if _global_smart_emoji_manager is None:
        _global_smart_emoji_manager = SmartEmojiManager()
    return _global_smart_emoji_manager


class EmojiManager(SmartEmojiManager):
    """兼容旧接口的包装类"""

    pass


def get_emoji_manager() -> EmojiManager:
    """获取全局表情包管理器实例（兼容）"""
    return get_smart_emoji_manager()
