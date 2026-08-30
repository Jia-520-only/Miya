"""调谐「配置」板块（ConfigPanelRoutes）核心逻辑回归测试

不启动 FastAPI，直接测试纯函数：
- 掩码 / .env 行级更新 / 原子写与备份
- 人设卡表单保存（文本级替换保注释）
- 管理账号（superadmins）读写与清洗
- 人设冷切换（无 decision_hub 时回退 last_form.json）
"""

from __future__ import annotations

import json

import pytest
import yaml

from core.web_api import config_routes as cr


@pytest.fixture()
def env_file(tmp_path, monkeypatch):
    """隔离的 .env 测试文件"""
    env_path = tmp_path / ".env"
    env_path.write_text(
        "# 弥娅密钥配置\nTAVILY_API_KEY=sk-old-key-123456\n\n# 分组二\nGITHUB_TOKEN=ghp_old\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TAVILY_API_KEY", "sk-old-key-123456")
    monkeypatch.setattr(cr, "_ENV_PATH", env_path)
    monkeypatch.setattr(cr, "_BACKUP_DIR", tmp_path / "backup")
    return env_path


@pytest.fixture()
def persona_dir(tmp_path, monkeypatch):
    """隔离的人设卡目录 + form_names 双映射文件"""
    pdir = tmp_path / "personalities"
    pdir.mkdir()
    (pdir / "normal.yaml").write_text(
        "# 默认形态\nname: 普通态\nfull_name: normal\ndescription: \"默认的弥娅\"\n\n"
        "prompt: |\n  第一行。\n  第二行。\n\nspeaking:\n  style: 自然\n",
        encoding="utf-8",
    )
    (pdir / "_base.yaml").write_text(
        "# 核心灵魂配置\ncore_identity: test\n\nform_names:\n  normal: \"普通态\"\n  feixue: \"绯雪态\"\n",
        encoding="utf-8",
    )
    text_cfg = tmp_path / "text_config.json"
    text_cfg.write_text(
        json.dumps({"form_names": {"normal": "普通态", "feixue": "绯雪态"}}, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )
    monkeypatch.setattr(cr, "_PERSONA_DIR", pdir)
    monkeypatch.setattr(cr, "_BASE_YAML_PATH", pdir / "_base.yaml")
    monkeypatch.setattr(cr, "_TEXT_CONFIG_PATH", text_cfg)
    monkeypatch.setattr(cr, "_BACKUP_DIR", tmp_path / "backup")
    return pdir


@pytest.fixture()
def permissions_file(tmp_path, monkeypatch):
    perm = tmp_path / "permissions.json"
    perm.write_text(
        json.dumps(
            {"version": "1.0.0", "superadmins": {"佳": {"name": "佳", "ids": {"qq": ["10001"]}}}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cr, "_PERMISSIONS_PATH", perm)
    monkeypatch.setattr(cr, "_BACKUP_DIR", tmp_path / "backup")
    return perm


@pytest.fixture()
def multi_model_file(tmp_path, monkeypatch):
    mm = tmp_path / "multi_model_config.json"
    payload = json.dumps(
        {
            "active": "main_model",
            "models": {
                "main_model": {
                    "name": "test-main",
                    "provider": "openai",
                    "base_url": "https://api.test/v1",
                    "env_key": "TEST_KEY",
                    "capabilities": ["simple_chat", "tool_calling"],
                    "cost_per_1k_tokens": {"input": 0.001, "output": 0.002},
                },
                "_custom_proxy_example": {"name": "template", "disabled": True},
            },
            "routing_strategy": {
                "simple_chat": {"primary": "@active", "fallback": "main_model"},
            },
        },
        ensure_ascii=False,
    ).replace("\n", "\r\n")  # CRLF，与真实文件一致
    with open(mm, "w", encoding="utf-8", newline="") as f:
        f.write(payload)
    monkeypatch.setattr(cr, "_MULTI_MODEL_PATH", mm)
    monkeypatch.setattr(cr, "_BACKUP_DIR", tmp_path / "backup")
    return mm


@pytest.fixture()
def form_files(tmp_path, monkeypatch):
    """通用表单的目标配置文件（隔离目录）"""
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "tts_config.json").write_text(
        json.dumps({"enabled": True, "preferred_engine": "gpt_sovits", "unknown_extra": "keep-me"}, ensure_ascii=False),
        encoding="utf-8",
    )
    proactive_raw = (
        "# 主动聊天配置\r\nproactive_chat:\r\n  enabled: true  # 启用\r\n"
        "  check_interval: 45  # 检查间隔\r\n  quiet_hours: [23, 0]\r\n"
    )
    with open(cfg_dir / "proactive_chat.yaml", "w", encoding="utf-8", newline="") as f:
        f.write(proactive_raw)
    monkeypatch.setattr(cr, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cr, "_BACKUP_DIR", tmp_path / "backup")
    return cfg_dir


# ── 掩码 ──

def test_mask_secret():
    assert cr._mask_secret("") == ""
    assert cr._mask_secret("short") == "****"
    assert cr._mask_secret("sk-1234567890abcdef") == "sk-1****cdef"


# ── .env 更新 ──

def test_update_env_replaces_existing_key(env_file):
    cr.update_env_value("TAVILY_API_KEY", "sk-new-key-9999")
    text = env_file.read_text(encoding="utf-8")
    assert "TAVILY_API_KEY=sk-new-key-9999" in text
    # 注释与其它键保留
    assert "# 弥娅密钥配置" in text
    assert "GITHUB_TOKEN=ghp_old" in text


def test_update_env_appends_missing_key(env_file):
    cr.update_env_value("ZHIPU_API_KEY", "zhipu.new")
    text = env_file.read_text(encoding="utf-8")
    assert "ZHIPU_API_KEY=zhipu.new" in text
    assert "TAVILY_API_KEY=sk-old-key-123456" in text


def test_update_env_syncs_os_environ(env_file, monkeypatch):
    cr.update_env_value("TAVILY_API_KEY", "sk-live-key")
    import os

    assert os.environ["TAVILY_API_KEY"] == "sk-live-key"
    monkeypatch.delenv("TAVILY_API_KEY")


def test_update_env_rejects_bad_input(env_file):
    with pytest.raises(ValueError):
        cr.update_env_value("BAD KEY NAME", "v")
    with pytest.raises(ValueError):
        cr.update_env_value("TAVILY_API_KEY", "   ")


def test_update_env_creates_backup(env_file):
    cr.update_env_value("TAVILY_API_KEY", "v1")
    backups = list((cr._BACKUP_DIR).glob(".env.*.bak"))
    assert len(backups) == 1
    assert "sk-old-key-123456" in backups[0].read_text(encoding="utf-8")


# ── 人设卡 ──

def test_list_personas_skips_underscore_files(persona_dir):
    personas = cr.list_personas()
    ids = [p["id"] for p in personas]
    assert "normal" in ids
    assert "_base" not in ids


def test_save_persona_form_preserves_comments(persona_dir):
    result = cr.save_persona_form(
        "normal",
        {"name": "新普通态", "description": "更新后的描述", "prompt": "新的第一行。\n新的第二行。"},
    )
    text = (persona_dir / "normal.yaml").read_text(encoding="utf-8")
    assert "# 默认形态" in text  # 注释保留
    assert "name: 新普通态" in text
    assert 'description: "更新后的描述"' in text
    assert "新的第一行。" in text
    assert "\n  第一行。" not in text  # 旧 prompt 已被替换
    assert "speaking:" in text  # 其余结构保留
    # 替换后仍是合法 YAML
    cfg = yaml.safe_load(text)
    assert cfg["name"] == "新普通态"
    assert cfg["prompt"].rstrip("\n") == "新的第一行。\n新的第二行。"
    assert set(result["updated_fields"]) == {"name", "description", "prompt"}


def test_save_persona_form_rejects_empty_prompt(persona_dir):
    with pytest.raises(ValueError, match="prompt"):
        cr.save_persona_form("normal", {"prompt": "  "})
    # 未落盘：文件内容不变
    assert "第一行。" in (persona_dir / "normal.yaml").read_text(encoding="utf-8")


def test_save_persona_form_appends_missing_scalar(persona_dir):
    (persona_dir / "plain.yaml").write_text("name: 素形态\nprompt: |\n  内容\n", encoding="utf-8")
    cr.save_persona_form("plain", {"description": "补写的描述"})
    cfg = yaml.safe_load((persona_dir / "plain.yaml").read_text(encoding="utf-8"))
    assert cfg["description"] == "补写的描述"


def test_switch_persona_cold_fallback(tmp_path, persona_dir, monkeypatch):
    last_form = tmp_path / "last_form.json"
    monkeypatch.setattr(cr, "_LAST_FORM_PATH", last_form)
    result = cr.switch_persona("normal", decision_hub=None)
    assert result["hot_switched"] is False
    assert json.loads(last_form.read_text(encoding="utf-8"))["current_form"] == "normal"


def test_switch_persona_rejects_unknown(persona_dir):
    with pytest.raises(FileNotFoundError):
        cr.switch_persona("no_such_persona", decision_hub=None)


def test_persona_create_from_template(persona_dir, monkeypatch):
    # _template.yaml 存在时从模板派生
    (persona_dir / "_template.yaml").write_text(
        "name: 人格名称\nfull_name: 英文名\ndescription: \"简短描述\"\nweights:\n  jingliu: 0.0\n",
        encoding="utf-8",
    )
    result = cr.create_persona({"id": "yingge", "name": "莺歌态", "full_name": "Yingge", "description": "夜莺与歌"})
    assert result["id"] == "yingge"
    cfg = yaml.safe_load((persona_dir / "yingge.yaml").read_text(encoding="utf-8"))
    assert cfg["name"] == "莺歌态"
    assert cfg["weights"] == {"jingliu": 0.0}  # 模板结构保留

    with pytest.raises(ValueError, match="已存在"):
        cr.create_persona({"id": "yingge", "name": "x"})
    with pytest.raises(ValueError, match="小写"):
        cr.create_persona({"id": "Bad ID", "name": "x"})


def test_persona_create_copy_existing(persona_dir):
    result = cr.create_persona({"id": "feixue_copy", "template": "normal", "name": "副本态"})
    assert result["template"] == "normal"
    cfg = yaml.safe_load((persona_dir / "feixue_copy.yaml").read_text(encoding="utf-8"))
    assert cfg["name"] == "副本态"
    assert cfg["prompt"] == "第一行。\n第二行。\n"  # 源卡内容带过来


def test_persona_delete_protections(persona_dir, tmp_path, monkeypatch):
    last_form = tmp_path / "last_form.json"
    last_form.write_text(json.dumps({"current_form": "normal"}), encoding="utf-8")
    monkeypatch.setattr(cr, "_LAST_FORM_PATH", last_form)

    with pytest.raises(ValueError, match="默认"):
        cr.delete_persona("normal")
    cr.create_persona({"id": "temp_card", "template": "normal"})
    with pytest.raises(FileNotFoundError):
        cr.delete_persona("ghost")
    cr.delete_persona("temp_card")
    assert not (persona_dir / "temp_card.yaml").exists()
    assert list(cr._BACKUP_DIR.glob("temp_card.yaml.*.bak"))  # 备份保留


# ── form_names 双文件同步 ──

def _read_form_names(persona_dir):
    text_cfg = json.loads(cr._TEXT_CONFIG_PATH.read_text(encoding="utf-8"))["form_names"]
    base = yaml.safe_load(cr._BASE_YAML_PATH.read_text(encoding="utf-8"))["form_names"]
    return text_cfg, base


def test_form_names_sync_on_create_and_rename(persona_dir):
    # 新建 → 两处 form_names 追加
    result = cr.create_persona({"id": "yingge", "name": "莺歌态", "template": "normal"})
    assert set(result["synced_files"]) == {"text_config.json", "_base.yaml"}
    text_cfg, base = _read_form_names(persona_dir)
    assert text_cfg["yingge"] == "莺歌态"
    assert base["yingge"] == "莺歌态"
    # _base.yaml 注释保留
    assert "# 核心灵魂配置" in cr._BASE_YAML_PATH.read_text(encoding="utf-8")
    # 既有条目不动
    assert text_cfg["feixue"] == "绯雪态"

    # 改名 → 两处同步更新
    cr.save_persona_form("yingge", {"name": "夜莺态"})
    text_cfg, base = _read_form_names(persona_dir)
    assert text_cfg["yingge"] == "夜莺态"
    assert base["yingge"] == "夜莺态"

    # 只改 prompt 不触发同步
    result = cr.save_persona_form("yingge", {"prompt": "新提示词"})
    assert result["synced_files"] == []


def test_form_names_sync_on_delete(persona_dir):
    cr.create_persona({"id": "yingge", "name": "莺歌态", "template": "normal"})
    cr.delete_persona("yingge")
    text_cfg, base = _read_form_names(persona_dir)
    assert "yingge" not in text_cfg
    assert "yingge" not in base
    # 其它条目保留
    assert "normal" in text_cfg and "feixue" in base


def test_form_names_sync_preserves_compact_format(persona_dir, tmp_path):
    # 文件其余部分的手写紧凑格式（内联单行 dict）不能被重排
    compact = tmp_path / "text_config.json"
    compact.write_text(
        '{\n    "form_names": {\n        "normal": "普通态"\n    },\n'
        '    "time_periods": {"late_night": {"range": [0, 6], "label": "深夜"}}\n}\n',
        encoding="utf-8",
    )
    cr._TEXT_CONFIG_PATH = compact
    cr._sync_form_names("yingge", "莺歌态")
    raw = compact.read_text(encoding="utf-8")
    assert '"time_periods": {"late_night": {"range": [0, 6], "label": "深夜"}}' in raw  # 内联格式保留
    assert '"yingge": "莺歌态"' in raw
    data = json.loads(raw)
    assert data["form_names"]["yingge"] == "莺歌态"

    # 删除最后条目 → 前驱尾逗号被正确移除，仍合法 JSON
    cr._sync_form_names("yingge", None, remove=True)
    raw = compact.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert "yingge" not in data["form_names"]
    assert data["form_names"] == {"normal": "普通态"}


def test_form_names_noop_when_missing_section(tmp_path, monkeypatch):
    # form_names 节不存在时静默跳过，不炸；所有目标文件都必须隔离
    pdir = tmp_path / "personalities"
    pdir.mkdir()
    (pdir / "normal.yaml").write_text("name: 普通态\n", encoding="utf-8")
    monkeypatch.setattr(cr, "_PERSONA_DIR", pdir)
    monkeypatch.setattr(cr, "_BASE_YAML_PATH", pdir / "_base.yaml")
    monkeypatch.setattr(cr, "_TEXT_CONFIG_PATH", tmp_path / "no_text_config.json")
    monkeypatch.setattr(cr, "_BACKUP_DIR", tmp_path / "backup")
    result = cr._sync_form_names("someone", "某形态")
    assert result["synced_files"] == []
    assert not (tmp_path / "no_text_config.json").exists()


# ── secret 字段 ──

def test_form_secret_masked_and_placeholder_skip(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "tts_config.json").write_text(
        json.dumps({"engines": {"api_tts": {"api_key": "sk-real-secret-9876"}}}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(cr, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cr, "_BACKUP_DIR", tmp_path / "backup")

    # overview 只回掩码
    forms = {f["id"]: f for f in cr.get_forms_overview()}
    field = next(f for f in forms["tts_engines"]["fields"] if f["key"] == "engines.api_tts.api_key")
    assert "****" in field["value"]
    assert "sk-real-secret-9876" not in json.dumps(forms)

    # 掩码占位提交 → 不修改
    cr.save_form_values("tts_engines", {"engines.api_tts.api_key": field["value"]})
    data = json.loads((cfg_dir / "tts_config.json").read_text(encoding="utf-8"))
    assert data["engines"]["api_tts"]["api_key"] == "sk-real-secret-9876"

    # 新值 → 覆盖
    cr.save_form_values("tts_engines", {"engines.api_tts.api_key": "sk-brand-new"})
    data = json.loads((cfg_dir / "tts_config.json").read_text(encoding="utf-8"))
    assert data["engines"]["api_tts"]["api_key"] == "sk-brand-new"


# ── 管理账号 ──

def test_superadmins_roundtrip(permissions_file):
    loaded = cr.load_superadmins()
    assert loaded["佳"]["ids"]["qq"] == ["10001"]

    cr.save_superadmins(
        {
            "佳": {
                "name": "佳",
                "ids": {"qq": ["10001"], "telegram": "42, 43", "webchat": []},
            }
        }
    )
    saved = json.loads(permissions_file.read_text(encoding="utf-8"))
    assert saved["version"] == "1.0.0"  # 其它节保留
    assert saved["superadmins"]["佳"]["ids"]["telegram"] == ["42", "43"]  # 字符串自动拆分
    assert "webchat" not in saved["superadmins"]["佳"]["ids"]  # 空列表剔除


def test_superadmins_rejects_empty(permissions_file):
    with pytest.raises(ValueError):
        cr.save_superadmins({})


# ── 模型池 ──

def test_models_list_skips_templates(multi_model_file):
    data = cr.list_models_data()
    ids = [m["id"] for m in data["models"]]
    assert "main_model" in ids
    assert "_custom_proxy_example" not in ids
    assert data["active"] == "main_model"


def test_model_save_new_and_edit(multi_model_file):
    # 新增
    result = cr.save_model_form("my_proxy", {"name": "k2", "base_url": "https://x/v1", "env_key": "MY_KEY"})
    assert result["created"] is True
    cfg = json.loads(multi_model_file.read_text(encoding="utf-8"))
    assert cfg["models"]["my_proxy"]["capabilities"] == ["simple_chat"]
    assert cfg["models"]["my_proxy"]["provider"] == "openai"  # 默认值

    # 编辑保留非表单字段
    cr.save_model_form("main_model", {"name": "renamed", "base_url": "https://api.test/v2", "disabled": False})
    cfg = json.loads(multi_model_file.read_text(encoding="utf-8"))
    m = cfg["models"]["main_model"]
    assert m["name"] == "renamed"
    assert m["capabilities"] == ["simple_chat", "tool_calling"]  # 保留
    assert "cost_per_1k_tokens" in m  # 保留
    assert "disabled" not in m  # False 不写入


def test_model_save_rejects_bad_input(multi_model_file):
    with pytest.raises(ValueError):
        cr.save_model_form("bad id!", {})
    with pytest.raises(ValueError):
        cr.save_model_form("_reserved", {})
    with pytest.raises(ValueError):
        cr.save_model_form("ok_id", {"name": "", "base_url": ""})


def test_model_delete_guards_and_cleans_routing(multi_model_file):
    with pytest.raises(ValueError, match="激活"):
        cr.delete_model("main_model")
    cr.set_active_model("_custom_proxy_example") or None  # 模板不在列表但可用于切换测试
    # 直接把 active 切到模板外的合法模型后再删
    cr.save_model_form("second", {"name": "s", "base_url": "https://s/v1"})
    cr.set_active_model("second")
    cfg = json.loads(multi_model_file.read_text(encoding="utf-8"))
    cfg["routing_strategy"]["simple_chat"]["fallback"] = "main_model"
    multi_model_file.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    cr.delete_model("main_model")
    cfg = json.loads(multi_model_file.read_text(encoding="utf-8"))
    assert "main_model" not in cfg["models"]
    assert "fallback" not in cfg["routing_strategy"]["simple_chat"]  # 路由引用已清理


def test_routing_validation(multi_model_file):
    result = cr.save_routing({"simple_chat": {"primary": "@active", "secondary": "ghost_model", "fallback": "main_model"}})
    # 未知模型 ghost_model 被剔除
    assert result["routing"]["simple_chat"] == {"primary": "@active", "fallback": "main_model"}
    with pytest.raises(ValueError):
        cr.save_routing({})


def test_model_inline_api_key_masked(multi_model_file):
    # 直存 key
    cr.save_model_form("proxy_a", {"name": "p", "base_url": "https://x/v1", "api_key": "sk-inline-secret-0000"})
    cfg = json.loads(multi_model_file.read_text(encoding="utf-8"))
    assert cfg["models"]["proxy_a"]["api_key"] == "sk-inline-secret-0000"

    # 掩码占位不覆盖已有 key
    cr.save_model_form("proxy_a", {"name": "p", "base_url": "https://x/v1", "api_key": "sk-i****0000"})
    cfg = json.loads(multi_model_file.read_text(encoding="utf-8"))
    assert cfg["models"]["proxy_a"]["api_key"] == "sk-inline-secret-0000"

    # 空值保留已有 key
    cr.save_model_form("proxy_a", {"name": "p", "base_url": "https://x/v1", "api_key": ""})
    cfg = json.loads(multi_model_file.read_text(encoding="utf-8"))
    assert cfg["models"]["proxy_a"]["api_key"] == "sk-inline-secret-0000"

    # 列表只回掩码，不回明文
    data = cr.list_models_data()
    entry = next(m for m in data["models"] if m["id"] == "proxy_a")
    assert entry["key_source"] == "inline"
    assert "****" in entry["api_key_masked"]
    assert "sk-inline-secret-0000" not in json.dumps(data)


# ── 通用表单 ──

def test_forms_overview_with_values(form_files):
    forms = {f["id"]: f for f in cr.get_forms_overview()}
    tts_fields = {f["key"]: f for f in forms["tts"]["fields"]}
    assert tts_fields["enabled"]["value"] is True
    assert tts_fields["preferred_engine"]["value"] == "gpt_sovits"


def test_form_save_json_preserves_extra_and_crlf(form_files):
    cr.save_form_values("tts", {"enabled": False, "preferred_engine": "api_tts"})
    raw = (form_files / "tts_config.json").read_text(encoding="utf-8")
    data = json.loads(raw)
    assert data["enabled"] is False
    assert data["preferred_engine"] == "api_tts"
    assert data["unknown_extra"] == "keep-me"  # 未知节保留


def test_form_save_yaml_preserves_comments_and_crlf(form_files):
    cr.save_form_values("proactive", {"proactive_chat.enabled": False, "proactive_chat.check_interval": 60})
    with open(form_files / "proactive_chat.yaml", "r", encoding="utf-8", newline="") as f:
        raw = f.read()
    assert "# 主动聊天配置" in raw  # 注释保留
    assert "# 启用" in raw
    assert "\r\n" in raw  # CRLF 保留
    cfg = yaml.safe_load(raw)
    assert cfg["proactive_chat"]["enabled"] is False
    assert cfg["proactive_chat"]["check_interval"] == 60
    assert cfg["proactive_chat"]["quiet_hours"] == [23, 0]  # 其它字段保留


def test_form_save_rejects_bad_values(form_files):
    with pytest.raises(ValueError, match="布尔"):
        cr.save_form_values("tts", {"enabled": "yes"})
    with pytest.raises(ValueError, match="之一"):
        cr.save_form_values("tts", {"preferred_engine": "not_an_engine"})
    with pytest.raises(ValueError, match="不能小于"):
        cr.save_form_values("tts", {"qq_max_message_length": 5})
    # 校验失败不落盘
    assert json.loads((form_files / "tts_config.json").read_text(encoding="utf-8"))["enabled"] is True


def test_form_ignores_unknown_keys_and_noop(form_files):
    # schema 之外的 key 静默忽略；全部无效时不落盘不备份
    before = (form_files / "proactive_chat.yaml").read_text(encoding="utf-8")
    result = cr.save_form_values("proactive", {"proactive_chat.no_such_field": 1})
    assert result["updated_fields"] == []
    assert (form_files / "proactive_chat.yaml").read_text(encoding="utf-8") == before


def test_replace_nested_yaml_scalar_crlf():
    text = "a:\r\n  b: 1\r\n"
    out = cr._replace_nested_yaml_scalar(text, "a.b", 2)
    assert out == "a:\r\n  b: 2\r\n"  # 尾部换行保留
    assert cr._replace_nested_yaml_scalar(text, "a.missing", 2) is None


# ── web_search 表单指向 qq_config.yaml（真实消费源） ──

def test_web_search_form_targets_qq_config(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "qq_config.yaml").write_text(
        "# QQ 主配置\nqq:\n  connect: true\n\nweb_search:\n"
        "  timeout: 10  # 搜索超时\n  crawl_timeout: 30\n"
        "  query_expansion:\n    enabled: true\n    max_queries: 4\n    bilingual: true\n"
        "  result_cache:\n    enabled: true\n    ttl_seconds: 1800\n    max_entries: 256\n"
        "  scihub:\n    enabled: false\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cr, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cr, "_BACKUP_DIR", tmp_path / "backup")

    # 表单 schema 指向 qq_config.yaml
    assert cr.GENERIC_FORMS["web_search"]["file"] == "qq_config.yaml"

    # 嵌套字段保存：注释与其它节保留
    cr.save_form_values("web_search", {
        "web_search.timeout": 20,
        "web_search.query_expansion.max_queries": 6,
        "web_search.result_cache.enabled": False,
    })
    raw = (cfg_dir / "qq_config.yaml").read_text(encoding="utf-8")
    assert "# QQ 主配置" in raw and "# 搜索超时" in raw
    cfg = yaml.safe_load(raw)
    assert cfg["web_search"]["timeout"] == 20
    assert cfg["web_search"]["query_expansion"]["max_queries"] == 6
    assert cfg["web_search"]["result_cache"]["enabled"] is False
    assert cfg["web_search"]["crawl_timeout"] == 30  # 未改字段保留
    assert cfg["qq"] == {"connect": True}


# ── QQ 超管双源联动 ──

def test_superadmin_dual_source_linkage(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("QQ_SUPERADMIN_QQ=10001\n", encoding="utf-8")
    perm = tmp_path / "permissions.json"
    perm.write_text(
        json.dumps({"superadmins": {"佳": {"name": "佳", "ids": {"qq": ["10001"]}}}}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(cr, "_ENV_PATH", env_path)
    monkeypatch.setattr(cr, "_PERMISSIONS_PATH", perm)
    monkeypatch.setattr(cr, "_BACKUP_DIR", tmp_path / "backup")

    # 面板改超管 → .env 联动
    cr.save_superadmins({"佳": {"name": "佳", "ids": {"qq": ["20002"], "desktop": ["default"]}}})
    assert "QQ_SUPERADMIN_QQ=20002" in env_path.read_text(encoding="utf-8")

    # .env 改超管 → permissions 联动
    cr.update_env_value("QQ_SUPERADMIN_QQ", "30003")
    saved = json.loads(perm.read_text(encoding="utf-8"))
    assert saved["superadmins"]["佳"]["ids"]["qq"] == ["30003"]
    assert saved["superadmins"]["佳"]["ids"]["desktop"] == ["default"]  # 其它平台不动

    # 非超管键不触发联动
    cr.update_env_value("TAVILY_API_KEY", "sk-x")
    assert json.loads(perm.read_text(encoding="utf-8"))["superadmins"]["佳"]["ids"]["qq"] == ["30003"]


# ── qq_config 深层节 + list/textarea/text-preserve ──

@pytest.fixture()
def qq_deep_config(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "qq_config.yaml").write_text(
        "# QQ 主配置\nqq:\n"
        "  connection:\n    ping_interval: 20  # 心跳\n"
        "  features:\n    poke_reply: true\n    passive_chat: true\n"
        "  access_control:\n    enabled: false\n    group_whitelist: []\n    user_blacklist: [\"111\", \"222\"]\n"
        "  commands:\n    prefix: \"/\"\n",
        encoding="utf-8",
    )
    text_cfg = cfg_dir / "text_config.json"
    with open(text_cfg, "w", encoding="utf-8", newline="") as f:
        f.write('{\n    "identity_anchor": "旧锚点",\n    "time_periods": {"late_night": {"range": [0, 6]}}\n}\n')
    monkeypatch.setattr(cr, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cr, "_BACKUP_DIR", tmp_path / "backup")
    return cfg_dir


def test_qq_deep_forms_roundtrip(qq_deep_config):
    # 深层嵌套 bool/int 保存，注释保留
    cr.save_form_values("qq_behavior", {"qq.connection.ping_interval": 30})
    cr.save_form_values("qq_features", {"qq.features.poke_reply": False, "qq.commands.prefix": "!"})
    cfg = yaml.safe_load((qq_deep_config / "qq_config.yaml").read_text(encoding="utf-8"))
    assert cfg["qq"]["connection"]["ping_interval"] == 30
    assert cfg["qq"]["features"]["poke_reply"] is False
    assert cfg["qq"]["commands"]["prefix"] == "!"
    assert "# 心跳" in (qq_deep_config / "qq_config.yaml").read_text(encoding="utf-8")


def test_list_field_roundtrip(qq_deep_config):
    # list 类型：逗号分隔字符串 ↔ yaml list，空串 = 清空
    cr.save_form_values("qq_access", {
        "qq.access_control.group_whitelist": "100, 200, 300",
        "qq.access_control.user_blacklist": "",
    })
    cfg = yaml.safe_load((qq_deep_config / "qq_config.yaml").read_text(encoding="utf-8"))
    ac = cfg["qq"]["access_control"]
    assert ac["group_whitelist"] == ["100", "200", "300"]
    assert ac["user_blacklist"] == []
    # overview 回显为逗号字符串
    forms = {f["id"]: f for f in cr.get_forms_overview()}
    gw = next(x for x in forms["qq_access"]["fields"] if x["key"] == "qq.access_control.group_whitelist")
    assert gw["value"] == "100, 200, 300"


def test_text_preserve_json_no_reformat(qq_deep_config):
    # text-preserve：顶层键替换不重排紧凑内联风格
    cr.save_form_values("persona_identity", {"identity_anchor": "新锚点内容"})
    with open(qq_deep_config / "text_config.json", "r", encoding="utf-8", newline="") as f:
        raw = f.read()
    assert '"time_periods": {"late_night": {"range": [0, 6]}}' in raw  # 内联格式原样保留
    data = json.loads(raw)
    assert data["identity_anchor"] == "新锚点内容"
