"""
弥娅认知记忆 — 后台史官子系统
"""

from memory.historian.job_queue import JobQueue
from memory.historian.worker import HistorianWorker

# V4.1.11: 兼容导入 — memory/historian.py 被同名目录包遮蔽，显式加载并暴露 get_historian
import importlib.util
import os

_hist_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "historian.py")
_spec = importlib.util.spec_from_file_location("memory._historian_file", _hist_path)
if _spec and _spec.loader:
    _hist_mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_hist_mod)
    Historian = _hist_mod.Historian
    get_historian = _hist_mod.get_historian

__all__ = ["JobQueue", "HistorianWorker", "Historian", "get_historian"]
