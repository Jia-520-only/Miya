#!/usr/bin/env python3
"""
表情包自动保存服务
处理用户发送的表情包自动保存到仓库的功能
"""

import hashlib
import imghdr
import io
import logging
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from PIL import Image

logger = logging.getLogger(__name__)


class AutoEmojiSaver:
    """表情包自动保存服务"""

    def __init__(self, emoji_manager):
        """
        初始化自动保存服务

        Args:
            emoji_manager: EmojiManager实例
        """
        self.emoji_manager = emoji_manager
        self.config = emoji_manager.config.get("auto_save_user_emojis", {})

        # 用户上传统计
        self.user_upload_stats = {}  # {user_id: {'count': int, 'last_upload': timestamp}}

        # 图片哈希缓存（用于重复检测）
        self.image_hash_cache = {}

        logger.info("[AutoEmojiSaver] 表情包自动保存服务已初始化")

    def is_enabled(self) -> bool:
        """检查自动保存功能是否启用"""
        return self.config.get("enabled", True)

    def can_user_upload(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """
        检查用户是否可以上传表情包

        Args:
            user_id: 用户ID

        Returns:
            (是否可以上传, 错误消息)
        """
        if not self.is_enabled():
            return False, "自动保存功能未启用"

        # 检查用户上传限制
        user_stats = self.user_upload_stats.get(user_id, {"count": 0})
        max_uploads = self.config.get("max_user_uploads_per_user", 50)

        if user_stats["count"] >= max_uploads:
            return False, f"已达到上传限制（最多{max_uploads}个）"

        return True, None

    def _validate_image(self, image_data: bytes, image_format: str = None) -> Tuple[bool, Optional[str]]:
        """
        验证图片是否适合保存为表情包

        Args:
            image_data: 图片数据
            image_format: 图片格式（可选，自动检测）

        Returns:
            (是否有效, 错误消息)
        """
        # 检查图片大小
        min_size_kb = self.config.get("min_image_size_kb", 10)
        max_size_kb = self.config.get("max_image_size_kb", 5120)
        size_kb = len(image_data) / 1024

        if size_kb < min_size_kb:
            return False, f"图片太小（{size_kb:.1f}KB < {min_size_kb}KB）"
        if size_kb > max_size_kb:
            return False, f"图片太大（{size_kb:.1f}KB > {max_size_kb}KB）"

        # 检测图片格式
        if not image_format:
            image_format = imghdr.what(None, image_data)

        if not image_format:
            return False, "无法识别的图片格式"

        # 检查是否支持该格式
        allowed_formats = self.emoji_manager.config.get("resources", {}).get("allowed_formats", [])
        format_ext = f".{image_format.lower()}"

        # 特殊处理：imghdr返回'jpeg'，但配置文件可能是'.jpg'
        if format_ext == ".jpeg" and ".jpg" in allowed_formats:
            format_ext = ".jpg"

        if format_ext not in allowed_formats:
            return False, f"不支持的图片格式: {format_ext}"

        # 检查GIF动图是否允许
        if image_format == "gif" and not self.config.get("smart_filtering", {}).get("allow_animated", True):
            return False, "GIF动图不被允许"

        # 检查图片尺寸（如果有智能过滤）
        smart_filtering = self.config.get("smart_filtering", {})
        if smart_filtering.get("enabled", True):
            try:
                with Image.open(io.BytesIO(image_data)) as img:
                    width, height = img.size

                    min_width = smart_filtering.get("min_width", 50)
                    min_height = smart_filtering.get("min_height", 50)
                    max_aspect = smart_filtering.get("max_aspect_ratio", 4.0)
                    min_aspect = smart_filtering.get("min_aspect_ratio", 0.25)

                    if width < min_width or height < min_height:
                        return False, f"图片尺寸太小（{width}x{height} < {min_width}x{min_height}）"

                    aspect_ratio = width / height
                    if aspect_ratio > max_aspect or aspect_ratio < min_aspect:
                        return False, f"图片宽高比不合适（{aspect_ratio:.2f}）"
            except Exception as e:
                logger.warning(f"图片尺寸检查失败: {e}")
                # 如果检查失败，继续处理

        return True, None

    def _check_duplicate(self, image_data: bytes) -> Tuple[bool, Optional[str]]:
        """
        检查图片是否重复

        Args:
            image_data: 图片数据

        Returns:
            (是否重复, 重复图片的哈希值)
        """
        duplicate_config = self.config.get("duplicate_detection", {})
        if not duplicate_config.get("enabled", True):
            return False, None

        # 计算图片哈希
        hash_method = duplicate_config.get("hash_method", "md5")

        if hash_method == "md5":
            image_hash = hashlib.md5(image_data).hexdigest()
        elif hash_method == "sha256":
            image_hash = hashlib.sha256(image_data).hexdigest()
        else:
            # 简单使用MD5
            image_hash = hashlib.md5(image_data).hexdigest()

        # 检查缓存
        if image_hash in self.image_hash_cache:
            logger.info(f"[AutoEmojiSaver] 检测到重复图片，哈希: {image_hash[:8]}...")
            return True, image_hash

        # 添加到缓存
        self.image_hash_cache[image_hash] = datetime.now()

        # 清理过期的缓存（24小时）
        expired_time = datetime.now().timestamp() - 24 * 3600
        self.image_hash_cache = {h: t for h, t in self.image_hash_cache.items() if t.timestamp() > expired_time}

        return False, None

    def _generate_filename(self, user_id: int, original_name: str = None) -> str:
        """
        生成表情包文件名

        Args:
            user_id: 用户ID
            original_name: 原始文件名（可选）

        Returns:
            生成的文件名
        """
        naming_config = self.config.get("naming_strategy", {})
        method = naming_config.get("method", "timestamp_user")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if method == "timestamp_user":
            prefix = naming_config.get("default_prefix", "user_upload_")
            return f"{prefix}{user_id}_{timestamp}"
        elif method == "original" and original_name:
            # 保留原始文件名，但添加时间戳避免冲突
            name_part, ext = os.path.splitext(original_name)
            return f"{name_part}_{timestamp}{ext}"
        else:
            # 默认方法
            prefix = naming_config.get("default_prefix", "user_upload_")
            return f"{prefix}{user_id}_{timestamp}"

    def _save_to_temp_file(self, image_data: bytes, image_format: str) -> Optional[str]:
        """
        将图片数据保存到临时文件

        Args:
            image_data: 图片数据
            image_format: 图片格式

        Returns:
            临时文件路径，失败返回None
        """
        try:
            # 确定文件扩展名
            ext_map = {"jpeg": ".jpg", "jpg": ".jpg", "png": ".png", "gif": ".gif", "bmp": ".bmp", "webp": ".webp"}
            ext = ext_map.get(image_format.lower(), f".{image_format}")

            # 创建临时文件
            temp_file = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            temp_file.write(image_data)
            temp_file.close()

            return temp_file.name
        except Exception as e:
            logger.error(f"保存到临时文件失败: {e}")
            return None

    async def auto_save_emoji(
        self, user_id: int, image_data: bytes, image_info: Dict[str, Any] = None, user_naming: str = None
    ) -> Dict[str, Any]:
        """
        自动保存用户发送的表情包

        Args:
            user_id: 用户ID
            image_data: 图片数据
            image_info: 图片信息字典（可选）
            user_naming: 用户指定的名称（可选）

        Returns:
            保存结果字典
        """
        result = {"success": False, "message": "", "emoji_path": None, "category": None}

        try:
            # 检查功能是否启用
            if not self.is_enabled():
                result["message"] = "表情包自动保存功能未启用"
                return result

            # 检查用户权限
            can_upload, error_msg = self.can_user_upload(user_id)
            if not can_upload:
                result["message"] = error_msg
                return result

            # 验证图片
            is_valid, error_msg = self._validate_image(image_data)
            if not is_valid:
                result["message"] = f"图片验证失败: {error_msg}"
                return result

            # 检查重复
            is_duplicate, duplicate_hash = self._check_duplicate(image_data)
            if is_duplicate:
                result["message"] = "检测到重复的表情包，跳过保存"
                return result

            # 检测图片格式
            image_format = imghdr.what(None, image_data)
            if not image_format:
                result["message"] = "无法识别图片格式"
                return result

            # 保存到临时文件
            temp_file = self._save_to_temp_file(image_data, image_format)
            if not temp_file:
                result["message"] = "保存临时文件失败"
                return result

            try:
                # 确定保存分类
                category = self.config.get("save_category", "user_uploaded")

                # 生成文件名
                original_name = image_info.get("file_name", "unknown") if image_info else None
                if user_naming:
                    # 使用用户指定的名称
                    name_part, ext = os.path.splitext(user_naming)
                    if not ext:
                        ext = f".{image_format}"
                    filename = f"{name_part}{ext}"
                else:
                    filename = self._generate_filename(user_id, original_name)

                # 调用EmojiManager添加表情包
                success = self.emoji_manager.add_emoji(temp_file, category)

                if success:
                    # 更新用户统计
                    if user_id not in self.user_upload_stats:
                        self.user_upload_stats[user_id] = {"count": 0, "last_upload": None}

                    self.user_upload_stats[user_id]["count"] += 1
                    self.user_upload_stats[user_id]["last_upload"] = datetime.now()

                    result["success"] = True
                    result["message"] = self.config.get("notifications", {}).get(
                        "success_message", "已自动保存你发送的表情包到我的仓库！"
                    )
                    result["category"] = category
                    result["filename"] = filename

                    logger.info(f"[AutoEmojiSaver] 用户 {user_id} 的表情包已自动保存到分类 '{category}'")
                else:
                    result["message"] = "保存到表情包仓库失败"

            finally:
                # 清理临时文件
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {e}")

        except Exception as e:
            logger.error(f"[AutoEmojiSaver] 自动保存表情包异常: {e}", exc_info=True)
            result["message"] = f"自动保存失败: {str(e)}"

        return result

    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """
        获取用户上传统计

        Args:
            user_id: 用户ID

        Returns:
            用户统计信息
        """
        stats = self.user_upload_stats.get(user_id, {"count": 0, "last_upload": None})

        return {
            "user_id": user_id,
            "upload_count": stats["count"],
            "last_upload": stats["last_upload"].isoformat() if stats["last_upload"] else None,
            "max_allowed": self.config.get("max_user_uploads_per_user", 50),
            "remaining": max(0, self.config.get("max_user_uploads_per_user", 50) - stats["count"]),
        }

    def get_global_stats(self) -> Dict[str, Any]:
        """
        获取全局统计信息

        Returns:
            全局统计信息
        """
        total_users = len(self.user_upload_stats)
        total_uploads = sum(stats["count"] for stats in self.user_upload_stats.values())

        return {
            "total_users": total_users,
            "total_uploads": total_uploads,
            "enabled": self.is_enabled(),
            "config": {
                "max_per_user": self.config.get("max_user_uploads_per_user", 50),
                "save_category": self.config.get("save_category", "user_uploaded"),
                "smart_filtering": self.config.get("smart_filtering", {}).get("enabled", True),
                "duplicate_detection": self.config.get("duplicate_detection", {}).get("enabled", True),
            },
        }


# 全局实例
_global_auto_saver = None


def get_auto_emoji_saver(emoji_manager=None) -> AutoEmojiSaver:
    """
    获取全局自动保存服务实例

    Args:
        emoji_manager: EmojiManager实例（可选）

    Returns:
        AutoEmojiSaver实例
    """
    global _global_auto_saver

    if _global_auto_saver is None:
        if emoji_manager is None:
            from .emoji_manager import get_emoji_manager

            emoji_manager = get_emoji_manager()

        _global_auto_saver = AutoEmojiSaver(emoji_manager)

    return _global_auto_saver
