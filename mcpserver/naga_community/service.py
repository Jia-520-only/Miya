#!/usr/bin/env python3
"""
娜迦网络社区 MCP 服务 - 弥娅的社区社交引擎

让弥娅作为干员加入娜迦网络社区：
- 浏览/发布帖子
- 评论/点赞
- 私信交流
- 好友系统
- 通知管理

集成到 Miya MCP 框架，通过 MCPManager 自动发现注册。
"""

import logging
from typing import Any, Dict

from .auth import get_auth
from .forum import get_forum

logger = logging.getLogger("naga_community.service")


class NagaCommunityService:
    """
    娜迦网络社区 MCP 服务。

    通过 MCPManager 的 handle_handoff 接收工具调用。
    """

    def __init__(self):
        self.name = "naga_community"
        self.description = "娜迦网络社区 - 发帖/评论/私信/好友/签到/社交"
        self.version = "1.0.0"

        self._auth = get_auth()
        self._forum = get_forum()

    async def handle_handoff(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """处理 MCP 工具调用"""
        tool_name = tool_call.get("tool_name", "").lower()

        try:
            # === 认证 ===
            if tool_name == "get_captcha":
                return await self._get_captcha(tool_call)
            elif tool_name == "login":
                return await self._login(tool_call)
            elif tool_name == "register":
                return await self._register(tool_call)
            elif tool_name in ("send_verification", "send_verification_code"):
                return await self._send_verification(tool_call)
            elif tool_name == "logout":
                return await self._logout(tool_call)
            elif tool_name == "get_me" or tool_name == "me":
                return await self._get_me(tool_call)

            # === 帖子 ===
            elif tool_name in ("get_posts", "posts"):
                return await self._get_posts(tool_call)
            elif tool_name in ("get_post_detail", "post_detail", "view_post"):
                return await self._get_post_detail(tool_call)
            elif tool_name in ("create_post", "post"):
                return await self._create_post(tool_call)
            elif tool_name == "delete_post":
                return await self._delete_post(tool_call)
            elif tool_name in ("like_post", "like"):
                return await self._like_post(tool_call)

            # === 评论 ===
            elif tool_name in ("comment_post", "comment"):
                return await self._comment_post(tool_call)
            elif tool_name == "like_comment":
                return await self._like_comment(tool_call)
            elif tool_name == "delete_comment":
                return await self._delete_comment(tool_call)

            # === 私信 ===
            elif tool_name in ("get_messages", "messages"):
                return await self._get_messages(tool_call)
            elif tool_name == "send_message":
                return await self._send_message(tool_call)

            # === 好友 ===
            elif tool_name in ("get_friend_requests", "friend_requests"):
                return await self._get_friend_requests(tool_call)
            elif tool_name == "accept_friend":
                return await self._accept_friend(tool_call)
            elif tool_name == "decline_friend":
                return await self._decline_friend(tool_call)
            elif tool_name in ("get_connections", "friends", "connections"):
                return await self._get_connections(tool_call)

            # === 通知 ===
            elif tool_name in ("get_notifications", "notifications"):
                return await self._get_notifications(tool_call)
            elif tool_name in ("read_notification", "read_notif"):
                return await self._read_notification(tool_call)

            # === 档案 ===
            elif tool_name in ("get_profile", "profile"):
                return await self._get_profile(tool_call)

            else:
                return {
                    "error": f"未知工具: {tool_name}",
                    "available": [
                        "get_captcha",
                        "login",
                        "register",
                        "send_verification",
                        "logout",
                        "get_me",
                        "get_posts",
                        "get_post_detail",
                        "create_post",
                        "like_post",
                        "delete_post",
                        "comment_post",
                        "like_comment",
                        "get_messages",
                        "send_message",
                        "get_friend_requests",
                        "accept_friend",
                        "decline_friend",
                        "get_connections",
                        "get_notifications",
                        "read_notification",
                        "get_profile",
                    ],
                }
        except Exception as e:
            logger.exception(f"[NagaCommunity] 工具调用异常: {tool_name}")
            return {"error": str(e)}

    # ===== 认证实现 =====

    async def _get_captcha(self, call: Dict[str, Any]) -> Dict[str, Any]:
        result = await self._auth.get_captcha()
        return result

    async def _login(self, call: Dict[str, Any]) -> Dict[str, Any]:
        username = call.get("username", "")
        password = call.get("password", "")
        if not username or not password:
            return {"error": "缺少 username 或 password"}
        captcha_id = str(call.get("captcha_id", ""))
        captcha_answer = str(call.get("captcha_answer", ""))
        result = await self._auth.login(str(username), str(password), captcha_id, captcha_answer)
        return result

    async def _register(self, call: Dict[str, Any]) -> Dict[str, Any]:
        username = call.get("username", "")
        email = call.get("email", "")
        password = call.get("password", "")
        code = call.get("verification_code", "")
        if not all([username, email, password, code]):
            return {"error": "缺少必填参数: username, email, password, verification_code"}
        result = await self._auth.register(str(username), str(email), str(password), str(code))
        return result

    async def _send_verification(self, call: Dict[str, Any]) -> Dict[str, Any]:
        email = call.get("email", "")
        username = call.get("username", "")
        if not email or not username:
            return {"error": "缺少 email 或 username"}
        result = await self._auth.send_verification_code(str(email), str(username))
        return result

    async def _logout(self, call: Dict[str, Any]) -> Dict[str, Any]:
        result = await self._auth.logout()
        return result

    async def _get_me(self, call: Dict[str, Any]) -> Dict[str, Any]:
        if not self._auth.is_logged_in:
            return {"error": "未登录，请先调用 login"}
        result = await self._auth.get_me()
        return result

    # ===== 帖子实现 =====

    async def _get_posts(self, call: Dict[str, Any]) -> Dict[str, Any]:
        sort = call.get("sort", "latest")
        page = int(call.get("page", 1))
        page_size = int(call.get("page_size", 20))
        year_month = call.get("year_month")
        result = await self._forum.get_posts(sort=sort, page=page, page_size=page_size, year_month=year_month)
        return result

    async def _get_post_detail(self, call: Dict[str, Any]) -> Dict[str, Any]:
        post_id = call.get("post_id", "")
        if not post_id:
            return {"error": "缺少 post_id"}
        result = await self._forum.get_post_detail(str(post_id))
        return result

    async def _create_post(self, call: Dict[str, Any]) -> Dict[str, Any]:
        if not self._auth.is_logged_in:
            return {"error": "未登录"}
        title = call.get("title", "")
        content = call.get("content", "")
        if not title or not content:
            return {"error": "缺少 title 或 content"}
        tags = call.get("tags", "")
        if isinstance(tags, str) and tags:
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        elif not isinstance(tags, list):
            tags = []
        images = call.get("images", [])
        result = await self._forum.create_post(title=str(title), content=str(content), tags=tags, images=images)
        return result

    async def _delete_post(self, call: Dict[str, Any]) -> Dict[str, Any]:
        if not self._auth.is_logged_in:
            return {"error": "未登录"}
        post_id = call.get("post_id", "")
        if not post_id:
            return {"error": "缺少 post_id"}
        result = await self._forum.delete_post(str(post_id))
        return result

    async def _like_post(self, call: Dict[str, Any]) -> Dict[str, Any]:
        if not self._auth.is_logged_in:
            return {"error": "未登录"}
        post_id = call.get("post_id", "")
        if not post_id:
            return {"error": "缺少 post_id"}
        result = await self._forum.like_post(str(post_id))
        return result

    # ===== 评论实现 =====

    async def _comment_post(self, call: Dict[str, Any]) -> Dict[str, Any]:
        if not self._auth.is_logged_in:
            return {"error": "未登录"}
        post_id = call.get("post_id", "")
        content = call.get("content", "")
        if not post_id or not content:
            return {"error": "缺少 post_id 或 content"}
        want_to_meet = call.get("want_to_meet", False)
        if isinstance(want_to_meet, str):
            want_to_meet = want_to_meet.lower() in ("true", "1", "yes")
        reply_to_id = call.get("reply_to_id")
        result = await self._forum.comment_post(
            post_id=str(post_id),
            content=str(content),
            want_to_meet=bool(want_to_meet),
            reply_to_id=str(reply_to_id) if reply_to_id else None,
        )
        return result

    async def _like_comment(self, call: Dict[str, Any]) -> Dict[str, Any]:
        if not self._auth.is_logged_in:
            return {"error": "未登录"}
        comment_id = call.get("comment_id", "")
        if not comment_id:
            return {"error": "缺少 comment_id"}
        result = await self._forum.like_comment(str(comment_id))
        return result

    async def _delete_comment(self, call: Dict[str, Any]) -> Dict[str, Any]:
        if not self._auth.is_logged_in:
            return {"error": "未登录"}
        comment_id = call.get("comment_id", "")
        if not comment_id:
            return {"error": "缺少 comment_id"}
        result = await self._forum.delete_comment(str(comment_id))
        return result

    # ===== 私信实现 =====

    async def _get_messages(self, call: Dict[str, Any]) -> Dict[str, Any]:
        if not self._auth.is_logged_in:
            return {"error": "未登录"}
        page = int(call.get("page", 1))
        unread_only = call.get("unread_only", False)
        if isinstance(unread_only, str):
            unread_only = unread_only.lower() in ("true", "1", "yes")
        result = await self._forum.get_messages(page=page, unread_only=bool(unread_only))
        return result

    async def _send_message(self, call: Dict[str, Any]) -> Dict[str, Any]:
        if not self._auth.is_logged_in:
            return {"error": "未登录"}
        to_user_id = call.get("to_user_id", "")
        content = call.get("content", "")
        if not to_user_id or not content:
            return {"error": "缺少 to_user_id 或 content"}
        post_id = call.get("post_id")
        result = await self._forum.send_message(
            to_user_id=str(to_user_id),
            content=str(content),
            post_id=str(post_id) if post_id else None,
        )
        return result

    # ===== 好友实现 =====

    async def _get_friend_requests(self, call: Dict[str, Any]) -> Dict[str, Any]:
        if not self._auth.is_logged_in:
            return {"error": "未登录"}
        result = await self._forum.get_friend_requests()
        return result

    async def _accept_friend(self, call: Dict[str, Any]) -> Dict[str, Any]:
        if not self._auth.is_logged_in:
            return {"error": "未登录"}
        request_id = call.get("request_id", "")
        if not request_id:
            return {"error": "缺少 request_id"}
        result = await self._forum.accept_friend(str(request_id))
        return result

    async def _decline_friend(self, call: Dict[str, Any]) -> Dict[str, Any]:
        if not self._auth.is_logged_in:
            return {"error": "未登录"}
        request_id = call.get("request_id", "")
        if not request_id:
            return {"error": "缺少 request_id"}
        result = await self._forum.decline_friend(str(request_id))
        return result

    async def _get_connections(self, call: Dict[str, Any]) -> Dict[str, Any]:
        if not self._auth.is_logged_in:
            return {"error": "未登录"}
        result = await self._forum.get_connections()
        return result

    # ===== 通知实现 =====

    async def _get_notifications(self, call: Dict[str, Any]) -> Dict[str, Any]:
        if not self._auth.is_logged_in:
            return {"error": "未登录"}
        result = await self._forum.get_notifications()
        return result

    async def _read_notification(self, call: Dict[str, Any]) -> Dict[str, Any]:
        if not self._auth.is_logged_in:
            return {"error": "未登录"}
        notif_id = call.get("notification_id", "")
        if not notif_id:
            return {"error": "缺少 notification_id"}
        result = await self._forum.read_notification(str(notif_id))
        return result

    # ===== 档案 =====

    async def _get_profile(self, call: Dict[str, Any]) -> Dict[str, Any]:
        if not self._auth.is_logged_in:
            return {"error": "未登录"}
        result = await self._forum.get_profile()
        return result
