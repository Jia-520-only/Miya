"""
查询系统基类
提供统一的查询接口和基础功能
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any, Callable, Union
import logging
import re
from pathlib import Path
import json
import time
from core.constants import Encoding


class BaseQuerySystem(ABC):
    """查询系统基类"""

    def __init__(self, data_path: str = "data/"):
        """
        初始化查询系统

        Args:
            data_path: 数据文件路径
        """
        self.data_path = Path(data_path)
        self.logger = logging.getLogger(self.__class__.__name__)
        self._index = {}  # 内存索引
        self._cache = {}  # 查询缓存

    @abstractmethod
    async def search(
        self,
        query: str,
        filters: Optional[Dict] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        执行查询

        Args:
            query: 查询关键词或自然语言
            filters: 过滤条件
            limit: 返回结果数量限制

        Returns:
            查询结果列表，每项包含内容和相关性分数
        """
        pass

    @abstractmethod
    async def index_data(self, data: Dict) -> bool:
        """
        索引数据

        Args:
            data: 要索引的数据

        Returns:
            是否成功
        """
        pass

    def calculate_relevance(self, query: str, content: str, field_weights: Optional[Dict[str, float]] = None) -> float:
        """
        计算相关性分数

        Args:
            query: 查询文本
            content: 内容文本
            field_weights: 字段权重

        Returns:
            相关性分数（0-1之间）
        """
        if not content:
            return 0.0

        query_lower = query.lower()
        content_lower = content.lower()

        score = 0.0

        # 1. 精确匹配（权重最高）
        if query_lower == content_lower:
            score += 2.0
        elif query_lower in content_lower:
            score += 1.0

        # 2. 关键词匹配
        keywords = re.findall(r'\w+', query_lower)
        keyword_matches = 0
        for keyword in keywords:
            if len(keyword) > 1:  # 忽略单字符
                count = content_lower.count(keyword)
                if count > 0:
                    keyword_matches += count

        if keyword_matches > 0:
            score += 0.5 * min(keyword_matches, 5)  # 最多加 2.5 分

        # 3. 词组匹配（连续词）
        if len(keywords) >= 2:
            phrase = ' '.join(keywords[:2])
            if phrase in content_lower:
                score += 0.8

        # 归一化到 0-1 之间
        return min(score / 5.0, 1.0)

    def fuzzy_match(self, pattern: str, text: str, threshold: float = 0.8) -> float:
        """
        模糊匹配

        Args:
            pattern: 匹配模式
            text: 目标文本
            threshold: 相似度阈值

        Returns:
            相似度分数
        """
        if not pattern or not text:
            return 0.0

        # 简单的字符相似度
        pattern_set = set(pattern.lower())
        text_set = set(text.lower())

        if not pattern_set:
            return 0.0

        intersection = pattern_set & text_set
        union = pattern_set | text_set

        similarity = len(intersection) / len(union)
        return similarity

    async def search_with_cache(
        self,
        cache_key: str,
        search_func: Callable,
        ttl: int = 300
    ) -> List[Dict]:
        """
        带缓存的查询

        Args:
            cache_key: 缓存键
            search_func: 搜索函数
            ttl: 缓存时间（秒）

        Returns:
            查询结果
        """
        # 检查缓存
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if cached.get('expires', 0) > time.time():
                return cached['results']

        # 执行查询
        results = await search_func()

        # 缓存结果
        self._cache[cache_key] = {
            'results': results,
            'expires': time.time() + ttl
        }

        return results

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        self.logger.info("查询缓存已清空")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        return {
            'index_size': len(self._index),
            'cache_size': len(self._cache),
            'data_path': str(self.data_path)
        }

    def _load_json(self, file_path: Path) -> Any:
        """
        加载 JSON 文件

        Args:
            file_path: 文件路径

        Returns:
            JSON 数据（可能是字典或列表）
        """
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding=Encoding.UTF8) as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self.logger.error(f"加载 JSON 文件失败 {file_path}: {e}")
            return {}

    def _save_json(self, file_path: Path, data: Dict) -> bool:
        """
        保存 JSON 文件

        Args:
            file_path: 文件路径
            data: 要保存的数据

        Returns:
            是否成功
        """
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding=Encoding.UTF8) as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"保存 JSON 文件失败 {file_path}: {e}")
            return False
