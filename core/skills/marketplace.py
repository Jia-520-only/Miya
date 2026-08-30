"""
弥娅技能市场 (Skill Marketplace)

功能：
1. 技能发布和发现
2. 技能评分和评论
3. 技能分类和搜索
4. 技能版本管理

作者: MIYA
日期: 2026-04-28
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ==================== 枚举定义 ====================


class SkillCategory(str, Enum):
    """技能分类"""

    AGENT = "agent"  # Agent技能
    TOOL = "tool"  # 工具技能
    INTEGRATION = "integration"  # 集成技能
    UTILITY = "utility"  # 实用工具
    ENTERTAINMENT = "entertainment"  # 娱乐


class SkillPublishStatus(str, Enum):
    """技能发布状态"""

    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


# ==================== 数据结构 ====================


@dataclass
class SkillReview:
    """技能评论"""

    review_id: str
    user_id: str
    rating: int  # 1-5
    comment: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class SkillListing:
    """技能列表项"""

    skill_id: str
    name: str
    description: str
    category: SkillCategory
    author: str
    version: str
    tags: List[str] = field(default_factory=list)
    downloads: int = 0
    rating: float = 0.0
    review_count: int = 0
    status: SkillPublishStatus = SkillPublishStatus.DRAFT
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    price: float = 0.0  # 价格，0表示免费


# ==================== 技能市场 ====================


class SkillMarketplace:
    """
    技能市场

    功能：
    - 技能发布
    - 技能发现
    - 技能搜索
    - 评分评论
    - 版本管理
    """

    def __init__(self, data_dir: str = "data/skills_marketplace"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._listings_file = self.data_dir / "listings.json"
        self._reviews_file = self.data_dir / "reviews.json"

        self._listings: Dict[str, SkillListing] = {}
        self._reviews: Dict[str, List[SkillReview]] = {}

        self._load_data()

    def _load_data(self):
        """加载数据"""
        # 加载列表
        if self._listings_file.exists():
            try:
                with open(self._listings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.values():
                        self._listings[item["skill_id"]] = SkillListing(**item)
                logger.info(f"[Marketplace] 加载了 {len(self._listings)} 个技能")
            except Exception as e:
                logger.warning(f"[Marketplace] 加载失败: {e}")

        # 加载评论
        if self._reviews_file.exists():
            try:
                with open(self._reviews_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for skill_id, reviews in data.items():
                        self._reviews[skill_id] = [SkillReview(**r) for r in reviews]
            except Exception as e:
                logger.warning(f"[Marketplace] 加载评论失败: {e}")

    def _save_data(self):
        """保存数据"""
        # 保存列表
        try:
            data = {sid: listing.__dict__ for sid, listing in self._listings.items()}
            with open(self._listings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[Marketplace] 保存失败: {e}")

        # 保存评论
        try:
            data = {sid: [review.__dict__ for review in reviews] for sid, reviews in self._reviews.items()}
            with open(self._reviews_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[Marketplace] 保存评论失败: {e}")

    def publish_skill(
        self,
        name: str,
        description: str,
        category: SkillCategory,
        author: str,
        version: str = "1.0.0",
        tags: List[str] = None,
        price: float = 0.0,
    ) -> str:
        """发布技能"""
        skill_id = str(uuid.uuid4())[:8]

        listing = SkillListing(
            skill_id=skill_id,
            name=name,
            description=description,
            category=category,
            author=author,
            version=version,
            tags=tags or [],
            status=SkillPublishStatus.PUBLISHED,
            price=price,
        )

        self._listings[skill_id] = listing
        self._save_data()

        logger.info(f"[Marketplace] 发布技能: {name} ({skill_id})")
        return skill_id

    def unpublish_skill(self, skill_id: str) -> bool:
        """下架技能"""
        if skill_id in self._listings:
            self._listings[skill_id].status = SkillPublishStatus.DEPRECATED
            self._save_data()
            logger.info(f"[Marketplace] 下架技能: {skill_id}")
            return True
        return False

    def get_skill(self, skill_id: str) -> Optional[SkillListing]:
        """获取技能"""
        return self._listings.get(skill_id)

    def list_skills(
        self,
        category: Optional[SkillCategory] = None,
        status: Optional[SkillPublishStatus] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """列出技能"""
        result = []

        for listing in self._listings.values():
            if status and listing.status != status:
                continue
            if category and listing.category != category:
                continue

            # 计算评分
            reviews = self._reviews.get(listing.skill_id, [])
            if reviews:
                listing.rating = sum(r.rating for r in reviews) / len(reviews)
                listing.review_count = len(reviews)

            result.append(
                {
                    "skill_id": listing.skill_id,
                    "name": listing.name,
                    "description": listing.description,
                    "category": listing.category.value,
                    "author": listing.author,
                    "version": listing.version,
                    "tags": listing.tags,
                    "downloads": listing.downloads,
                    "rating": listing.rating,
                    "review_count": listing.review_count,
                    "price": listing.price,
                }
            )

        # 按下载量排序
        result.sort(key=lambda x: x["downloads"], reverse=True)
        return result[:limit]

    def search_skills(
        self,
        query: str,
        category: Optional[SkillCategory] = None,
        tags: List[str] = None,
        limit: int = 20,
    ) -> List[Dict]:
        """搜索技能"""
        query = query.lower()
        results = []

        for listing in self._listings.values():
            if listing.status != SkillPublishStatus.PUBLISHED:
                continue

            # 关键词匹配
            match = (
                query in listing.name.lower()
                or query in listing.description.lower()
                or any(query in tag.lower() for tag in listing.tags)
            )

            if not match:
                continue

            # 分类过滤
            if category and listing.category != category:
                continue

            # 标签过滤
            if tags and not any(tag in listing.tags for tag in tags):
                continue

            results.append(
                {
                    "skill_id": listing.skill_id,
                    "name": listing.name,
                    "description": listing.description,
                    "category": listing.category.value,
                    "author": listing.author,
                    "tags": listing.tags,
                }
            )

        return results[:limit]

    def add_review(
        self,
        skill_id: str,
        user_id: str,
        rating: int,
        comment: str,
    ) -> bool:
        """添加评论"""
        if skill_id not in self._listings:
            return False

        if rating < 1 or rating > 5:
            return False

        review = SkillReview(
            review_id=str(uuid.uuid4())[:8],
            user_id=user_id,
            rating=rating,
            comment=comment,
        )

        if skill_id not in self._reviews:
            self._reviews[skill_id] = []

        self._reviews[skill_id].append(review)
        self._save_data()

        logger.info(f"[Marketplace] 添加评论: {skill_id} - {rating}星")
        return True

    def get_reviews(self, skill_id: str) -> List[Dict]:
        """获取技能评论"""
        reviews = self._reviews.get(skill_id, [])
        return [
            {
                "review_id": r.review_id,
                "user_id": r.user_id,
                "rating": r.rating,
                "comment": r.comment,
                "created_at": r.created_at,
            }
            for r in reviews
        ]

    def increment_downloads(self, skill_id: str) -> bool:
        """增加下载量"""
        if skill_id in self._listings:
            self._listings[skill_id].downloads += 1
            self._save_data()
            return True
        return False

    def get_stats(self) -> Dict:
        """获取市场统计"""
        published = sum(1 for l in self._listings.values() if l.status == SkillPublishStatus.PUBLISHED)

        total_reviews = sum(len(r) for r in self._reviews.values())

        return {
            "total_skills": len(self._listings),
            "published_skills": published,
            "total_reviews": total_reviews,
            "categories": {
                cat.value: sum(
                    1 for l in self._listings.values() if l.category == cat and l.status == SkillPublishStatus.PUBLISHED
                )
                for cat in SkillCategory
            },
        }


# ==================== 全局实例 ====================


_marketplace: Optional[SkillMarketplace] = None


def get_skill_marketplace(
    data_dir: str = "data/skills_marketplace",
) -> SkillMarketplace:
    """获取技能市场"""
    global _marketplace
    if _marketplace is None:
        _marketplace = SkillMarketplace(data_dir)
    return _marketplace


__all__ = [
    "SkillCategory",
    "SkillPublishStatus",
    "SkillReview",
    "SkillListing",
    "SkillMarketplace",
    "get_skill_marketplace",
]
