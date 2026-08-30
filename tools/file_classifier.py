"""
智能文件分类器 - 弥娅核心模块
支持自动整理下载文件夹
"""

import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import hashlib
import logging

logger = logging.getLogger(__name__)


class FileClassifier:
    """智能文件分类器"""

    def __init__(self):
        # 文件分类规则
        self.classification_rules = {
            # 文档类
            "文档": {
                "extensions": ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt', '.md'],
                "keywords": ['文档', '报告', '论文', '资料', 'manual', 'guide'],
                "folder": "📄 文档"
            },
            # 图片类
            "图片": {
                "extensions": ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico'],
                "keywords": ['截图', '图片', '照片', 'image', 'screenshot'],
                "folder": "🖼️ 图片"
            },
            # 视频类
            "视频": {
                "extensions": ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'],
                "keywords": ['视频', 'movie', 'film'],
                "folder": "🎬 视频"
            },
            # 音频类
            "音频": {
                "extensions": ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma'],
                "keywords": ['音频', '音乐', 'audio', 'music', 'sound'],
                "folder": "🎵 音频"
            },
            # 压缩包类
            "压缩包": {
                "extensions": ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2'],
                "keywords": ['压缩', 'archive', 'package'],
                "folder": "📦 压缩包"
            },
            # 办公软件类
            "办公软件": {
                "extensions": ['.xlsx', '.xls', '.csv', '.ppt', '.pptx', '.pps', '.ppsx'],
                "keywords": ['表格', '演示', 'excel', 'powerpoint', 'slides'],
                "folder": "📊 办公"
            },
            # 代码类
            "代码": {
                "extensions": ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.html', '.css', '.json', '.xml', '.sql'],
                "keywords": ['代码', 'source', '项目', 'project'],
                "folder": "💻 代码"
            },
            # 可执行文件类
            "程序": {
                "extensions": ['.exe', '.msi', '.app', '.dmg', '.deb', '.rpm'],
                "keywords": ['安装', 'setup', 'install', 'program'],
                "folder": "⚙️ 程序"
            },
            # 电子书类
            "电子书": {
                "extensions": ['.epub', '.mobi', '.azw', '.azw3', '.djvu'],
                "keywords": ['书籍', '电子书', 'ebook', 'novel'],
                "folder": "📚 电子书"
            },
            # 字体类
            "字体": {
                "extensions": ['.ttf', '.otf', '.woff', '.woff2', '.eot'],
                "keywords": ['字体', 'font'],
                "folder": "🔤 字体"
            },
            # 安装包类
            "安装包": {
                "extensions": ['.apk', '.ipa', '.deb', '.rpm'],
                "keywords": ['安装包', 'app'],
                "folder": "📱 应用"
            }
        }

    def classify_file(self, file_path: str) -> Dict[str, Any]:
        """
        分类单个文件

        Args:
            file_path: 文件路径

        Returns:
            分类结果
        """
        path = Path(file_path)
        file_name = path.stem.lower()
        file_ext = path.suffix.lower()

        # 优先级1: 扩展名匹配
        for category, rule in self.classification_rules.items():
            if file_ext in rule["extensions"]:
                return {
                    "文件": file_path,
                    "分类": category,
                    "目标文件夹": rule["folder"],
                    "匹配方式": "扩展名"
                }

        # 优先级2: 文件名关键词匹配
        for category, rule in self.classification_rules.items():
            for keyword in rule["keywords"]:
                if keyword in file_name:
                    return {
                        "文件": file_path,
                        "分类": category,
                        "目标文件夹": rule["folder"],
                        "匹配方式": "关键词"
                    }

        # 默认分类
        return {
            "文件": file_path,
            "分类": "其他",
            "目标文件夹": "📁 其他",
            "匹配方式": "默认"
        }

    def organize_directory(
        self,
        source_dir: str,
        target_dir: str,
        mode: str = "move"
    ) -> Dict[str, Any]:
        """
        整理目录

        Args:
            source_dir: 源目录
            target_dir: 目标目录
            mode: 处理模式 ("move"=移动, "copy"=复制, "report_only"=仅报告)

        Returns:
            整理结果
        """
        source_path = Path(source_dir)
        target_path = Path(target_dir)

        if not source_path.exists():
            return {"error": "源目录不存在"}

        # 创建目标目录
        target_path.mkdir(parents=True, exist_ok=True)

        # 扫描文件
        all_files = []
        for item in source_path.rglob('*'):
            if item.is_file():
                all_files.append(item)

        logger.info(f"扫描到 {len(all_files)} 个文件")

        # 分类并处理文件
        results = {
            "总文件数": len(all_files),
            "已处理": 0,
            "分类统计": {},
            "文件列表": [],
            "错误": []
        }

        for file_path in all_files:
            try:
                # 跳过目标目录中的文件
                if target_path in file_path.parents:
                    continue

                # 分类文件
                classification = self.classify_file(str(file_path))
                target_folder = classification["目标文件夹"]
                category = classification["分类"]

                # 更新统计
                if category not in results["分类统计"]:
                    results["分类统计"][category] = 0
                results["分类统计"][category] += 1

                # 构建目标路径
                relative_path = file_path.relative_to(source_path)
                destination = target_path / target_folder[2:] / relative_path  # 移除emoji
                destination.parent.mkdir(parents=True, exist_ok=True)

                # 处理文件
                if mode == "move":
                    shutil.move(str(file_path), str(destination))
                    logger.info(f"移动: {file_path.name} → {target_folder}/{relative_path.parent}")
                elif mode == "copy":
                    shutil.copy2(str(file_path), str(destination))
                    logger.info(f"复制: {file_path.name} → {target_folder}/{relative_path.parent}")

                results["已处理"] += 1
                results["文件列表"].append({
                    "源文件": str(file_path),
                    "目标位置": str(destination),
                    "分类": category
                })

            except Exception as e:
                error_msg = f"处理文件失败 {file_path.name}: {e}"
                logger.error(error_msg)
                results["错误"].append(error_msg)

        return results

    def generate_report(
        self,
        organization_results: Dict[str, Any],
        report_path: str
    ) -> bool:
        """
        生成整理报告

        Args:
            organization_results: 整理结果
            report_path: 报告输出路径

        Returns:
            是否成功
        """
        stats = organization_results.get("分类统计", {})
        total = organization_results.get("总文件数", 0)
        processed = organization_results.get("已处理", 0)

        # 计算分类覆盖率
        categorized = sum(stats.values())
        uncategorized = total - categorized
        success_rate = (categorized / total * 100) if total > 0 else 0

        # 生成报告
        report = f"""# 文件整理报告

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 📊 统计摘要

| 项目 | 数值 |
|------|------|
| 扫描文件总数 | {total} |
| 已处理文件数 | {processed} |
| 已分类文件数 | {categorized} |
| 未分类文件数 | {uncategorized} |
| 分类成功率 | {success_rate}% |

## 📁 分类详情

"""

        # 按文件数排序
        sorted_categories = sorted(stats.items(), key=lambda x: x[1], reverse=True)

        for category, count in sorted_categories:
            percentage = (count / total * 100) if total > 0 else 0
            # 查找对应文件夹
            folder_name = ""
            for cat_name, rule in self.classification_rules.items():
                if cat_name == category:
                    folder_name = rule["folder"]
                    break

            report += f"""
### {category} - {count}个 ({percentage:.1f}%)
**目标文件夹**: {folder_name}

---

"""

        # 添加错误信息
        errors = organization_results.get("错误", [])
        if errors:
            report += "\n## ⚠️ 错误日志\n\n"
            for error in errors:
                report += f"- {error}\n"

        # 保存报告
        try:
            Path(report_path).parent.mkdir(parents=True, exist_ok=True)
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report)

            logger.info(f"整理报告已保存: {report_path}")
            return True

        except Exception as e:
            logger.error(f"生成报告失败: {e}")
            return False

    def find_duplicates(
        self,
        directory: str,
        method: str = "hash"
    ) -> List[Dict[str, Any]]:
        """
        查找重复文件

        Args:
            directory: 目录路径
            method: 比较方法 ("hash", "name", "size")

        Returns:
            重复文件列表
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            return []

        file_info = []
        for file_path in dir_path.rglob('*'):
            if file_path.is_file():
                file_info.append(file_path)

        logger.info(f"扫描 {len(file_info)} 个文件查找重复")

        duplicates = []

        if method == "hash":
            # 使用文件哈希查找重复
            hash_map = {}

            for file_path in file_info:
                try:
                    file_hash = self._calculate_file_hash(file_path)

                    if file_hash in hash_map:
                        duplicates.append({
                            "原始文件": str(hash_map[file_hash]),
                            "重复文件": str(file_path),
                            "哈希值": file_hash
                        })
                    else:
                        hash_map[file_hash] = file_path

                except Exception as e:
                    logger.error(f"计算哈希失败 {file_path.name}: {e}")

        elif method == "name":
            # 按文件名查找重复
            name_map = {}

            for file_path in file_info:
                name = file_path.stem.lower()

                if name in name_map:
                    duplicates.append({
                        "原始文件": str(name_map[name]),
                        "重复文件": str(file_path),
                        "文件名": file_path.name
                    })
                else:
                    name_map[name] = file_path

        elif method == "size":
            # 按文件大小查找重复
            size_map = {}

            for file_path in file_info:
                size = file_path.stat().st_size

                if size in size_map:
                    duplicates.append({
                        "原始文件": str(size_map[size]),
                        "重复文件": str(file_path),
                        "文件大小": f"{size/1024/1024:.2f}MB"
                    })
                else:
                    size_map[size] = file_path

        logger.info(f"找到 {len(duplicates)} 个重复文件")
        return duplicates

    def _calculate_file_hash(self, file_path: Path) -> str:
        """计算文件哈希值"""
        hash_md5 = hashlib.md5()

        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_md5.update(chunk)

        return hash_md5.hexdigest()

    def clean_empty_folders(self, directory: str) -> List[str]:
        """
        清理空文件夹

        Args:
            directory: 目录路径

        Returns:
            清理的文件夹列表
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            return []

        cleaned = []

        # 从下往上查找空文件夹
        for folder in sorted(dir_path.rglob('*'), reverse=True):
            if folder.is_dir():
                # 检查是否为空
                contents = list(folder.glob('*'))
                if not contents:
                    # 删除空文件夹
                    folder.rmdir()
                    cleaned.append(str(folder))
                    logger.info(f"删除空文件夹: {folder}")

        logger.info(f"清理了 {len(cleaned)} 个空文件夹")
        return cleaned


