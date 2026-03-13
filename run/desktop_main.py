"""
弥娅桌面端主入口

启动桌面端Electron应用和Web API服务
参考 web_main.py 的架构模式
"""
import sys
import logging
import asyncio
import subprocess
from pathlib import Path
import uvicorn
from threading import Thread
import time

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config import Settings
from run.main import Miya


FASTAPI_AVAILABLE = False
try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    FASTAPI_AVAILABLE = True
except ImportError:
    pass


class MiyaDesktop:
    """弥娅桌面端主类"""

    def __init__(self):
        self.logger = self._setup_logger()
        self.settings = Settings()

        # 初始化核心系统
        self.miya = None
        self.web_api = None
        self.electron_process = None
        self.electron_port = 5173

    def _setup_logger(self) -> logging.Logger:
        """设置日志"""
        logger = logging.getLogger('MiyaDesktop')
        logger.setLevel(logging.INFO)

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # 文件处理器
        log_dir = Path(__file__).parent.parent / 'logs'
        log_dir.mkdir(exist_ok=True)

        file_handler = logging.FileHandler(
            log_dir / f'miya_desktop_{Path(__file__).stem}.log',
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
        self.logger.info("初始化弥娅桌面端系统...")

        # 创建弥娅核心实例
        self.miya = Miya()

        # 异步初始化 MemoryNet
        if self.miya.memory_net:
            await self.miya._initialize_memory_net_async()

        self.logger.info("弥娅核心系统初始化完成")

        # 初始化TTS系统
        self.tts_net = None
        self._init_tts_system()

        # 获取 Web API 实例
        if self.miya.web_api:
            self.web_api = self.miya.web_api
            # 将TTS系统传递给Web API
            if self.tts_net:
                self.web_api.tts_net = self.tts_net
        else:
            self.logger.warning("Web API 未初始化")

    def _init_tts_system(self):
        """初始化TTS系统"""
        try:
            import json
            from pathlib import Path
            from core.constants import Encoding
            
            from webnet.tts import TTSNet
            # 初始化 TTSNet
            self.tts_net = TTSNet(self.miya.mlink if hasattr(self.miya, 'mlink') else None)
            # 加载TTS配置
            tts_config_path = Path(__file__).parent.parent / 'config' / 'tts_config.json'
            if tts_config_path.exists():
                with open(tts_config_path, 'r', encoding=Encoding.UTF8) as f:
                    tts_config = json.load(f)
                self.tts_net.initialize(tts_config)
                self.logger.info("TTS系统初始化成功")
            else:
                self.logger.warning("TTS配置文件不存在，使用默认配置")
        except Exception as e:
            self.logger.warning(f"TTS系统初始化失败: {e}")
            self.tts_net = None

    def start_server(self, host: str = "127.0.0.1", port: int = 8000):
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

            app = FastAPI(title="弥娅桌面端 API")

            # 配置 CORS
            app.add_middleware(
                CORSMiddleware,
                allow_origins=cors_origins.split(','),
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

            # 注册路由（不要加前缀，因为 web_api.router 已经有 /api 前缀）
            if self.web_api:
                app.include_router(self.web_api.router)
            else:
                @app.get("/")
                async def root():
                    return {"message": "弥娅桌面端 API 服务运行中", "status": "web_api_not_initialized"}

            # 启动服务器
            uvicorn.run(
                app,
                host=api_host,
                port=api_port,
                log_level="info"
            )

        except Exception as e:
            self.logger.error(f"启动 Web 服务器失败: {e}")
            raise

    def start_electron(self):
        """启动 Electron 桌面应用（使用 concurrently 同时启动 Vite 和 Electron）"""
        try:
            desktop_dir = project_root / 'miya-desktop'

            if not desktop_dir.exists():
                self.logger.error(f"桌面端目录不存在: {desktop_dir}")
                self.logger.error("请先运行 npm install 在 miya-desktop 目录中")
                return False

            # 检查 node_modules
            node_modules = desktop_dir / 'node_modules'
            if not node_modules.exists():
                self.logger.info("首次启动，正在安装桌面端依赖...")
                self.logger.info("请手动运行以下命令:")
                self.logger.info(f"  cd {desktop_dir}")
                self.logger.info("  npm install")
                return False

            # 检查 package.json
            package_json = desktop_dir / 'package.json'
            if not package_json.exists():
                self.logger.error(f"package.json 不存在: {package_json}")
                return False

            self.logger.info("启动 Electron 桌面应用...")

            npm_cmd = 'npm.cmd' if sys.platform == 'win32' else 'npm'

            # 使用 dev 脚本启动 Vite 和 Electron（vite-plugin-electron 会自动启动 Electron）
            self.logger.info("正在启动 Vite 和 Electron...")
            log_file = desktop_dir / 'dev.log'
            log = open(log_file, 'w', encoding='utf-8')

            # 使用 dev 脚本，vite-plugin-electron 会自动编译并启动 Electron
            self.electron_process = subprocess.Popen(
                [npm_cmd, 'run', 'dev'],
                cwd=str(desktop_dir),
                stdout=log,
                stderr=subprocess.STDOUT
            )

            self.logger.info(f"已启动 (PID: {self.electron_process.pid})")

            # 等待 Vite 启动并验证
            self.logger.info("等待 Vite 启动...")
            import socket
            vite_port = 5173
            max_attempts = 30  # 最多等待 30 秒

            for attempt in range(max_attempts):
                time.sleep(1)

                # 检查进程是否还在运行
                if self.electron_process.poll() is not None:
                    self.logger.error(f"进程已退出！返回码: {self.electron_process.returncode}")
                    # 检查日志
                    try:
                        with open(log_file, 'r', encoding='utf-8') as f:
                            log_content = f.read()
                            self.logger.error(f"日志:\n{log_content}")
                    except:
                        pass
                    return False

                # 检查端口是否可连接
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    result = sock.connect_ex(('127.0.0.1', vite_port))
                    sock.close()

                    if result == 0:
                        self.logger.info(f"Vite 已启动并监听端口 {vite_port}")
                        break
                except:
                    pass

                self.logger.debug(f"等待 Vite... ({attempt + 1}/{max_attempts})")
            else:
                self.logger.error(f"Vite 在 {max_attempts} 秒内未启动成功")
                return False

            # 额外等待 5 秒确保 Electron 也启动了
            time.sleep(5)

            # 检查 Electron 是否还在运行
            if self.electron_process.poll() is not None:
                self.logger.error(f"进程已退出！返回码: {self.electron_process.returncode}")
                # 检查日志
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        log_content = f.read()
                        self.logger.error(f"日志:\n{log_content}")
                except:
                    pass
                return False

            self.logger.info("Vite 和 Electron 进程运行正常")
            return True

        except Exception as e:
            self.logger.error(f"启动 Electron 失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    async def run(self):
        """运行桌面端系统"""
        try:
            # 初始化核心系统
            await self.initialize()

            # 启动 Web API 服务器（在后台线程）
            server_thread = Thread(target=self.start_server, daemon=False)
            server_thread.start()

            # 等待服务器启动
            self.logger.info("等待 Web API 服务器启动...")
            await asyncio.sleep(3)

            # 启动 Electron（包含 Vite）
            if not self.start_electron():
                self.logger.error("Electron 启动失败")
                return

            self.logger.info("=" * 60)
            self.logger.info("弥娅桌面端已启动!")
            self.logger.info("=" * 60)
            self.logger.info("桌面端: Electron 窗口")
            self.logger.info("前端开发服务器: http://localhost:5173")
            self.logger.info("Web API 服务器: http://localhost:8000")
            self.logger.info("=" * 60)
            self.logger.info("按 Ctrl+C 停止所有服务")

            # 保持运行 - 监控进程状态
            try:
                while True:
                    # 检查 Electron 进程（由 Vite 管理）
                    if self.electron_process and self.electron_process.poll() is not None:
                        self.logger.warning("Electron 进程已退出，正在关闭系统...")
                        break

                    # 检查服务器线程
                    if not server_thread.is_alive():
                        self.logger.warning("服务器线程已停止，正在关闭系统...")
                        break

                    # 等待 1 秒
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                self.logger.info("接收到中断信号，正在关闭...")

        except KeyboardInterrupt:
            self.logger.info("接收到中断信号，正在关闭...")
        except Exception as e:
            self.logger.error(f"运行错误: {e}")
            raise
        finally:
            self._shutdown()

    def _shutdown(self):
        """关闭系统"""
        self.logger.info("正在关闭桌面端系统...")

        # 关闭 dev:all 进程（包含 Vite 和 Electron）
        if self.electron_process:
            self.logger.info("关闭 Vite 和 Electron 进程...")
            try:
                self.electron_process.terminate()
                try:
                    self.electron_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    if sys.platform == 'win32':
                        self.electron_process.kill()
                    else:
                        self.electron_process.kill()
            except:
                pass

        # 清理弥娅核心的异步任务
        if self.miya:
            try:
                # 尝试关闭对话历史管理器
                if hasattr(self.miya, 'conversation_history_manager'):
                    self.logger.info("等待对话历史保存完成...")
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(self.miya.conversation_history_manager.close())
                    except:
                        pass
                    finally:
                        loop.close()
            except Exception as e:
                self.logger.warning(f"关闭对话历史管理器时出错: {e}")

        # 清理临时文件
        desktop_dir = project_root / 'miya-desktop'
        for temp_file in ['start_all_temp.bat']:
            temp_path = desktop_dir / temp_file
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except:
                    pass

        self.logger.info("桌面端系统已关闭")


def main():
    """主函数"""
    import os
    os.environ['PYTHONIOENCODING'] = 'utf-8'

    miya_desktop = MiyaDesktop()

    try:
        # 运行系统
        asyncio.run(miya_desktop.run())
    except KeyboardInterrupt:
        miya_desktop.shutdown()
    except Exception as e:
        miya_desktop.logger.error(f"启动失败: {e}")
        raise


if __name__ == '__main__':
    main()
