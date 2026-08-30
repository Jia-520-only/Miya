"""
AstrBot T2I 图生图模板系统

提供图像生成模板管理能力
- 模板CRUD操作
- 内置模板和用户模板
- 模板渲染
"""

from .manager import TemplateManager, get_template_manager

__all__ = [
    "TemplateManager",
    "get_template_manager",
]
