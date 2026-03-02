"""代码插件 - 弥娅代码分析能力实现

提供代码相关功能：
- 代码搜索
- 代码分析
- 代码生成
- 文档生成
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..plugin_base import BaseAgentPlugin, PluginMetadata

logger = logging.getLogger(__name__)


class CodePlugin(BaseAgentPlugin):
    """代码插件"""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="code",
            version="1.0.0",
            author="Miya",
            description="代码分析插件，支持代码搜索、分析和生成",
            category="code",
            capabilities=["code_search", "code_analysis", "code_generation", "doc_generation"],
            config={
                "max_file_size": 1024 * 1024,  # 1MB
                "supported_languages": ["python", "javascript", "typescript", "java", "cpp", "go"],
                "index_enabled": True
            }
        )

    async def register_tools(self):
        """注册工具"""
        self.register_tool(
            name="search_code",
            description="在项目中搜索代码",
            handler=self._search_code,
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "搜索模式（支持正则表达式）"
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "文件名模式（如 *.py）",
                        "default": "*"
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "上下文行数",
                        "default": 3
                    }
                },
                "required": ["pattern"]
            }
        )

        self.register_tool(
            name="analyze_code",
            description="分析代码文件的结构和复杂度",
            handler=self._analyze_code,
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "代码文件路径"
                    }
                },
                "required": ["file_path"]
            }
        )

        self.register_tool(
            name="generate_code",
            description="根据需求生成代码",
            handler=self._generate_code,
            parameters={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "代码需求描述"
                    },
                    "language": {
                        "type": "string",
                        "description": "编程语言",
                        "default": "python"
                    },
                    "framework": {
                        "type": "string",
                        "description": "框架（如 flask/django/fastapi）",
                        "default": ""
                    }
                },
                "required": ["description"]
            }
        )

    # ==================== 工具实现 ====================

    async def _search_code(
        self,
        pattern: str,
        file_pattern: str = "*",
        context_lines: int = 3
    ) -> Dict[str, Any]:
        """搜索代码"""
        try:
            logger.info(f"[Code] 搜索代码: {pattern} (文件: {file_pattern})")

            # 模拟代码搜索
            results = await self._simulate_code_search(pattern, file_pattern, context_lines)

            return {
                "pattern": pattern,
                "file_pattern": file_pattern,
                "context_lines": context_lines,
                "num_matches": len(results),
                "results": results
            }

        except Exception as e:
            logger.error(f"[Code] 代码搜索失败: {e}")
            raise Exception(f"代码搜索失败: {str(e)}")

    async def _analyze_code(self, file_path: str) -> Dict[str, Any]:
        """分析代码"""
        try:
            logger.info(f"[Code] 分析代码: {file_path}")

            # 检查文件存在
            path = Path(file_path)
            if not path.exists():
                raise Exception(f"文件不存在: {file_path}")

            # 读取文件
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # 简单分析
            lines = content.splitlines()
            analysis = {
                "file_path": file_path,
                "total_lines": len(lines),
                "total_chars": len(content),
                "language": self._detect_language(path),
                "functions": self._extract_functions(content),
                "classes": self._extract_classes(content),
                "imports": self._extract_imports(content),
                "complexity": self._calculate_complexity(content)
            }

            return analysis

        except Exception as e:
            logger.error(f"[Code] 代码分析失败: {e}")
            raise Exception(f"代码分析失败: {str(e)}")

    async def _generate_code(
        self,
        description: str,
        language: str = "python",
        framework: str = ""
    ) -> Dict[str, Any]:
        """生成代码"""
        try:
            logger.info(f"[Code] 生成代码: {description} (语言: {language}, 框架: {framework})")

            # 模拟代码生成
            code = await self._simulate_code_generation(description, language, framework)

            return {
                "description": description,
                "language": language,
                "framework": framework,
                "code": code,
                "warnings": []
            }

        except Exception as e:
            logger.error(f"[Code] 代码生成失败: {e}")
            raise Exception(f"代码生成失败: {str(e)}")

    # ==================== 辅助方法 ====================

    async def _simulate_code_search(
        self,
        pattern: str,
        file_pattern: str,
        context_lines: int
    ) -> List[Dict[str, Any]]:
        """模拟代码搜索"""
        await asyncio.sleep(0.3)

        # 模拟结果
        return [
            {
                "file": f"src/{file_pattern.replace('*', 'example')}_file.py",
                "line": 10,
                "match": pattern,
                "context": [
                    f"# 上下文行 {i}" for i in range(context_lines)
                ]
            }
        ]

    def _detect_language(self, path: Path) -> str:
        """检测编程语言"""
        ext = path.suffix.lower()

        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php"
        }

        return language_map.get(ext, "unknown")

    def _extract_functions(self, content: str) -> List[Dict[str, Any]]:
        """提取函数定义（简化实现）"""
        import re

        pattern = r'def\s+(\w+)\s*\((.*?)\):'
        matches = re.findall(pattern, content)

        functions = []
        for name, params in matches:
            functions.append({
                "name": name,
                "parameters": [p.strip() for p in params.split(',') if p.strip()],
                "line_number": content.find(f"def {name}") // 80 + 1  # 粗略估计
            })

        return functions

    def _extract_classes(self, content: str) -> List[Dict[str, Any]]:
        """提取类定义（简化实现）"""
        import re

        pattern = r'class\s+(\w+)\s*(?:\(.*?\))?:'
        matches = re.findall(pattern, content)

        classes = []
        for name in matches:
            classes.append({
                "name": name,
                "line_number": content.find(f"class {name}") // 80 + 1
            })

        return classes

    def _extract_imports(self, content: str) -> List[str]:
        """提取导入语句"""
        import re

        imports = []
        patterns = [
            r'import\s+([^\n]+)',
            r'from\s+([^\s]+)\s+import'
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content)
            imports.extend(matches)

        return list(set(imports))

    def _calculate_complexity(self, content: str) -> int:
        """计算圈复杂度（简化实现）"""
        # 简单计算：统计关键字数量
        keywords = ["if", "elif", "else", "for", "while", "try", "except", "and", "or"]
        complexity = 1  # 基础复杂度

        for keyword in keywords:
            complexity += content.count(f"{keyword} ")

        return complexity

    async def _simulate_code_generation(
        self,
        description: str,
        language: str,
        framework: str
    ) -> str:
        """模拟代码生成"""
        await asyncio.sleep(1.0)

        if language == "python":
            code = f'''# 自动生成的代码
# 描述: {description}

def main():
    """主函数"""
    print("Hello, World!")

if __name__ == "__main__":
    main()
'''
        else:
            code = f"// 自动生成的 {language} 代码\n// 描述: {description}\n\nconsole.log('Hello, World!');"

        return code


# 导出插件实例
_code_plugin_instance: Optional[CodePlugin] = None


def get_code_plugin() -> CodePlugin:
    """获取代码插件单例"""
    global _code_plugin_instance
    if _code_plugin_instance is None:
        _code_plugin_instance = CodePlugin()
    return _code_plugin_instance
