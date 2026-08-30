"""
独立运行 Runtime API Server

用法:
    python run/runtime_api_start.py

或者使用 start.bat 选项4
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.runtime_api_server import RuntimeAPIServer

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """启动 Runtime API Server"""
    logger.info("=========================================")
    logger.info("    弥娅 Runtime API Server")
    logger.info("=========================================")
    logger.info("")

    try:
        # 创建服务器实例
        server = RuntimeAPIServer(
            host="0.0.0.0",
            port=8001,  # 使用8001端口避免与Web API冲突
            enable_api=True,
        )

        # 启动服务器
        await server.start()

        logger.info("")
        logger.info("✅ Runtime API Server 启动成功")
        logger.info(f"📡 API 地址: http://localhost:8001")
        logger.info(f"📝 API 文档: http://localhost:8001/docs")
        logger.info("")
        logger.info("按 Ctrl+C 停止服务器")
        logger.info("")

        # 保持运行
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("")
            logger.info("正在停止服务器...")
            await server.stop()
            logger.info("✅ 服务器已停止")

    except Exception as e:
        logger.error(f"启动失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序已退出")
