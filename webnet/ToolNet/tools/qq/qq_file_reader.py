"""
QQ文件读取工具

支持读取和分析QQ文件内容，包括TXT、PDF、DOCX等格式
"""

import logging
import mimetypes
import os
import traceback
from typing import Any, Dict

import chardet

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)


class QQFileReaderTool(BaseTool):
    """QQ文件读取工具"""

    # 支持的文件类型
    SUPPORTED_FILE_TYPES = {
        # 文本文件
        ".txt": "文本文件",
        ".log": "日志文件",
        ".md": "Markdown文档",
        ".json": "JSON文件",
        ".xml": "XML文件",
        ".html": "HTML文件",
        ".htm": "HTML文件",
        ".csv": "CSV文件",
        ".yml": "YAML文件",
        ".yaml": "YAML文件",
        ".ini": "配置文件",
        ".cfg": "配置文件",
        ".conf": "配置文件",
        # 文档文件
        ".pdf": "PDF文档",
        ".doc": "Word文档",
        ".docx": "Word文档",
        # 代码文件
        ".py": "Python代码",
        ".js": "JavaScript代码",
        ".ts": "TypeScript代码",
        ".java": "Java代码",
        ".cpp": "C++代码",
        ".c": "C代码",
        ".go": "Go代码",
        ".rs": "Rust代码",
        ".php": "PHP代码",
        ".rb": "Ruby代码",
        ".sh": "Shell脚本",
        ".bat": "批处理文件",
        ".ps1": "PowerShell脚本",
    }

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "qq_file_reader",
            "description": "读取和分析QQ文件内容。支持TXT、PDF、DOCX等格式。当用户发送文件并询问内容时，自动调用此工具。可以提取文本、统计信息、分析结构等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "操作类型：read(读取内容)、analyze(分析)、summary(摘要)、search(搜索)、info(信息)",
                        "enum": ["read", "analyze", "summary", "search", "info"],
                        "default": "read",
                    },
                    "file_path": {"type": "string", "description": "文件路径（如果通过QQ发送的文件，系统会自动提供）"},
                    "max_length": {
                        "type": "integer",
                        "description": "最大读取长度（字符数）",
                        "minimum": 100,
                        "maximum": 10000,
                        "default": 2000,
                    },
                    "search_keyword": {"type": "string", "description": "搜索关键词（仅当action=search时使用）"},
                    "include_statistics": {"type": "boolean", "description": "是否包含统计信息", "default": True},
                    "encoding": {
                        "type": "string",
                        "description": "文本文件编码（自动检测，可手动指定）",
                        "enum": ["auto", "utf-8", "gbk", "gb2312", "ascii", "latin-1"],
                    },
                },
                "required": ["file_path"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行文件读取"""
        try:
            action = args.get("action", "read")
            file_path = args.get("file_path", "")
            max_length = args.get("max_length", 2000)
            search_keyword = args.get("search_keyword", "")
            include_statistics = args.get("include_statistics", True)
            encoding = args.get("encoding", "auto")

            if not file_path:
                # 尝试从上下文获取
                if hasattr(context, "file_path") and context.file_path:
                    file_path = context.file_path
                else:
                    return "❌ 请提供文件路径，或通过QQ发送文件"

            # 检查文件是否存在
            if not os.path.exists(file_path):
                return f"❌ 文件不存在: {file_path}"

            # 检查文件类型
            file_ext = self._get_file_extension(file_path)
            file_type = self.SUPPORTED_FILE_TYPES.get(file_ext.lower(), "未知类型")

            logger.info(f"处理文件: {file_path} ({file_type}, {os.path.getsize(file_path)} bytes)")

            # 根据操作类型处理
            if action == "read":
                return await self._read_file_content(file_path, file_ext, max_length, encoding, include_statistics)
            elif action == "analyze":
                return await self._analyze_file(file_path, file_ext)
            elif action == "summary":
                return await self._file_summary(file_path, file_ext, max_length)
            elif action == "search":
                if not search_keyword:
                    return "❌ 搜索操作需要提供 search_keyword 参数"
                return await self._search_in_file(file_path, file_ext, search_keyword)
            elif action == "info":
                return self._file_info(file_path, file_ext)
            else:
                return f"❌ 不支持的操作类型: {action}"

        except Exception as e:
            logger.error(f"文件读取失败: {e}", exc_info=True)
            return f"❌ 文件读取失败: {str(e)}\n{traceback.format_exc()[:500]}"

    def _get_file_extension(self, file_path: str) -> str:
        """获取文件扩展名"""
        return os.path.splitext(file_path)[1].lower()

    def _file_info(self, file_path: str, file_ext: str) -> str:
        """获取文件基本信息"""
        try:
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
            file_type = self.SUPPORTED_FILE_TYPES.get(file_ext, "未知类型")

            # 获取创建和修改时间
            import datetime

            create_time = datetime.datetime.fromtimestamp(os.path.getctime(file_path))
            modify_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))

            # 获取MIME类型
            mime_type, _ = mimetypes.guess_type(file_path)

            info = "📄 **文件信息**\n"
            info += f"文件名: {file_name}\n"
            info += f"类型: {file_type} ({file_ext})\n"
            info += f"MIME类型: {mime_type or '未知'}\n"
            info += f"大小: {file_size:,} 字节 ({self._format_file_size(file_size)})\n"
            info += f"路径: {file_path}\n"
            info += f"创建时间: {create_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            info += f"修改时间: {modify_time.strftime('%Y-%m-%d %H:%M:%S')}\n"

            return info

        except Exception as e:
            return f"❌ 获取文件信息失败: {str(e)}"

    async def _read_file_content(
        self, file_path: str, file_ext: str, max_length: int, encoding: str, include_statistics: bool
    ) -> str:
        """读取文件内容"""
        try:
            # 根据文件类型读取
            if file_ext in [
                ".txt",
                ".log",
                ".md",
                ".json",
                ".xml",
                ".html",
                ".htm",
                ".csv",
                ".yml",
                ".yaml",
                ".ini",
                ".cfg",
                ".conf",
            ]:
                content = await self._read_text_file(file_path, encoding)
                response = await self._process_text_content(content, file_path, max_length, include_statistics)

            elif file_ext in [".pdf", ".doc", ".docx"]:
                content = await self._read_document_file(file_path)
                response = await self._process_document_content(content, file_path, max_length)

            elif file_ext in [
                ".py",
                ".js",
                ".ts",
                ".java",
                ".cpp",
                ".c",
                ".go",
                ".rs",
                ".php",
                ".rb",
                ".sh",
                ".bat",
                ".ps1",
            ]:
                content = await self._read_text_file(file_path, encoding)
                response = await self._process_code_content(content, file_path, file_ext, max_length)

            else:
                # 尝试作为文本文件读取
                try:
                    content = await self._read_text_file(file_path, encoding)
                    response = await self._process_text_content(content, file_path, max_length, include_statistics)
                except:
                    return f"❌ 不支持的文件类型: {file_ext}\n支持的类型: {', '.join(self.SUPPORTED_FILE_TYPES.keys())}"

            return response

        except Exception as e:
            logger.error(f"读取文件内容失败: {e}")
            return f"❌ 读取文件内容失败: {str(e)}"

    async def _read_text_file(self, file_path: str, encoding: str = "auto") -> str:
        """读取文本文件"""
        try:
            # 检测文件编码
            if encoding == "auto":
                with open(file_path, "rb") as f:
                    raw_data = f.read(1024 * 10)  # 读取前10KB用于检测
                    detected = chardet.detect(raw_data)
                    encoding = detected.get("encoding", "utf-8")
                    confidence = detected.get("confidence", 0)

                    if confidence < 0.7:
                        encoding = "utf-8"  # 默认使用UTF-8

            # 读取文件
            with open(file_path, "r", encoding=encoding, errors="replace") as f:
                return f.read()

        except UnicodeDecodeError as e:
            # 尝试其他编码
            for enc in ["utf-8", "gbk", "gb2312", "latin-1", "ascii"]:
                try:
                    with open(file_path, "r", encoding=enc, errors="replace") as f:
                        return f.read()
                except:
                    continue
            raise Exception(f"无法解码文件，尝试的编码都失败: {str(e)}")
        except Exception as e:
            raise Exception(f"读取文本文件失败: {str(e)}")

    async def _read_document_file(self, file_path: str) -> Dict[str, Any]:
        """读取文档文件（PDF/DOCX）"""
        try:
            # 尝试导入现有的PDF处理器
            from webnet.ToolNet.tools.office.pdf_docx_processor import PDFDocxProcessor

            processor = PDFDocxProcessor()
            doc_data = processor.load_file(file_path)

            if not doc_data:
                raise Exception("PDF/DOCX处理器无法加载文件")

            return doc_data

        except ImportError as e:
            logger.warning(f"PDF/DOCX处理器不可用: {e}")
            raise Exception("PDF/DOCX处理器不可用，请确保已安装相关依赖")
        except Exception as e:
            logger.error(f"读取文档文件失败: {e}")
            raise Exception(f"读取文档文件失败: {str(e)}")

    async def _process_text_content(
        self, content: str, file_path: str, max_length: int, include_statistics: bool
    ) -> str:
        """处理文本内容"""
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        response = f"📄 **文件内容** - {file_name}\n"
        response += f"大小: {self._format_file_size(file_size)}\n"

        if include_statistics:
            stats = self._calculate_text_statistics(content)
            response += f"字符数: {stats['char_count']:,}\n"
            response += f"行数: {stats['line_count']:,}\n"
            response += f"单词数: {stats['word_count']:,}\n"

        response += "\n--- 内容预览 ---\n"

        # 截取内容
        if len(content) > max_length:
            preview = content[:max_length]
            remaining = len(content) - max_length
            response += f"{preview}\n...（还有 {remaining:,} 个字符）"
        else:
            response += content

        return response

    async def _process_document_content(self, doc_data: Dict[str, Any], file_path: str, max_length: int) -> str:
        """处理文档内容"""
        file_name = os.path.basename(file_path)
        file_type = doc_data.get("文件类型", "未知")

        response = f"📄 **文档内容** - {file_name}\n"
        response += f"类型: {file_type}\n"

        if file_type == "PDF":
            page_count = doc_data.get("总页数", 0)
            response += f"页数: {page_count}\n"
        elif file_type == "Word":
            para_count = doc_data.get("总段落数", 0)
            table_count = doc_data.get("总表格数", 0)
            response += f"段落数: {para_count}\n"
            response += f"表格数: {table_count}\n"

        full_text = doc_data.get("完整文本", "")
        char_count = len(full_text)
        response += f"字符数: {char_count:,}\n"

        response += "\n--- 内容预览 ---\n"

        # 截取内容
        if len(full_text) > max_length:
            preview = full_text[:max_length]
            remaining = len(full_text) - max_length
            response += f"{preview}\n...（还有 {remaining:,} 个字符）"
        else:
            response += full_text

        return response

    async def _process_code_content(self, content: str, file_path: str, file_ext: str, max_length: int) -> str:
        """处理代码内容"""
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        language = self._get_language_name(file_ext)

        response = f"💻 **代码文件** - {file_name}\n"
        response += f"语言: {language}\n"
        response += f"大小: {self._format_file_size(file_size)}\n"

        # 代码统计
        lines = content.split("\n")
        line_count = len(lines)
        len(content)

        # 统计空行和注释行
        empty_lines = 0
        comment_lines = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                empty_lines += 1
            elif stripped.startswith(("#", "//", "/*", "*", "*/")) or "#" in stripped:
                comment_lines += 1

        response += f"总行数: {line_count:,}\n"
        response += f"代码行: {line_count - empty_lines - comment_lines:,}\n"
        response += f"空行: {empty_lines:,}\n"
        response += f"注释行: {comment_lines:,}\n"

        response += f"\n--- 代码预览 ---\n```{self._get_code_language(file_ext)}\n"

        # 截取内容
        if len(content) > max_length:
            preview = content[:max_length]
            remaining = len(content) - max_length
            response += f"{preview}\n...（还有 {remaining:,} 个字符）"
        else:
            response += content

        response += "\n```"

        return response

    async def _analyze_file(self, file_path: str, file_ext: str) -> str:
        """分析文件"""
        try:
            if file_ext in [".pdf", ".doc", ".docx"]:
                # 使用PDF处理器进行深度分析
                from webnet.ToolNet.tools.office.pdf_docx_processor import PDFDocxProcessor

                processor = PDFDocxProcessor()
                analysis = processor.analyze_document(file_path)

                if analysis.get("success"):
                    analysis_data = analysis.get("analysis", {})

                    response = f"📊 **文档深度分析** - {os.path.basename(file_path)}\n"

                    # 文件信息
                    file_info = analysis_data.get("文件信息", {})
                    response += f"类型: {file_info.get('文件类型', '未知')}\n"

                    if file_info.get("文件类型") == "PDF":
                        response += f"页数: {file_info.get('总页数', 0)}\n"
                    elif file_info.get("文件类型") == "Word":
                        response += f"段落数: {file_info.get('总段落数', 0)}\n"
                        response += f"表格数: {file_info.get('总表格数', 0)}\n"

                    # 文本统计
                    text_stats = analysis_data.get("文本统计", {})
                    response += f"总字符数: {text_stats.get('总字符数', 0):,}\n"
                    response += f"总行数: {text_stats.get('总行数', 0):,}\n"
                    response += f"平均句长: {text_stats.get('平均句长', 0):.1f}\n"
                    response += f"中文比例: {text_stats.get('中文比例', 0):.1f}%\n"

                    # 关键词提取
                    keywords = analysis_data.get("关键词提取", [])
                    if keywords:
                        response += "\n🔑 **关键词 Top 10:**\n"
                        for i, kw in enumerate(keywords[:10]):
                            response += f"{i + 1}. {kw.get('关键词', '')} ({kw.get('频次', 0)}次)\n"

                    return response
                else:
                    return f"❌ 文档分析失败: {analysis.get('error', '未知错误')}"

            else:
                # 对文本文件进行基本分析
                content = await self._read_text_file(file_path, "auto")

                response = f"📊 **文件分析** - {os.path.basename(file_path)}\n"

                stats = self._calculate_text_statistics(content)
                response += f"字符数: {stats['char_count']:,}\n"
                response += f"行数: {stats['line_count']:,}\n"
                response += f"单词数: {stats['word_count']:,}\n"
                response += f"平均行长度: {stats['avg_line_length']:.1f}\n"

                # 检测可能的编码问题
                encoding_info = self._detect_encoding_info(content[:5000])
                if encoding_info:
                    response += f"编码检测: {encoding_info}\n"

                return response

        except Exception as e:
            logger.error(f"文件分析失败: {e}")
            return f"❌ 文件分析失败: {str(e)}"

    async def _file_summary(self, file_path: str, file_ext: str, max_length: int) -> str:
        """生成文件摘要"""
        try:
            if file_ext in [".txt", ".log", ".md"]:
                content = await self._read_text_file(file_path, "auto")
                summary = self._generate_text_summary(content, max_length)

                response = f"📋 **文件摘要** - {os.path.basename(file_path)}\n"
                response += f"大小: {self._format_file_size(os.path.getsize(file_path))}\n"
                response += f"字符数: {len(content):,}\n"
                response += f"\n{summary}"

                return response

            elif file_ext in [".pdf", ".doc", ".docx"]:
                doc_data = await self._read_document_file(file_path)
                full_text = doc_data.get("完整文本", "")

                # 生成摘要（简单实现：取前几段）
                paragraphs = full_text.split("\n\n")
                summary_paragraphs = paragraphs[:3]  # 取前3段
                summary = "\n\n".join(summary_paragraphs)

                if len(summary) > max_length:
                    summary = summary[:max_length] + "..."

                response = f"📋 **文档摘要** - {os.path.basename(file_path)}\n"
                response += f"类型: {doc_data.get('文件类型', '未知')}\n"

                if doc_data.get("文件类型") == "PDF":
                    response += f"页数: {doc_data.get('总页数', 0)}\n"
                elif doc_data.get("文件类型") == "Word":
                    response += f"段落数: {doc_data.get('总段落数', 0)}\n"

                response += f"字符数: {len(full_text):,}\n"
                response += f"\n{summary}"

                return response

            else:
                return await self._read_file_content(file_path, file_ext, max_length, "auto", True)

        except Exception as e:
            logger.error(f"生成文件摘要失败: {e}")
            return f"❌ 生成文件摘要失败: {str(e)}"

    async def _search_in_file(self, file_path: str, file_ext: str, keyword: str) -> str:
        """在文件中搜索关键词"""
        try:
            if file_ext in [".pdf", ".doc", ".docx"]:
                # 使用PDF处理器搜索
                from webnet.ToolNet.tools.office.pdf_docx_processor import PDFDocxProcessor

                processor = PDFDocxProcessor()
                search_results = processor.search_in_document(file_path, keyword)

                response = f"🔍 **搜索 '{keyword}'** - {os.path.basename(file_path)}\n"
                response += f"找到 {len(search_results)} 处匹配\n\n"

                for i, result in enumerate(search_results[:5]):  # 最多显示5个结果
                    context = result.get("上下文", "")
                    response += f"{i + 1}. {context}\n\n"

                if len(search_results) > 5:
                    response += f"... 还有 {len(search_results) - 5} 个结果未显示\n"

                return response

            else:
                # 在文本文件中搜索
                content = await self._read_text_file(file_path, "auto")

                # 简单的字符串搜索
                positions = []
                start = 0

                while True:
                    pos = content.find(keyword, start)
                    if pos == -1:
                        break

                    # 获取上下文
                    context_start = max(0, pos - 50)
                    context_end = min(len(content), pos + len(keyword) + 50)
                    context = content[context_start:context_end]

                    positions.append({"position": pos, "context": context})

                    start = pos + 1

                response = f"🔍 **搜索 '{keyword}'** - {os.path.basename(file_path)}\n"
                response += f"找到 {len(positions)} 处匹配\n\n"

                for i, pos_info in enumerate(positions[:5]):  # 最多显示5个结果
                    context = pos_info.get("context", "")
                    response += f"{i + 1}. ...{context}...\n\n"

                if len(positions) > 5:
                    response += f"... 还有 {len(positions) - 5} 个结果未显示\n"

                return response

        except Exception as e:
            logger.error(f"文件搜索失败: {e}")
            return f"❌ 文件搜索失败: {str(e)}"

    def _calculate_text_statistics(self, text: str) -> Dict[str, Any]:
        """计算文本统计信息"""
        lines = text.split("\n")
        words = text.split()

        total_chars = len(text)
        total_lines = len(lines)
        total_words = len(words)

        # 计算平均行长度
        avg_line_length = sum(len(line) for line in lines) / total_lines if total_lines > 0 else 0

        return {
            "char_count": total_chars,
            "line_count": total_lines,
            "word_count": total_words,
            "avg_line_length": avg_line_length,
        }

    def _generate_text_summary(self, text: str, max_length: int = 500) -> str:
        """生成文本摘要"""
        # 简单实现：取前几段
        paragraphs = text.split("\n\n")

        summary_parts = []
        total_length = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if total_length + len(para) <= max_length:
                summary_parts.append(para)
                total_length += len(para)
            else:
                # 如果段落太长，截取一部分
                remaining = max_length - total_length
                if remaining > 50:  # 至少保留50字符
                    summary_parts.append(para[:remaining] + "...")
                break

        summary = "\n\n".join(summary_parts)

        if len(summary) < len(text):
            summary += f"\n\n[摘要生成，完整内容 {len(text):,} 字符]"

        return summary

    def _detect_encoding_info(self, sample: str) -> str:
        """检测编码信息"""
        try:
            import chardet

            if isinstance(sample, str):
                sample = sample.encode("utf-8", errors="replace")

            result = chardet.detect(sample[:4096])  # 检测前4KB

            encoding = result.get("encoding", "unknown")
            confidence = result.get("confidence", 0) * 100

            if confidence > 50:
                return f"{encoding} ({confidence:.1f}% 置信度)"
            else:
                return "编码检测置信度低"
        except:
            return "编码检测失败"

    def _format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def _get_language_name(self, file_ext: str) -> str:
        """根据文件扩展名获取语言名称"""
        language_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".java": "Java",
            ".cpp": "C++",
            ".c": "C",
            ".go": "Go",
            ".rs": "Rust",
            ".php": "PHP",
            ".rb": "Ruby",
            ".sh": "Shell",
            ".bat": "Batch",
            ".ps1": "PowerShell",
        }
        return language_map.get(file_ext, "未知语言")

    def _get_code_language(self, file_ext: str) -> str:
        """获取代码高亮语言"""
        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".go": "go",
            ".rs": "rust",
            ".php": "php",
            ".rb": "ruby",
            ".sh": "bash",
            ".bat": "batch",
            ".ps1": "powershell",
            ".json": "json",
            ".xml": "xml",
            ".html": "html",
            ".htm": "html",
            ".css": "css",
            ".md": "markdown",
        }
        return language_map.get(file_ext, "text")
