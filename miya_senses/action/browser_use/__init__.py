from __future__ import annotations

"""
弥娅 Browser Use Agent — 基于 DeepSeek Harness 的浏览器自动化子系统

集成路径：
  BrowserUseExecutor → DeepSeek Harness → 浏览器执行
  → ScreenVision → 结果感知
"""

from miya_senses.action.browser_use.adapter import BrowserUseExecutor

__all__ = ["BrowserUseExecutor"]
