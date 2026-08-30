"""
弥娅系统常量替换辅助脚本

用于批量替换项目中的硬编码常量：
1. HTTP状态码 → HTTPStatus枚举
2. 编码常量 → Encoding.UTF8
3. 超时常量 → NetworkTimeout.*
"""
import os
import re
from pathlib import Path
from typing import List, Tuple


class ConstantReplacer:
    """常量替换器"""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.replacements: List[Tuple[str, str]] = []

        # HTTP状态码映射
        self.http_status_map = {
            "status=HTTPStatus.OK": "status=HTTPStatus.OK",
            "status_code == HTTPStatus.OK": "status_code == HTTPStatus.OK",
            "status=HTTPStatus.BAD_REQUEST": "status=HTTPStatus.BAD_REQUEST",
            "status=HTTPStatus.NOT_FOUND": "status=HTTPStatus.NOT_FOUND",
            "status=HTTPStatus.INTERNAL_ERROR": "status=HTTPStatus.INTERNAL_ERROR",
        }

        # 编码映射
        self.encoding_map = {
            "encoding=Encoding.UTF8": "encoding=Encoding.UTF8",
            'encoding=Encoding.UTF8': 'encoding=Encoding.UTF8',
            "encoding=Encoding.UTF8": "encoding=Encoding.UTF8",
            'encoding=Encoding.UTF8': 'encoding=Encoding.UTF8',
        }

        # 超时映射
        self.timeout_map = {
            "timeout=NetworkTimeout.WEBSOCKET_PING_INTERVAL": "timeout=NetworkTimeout.WEBSOCKET_PING_INTERVAL",
            "timeout=NetworkTimeout.API_REQUEST_TIMEOUT": "timeout=NetworkTimeout.API_REQUEST_TIMEOUT",
            "timeout=NetworkTimeout.REDIS_CONNECT_TIMEOUT": "timeout=NetworkTimeout.REDIS_CONNECT_TIMEOUT",
            "ping_timeout=NetworkTimeout.WEBSOCKET_PING_TIMEOUT": "ping_timeout=NetworkTimeout.WEBSOCKET_PING_TIMEOUT",
        }

    def add_http_import(self, file_path: Path) -> bool:
        """添加HTTPStatus导入到文件"""
        try:
            with open(file_path, 'r', encoding=Encoding.UTF8) as f:
                content = f.read()

            # 检查是否已导入
            if "from core.constants import" in content and "HTTPStatus" in content:
                return False

            # 查找导入位置
            lines = content.split('\n')
            insert_pos = 0

            # 找到最后一个导入语句
            for i, line in enumerate(lines):
                if line.startswith('import ') or line.startswith('from '):
                    insert_pos = i + 1

            # 检查是否已有其他core.constants导入
            has_core_constants = any('from core.constants' in line for line in lines)

            # 插入导入语句
            if has_core_constants:
                # 更新现有导入
                for i, line in enumerate(lines):
                    if 'from core.constants' in line:
                        lines[i] = line.rstrip() + ', HTTPStatus' if 'import' not in line else line
                        break
            else:
                lines.insert(insert_pos, "from core.constants import HTTPStatus")

            new_content = '\n'.join(lines)
            with open(file_path, 'w', encoding=Encoding.UTF8) as f:
                f.write(new_content)

            return True
        except Exception as e:
            print(f"处理导入失败 {file_path}: {e}")
            return False

    def add_encoding_import(self, file_path: Path) -> bool:
        """添加Encoding导入到文件"""
        try:
            with open(file_path, 'r', encoding=Encoding.UTF8) as f:
                content = f.read()

            # 检查是否已导入
            if "from core.constants import" in content and "Encoding" in content:
                return False

            lines = content.split('\n')
            insert_pos = 0

            for i, line in enumerate(lines):
                if line.startswith('import ') or line.startswith('from '):
                    insert_pos = i + 1

            has_core_constants = any('from core.constants' in line for line in lines)

            if has_core_constants:
                for i, line in enumerate(lines):
                    if 'from core.constants' in line:
                        lines[i] = line.rstrip() + ', Encoding' if 'import' not in line else line
                        break
            else:
                lines.insert(insert_pos, "from core.constants import Encoding")

            new_content = '\n'.join(lines)
            with open(file_path, 'w', encoding=Encoding.UTF8) as f:
                f.write(new_content)

            return True
        except Exception as e:
            print(f"处理导入失败 {file_path}: {e}")
            return False

    def add_timeout_import(self, file_path: Path) -> bool:
        """添加NetworkTimeout导入到文件"""
        try:
            with open(file_path, 'r', encoding=Encoding.UTF8) as f:
                content = f.read()

            if "from core.constants import" in content and "NetworkTimeout" in content:
                return False

            lines = content.split('\n')
            insert_pos = 0

            for i, line in enumerate(lines):
                if line.startswith('import ') or line.startswith('from '):
                    insert_pos = i + 1

            has_core_constants = any('from core.constants' in line for line in lines)

            if has_core_constants:
                for i, line in enumerate(lines):
                    if 'from core.constants' in line:
                        lines[i] = line.rstrip() + ', NetworkTimeout' if 'import' not in line else line
                        break
            else:
                lines.insert(insert_pos, "from core.constants import NetworkTimeout")

            new_content = '\n'.join(lines)
            with open(file_path, 'w', encoding=Encoding.UTF8) as f:
                f.write(new_content)

            return True
        except Exception as e:
            print(f"处理导入失败 {file_path}: {e}")
            return False

    def replace_in_file(self, file_path: Path, replacements: List[Tuple[str, str]]) -> int:
        """在文件中执行替换"""
        try:
            with open(file_path, 'r', encoding=Encoding.UTF8) as f:
                content = f.read()

            original_content = content
            count = 0

            for old, new in replacements:
                if old in content:
                    content = content.replace(old, new)
                    count += content.count(old) - original_content.count(old) if old != new else 0

            if content != original_content:
                with open(file_path, 'w', encoding=Encoding.UTF8) as f:
                    f.write(content)
                return count

            return 0
        except Exception as e:
            print(f"替换失败 {file_path}: {e}")
            return 0

    def replace_http_status_codes(self, exclude_dirs: List[str] = None) -> int:
        """替换HTTP状态码"""
        exclude_dirs = exclude_dirs or ['venv', '__pycache__', '.git']
        total = 0

        for file_path in self.project_root.rglob('*.py'):
            if any(excl in str(file_path) for excl in exclude_dirs):
                continue

            # 检查是否需要替换
            content = file_path.read_text(encoding=Encoding.UTF8)
            needs_import = any(old in content for old in self.http_status_map.keys())

            if needs_import:
                # 添加导入
                self.add_http_import(file_path)

                # 执行替换
                count = self.replace_in_file(file_path, list(self.http_status_map.items()))
                if count > 0:
                    print(f"✓ {file_path}: 替换 {count} 处HTTP状态码")
                    total += count

        return total

    def replace_encodings(self, exclude_dirs: List[str] = None) -> int:
        """替换编码常量"""
        exclude_dirs = exclude_dirs or ['venv', '__pycache__', '.git']
        total = 0

        for file_path in self.project_root.rglob('*.py'):
            if any(excl in str(file_path) for excl in exclude_dirs):
                continue

            content = file_path.read_text(encoding=Encoding.UTF8)
            needs_import = any(old in content for old in self.encoding_map.keys())

            if needs_import:
                self.add_encoding_import(file_path)
                count = self.replace_in_file(file_path, list(self.encoding_map.items()))
                if count > 0:
                    print(f"✓ {file_path}: 替换 {count} 处编码常量")
                    total += count

        return total

    def replace_timeouts(self, exclude_dirs: List[str] = None) -> int:
        """替换超时常量"""
        exclude_dirs = exclude_dirs or ['venv', '__pycache__', '.git']
        total = 0

        for file_path in self.project_root.rglob('*.py'):
            if any(excl in str(file_path) for excl in exclude_dirs):
                continue

            content = file_path.read_text(encoding=Encoding.UTF8)
            needs_import = any(old in content for old in self.timeout_map.keys())

            if needs_import:
                self.add_timeout_import(file_path)
                count = self.replace_in_file(file_path, list(self.timeout_map.items()))
                if count > 0:
                    print(f"✓ {file_path}: 替换 {count} 处超时常量")
                    total += count

        return total


def main():
    """主函数"""
    import sys

    # 获取项目根目录
    if len(sys.argv) > 1:
        project_root = sys.argv[1]
    else:
        project_root = Path(__file__).parent.parent

    print(f"项目根目录: {project_root}")
    print("-" * 60)

    replacer = ConstantReplacer(project_root)

    # 替换HTTP状态码
    print("\n[1/3] 替换HTTP状态码...")
    http_count = replacer.replace_http_status_codes()
    print(f"HTTP状态码替换完成: {http_count} 处")

    # 替换编码常量
    print("\n[2/3] 替换编码常量...")
    encoding_count = replacer.replace_encodings()
    print(f"编码常量替换完成: {encoding_count} 处")

    # 替换超时常量
    print("\n[3/3] 替换超时常量...")
    timeout_count = replacer.replace_timeouts()
    print(f"超时常量替换完成: {timeout_count} 处")

    print("-" * 60)
    print(f"总计: {http_count + encoding_count + timeout_count} 处替换")
    print("\n⚠️  请检查修改后的代码并运行测试")


if __name__ == '__main__':
    main()
