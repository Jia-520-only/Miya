"""回归测试：覆盖 config loader / config utils 近期修复点。

这些用例不依赖真实的 .env 内容，也不读取本地敏感配置。
"""

from core.config_loader import ConfigLoader, get_text_config_value
from config.config_utils import get_value


def test_get_base_url_prefers_provider_api_base(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
    assert ConfigLoader().get_base_url("deepseek") == "https://api.deepseek.com/v1"


def test_get_base_url_uses_provider_convention(monkeypatch):
    monkeypatch.delenv("SILICONFLOW_API_BASE", raising=False)
    monkeypatch.setenv("SILICONFLOW_BASE_URL", "https://example.com/v1")
    assert ConfigLoader().get_base_url("siliconflow") == "https://example.com/v1"


def test_get_text_config_value_supports_dotted_key(monkeypatch):
    monkeypatch.setattr(
        "config.config_utils._load_text_config",
        lambda: {"memory": {"default_top_k": 5}},
    )
    assert get_text_config_value("memory.default_top_k") == 5


def test_get_value_supports_dotted_key(monkeypatch):
    monkeypatch.setattr(
        "config.config_utils._load_text_config",
        lambda: {"qq": {"bot_qq": 3681817929}},
    )
    assert get_value("qq.bot_qq") == 3681817929


def test_mcp_manager_default_dir_uses_project_root():
    from core.mcp_manager import MCPManager
    from core.path_resolver import get_project_root

    assert MCPManager(auto_register=False).mcp_dir == str(get_project_root() / "mcpserver")
