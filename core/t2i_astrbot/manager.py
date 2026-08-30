"""
AstrBot T2I Template Manager
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class TemplateManager:
    """
    T2I 模板管理器

    提供:
    - 模板CRUD操作
    - 内置和用户模板管理
    - 模板渲染
    """

    CORE_TEMPLATES = [
        "base",
        "default",
    ]

    def __init__(self, template_dir: Optional[str] = None):
        if template_dir:
            self.template_dir = Path(template_dir)
        else:
            self.template_dir = Path.home() / ".miya" / "t2i_templates"

        self.template_dir.mkdir(parents=True, exist_ok=True)
        self._initialize_templates()
        logger.info(f"[TemplateManager] 初始化完成: {self.template_dir}")

    def _initialize_templates(self):
        """初始化默认模板"""
        for name in self.CORE_TEMPLATES:
            template_path = self.template_dir / f"{name}.html"
            if not template_path.exists():
                default_content = self._get_default_template(name)
                template_path.write_text(default_content, encoding="utf-8")

    def _get_default_template(self, name: str) -> str:
        """获取默认模板内容"""
        if name == "base":
            return """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Image Generation</title>
</head>
<body>
    <div class="container">
        {{ content }}
    </div>
</body>
</html>"""
        else:
            return """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Generated Image</title>
</head>
<body>
    {{ content }}
</body>
</html>"""

    def list_templates(self) -> List[Dict[str, any]]:
        """列出所有可用模板"""
        templates = []
        for f in self.template_dir.glob("*.html"):
            name = f.stem
            templates.append(
                {
                    "name": name,
                    "path": str(f),
                    "is_default": name in self.CORE_TEMPLATES,
                }
            )
        return templates

    def get_template(self, name: str) -> Optional[str]:
        """获取模板内容"""
        template_path = self.template_dir / f"{name}.html"
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")
        return None

    def create_template(self, name: str, content: str) -> Dict[str, any]:
        """创建新模板"""
        try:
            template_path = self.template_dir / f"{name}.html"
            template_path.write_text(content, encoding="utf-8")
            return {"success": True, "name": name, "path": str(template_path)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_template(self, name: str, content: str) -> Dict[str, any]:
        """更新模板"""
        try:
            template_path = self.template_dir / f"{name}.html"
            if not template_path.exists():
                return {"success": False, "error": "模板不存在"}
            template_path.write_text(content, encoding="utf-8")
            return {"success": True, "name": name}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_template(self, name: str) -> Dict[str, any]:
        """删除模板"""
        try:
            if name in self.CORE_TEMPLATES:
                return {"success": False, "error": "不能删除内置模板"}

            template_path = self.template_dir / f"{name}.html"
            if template_path.exists():
                template_path.unlink()
                return {"success": True, "name": name}
            return {"success": False, "error": "模板不存在"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def render_template(self, name: str, context: Dict[str, any]) -> Optional[str]:
        """渲染模板"""
        template = self.get_template(name)
        if not template:
            return None

        try:
            rendered = template
            for key, value in context.items():
                placeholder = f"{{{{ {key} }}}}"
                rendered = rendered.replace(placeholder, str(value))
            return rendered
        except Exception as e:
            logger.error(f"[TemplateManager] 渲染失败: {e}")
            return None


_template_manager: Optional[TemplateManager] = None


def get_template_manager(template_dir: Optional[str] = None) -> TemplateManager:
    """获取全局TemplateManager实例"""
    global _template_manager
    if _template_manager is None:
        _template_manager = TemplateManager(template_dir)
    return _template_manager
