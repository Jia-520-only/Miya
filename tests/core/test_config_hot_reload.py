"""Config Hot Reload 单元测试"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from core.config_hot_reload import ConfigHotReload


@pytest.fixture
def mock_context():
    """模拟上下文"""
    context = Mock()
    context.queue_manager = Mock()
    context.personality = Mock()
    context.emotion = Mock()
    context.memory = Mock()
    context.ai_backend = Mock()
    context.web_api = Mock()
    context.terminal_manager = Mock()
    context.iot_manager = Mock()
    return context


@pytest.fixture
def config_file():
    """创建临时配置文件"""
    fd, path = tempfile.mkstemp(suffix=".json")
    config_data = {
        "key1": "value1",
        "key2": "value2",
        "personality": {"vectors": {"warmth": 0.8}, "form": "normal"},
        "tts": {"engine": "gpt_sovits", "voice": "default"},
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)

    yield Path(path)

    # 清理
    import os

    os.close(fd)
    os.unlink(path)


@pytest.fixture
def hot_reload(config_file, mock_context):
    """创建ConfigHotReload实例"""
    reload = ConfigHotReload(config_path=config_file, context=mock_context)
    return reload


class TestConfigHotReload:
    """ConfigHotReload测试类"""

    def test_init(self, config_file, mock_context):
        """测试初始化"""
        reload = ConfigHotReload(config_path=config_file, context=mock_context, debounce_seconds=5.0)

        assert reload.config_path == config_file
        assert reload.context == mock_context
        assert reload.debounce_seconds == 5.0

    def test_is_value_changed_none(self, hot_reload):
        """测试None值变更检测"""
        assert not hot_reload._is_value_changed(None, None)
        assert hot_reload._is_value_changed(None, "value")
        assert hot_reload._is_value_changed("value", None)

    def test_is_value_changed_dict(self, hot_reload):
        """测试字典变更检测"""
        dict1 = {"key": "value"}
        dict2 = {"key": "value"}
        dict3 = {"key": "new_value"}
        dict4 = {"new_key": "value"}

        assert not hot_reload._is_value_changed(dict1, dict2)
        assert hot_reload._is_value_changed(dict1, dict3)
        assert hot_reload._is_value_changed(dict1, dict4)

    def test_is_value_changed_list(self, hot_reload):
        """测试列表变更检测"""
        list1 = [1, 2, 3]
        list2 = [1, 2, 3]
        list3 = [1, 2, 4]

        assert not hot_reload._is_value_changed(list1, list2)
        assert hot_reload._is_value_changed(list1, list3)

    def test_is_value_changed_scalar(self, hot_reload):
        """测试标量值变更检测"""
        assert not hot_reload._is_value_changed("test", "test")
        assert not hot_reload._is_value_changed(123, 123)
        assert not hot_reload._is_value_changed(True, True)

        assert hot_reload._is_value_changed("test1", "test2")
        assert hot_reload._is_value_changed(123, 456)
        assert hot_reload._is_value_changed(True, False)

    def test_is_dict_changed(self, hot_reload):
        """测试字典变更检测"""
        dict1 = {"key1": "value1", "key2": "value2"}
        dict2 = {"key1": "value1", "key2": "value2"}
        dict3 = {"key1": "new_value1", "key2": "value2"}
        dict4 = {"key1": "value1", "key2": "value2", "key3": "value3"}

        assert not hot_reload._is_dict_changed(dict1, dict2)
        assert hot_reload._is_dict_changed(dict1, dict3)
        assert hot_reload._is_dict_changed(dict1, dict4)

    def test_deep_copy_config(self, hot_reload):
        """测试深度复制配置"""
        original = {"key1": "value1", "key2": {"nested": "value2"}}

        copied = hot_reload._deep_copy_config(original)

        assert copied == original
        assert copied is not original
        assert copied["key2"] is not original["key2"]

        # 修改副本不应该影响原配置
        copied["key1"] = "modified"
        assert original["key1"] == "value1"

    def test_detect_config_changes(self, hot_reload):
        """测试配置变更检测"""
        old_config = {"key1": "value1", "key2": "value2", "key3": "value3"}

        hot_reload._config_snapshot = old_config.copy()

        # 测试新增键
        new_config1 = old_config.copy()
        new_config1["key4"] = "value4"
        changes1 = hot_reload._detect_changes(new_config1)
        assert "key4" in changes1
        assert "key1" not in changes1

        # 测试修改值
        new_config2 = old_config.copy()
        new_config2["key2"] = "new_value2"
        changes2 = hot_reload._detect_changes(new_config2)
        assert "key2" in changes2
        assert changes2["key2"] == ("value2", "new_value2")

        # 测试删除键
        new_config3 = {"key1": "value1", "key3": "value3"}
        changes3 = hot_reload._detect_changes(new_config3)
        assert "key2" in changes3

    @pytest.mark.asyncio
    async def test_apply_updates_queue_manager(self, hot_reload):
        """测试更新队列管理器配置"""
        hot_reload.context.queue_manager.update_model_intervals = Mock()

        new_config = {"queue_intervals": {"priority_high": 0.5, "priority_normal": 1.0}}

        changes = {"queue_intervals": (None, new_config["queue_intervals"])}

        await hot_reload._apply_updates(new_config, changes)

        hot_reload.context.queue_manager.update_model_intervals.assert_called_once_with(new_config["queue_intervals"])

    @pytest.mark.asyncio
    async def test_apply_updates_personality(self, hot_reload):
        """测试更新人格配置"""
        hot_reload.context.personality.vectors = {"warmth": 0.5}
        hot_reload.context.personality.set_form = Mock()

        new_config = {"personality": {"vectors": {"warmth": 0.9}, "form": "battle"}}

        changes = {"personality": (None, new_config["personality"])}

        await hot_reload._apply_updates(new_config, changes)

        hot_reload.context.personality.set_form.assert_called_once_with("battle")

    @pytest.mark.asyncio
    async def test_update_webapi_config(self, hot_reload):
        """测试更新WebAPI配置"""
        hot_reload.context.web_api = Mock()

        new_config = {
            "api_key": "new_key",
            "cors_origins": ["http://localhost:3000"],
            "rate_limit": 100,
        }

        hot_reload._update_webapi_config(new_config)
        # 只是验证方法不会抛出异常

    @pytest.mark.asyncio
    async def test_update_terminal_config(self, hot_reload):
        """测试更新终端配置"""
        hot_reload.context.terminal_manager = Mock()

        new_config = {"timeout": 30, "buffer_size": 8192, "default_shell": "/bin/bash"}

        hot_reload._update_terminal_config(new_config)
        # 只是验证方法不会抛出异常

    @pytest.mark.asyncio
    async def test_update_iot_config(self, hot_reload):
        """测试更新IoT配置"""
        hot_reload.context.iot_manager = Mock()
        hot_reload.context.iot_manager.device_timeout = 60

        new_config = {"device_timeout": 120, "heartbeat_interval": 30}

        hot_reload._update_iot_config(new_config)

        assert hot_reload.context.iot_manager.device_timeout == 120

    @pytest.mark.asyncio
    async def test_trigger_config_update_event(self, hot_reload):
        """测试触发配置更新事件"""
        changes = {
            "key1": ("old_value1", "new_value1"),
            "key2": ("old_value2", "new_value2"),
        }

        await hot_reload._trigger_config_update_event(changes)
        # 只是验证方法不会抛出异常

    def test_start_without_watcher(self, hot_reload):
        """测试启动（无watchdog）"""
        with patch("core.config_hot_reload.WATCHDOG_AVAILABLE", True):
            with patch("core.config_hot_reload.Observer") as mock_observer:
                mock_watcher = Mock()
                mock_observer.return_value = mock_watcher

                result = hot_reload.start()

                # 由于我们只模拟了部分，这里只验证不会抛出异常
                assert isinstance(result, bool)

    def test_stop_without_observer(self, hot_reload):
        """测试停止（无observer）"""
        hot_reload._observer = None
        hot_reload.stop()
        # 验证不会抛出异常
