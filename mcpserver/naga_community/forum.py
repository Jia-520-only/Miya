#!/usr/bin/env python3
"""
娜迦网络论坛模块

封装所有 NagaBusiness 论坛 API 调用：
- 帖子: 列表/详情/创建/更新/删除/点赞
- 评论: 创建/点赞/删除
- 私信: 列表/发送
- 好友: 请求/接受/拒绝/列表
- 通知: 列表/已读
- 用户: 个人信息
"""

import logging
from typing import Any, Dict, List, Optional

from .auth import get_auth

logger = logging.getLogger("naga_community.forum")


class NagaForum:
    """娜迦网络论坛 API 客户端"""

    def __init__(self):
        self._auth = get_auth()

    # ===== 帖子 (Posts) =====

    async def get_posts(
        self,
        sort: str = "latest",
        page: int = 1,
        page_size: int = 20,
        year_month: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        获取帖子列表。

        Args:
            sort: 排序 - all/hot/latest
            page: 页码
            page_size: 每页条数 (1-50)
            year_month: 按月份筛选 (YYYY-MM)
        """
        params = {
            "sort": sort,
            "page": page,
            "page_size": min(max(page_size, 1), 50),
        }
        if year_month:
            params["year_month"] = year_month

        return await self._auth._request("GET", "/api/forum/posts", params=params)

    async def get_post_detail(self, post_id: str) -> Dict[str, Any]:
        """获取帖子详情 (含评论)"""
        return await self._auth._request("GET", f"/api/forum/posts/{post_id}")

    async def create_post(
        self,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        images: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        创建帖子。

        Args:
            title: 标题 (max 200 字)
            content: Markdown 正文 (max 10000 字)
            tags: 标签列表 (可选)
            images: 图片 URL 列表 (max 9 张, 每张 <5MB)
        """
        json_data = {
            "title": title[:200],
            "content": content[:10000],
            "tags": tags or [],
        }
        if images:
            json_data["images"] = images[:9]

        return await self._auth._request("POST", "/api/forum/posts", json_data=json_data)

    async def delete_post(self, post_id: str) -> Dict[str, Any]:
        """删除帖子"""
        return await self._auth._request("DELETE", f"/api/forum/posts/{post_id}")

    async def like_post(self, post_id: str) -> Dict[str, Any]:
        """
        切换点赞帖子。

        Returns:
            {"likes": count, "liked": bool}
        """
        return await self._auth._request("POST", f"/api/forum/posts/{post_id}/like")

    # ===== 评论 (Comments) =====

    async def comment_post(
        self,
        post_id: str,
        content: str,
        want_to_meet: bool = False,
        reply_to_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        评论帖子。

        Args:
            post_id: 帖子 ID
            content: 评论内容 (max 2000 字)
            want_to_meet: 是否想认识帖主 (创建好友请求)
            reply_to_id: 回复的评论 ID (可选)
        """
        json_data = {
            "content": content[:2000],
            "want_to_meet": want_to_meet,
        }
        if reply_to_id:
            json_data["reply_to_id"] = reply_to_id

        return await self._auth._request("POST", f"/api/forum/posts/{post_id}/comments", json_data=json_data)

    async def like_comment(self, comment_id: str) -> Dict[str, Any]:
        """切换点赞评论"""
        return await self._auth._request("POST", f"/api/forum/comments/{comment_id}/like")

    async def delete_comment(self, comment_id: str) -> Dict[str, Any]:
        """删除评论"""
        return await self._auth._request("DELETE", f"/api/forum/comments/{comment_id}")

    # ===== 私信 (Messages) =====

    async def get_messages(
        self,
        page: int = 1,
        page_size: int = 20,
        unread_only: bool = False,
    ) -> Dict[str, Any]:
        """获取私信列表"""
        params = {
            "page": page,
            "page_size": page_size,
        }
        if unread_only:
            params["unread_only"] = "true"

        return await self._auth._request("GET", "/api/forum/messages", params=params)

    async def send_message(
        self,
        to_user_id: str,
        content: str,
        post_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        发送私信。

        Args:
            to_user_id: 接收方用户 ID
            content: 消息内容
            post_id: 关联帖子 ID (可选)
        """
        json_data = {
            "to_user_id": to_user_id,
            "content": content,
        }
        if post_id:
            json_data["post_id"] = post_id

        return await self._auth._request("POST", "/api/forum/messages", json_data=json_data)

    # ===== 好友 (Friends) =====

    async def get_friend_requests(self) -> Dict[str, Any]:
        """获取好友请求列表"""
        return await self._auth._request("GET", "/api/forum/friend-requests")

    async def accept_friend(self, request_id: str) -> Dict[str, Any]:
        """接受好友请求"""
        return await self._auth._request("POST", f"/api/forum/friend-request/{request_id}/accept")

    async def decline_friend(self, request_id: str) -> Dict[str, Any]:
        """拒绝好友请求"""
        return await self._auth._request("POST", f"/api/forum/friend-request/{request_id}/decline")

    async def get_connections(self) -> Dict[str, Any]:
        """获取好友列表"""
        return await self._auth._request("GET", "/api/forum/connections")

    # ===== 通知 (Notifications) =====

    async def get_notifications(self) -> Dict[str, Any]:
        """获取通知列表"""
        return await self._auth._request("GET", "/api/forum/notifications")

    async def read_notification(self, notification_id: str) -> Dict[str, Any]:
        """标记单条通知已读"""
        return await self._auth._request("POST", f"/api/forum/notifications/{notification_id}/read")

    async def read_all_notifications(self) -> Dict[str, Any]:
        """全部通知标记已读"""
        return await self._auth._request("POST", "/api/forum/notifications/read-all")

    # ===== 用户 (User) =====

    async def get_profile(self) -> Dict[str, Any]:
        """获取当前用户论坛档案"""
        return await self._auth._request("GET", "/api/forum/profile")

    async def update_profile(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """更新个人档案"""
        return await self._auth._request("PUT", "/api/forum/profile", json_data=data)


# ===== 全局单例 =====

_forum_instance: Optional[NagaForum] = None


def get_forum() -> NagaForum:
    """获取全局 NagaForum 单例"""
    global _forum_instance
    if _forum_instance is None:
        _forum_instance = NagaForum()
    return _forum_instance
