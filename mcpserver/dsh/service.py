#!/usr/bin/env python3
"""
DSH MCP 服务 — 弥娅的「手」/肢体工具

通过 DeepSeek Harness (DSH) 执行文件操作、命令执行、代码生成等任务。
DSH 是 DeepSeek 官方开源 agent harness（MIT），以 headless profile 无头执行：
`dsh --profile headless "<任务>"` —— 单次执行、stdout 输出最终结果、退出码即成败。

能力集（DSH 内置）：文件读写/搜索、bash/pwsh 命令、子代理、技能、工作流、
多阶段规划、MCP 客户端（可接 miya-soul 等弥娅 MCP 服务）。
"""

import json
import logging
import platform
import os
import shutil
import subprocess
from pathlib import Path

from .config_bridge import ensure_dsh_config, get_dsh_home

logger = logging.getLogger("mcpserver.dsh")

MIYA_ROOT = Path(__file__).parent.parent.parent

DEFAULT_TIMEOUT = 300  # headless agent 循环比单次 CLI 慢，默认给 5 分钟


class DSHEngineService:
    """DSH 执行引擎 MCP 服务（弥娅的手/肢体工具）"""

    def __init__(self):
        self.name = "dsh"
        self.description = "DSH 执行引擎 — 弥娅的手/肢体工具（DeepSeek Harness）"
        self.version = "1.0.0"
        self._bin_path: Path | None = None
        self._node_exe: str = "node"
        self._init_executor()

    # ===== 执行器定位 =====

    def _init_executor(self):
        # 1) 弥娅嵌入式构建产物（deepseek-harness submodule，自包含）
        embedded = MIYA_ROOT / "deepseek-harness" / "apps" / "cli" / "lib" / "bin.js"
        # 2) npm 全局安装的 @deepseek-ai/dsh
        global_bin: Path | None = None
        try:
            result = subprocess.run(
                ["npm", "root", "-g"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            if result.returncode == 0:
                candidate = Path(result.stdout.strip()) / "@deepseek-ai" / "dsh" / "lib" / "bin.js"
                if candidate.exists():
                    global_bin = candidate
        except Exception:
            pass

        for candidate in [embedded, global_bin]:
            if candidate and candidate.exists():
                self._bin_path = candidate
                break

        node_candidates: list[str] = []
        if platform.system() == "Windows":
            node_candidates = [
                shutil.which("node") or "",
                "C:\\Program Files\\nodejs\\node.exe",
            ]
            # fnm 安装的 node：动态发现任意版本，避免硬编码版本号
            fnm_base = Path.home() / "AppData" / "Roaming" / "fnm" / "node-versions"
            if fnm_base.exists():
                for vdir in sorted(fnm_base.glob("v*"), reverse=True):
                    node_exe = vdir / "installation" / "node.exe"
                    if node_exe.exists():
                        node_candidates.append(str(node_exe))
        else:
            node_candidates = [
                shutil.which("node") or "",
                "/usr/local/bin/node",
                "/usr/bin/node",
            ]

        for candidate in node_candidates:
            if candidate and Path(candidate).exists():
                self._node_exe = candidate
                break

        if self._bin_path:
            logger.info(f"[DSH] 执行器就绪: {self._node_exe} {self._bin_path}")
        else:
            logger.warning("[DSH] 未找到 DSH CLI（deepseek-harness/apps/cli/lib/bin.js）")

    @property
    def is_available(self) -> bool:
        return self._bin_path is not None and self._bin_path.exists()

    def _get_model_env(self) -> dict[str, str]:
        """从 ModelPoolManager 获取活跃模型配置，回退 .env（模型统一由弥娅管理）"""
        from .config_bridge import resolve_model_env

        return resolve_model_env()

    # ===== MCP 入口 =====

    async def handle_handoff(self, tool_call: dict) -> str:
        tool_name = tool_call.get("tool_name", "")

        if tool_name == "execute":
            return await self._execute(tool_call)
        elif tool_name == "get_status":
            return self._get_status()
        else:
            return json.dumps({"success": False, "error": f"未知工具: {tool_name}"})

    async def _execute(self, tool_call: dict) -> str:
        task = tool_call.get("task", "")
        working_dir = tool_call.get("working_dir") or str(MIYA_ROOT)
        timeout = int(tool_call.get("timeout", DEFAULT_TIMEOUT))

        if not task:
            return json.dumps({"success": False, "error": "缺少 task 参数"})

        if not self.is_available:
            return json.dumps(
                {
                    "success": False,
                    "error": "DSH CLI 未就绪，请确认 deepseek-harness/apps/cli/lib/bin.js 存在"
                    "（在 deepseek-harness 目录执行 pnpm install && pnpm run build）",
                }
            )

        model_env = self._get_model_env()
        config = ensure_dsh_config(model_env)

        env = {
            **{k: v for k, v in os.environ.items()},
            "DSH_HOME": config["home"],  # 弥娅专属配置目录，与 ~/.dsh 隔离
            "DEEPSEEK_API_KEY": model_env.get("api_key", ""),  # 进程环境优先级最高
            "DSH_PERMISSION_MODE": "danger-full-access",  # 等价 CCE 的 bypassPermissions
        }

        try:
            creationflags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0

            logger.info(f"[DSH] 执行任务: {task[:80]}...")
            proc = subprocess.run(
                [self._node_exe, str(self._bin_path), "--profile", "headless", task],
                cwd=working_dir,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                creationflags=creationflags,
            )

            return json.dumps(
                {
                    "success": proc.returncode == 0,
                    "output": proc.stdout,
                    "error": proc.stderr,
                    "exit_code": proc.returncode,
                }
            )
        except subprocess.TimeoutExpired:
            return json.dumps({"success": False, "error": f"DSH 执行超时 ({timeout}s)"})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def _get_status(self) -> str:
        return json.dumps(
            {
                "name": self.name,
                "version": self.version,
                "description": self.description,
                "available": self.is_available,
                "bin_path": str(self._bin_path) if self._bin_path else None,
                "node_exe": self._node_exe,
                "dsh_home": str(get_dsh_home()),
            }
        )


service = DSHEngineService()


if __name__ == "__main__":
    import asyncio

    async def test():
        print(f"DSH 服务状态: {service._get_status()}")
        if service.is_available:
            result = await service._execute(
                {
                    "task": "列出当前目录前 5 个文件",
                    "working_dir": str(MIYA_ROOT),
                    "timeout": 120,
                }
            )
            print(f"测试执行结果: {result[:300]}")

    asyncio.run(test())
