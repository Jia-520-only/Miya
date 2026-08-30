"""
吟美虚拟主播插件 - MIYA 集成入口

将此模块挂载到 MIYA 的 FastAPI 实例上即可启用全部虚拟主播功能。

用法:
    from plugins.yinmei.integration import install_yinmei_plugin
    install_yinmei_plugin(app)  # app 为 FastAPI 实例

或在 daemon.py 中自动加载。
"""

import logging
from typing import Optional

from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler

from plugins.yinmei.routes import yinmei_router
from plugins.yinmei.core.live_stream_hub import LiveStreamHub
from plugins.yinmei.core import SharedData

logger = logging.getLogger(__name__)

_yinmei_installed = False
_hub: Optional[LiveStreamHub] = None
_scheduler: Optional[BackgroundScheduler] = None


def install_yinmei_plugin(
    app: FastAPI,
    enable_scheduler: bool = True,
    tts_callback=None,
    llm_chat_callback=None,
    emote_callback=None,
) -> LiveStreamHub:
    """
    将吟美虚拟主播插件安装到 MIYA 的 FastAPI 实例

    Args:
        app: FastAPI 应用实例
        enable_scheduler: 是否启动定时任务调度器
        tts_callback: TTS 回调函数 callback(text: str)
        llm_chat_callback: LLM 对话回调
        emote_callback: 表情回调 callback(text: str) -> list[dict]

    Returns:
        LiveStreamHub 实例
    """
    global _yinmei_installed, _hub, _scheduler

    if _yinmei_installed:
        logger.warning("吟美插件已安装，跳过重复安装")
        return _hub

    # 1. 注册路由
    app.include_router(yinmei_router)
    logger.info("吟美虚拟主播 API 路由已注册")

    # 2. 创建中枢
    _hub = LiveStreamHub()

    # 3. 初始化场景 + B站弹幕
    _hub.init_scene()
    _hub.start_bilibili()

    # 4. 注册回调 - 对接 MIYA 现有系统
    if tts_callback:
        _hub.set_tts_callback(tts_callback)
        logger.info("吟美 TTS 回调已注册")
    if llm_chat_callback:
        _hub.set_llm_chat_callback(llm_chat_callback)
        logger.info("吟美 LLM 回调已注册")
    if emote_callback:
        _hub.set_emote_callback(emote_callback)
        logger.info("吟美表情回调已注册")

    # 4. 启动定时任务调度
    if enable_scheduler:
        _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        _hub.register_scheduler(_scheduler)
        _scheduler.start()
        logger.info("吟美定时任务调度器已启动")

    # 5. 注册关闭事件
    @app.on_event("shutdown")
    async def shutdown_yinmei():
        if _scheduler:
            _scheduler.shutdown(wait=False)
        if _hub:
            _hub.shutdown()
        logger.info("吟美插件已关闭")

    _yinmei_installed = True

    data = SharedData()
    logger.info(f"==============================================")
    logger.info(f"AI 虚拟主播【{data.Ai_Name}】吟美插件安装完成！")
    logger.info(f"API 前缀: /api/yinmei")
    logger.info(f"==============================================")

    return _hub


def get_yinmei_hub() -> Optional[LiveStreamHub]:
    """获取已安装的 LiveStreamHub 实例"""
    return _hub
