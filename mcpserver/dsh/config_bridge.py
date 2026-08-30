#!/usr/bin/env python3
"""
DSH 配置桥接 - 注入弥娅模型池配置到 data/dsh (DSH_HOME)

DSH (DeepSeek Harness) 通过 $DSH_HOME 定位配置目录（默认 ~/.dsh）：
  - settings.yaml:     agent-default-model (provider/model/reasoningEffort) 等
  - .credentials.yaml: DEEPSEEK_API_KEY（DSH 凭据文件）
  - .env:             只读回退（进程环境变量优先级最高）

弥娅启动 DSH 前调用 ensure_dsh_config()，把守护进程的模型配置注入弥娅自己的
data/dsh 目录，与用户个人 ~/.dsh（Web GUI 实例）完全隔离，互不干扰。
"""

import logging
import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - 环境兜底
    yaml = None

logger = logging.getLogger("mcpserver.dsh.config")

MIYA_ROOT = Path(__file__).resolve().parent.parent.parent
DSH_HOME = MIYA_ROOT / "data" / "dsh"

OFFICIAL_BASE_URLS = ("https://api.deepseek.com", "http://api.deepseek.com")


def get_dsh_home() -> Path:
    """弥娅专属的 DSH 配置目录（data/dsh）"""
    return DSH_HOME


def _load_dotenv() -> dict[str, str]:
    """读取 config/.env 的环境变量（与守护进程一致的兜底来源）"""
    dotenv_path = MIYA_ROOT / "config" / ".env"
    env_vars: dict[str, str] = {}
    if dotenv_path.exists():
        for line in dotenv_path.read_text(encoding="utf-8").split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env_vars[key.strip()] = value.strip()
    return env_vars


