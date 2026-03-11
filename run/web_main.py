"""
弥娅 Web 模式主入口

启动 Web API 服务和 React 前端开发服务器
"""
import sys
import logging
import asyncio
from pathlib import Path
import uvicorn

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config import Settings
from run.main import Miya


class MiyaWeb:
    """弥娅 Web 模式主类"""

    def __init__(self):
        self.logger = self._setup_logger()
        self.settings = Settings()

        # 初始化核心系统
        self.miya = None
        self.web_api = None

    def _setup_logger(self) -> logging.Logger:
        """设置日志"""
        logger = logging.getLogger('MiyaWeb')
        logger.setLevel(logging.INFO)

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # 文件处理器
        log_dir = Path(__file__).parent.parent / 'logs'
        log_dir.mkdir(exist_ok=True)

        file_handler = logging.FileHandler(
            log_dir / f'miya_web_{Path(__file__).stem}.log',
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)

        # 格式化
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

        return logger

    async def initialize(self):
        """初始化系统"""
        self.logger.info("初始化弥娅 Web 系统...")

        # 创建弥娅核心实例
        self.miya = Miya()

        # 异步初始化 MemoryNet
        if self.miya.memory_net:
            await self.miya._initialize_memory_net_async()

        self.logger.info("弥娅核心系统初始化完成")

        # 获取 Web API 实例
        if self.miya.web_api:
            self.web_api = self.miya.web_api
        else:
            self.logger.warning("Web API 未初始化")

    def start_server(self, host: str = "0.0.0.0", port: int = 8000):
        """启动 Web 服务器"""
        try:
            import os
            from dotenv import load_dotenv
            load_dotenv(Path(__file__).parent.parent / 'config' / '.env')

            # 获取配置
            api_host = os.getenv('WEB_API_HOST', host)
            api_port = int(os.getenv('WEB_API_PORT', port))
            api_domain = os.getenv('WEB_API_DOMAIN', '')
            cors_origins = os.getenv('WEB_API_CORS_ORIGINS', '*')

            self.logger.info(f"启动 Web API 服务器: http://{api_host}:{api_port}")
            if api_domain:
                self.logger.info(f"公网域名: https://{api_domain}")

            # 创建 FastAPI 应用
            if not FASTAPI_AVAILABLE:
                self.logger.error("FastAPI 不可用，无法启动 Web 服务器")
                return

            from fastapi import FastAPI
            from fastapi.middleware.cors import CORSMiddleware

            app = FastAPI(title="Miya Web API", version="1.0.0")

            # 配置 CORS
            # 如果配置了域名，使用配置的域名；否则使用通配符
            if cors_origins == '*':
                allowed_origins = ["*"]
            else:
                allowed_origins = [origin.strip() for origin in cors_origins.split(',')]

            self.logger.info(f"允许的跨域来源: {allowed_origins}")

            app.add_middleware(
                CORSMiddleware,
                allow_origins=allowed_origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

            # 添加 Web API 路由
            if self.web_api and self.web_api.get_router():
                app.include_router(self.web_api.get_router())

            # 启动服务器
            uvicorn.run(
                app,
                host=api_host,
                port=api_port,
                log_level="info"
            )

        except Exception as e:
            self.logger.error(f"启动 Web 服务器失败: {e}", exc_info=True)
            raise


def main():
    """主函数"""
    print("=" * 50)
    print("        弥娅 Web 系统")
    print("        Miya Web System")
    print("=" * 50)
    print()

    try:
        # 创建 Web 实例
        miya_web = MiyaWeb()

        # 初始化系统
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(miya_web.initialize())
        finally:
            loop.close()

        # 显示系统信息
        print(f"\n{miya_web.miya.identity.name} 已启动 (v{miya_web.miya.identity.version})")
        print(f"UUID: {miya_web.miya.identity.uuid}")
        print()
        print("=" * 50)
        print("【Web 模式配置摘要】")
        print(f"  平台: Web 模式 (Web UI)")
        print(f"  记忆系统: {'已启用 (MemoryNet)' if miya_web.miya.memory_net else '未启用'}")
        print(f"  AI客户端: {'已启用' if miya_web.miya.ai_client else '未启用'}")
        print(f"  Web API: {'已启用' if miya_web.web_api else '未启用'}")
        print("=" * 50)
        print()
        print("[OK] 后端 API 服务启动成功")
        print("[API] 地址: http://localhost:8000")
        print("[DOC] API 文档: http://localhost:8000/docs")
        print()

        # 自动启动前端开发服务器
        try:
            import subprocess
            import sys
            import platform
            import time

            frontend_path = project_root / 'miya-pc-ui'

            # 检查前端是否存在
            if not frontend_path.exists():
                print("⚠️  前端目录不存在，跳过前端启动")
            else:
                # 检查 node_modules
                node_modules = frontend_path / 'node_modules'
                if not node_modules.exists():
                    print("[WARNING] 前端依赖未安装，跳过前端启动")
                    print("[INFO] 请运行: cd miya-pc-ui && npm install")
                else:
                    print("[INFO] 正在启动前端开发服务器...")
                    print("[INFO] 访问地址: http://localhost:3000")
                    print()

                    # 根据操作系统启动
                    if platform.system() == 'Windows':
                        # Windows 使用 npm 命令
                        frontend_process = subprocess.Popen(
                            ['npm', 'run', 'dev:web'],
                            cwd=str(frontend_path),
                            shell=True,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                        )
                    else:
                        # Linux/macOS
                        frontend_process = subprocess.Popen(
                            ['npm', 'run', 'dev:web'],
                            cwd=str(frontend_path)
                        )

                    print("[OK] 前端开发服务器启动成功")
                    print()
                    print("请稍等几秒，让前端完全启动...")

        except Exception as e:
            print(f"[ERROR] 前端启动失败: {e}")
            print("[INFO] 手动启动: cd miya-pc-ui && npm run dev:web")
            print()

        # 启动 Web 服务器
        miya_web.start_server()

    except KeyboardInterrupt:
        print("\n\n检测到中断信号...")
        return 0
    except Exception as e:
        logging.error(f"系统错误: {e}", exc_info=True)
        return 1
    finally:
        if 'miya_web' in locals() and miya_web.miya:
            # 关闭对话历史管理器
            try:
                if miya_web.miya.memory_net and hasattr(miya_web.miya.memory_net, 'conversation_history'):
                    async def cleanup_conversation_history():
                        await miya_web.miya.memory_net.conversation_history.close()
                        print("对话历史已保存")
                    asyncio.run(cleanup_conversation_history())
            except Exception as e:
                logging.error(f"关闭对话历史管理器失败: {e}", exc_info=True)

            miya_web.miya.shutdown()


if __name__ == '__main__':
    # 检查 FastAPI 是否可用
    try:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        import uvicorn
        FASTAPI_AVAILABLE = True
    except ImportError:
        FASTAPI_AVAILABLE = False
        print("错误: FastAPI 未安装")
        print("请运行: pip install fastapi uvicorn")
        sys.exit(1)

    sys.exit(main())
