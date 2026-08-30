"""
智能查询构造器 - 弥娅资源猎手核心

把用户的原始搜索词加工成多组高命中率查询：
- 从聊天式长句中提取核心关键词（去掉口语前缀/语气词/疑问词）
- 类型化查询模板（apk → "XX APK 下载 最新版"）
- 中英混合双语查询（搜索引擎友好，无需翻译器）
- 纯规则式实现，零延迟、无外部依赖

所有参数从 qq_config.yaml 的 web_search.query_expansion 读取。
"""

import re
from typing import Dict, List, Optional

from config.config_utils import get_qq_config

# 类型化查询后缀模板（中英混合，命中率高）
_TYPE_SUFFIXES: Dict[str, List[str]] = {
    "image": ["高清图片", "壁纸", "hd wallpaper"],
    "video": ["视频 下载", "完整版", "video download"],
    "apk": ["APK 下载", "安卓版 下载 最新版", "apk download"],
    "program": ["官网", "官方下载", "official download", "最新版 下载"],
    "document": ["PDF 下载", "电子书", "pdf download"],
    "archive": ["压缩包 下载", "资源包", "download"],
    "audio": ["音频 下载", "MP3", "mp3 download"],
    "any": [],
}

# 英文类型关键词（直接拼进中文查询也有效，Bing/Google 可识别）
_TYPE_EN_KEYWORD: Dict[str, str] = {
    "image": "image",
    "video": "video",
    "apk": "apk",
    "program": "download",
    "document": "pdf",
    "archive": "archive",
    "audio": "mp3",
}

# 口语前缀（搜索词中无意义，直接剥离；长前缀必须排在短前缀之前）
_QUERY_PREFIXES = (
    "请你帮我找一下",
    "请帮我找一下",
    "帮我找一下",
    "帮我找下",
    "请你帮我找",
    "请帮我找",
    "帮我找",
    "帮我搜",
    "帮我查",
    "帮我看看",
    "帮我查查",
    "找一下",
    "搜一下",
    "查一下",
    "我想找",
    "我想搜",
    "我想查",
    "我要找",
    "我要搜",
    "我想知道",
    "请问",
    "你知道",
    "告诉我",
)

# 口语后缀（疑问/语气/礼貌词）
_QUERY_SUFFIXES = (
    "谢谢啦",
    "谢谢了",
    "谢谢你",
    "谢谢",
    "多谢",
    "感谢",
    "麻烦了",
    "麻烦",
    "吗",
    "呢",
    "呀",
    "吧",
    "啊",
    "啦",
    "哦",
    "呗",
    "嘛",
    "在哪",
    "在哪里",
    "有哪些",
    "是什么",
    "是什么呀",
    "怎么样",
    "怎么下载",
    "如何下载",
    "多少钱",
)

# 类型化尾词（知道资源类型时，剥离查询尾部的泛型名词；长尾词排在前面）
_TYPE_TAIL_WORDS: Dict[str, List[str]] = {
    "apk": ["的安卓安装包", "安卓安装包", "的安装包", "安装包", "安卓包", "安卓版", "的应用", "应用"],
    "program": ["的安装包", "安装包", "软件", "应用程序", "电脑版"],
    "video": ["的视频", "视频资源", "视频"],
    "document": ["的文档", "文档", "电子书"],
    "audio": ["的音频", "音频"],
    "image": ["的图片", "的照片", "图片"],
    "archive": ["的压缩包", "压缩包"],
}

# 疑问短语（长句压缩时剔除）
_INTERROGATIVE_PHRASES = (
    "最近有什么",
    "现在有什么",
    "目前有什么",
    "最近有没有",
    "现在有没有",
    "有什么",
    "有没有",
    "有哪些",
    "推荐一些",
    "推荐几个",
    "推荐一下",
    "给我推荐",
)

# 高频口语虚词（仅当整体是长句时才剔除，短词查询不受影响）
_FILLER_WORDS = ("一下", "一些", "一个", "几个", "点", "些")

# 中文+英文+数字的正则（用于判断查询是否值得保留）
_TOKEN_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9.+_\- ]+")