def classify_files_command(
    source_dir: str,
    target_dir: str,
    operations: List[str]
) -> Dict[str, Any]:
    """
    文件分类的统一接口

    Args:
        source_dir: 源目录
        target_dir: 目标目录
        operations: 操作列表 ["organize", "find_duplicates", "clean_empty", "report"]

    Returns:
        处理结果
    """
    classifier = FileClassifier()
    results = {
        "操作": [],
        "结果": {}
    }

    for op in operations:
        if op == "organize":
            result = classifier.organize_directory(source_dir, target_dir, mode="copy")
            results["结果"]["整理"] = result
            results["操作"].append("整理文件")

        elif op == "find_duplicates":
            duplicates = classifier.find_duplicates(source_dir, method="hash")
            results["结果"]["重复文件"] = duplicates
            results["操作"].append(f"查找重复: 找到 {len(duplicates)} 个")

        elif op == "clean_empty":
            cleaned = classifier.clean_empty_folders(source_dir)
            results["结果"]["清理空文件夹"] = cleaned
            results["操作"].append(f"清理空文件夹: {len(cleaned)} 个")

        elif op == "report":
            if "整理" in results["结果"]:
                report_path = f"{target_dir}/整理报告.md"
                classifier.generate_report(results["结果"]["整理"], report_path)
                results["操作"].append(f"生成报告: {report_path}")

    return results
