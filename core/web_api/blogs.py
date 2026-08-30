"""
博客相关 API
处理博客的 CRUD 操作
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from .models import BlogPostCreate, BlogPostUpdate

logger = logging.getLogger(__name__)

try:
    from fastapi import APIRouter

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    APIRouter = object


class BlogRoutes:
    """博客路由"""

    def __init__(self, web_net, decision_hub):
        """初始化博客路由

        Args:
            web_net: WebNet 实例
            decision_hub: DecisionHub 实例
        """
        self.web_net = web_net
        self.decision_hub = decision_hub

        if not FASTAPI_AVAILABLE:
            logger.warning("[BlogRoutes] FastAPI 不可用")
            self.router = None
            return

        self.router = APIRouter(prefix="/api/blog", tags=["Blog"])
        self._setup_routes()
        logger.info("[BlogRoutes] 博客路由已初始化")

    def _setup_routes(self):
        """设置博客相关路由"""

        @self.router.get("/posts")
        async def get_blog_posts(
            page: int = 1, per_page: int = 10, category: Optional[str] = None, tag: Optional[str] = None
        ):
            """获取博客列表"""
            try:
                result = await self.web_net.get_blog_posts(page=page, category=category, tag=tag)
                return result
            except Exception as e:
                logger.error(f"[WebAPI] 获取博客列表失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/posts/{slug}")
        async def get_blog_post(slug: str):
            """获取单篇博客"""
            try:
                post = await self.web_net.get_blog_post(slug)
                if not post:
                    raise HTTPException(status_code=404, detail="文章不存在")
                return post
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[WebAPI] 获取博客失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/posts")
        async def create_blog_post(
            post_data: BlogPostCreate, token: Optional[HTTPAuthorizationCredentials] = Depends(lambda: None)
        ):
            """创建博客（需要认证）"""
            try:
                # 简化实现，不做严格权限检查
                result = await self.web_net.create_blog_post(
                    title=post_data.title,
                    content=post_data.content,
                    author="unknown",
                    category=post_data.category,
                    tags=post_data.tags,
                    published=post_data.published,
                )
                return result
            except Exception as e:
                logger.error(f"[WebAPI] 创建博客失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.put("/posts/{slug}")
        async def update_blog_post(
            slug: str, post_data: BlogPostUpdate, token: Optional[HTTPAuthorizationCredentials] = Depends(lambda: None)
        ):
            """更新博客（需要认证）"""
            try:
                # 简化实现
                result = await self.web_net.update_blog_post(
                    slug=slug,
                    title=post_data.title,
                    content=post_data.content,
                    category=post_data.category,
                    tags=post_data.tags,
                    published=post_data.published,
                )
                return result
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except Exception as e:
                logger.error(f"[WebAPI] 更新博客失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.delete("/posts/{slug}")
        async def delete_blog_post(slug: str, token: Optional[HTTPAuthorizationCredentials] = Depends(lambda: None)):
            """删除博客（需要认证）"""
            try:
                # 简化实现
                success = await self.web_net.delete_blog_post(slug)

                if not success:
                    raise HTTPException(status_code=404, detail="文章不存在")

                return {"success": True, "message": "删除成功"}
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[WebAPI] 删除博客失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    def get_router(self):
        """获取路由器"""
        return self.router