def resolve_model_env() -> dict[str, str]:
    """
    解析 DSH 应使用的模型配置。

    优先级：ModelPoolManager 活跃模型 → system_defaults.default_model → config/.env。
    返回 {"api_key", "base_url", "model", "provider"}。
    """
    try:
        from core.model_pool_manager import get_model_pool, resolve_api_key_by_provider

        pool = get_model_pool()
        active_model = pool.select_model("simple_chat")
        if active_model and active_model.base_url:
            return {
                "api_key": resolve_api_key_by_provider(
                    active_model.provider,
                    getattr(active_model, "env_key", ""),
                ),
                "base_url": active_model.base_url,
                "model": active_model.name,
                "provider": "deepseek-official",
            }

        system_defaults = pool._config.get("system_defaults", {})
        default_model_id = system_defaults.get("default_model", "")
        if default_model_id:
            model = pool.get_model(default_model_id)
            if model and model.enabled:
                return {
                    "api_key": resolve_api_key_by_provider(
                        model.provider,
                        getattr(model, "env_key", ""),
                    ),
                    "base_url": model.base_url,
                    "model": model.name,
                    "provider": "deepseek-official",
                }
    except Exception as e:
        logger.debug(f"[DSH] ModelPoolManager 获取模型失败，回退 .env: {e}")

    env_vars = _load_dotenv()
    base_url = env_vars.get("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
    # 非官方 base_url 时使用 deepseek-official 可能连不上；仅官方地址走官方 provider。
    # 自定义 base_url 场景由用户自行在 data/dsh/settings.yaml 维护 provider。
    return {
        "api_key": env_vars.get("DEEPSEEK_API_KEY", ""),
        "base_url": base_url,
        "model": env_vars.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        "provider": "deepseek-official"
        if any(base_url.startswith(u) for u in OFFICIAL_BASE_URLS)
        else "deepseek-official",
    }


def _ensure_home() -> None:
    DSH_HOME.mkdir(parents=True, exist_ok=True)


def _read_yaml_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        if yaml is not None:
            data = yaml.safe_load(text)
            return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning(f"[DSH] 读取 {path.name} 失败: {e}")
    return {}


def _write_yaml_file(path: Path, data: dict) -> None:
    if yaml is None:
        raise RuntimeError("PyYAML 未安装，无法写入 DSH 配置")
    _ensure_home()
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def ensure_dsh_config(model_env: dict[str, str] | None = None) -> dict:
    """
    确保弥娅专属 DSH 配置就绪，并注入当前模型。

    返回 {"home": str, "model": str, "provider": str, "api_key_configured": bool}
    """
    _ensure_home()

    model = model_env or resolve_model_env()

    # settings.yaml — 保留用户已有键，只更新 agent-default-model
    settings_path = DSH_HOME / "settings.yaml"
    settings = _read_yaml_file(settings_path)
    settings["agent-default-model"] = {
        "provider": model.get("provider", "deepseek-official"),
        "model": model.get("model", "deepseek-v4-flash"),
    }
    _write_yaml_file(settings_path, settings)

    # .credentials.yaml — DEEPSEEK_API_KEY
    creds_path = DSH_HOME / ".credentials.yaml"
    creds = _read_yaml_file(creds_path)
    api_key = model.get("api_key", "") or os.environ.get("DEEPSEEK_API_KEY", "")
    if api_key:
        creds["DEEPSEEK_API_KEY"] = api_key
    _write_yaml_file(creds_path, creds)

    # headless profile 用户层 — 接入弥娅原生 MCP 服务（miya-soul 等）
    _ensure_headless_profile()

    logger.info(f"[DSH] 配置就绪: home={DSH_HOME}, model={model.get('model')}, key={'有' if api_key else '无'}")
    return {
        "home": str(DSH_HOME),
        "model": model.get("model", ""),
        "provider": model.get("provider", "deepseek-official"),
        "api_key_configured": bool(api_key),
    }


def _ensure_headless_profile() -> None:
    """为 headless profile 生成用户 patch 层，把弥娅 MCP 服务注册为 DSH 工具。

    DSH profile 结构（$DSH_HOME/profiles/<name>/）：
      - cordis.yml        根文件，保持空列表（组合由 bundle + patch 层构成）
      - cordis.patch.yml  用户 patch 层（id 定向覆盖 / disable / insert 列表）

    工具名形如 mcp__miya-soul__miya_get_status（与 Claude Code 的限定形式一致）。
    配置在 data/dsh 下运行时生成（含本机 python 路径），随目录一起被 git 忽略。
    """
    profile_dir = DSH_HOME / "profiles" / "headless"
    profile_dir.mkdir(parents=True, exist_ok=True)

    python_exe = sys.executable or "python"

    def _mcp_plugin(pid: str, server_name: str, module: str) -> dict:
        # 以模块模式启动（python -m mcpserver.xxx.server），避免脚本模式下的相对导入失败
        return {
            "id": pid,
            "name": "@deepseek-ai/dsh-mcp-client",
            "config": {
                "serverName": server_name,
                "transport": "stdio",
                "command": python_exe,
                "args": ["-m", module],
                "cwd": str(MIYA_ROOT),
                "env": {},
            },
        }

    entries = [
        _mcp_plugin("mcp-miya-soul", "miya-soul", "mcpserver.miya.server"),
        _mcp_plugin("mcp-miya-mineradio", "miya-mineradio", "mcpserver.miya_mineradio.server"),
    ]

    # cordis.yml — 根文件，保持空列表
    root_yaml = DSH_HOME / "profiles" / "headless" / "cordis.yml"
    if yaml is None:
        raise RuntimeError("PyYAML 未安装，无法写入 DSH profile")
    root_yaml.write_text(
        "# dsh profile root — an empty entry list. The tree is composed as patches:\n"
        "# each bundle, then cordis.patch.yml, then any --patch overlays.\n"
        "[]\n",
        encoding="utf-8",
    )

    # cordis.patch.yml — 用户 patch 层：插入弥娅 MCP 服务
    patch_yaml = DSH_HOME / "profiles" / "headless" / "cordis.patch.yml"
    patch_yaml.write_text(
        "# 弥娅生成的 patch 层（运行时生成，勿手改）— 接入 miya-soul / miya-mineradio\n"
        + yaml.safe_dump([{"insert": entries}], allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    logger.info(f"[DSH] headless profile 已写入 {len(entries)} 个弥娅 MCP 服务: {patch_yaml}")


if __name__ == "__main__":
    print(ensure_dsh_config())