def _cfg() -> Dict:
    cfg = get_qq_config("web_search", "query_expansion", default={}) or {}
    if not isinstance(cfg, dict):
        cfg = {}
    return cfg


def extract_core_query(text: str, resource_type: Optional[str] = None, max_len: int = 24) -> str:
    """从聊天式长句中提取核心搜索词。

    例: "帮我找一下红果短剧的安卓安装包，谢谢啦" → "红果短剧"
         "最近有什么好玩的单机游戏吗" → "好玩的单机游戏"
    """
    q = (text or "").strip()
    if not q:
        return ""

    # 1. 剥离口语前缀
    for prefix in _QUERY_PREFIXES:
        if q.startswith(prefix):
            q = q[len(prefix):].strip()
            break

    # 2. 剥离口语后缀
    changed = True
    while changed and q:
        changed = False
        for suffix in _QUERY_SUFFIXES:
            if q.endswith(suffix):
                q = q[: -len(suffix)].strip()
                changed = True
                break

    # 3. 剔除疑问短语
    for phrase in _INTERROGATIVE_PHRASES:
        q = q.replace(phrase, " ")

    # 4. 清理标点与空格
    q = re.sub(r"[?？!！。．.~～、，,：:；;]+", " ", q)
    q = re.sub(r"\s+", " ", q).strip()

    # 5. 长句才剔除口语虚词（避免破坏短查询，如「镜流的」这类短词）
    if len(q) > 12:
        # 「一下」在任何长句位置都是口语化虚词，直接剔除
        q = q.replace("一下", " ")
        for w in _FILLER_WORDS:
            q = re.sub(rf"{w}(?=[\s，,、]|$)", " ", q)
        q = re.sub(r"\s+", " ", q).strip()

    # 6. 已知资源类型时，剥离查询尾部的泛型类型词
    #    例: "红果短剧的安卓安装包" (apk) → "红果短剧"
    if resource_type:
        changed = True
        while changed and q:
            changed = False
            for tail in _TYPE_TAIL_WORDS.get(resource_type, []):
                if q.endswith(tail) and len(q) - len(tail) >= 2:
                    q = q[: -len(tail)].strip()
                    changed = True
                    break
        # 剥离后残留的句尾「的」
        if q.endswith("的") and len(q) > 1:
            q = q[:-1].strip()

    # 7. 截断过长查询
    if len(q) > max_len:
        # 优先保留前半部分（核心词通常在前）
        q = q[:max_len].strip()
        # 避免截断半个词
        if " " in q:
            q = q.rsplit(" ", 1)[0].strip()

    # 8. 兜底：剥离后为空则返回原文
    return q or (text or "").strip()


def build_queries(query: str, resource_type: str = "any", site: Optional[str] = None) -> List[str]:
    """根据资源类型生成多组增强查询（去重、限数）。

    Args:
        query: 原始搜索词
        resource_type: image/video/apk/program/document/archive/audio/any
        site: 可选站点限定（暂不参与查询构造，由调用方处理）

    Returns:
        查询列表（第 1 个为最优查询）
    """
    cfg = _cfg()
    if not cfg.get("enabled", True):
        return [query.strip()] if query.strip() else []

    base = extract_core_query(query, resource_type)
    if not base:
        return []

    max_queries = int(cfg.get("max_queries", 4) or 4)
    bilingual = bool(cfg.get("bilingual", True))

    candidates: List[str] = [base]

    # 类型化后缀查询
    for suffix in _TYPE_SUFFIXES.get(resource_type, []):
        candidates.append(f"{base} {suffix}")

    # 中英混合查询
    if bilingual:
        en_kw = _TYPE_EN_KEYWORD.get(resource_type)
        if en_kw:
            candidates.append(f"{base} {en_kw}")

    # 去重（忽略首尾空格）
    seen = set()
    queries: List[str] = []
    for c in candidates:
        key = c.strip().lower()
        if key and key not in seen:
            seen.add(key)
            queries.append(c.strip())
        if len(queries) >= max_queries:
            break

    return queries
