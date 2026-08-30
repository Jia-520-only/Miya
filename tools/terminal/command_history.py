"""
命令历史模块
记录和查询命令执行历史
"""
import json
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class CommandHistory:
    """命令历史记录器"""

    def __init__(self, max_entries: int = 1000, storage_path: Optional[str] = None):
        """
        初始化命令历史

        Args:
            max_entries: 最大记录数
            storage_path: 存储文件路径
        """
        self.max_entries = max_entries

        # 设置存储路径
        if storage_path is None:
            project_root = Path(__file__).parent.parent.parent
            logs_dir = project_root / 'logs'
            logs_dir.mkdir(exist_ok=True)
            storage_path = logs_dir / 'terminal_history.json'

        self.storage_path = storage_path
        self.history: List[Dict[str, Any]] = []

        # 加载历史记录
        self._load()

        logger.info(f"命令历史初始化完成，当前记录数: {len(self.history)}")

    def _load(self) -> None:
        """从文件加载历史记录"""
        if not os.path.exists(self.storage_path):
            self.history = []
            return

        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                self.history = json.load(f)
            logger.info(f"加载了 {len(self.history)} 条历史记录")
        except Exception as e:
            logger.warning(f"加载历史记录失败: {e}")
            self.history = []

    def _save(self) -> None:
        """保存历史记录到文件"""
        try:
            # 只保留最近的记录
            if len(self.history) > self.max_entries:
                self.history = self.history[-self.max_entries:]

            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存历史记录失败: {e}")

    def record(self, input_text: str, command: str, result: Any) -> None:
        """
        记录命令执行

        Args:
            input_text: 用户输入
            command: 实际执行的命令
            result: 执行结果
        """
        # 提取结果信息
        if hasattr(result, 'to_dict'):
            result_dict = result.to_dict()
        else:
            result_dict = {
                'success': getattr(result, 'success', False),
                'return_code': getattr(result, 'return_code', -1),
                'stdout': getattr(result, 'stdout', '')[:500],  # 限制长度
                'stderr': getattr(result, 'stderr', '')[:500],
            }

        entry = {
            'timestamp': datetime.now().isoformat(),
            'input_text': input_text,
            'command': command,
            'result': result_dict,
        }

        self.history.append(entry)
        self._save()

        logger.debug(f"记录命令: {command}")

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的历史记录

        Args:
            limit: 返回数量限制

        Returns:
            List[Dict[str, Any]]: 历史记录列表
        """
        return self.history[-limit:] if self.history else []

    def search(self, keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        搜索历史记录

        Args:
            keyword: 搜索关键词
            limit: 返回数量限制

        Returns:
            List[Dict[str, Any]]: 匹配的记录
        """
        keyword_lower = keyword.lower()
        matches = []

        for entry in reversed(self.history):
            if keyword_lower in entry.get('command', '').lower() or \
               keyword_lower in entry.get('input_text', '').lower():
                matches.append(entry)

            if len(matches) >= limit:
                break

        return matches

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            Dict[str, Any]: 统计数据
        """
        if not self.history:
            return {
                'total': 0,
                'successful': 0,
                'failed': 0,
                'success_rate': 0.0,
            }

        total = len(self.history)
        successful = sum(1 for h in self.history if h['result'].get('success', False))
        failed = total - successful

        return {
            'total': total,
            'successful': successful,
            'failed': failed,
            'success_rate': f"{(successful / total * 100):.2f}%",
        }

    def get_count(self) -> int:
        """获取历史记录总数"""
        return len(self.history)

    def clear(self) -> None:
        """清空历史记录"""
        self.history = []
        self._save()
        logger.info("命令历史已清空")

    def get_last_directory(self, current_dir: str) -> Optional[str]:
        """
        获取上一个工作目录（用于 cd - 命令）

        Args:
            current_dir: 当前目录

        Returns:
            Optional[str]: 上一个目录
        """
        for entry in reversed(self.history):
            if 'cd' in entry.get('command', ''):
                # 从历史中提取目录
                # 这里简化处理，实际应该更精确
                return current_dir
        return None
