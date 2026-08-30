"""
弥娅唱歌引擎路由 — 跨平台共享模块

从决策层快速命令调用，不依赖 M-Link。
所有触发词和用户文本从 config/text_config.json 读取。
"""

import asyncio
import logging
import re as _re

logger = logging.getLogger(__name__)


def _get_sing_trigger_words() -> list:
    from core.text_loader import get_command_keywords

    return get_command_keywords().get("sing", [])


def _get_sing_control_words() -> list:
    from core.text_loader import get_command_keywords

    ck = get_command_keywords()
    return ck.get("sing_control_list", []) + ck.get("sing_control_skip", []) + ck.get("sing_control_stop", [])


def _get_singing_text(key: str, default: str = "", **kwargs) -> str:
    from core.text_loader import get_singing_text

    return get_singing_text(key, default, **kwargs)


def _load_config() -> dict:
    import json

    config_path = "config/singing_config.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def is_sing_request(text: str) -> bool:
    text_lower = text.strip().lower()
    for skip in _get_sing_control_words():
        if text_lower.startswith(skip.lower()):
            return False
    return any(word.lower() in text_lower for word in _get_sing_trigger_words())


_SONG_NAME_STRIP_SYMBOLS = "《》「」『』“”\"'‘’【】·`*"
_SONG_NAME_STRIP_EDGES = " ,，。.;；:：!！?？~～-—_ \t"

# 颜文字/装饰符号（歌名清洗时直接删除）
_SONG_DECOR_CHARS = (
    "●○◐◑◕◔◉◈◦•·∙―—–―‐…⋯~～≈≦≧★☆♥❤♡♪♫☀☁☂☃☄♠♣♧♨♬✿❀❁❃❄❅❆❇❈❉❊❋"
    "✳✴✵✶✷✸✹✺✻✼✽✾✿✧✦✩✪✫✬✭✮✯✰✱✲✓✔✕✖✗✘①②③④⑤⑥⑦⑧⑨⑩"
)

# emoji / 特殊符号 Unicode 区块
_EMOJI_RE = _re.compile(
    "[\U0001F000-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F900-\U0001F9FF"
    "\U00002B00-\U00002BFF"
    "\U0000FE00-\U0000FE0F"
    "\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF]"
)

# 成对括号（内容为纯符号时整体删除，如颜文字 (●—●)）
_PAIR_RE = _re.compile(r"[（(【\[「『]([^（）()【\]\[\]「」『』]{1,12})[)）】\]」』]")
_HAS_MEANING_RE = _re.compile(r"[\u4e00-\u9fffA-Za-z0-9]")


def clean_song_query(name: str) -> str:
    """清洗歌名：去掉书名号/引号/括号等装饰符号、颜文字、emoji 与首尾标点

    例: 《你从未离去》 → 你从未离去
       你从未离去(●—●) → 你从未离去
    """
    if not name:
        return name

    # 1. 成对括号内为纯符号/颜文字 → 连同括号整体删除
    prev = None
    while prev != name:
        prev = name
        name = _PAIR_RE.sub(
            lambda m: "" if not _HAS_MEANING_RE.search(m.group(1)) else m.group(0), name
        )

    # 2. 删除中文装饰符号（《你从未离去》 → 你从未离去）
    for ch in _SONG_NAME_STRIP_SYMBOLS:
        name = name.replace(ch, "")

    # 3. 西式括号：成对且内容有意义的保留 (孤勇者 (DJ版))，孤立/残留的删除
    for open_ch, close_ch in (("(", ")"), ("（", "）"), ("[", "]"), ("【", "】")):
        if name.count(open_ch) != name.count(close_ch):
            name = name.replace(open_ch, "").replace(close_ch, "")

    # 4. 删除颜文字装饰字符与 emoji（●—● → 空）
    for ch in _SONG_DECOR_CHARS:
        name = name.replace(ch, "")
    name = _EMOJI_RE.sub("", name)

    return name.strip(_SONG_NAME_STRIP_EDGES)


def extract_song_name(text: str) -> str:
    text_lower = text.strip().lower()

    for word in sorted(_get_sing_trigger_words(), key=len, reverse=True):
        pos = text_lower.find(word.lower())
        if pos != -1:
            name = text[pos + len(word) :].strip()
            return clean_song_query(name)
    return ""


async def handle_sing_request(query: str, username: str = "") -> str:
    from core.singing import get_singing_registry

    registry = get_singing_registry()
    engine = registry.get_engine()

    if engine is None or not engine.is_initialized:
        config = _load_config()
        if not config:
            return _get_singing_text("not_configured")
        await _init_from_config(registry, config)
        engine = registry.get_engine()
        if engine is None or not engine.is_initialized:
            return _get_singing_text("init_failed")

    return await registry.workflow.process_song_request(query, username)


async def _init_from_config(registry, config: dict):
    from core.singing import AutoConvertMusicEngine, BuiltinSingingEngine, RVCEngine

    engines_cfg = config.get("engines", {})
    preferred = config.get("preferred_engine", "builtin")

    for name, cfg in engines_cfg.items():
        if not cfg.get("enabled", False):
            continue

        if name == "builtin":
            engine = BuiltinSingingEngine()
            registry.register_engine(engine, is_default=(preferred == name))
            await asyncio.get_event_loop().run_in_executor(None, engine.initialize, cfg)
        elif name == "auto_convert_music":
            engine = AutoConvertMusicEngine()
            registry.register_engine(engine, is_default=(preferred == name))
            await asyncio.get_event_loop().run_in_executor(None, engine.initialize, cfg)
            if engine.is_initialized and engine.speaker:
                engine._get(f"/set_speaker/{engine.speaker}")
                logger.info(f"[唱歌] ACM speaker set: {engine.speaker}")
        elif name == "rvc":
            engine = RVCEngine()
            registry.register_engine(engine, is_default=(preferred == name))
            await asyncio.get_event_loop().run_in_executor(None, engine.initialize, cfg)
