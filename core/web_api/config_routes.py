"""结构化配置面板 API — 调谐「配置」板块

为桌面前端提供 API Key(.env) / 人设卡(personalities/*.yaml) / 管理账号(permissions.json)
的表单化读写能力，替代手动进 config/ 目录改文件。

安全原则:
- 敏感值（API Key / Token）永不回传明文，只返回掩码
- 所有写入先备份到 config/backup/panel/，再原子写（临时文件 + os.replace）
- .env 更新后同步 os.environ，保证 get_api_key() 无须重启即读到新值
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from fastapi import APIRouter, HTTPException

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    APIRouter = object
    HTTPException = Exception

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = _PROJECT_ROOT / "config" / ".env"
_PERSONA_DIR = _PROJECT_ROOT / "config" / "personalities"
_BASE_YAML_PATH = _PERSONA_DIR / "_base.yaml"
_TEXT_CONFIG_PATH = _PROJECT_ROOT / "config" / "text_config.json"
_PERMISSIONS_PATH = _PROJECT_ROOT / "config" / "permissions.json"
_LAST_FORM_PATH = _PROJECT_ROOT / "data" / "last_form.json"
_BACKUP_DIR = _PROJECT_ROOT / "config" / "backup" / "panel"
_BACKUP_KEEP = 20
_MULTI_MODEL_PATH = _PROJECT_ROOT / "config" / "multi_model_config.json"


def _detect_eol(raw: str) -> str:
    return "\r\n" if "\r\n" in raw else "\n"


def _read_text_raw(path: Path) -> str:
    """原样读取（不做 universal newline 转换），保留文件的 CRLF/LF 风格供写回时检测"""
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def _atomic_write(path: Path, content: str) -> None:
    """原子写入：先写临时文件再替换，避免运行中的进程读到半截文件"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8", newline="")
    os.replace(tmp, path)

# .env 中适合在面板配置的 Key 分组（不含调试类内部变量）
ENV_KEY_GROUPS: List[Dict[str, Any]] = [
    {
        "group": "AI 模型",
        "keys": [
            {"key": "OPENAI_API_KEY", "label": "OpenAI"},
            {"key": "DEEPSEEK_API_KEY", "label": "DeepSeek"},
            {"key": "ZHIPU_API_KEY", "label": "智谱 GLM"},
            {"key": "SILICONFLOW_API_KEY", "label": "硅基流动"},
            {"key": "DASHSCOPE_API_KEY", "label": "阿里 DashScope"},
            {"key": "GROK_API_KEY", "label": "Grok"},
            {"key": "MOONSHOT_API_KEY", "label": "月之暗面 Kimi"},
            {"key": "PROXY_API_KEY", "label": "中转 API (PROXY)"},
        ],
        "effect": "instant",
    },
    {
        "group": "平台接入",
        "keys": [
            {"key": "QQ_APPID", "label": "QQ 官方 AppID"},
            {"key": "QQ_SECRET", "label": "QQ 官方 Secret"},
            {"key": "QQ_BOT_QQ", "label": "QQ 机器人号"},
            {"key": "QQ_SUPERADMIN_QQ", "label": "QQ 超管号"},
            {"key": "QQ_ONEBOT_WS_URL", "label": "OneBot WS 地址"},
            {"key": "QQ_ONEBOT_TOKEN", "label": "OneBot Token"},
            {"key": "DISCORD_BOT_TOKEN", "label": "Discord Token"},
            {"key": "SLACK_BOT_TOKEN", "label": "Slack Token"},
            {"key": "KOOK_TOKEN", "label": "KOOK Token"},
            {"key": "LARK_APP_ID", "label": "飞书 AppID"},
            {"key": "LARK_APP_SECRET", "label": "飞书 Secret"},
            {"key": "DINGTALK_APP_KEY", "label": "钉钉 AppKey"},
            {"key": "DINGTALK_APP_SECRET", "label": "钉钉 Secret"},
            {"key": "WECOM_CORP_ID", "label": "企业微信 CorpID"},
            {"key": "WECOM_SECRET", "label": "企业微信 Secret"},
        ],
        "effect": "restart",
    },
    {
        "group": "工具服务",
        "keys": [
            {"key": "TAVILY_API_KEY", "label": "Tavily 搜索"},
            {"key": "GITHUB_TOKEN", "label": "GitHub Token"},
            {"key": "SENIVERSE_API_KEY", "label": "心知天气"},
            {"key": "PIXIV_COOKIE", "label": "Pixiv Cookie"},
            {"key": "NOVELAI_API_KEY", "label": "NovelAI"},
        ],
        "effect": "instant",
    },
]

# 人设卡表单可编辑的顶层字段
PERSONA_EDITABLE_SCALARS = ("name", "full_name", "description")


# ── 通用工具 ──────────────────────────────────────────────

def _mask_secret(value: str) -> str:
    """敏感值掩码：保留首尾各 4 位，中间打码；短值全打码"""
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"


def _read_env_values() -> Dict[str, str]:
    """读取 .env 原始键值（仅内部使用，不直接下发明文）"""
    values: Dict[str, str] = {}
    if not _ENV_PATH.exists():
        return values
    try:
        for raw in _ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, val = line.split("=", 1)
            values[name.strip()] = val.strip().strip("\"'")
    except OSError as e:
        logger.warning(f"[ConfigPanel] 读取 .env 失败: {e}")
    return values


def update_env_value(key: str, value: str, linkage: bool = True) -> bool:
    """更新 .env 中单个 KEY（行级替换，保留注释与顺序），并同步 os.environ。

    linkage=False 时跳过超管联动（内部调用防止递归）。

    Returns:
        是否写入成功
    """
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
        raise ValueError(f"非法的环境变量名: {key}")
    value = value.strip()
    if not value:
        raise ValueError("值不能为空（如需删除请手动编辑 config/.env）")

    lines = _ENV_PATH.read_text(encoding="utf-8").splitlines() if _ENV_PATH.exists() else []
    replaced = False
    out: List[str] = []
    for line in lines:
        stripped = line.strip()
        if not replaced and not stripped.startswith("#") and "=" in stripped:
            name = stripped.split("=", 1)[0].strip()
            if name == key:
                _backup_file(_ENV_PATH)
                out.append(f"{key}={value}")
                replaced = True
                continue
        out.append(line)
    if not replaced:
        _backup_file(_ENV_PATH)
        out.append(f"{key}={value}")

    _atomic_write(_ENV_PATH, "\n".join(out) + "\n")
    # get_api_key() 优先读 os.environ，必须同步才能不重启生效
    os.environ[key] = value
    logger.info(f"[ConfigPanel] 环境变量已更新: {key}")

    # QQ 超管双源联动：.env 的 QQ_SUPERADMIN_QQ 与 permissions.json superadmins 保持一致
    if linkage and key == "QQ_SUPERADMIN_QQ":
        _sync_superadmin_to_permissions(value)
    return True


def _sync_superadmin_to_permissions(qq_id: str) -> bool:
    """把 .env QQ_SUPERADMIN_QQ 的值回写到 permissions.json 已有超管的 qq 列表"""
    if not _PERMISSIONS_PATH.exists():
        return False
    try:
        cfg = json.loads(_read_text_raw(_PERMISSIONS_PATH))
        changed = False
        for info in (cfg.get("superadmins") or {}).values():
            ids = info.get("ids") or {}
            if "qq" in ids and ids["qq"] != [qq_id]:
                ids["qq"] = [qq_id]
                changed = True
                break  # 只更新第一个定义了 qq 的超管，与 .env 单值语义一致
        if changed:
            _backup_file(_PERMISSIONS_PATH)
            _atomic_write(_PERMISSIONS_PATH, json.dumps(cfg, ensure_ascii=False, indent=2))
            logger.info("[ConfigPanel] permissions.json 超管 qq 已随 .env 联动更新")
        return changed
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"[ConfigPanel] 超管联动到 permissions.json 失败: {e}")
        return False


def _sync_superadmin_to_env(superadmins: Dict[str, Any]) -> bool:
    """把 permissions.json 第一个 qq 超管 id 回写到 .env QQ_SUPERADMIN_QQ"""
    for info in (superadmins or {}).values():
        qq_ids = (info.get("ids") or {}).get("qq") or []
        if qq_ids:
            try:
                update_env_value("QQ_SUPERADMIN_QQ", str(qq_ids[0]), linkage=False)
                return True
            except (ValueError, OSError) as e:
                logger.warning(f"[ConfigPanel] 超管联动到 .env 失败: {e}")
                return False
    return False


def _backup_file(path: Path) -> Optional[Path]:
    """写入前备份到 config/backup/panel/，并清理过期备份"""
    if not path.exists():
        return None
    try:
        _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = _BACKUP_DIR / f"{path.name}.{stamp}.bak"
        shutil.copy2(path, backup)
        # 同名快速连续写会撞时间戳，撞了就说明上一次备份内容几乎相同，跳过即可
        backups = sorted(_BACKUP_DIR.glob(f"{path.name}.*.bak"))
        for old in backups[:-_BACKUP_KEEP]:
            old.unlink(missing_ok=True)
        return backup
    except OSError as e:
        logger.warning(f"[ConfigPanel] 备份失败({path.name}): {e}")
        return None


# ── form_names 同步（text_config.json + _base.yaml 双映射） ──

def _update_json_form_names(raw: str, persona_id: str, chinese_name: Optional[str], remove: bool) -> Optional[str]:
    """在 JSON 文本的 form_names 节内做文本级增/改/删，绝不重排文件其余格式。

    Returns:
        更新后的全文；无需变更返回 None；解析异常抛 ValueError
    """
    norm = raw.replace("\r\n", "\n")
    section = re.search(r'^([ \t]*)"form_names"\s*:\s*\{', norm, re.MULTILINE)
    if not section:
        return None
    body_start = section.end()
    depth = 1
    i = body_start
    while i < len(norm) and depth:
        if norm[i] == "{":
            depth += 1
        elif norm[i] == "}":
            depth -= 1
        i += 1
    if depth:
        raise ValueError("form_names 节括号不配对")
    body_end = i - 1
    body = norm[body_start:body_end]

    entry_line = re.compile(rf'^[ \t]*"{re.escape(persona_id)}"\s*:\s*"[^"]*"[ \t]*,?[ \t]*(?:\n|$)', re.MULTILINE)
    entry_inline = re.compile(rf'"{re.escape(persona_id)}"\s*:\s*"[^"]*"')
    existing = entry_line.search(body) or entry_inline.search(body)

    if remove:
        if not existing:
            return None
        body = entry_line.sub("", body, count=1) if entry_line.search(body) else entry_inline.sub("", body, count=1)
        # 删掉行级条目后，悬空尾逗号移除（保留右侧缩进空白）
        stripped = body.rstrip()
        if stripped.endswith(","):
            body = stripped[:-1] + body[len(stripped):]
    elif chinese_name:
        if existing:
            body = entry_inline.sub(f'"{persona_id}": "{chinese_name}"', body, count=1)
        else:
            # 追加到节尾，缩进随节内既有条目（无条目时取节缩进 + 4）；保留尾部空白
            indent_m = re.search(r'\n([ \t]+)"', body)
            indent = indent_m.group(1) if indent_m else section.group(1) + "    "
            stripped = body.rstrip()
            trailing_ws = body[len(stripped):]
            if stripped:
                body = stripped + "," + ("\n" if "\n" in trailing_ws or stripped.endswith("\n") else " ") + indent + f'"{persona_id}": "{chinese_name}"' + trailing_ws
            else:
                body = ("\n" if trailing_ws.startswith("\n") or not trailing_ws.strip() else " ") + indent + f'"{persona_id}": "{chinese_name}"' + trailing_ws
    else:
        return None

    updated = norm[:body_start] + body + norm[body_end:]
    json.loads(updated)  # 结构校验，失败抛异常并放弃写入
    return updated


def _sync_form_names(persona_id: str, chinese_name: Optional[str], remove: bool = False) -> Dict[str, Any]:
    """人设卡中文形态名双向同步。

    - text_config.json 的 form_names：decision_hub 形态命令/显示用（lru_cache，写后清缓存）
    - _base.yaml 的 form_names：人格日志前缀与 prompt 注入用（文本级替换保注释）
    """
    synced: List[str] = []

    # 1) text_config.json（文本级替换，保留手写紧凑格式）
    if _TEXT_CONFIG_PATH.exists():
        try:
            updated = _update_json_form_names(_read_text_raw(_TEXT_CONFIG_PATH), persona_id, chinese_name, remove)
        except json.JSONDecodeError as e:
            raise ValueError(f"text_config.json form_names 替换后解析失败: {e}")
        if updated is not None:
            if _detect_eol(_read_text_raw(_TEXT_CONFIG_PATH)) == "\r\n":
                updated = updated.replace("\n", "\r\n")
            _backup_file(_TEXT_CONFIG_PATH)
            _atomic_write(_TEXT_CONFIG_PATH, updated)
            synced.append("text_config.json")

    # 2) _base.yaml（文本级，保留注释）
    if _BASE_YAML_PATH.exists():
        raw = _read_text_raw(_BASE_YAML_PATH)
        eol = _detect_eol(raw)
        lines = raw.replace("\r\n", "\n").split("\n")

        section_idx = None
        for i, line in enumerate(lines):
            if re.match(r"^form_names:\s*(#.*)?$", line):
                section_idx = i
                break
        if section_idx is not None:
            end = len(lines)
            for i in range(section_idx + 1, len(lines)):
                if lines[i].strip() and not lines[i][0].isspace():
                    end = i
                    break
            entry_pat = re.compile(rf"^[ \t]+{re.escape(persona_id)}:[ \t]*.*$")
            found = None
            for i in range(section_idx + 1, end):
                if entry_pat.match(lines[i]):
                    found = i
                    break

            changed = False
            if remove:
                if found is not None:
                    del lines[found]
                    changed = True
            elif chinese_name:
                entry_line = f'  {persona_id}: "{chinese_name}"'
                if found is not None:
                    if lines[found] != entry_line:
                        lines[found] = entry_line
                        changed = True
                else:
                    insert_at = end
                    while insert_at > section_idx + 1 and not lines[insert_at - 1].strip():
                        insert_at -= 1
                    lines.insert(insert_at, entry_line)
                    changed = True

            if changed:
                import yaml

                updated = eol.join(lines)
                try:
                    yaml.safe_load(updated)
                except yaml.YAMLError as e:
                    raise ValueError(f"_base.yaml 替换后解析失败，已放弃写入: {e}")
                _backup_file(_BASE_YAML_PATH)
                _atomic_write(_BASE_YAML_PATH, updated)
                synced.append("_base.yaml")

    # 3) 清缓存：text_config 的 lru_cache + 人设加载器的 base 缓存
    if synced:
        try:
            from config.config_utils import reload_config

            reload_config()
        except Exception:
            pass
        try:
            from core.personality_loader import get_personality_loader

            loader = get_personality_loader()
            loader._base_config = None
            loader._cache.clear()
        except Exception:
            pass
        logger.info(f"[ConfigPanel] form_names 已同步 ({persona_id} -> {chinese_name or '删除'}): {', '.join(synced)}")
    return {"persona_id": persona_id, "synced_files": synced}


# ── 人设卡 ──────────────────────────────────────────────

def _load_yaml(path: Path) -> Dict[str, Any]:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def list_personas() -> List[Dict[str, Any]]:
    """列出 config/personalities/ 下所有可用角色卡（_ 开头的内部文件除外）"""
    personas: List[Dict[str, Any]] = []
    for yaml_file in sorted(_PERSONA_DIR.glob("*.yaml")):
        if yaml_file.name.startswith("_"):
            continue
        try:
            cfg = _load_yaml(yaml_file)
        except Exception as e:
            logger.warning(f"[ConfigPanel] 解析人设卡失败 {yaml_file.name}: {e}")
            continue
        personas.append(
            {
                "id": yaml_file.stem,
                "name": cfg.get("name", yaml_file.stem),
                "full_name": cfg.get("full_name", ""),
                "description": cfg.get("description", ""),
                "path": str(yaml_file),
            }
        )
    return personas


def get_current_persona_id() -> str:
    """当前激活人设：优先运行中的 Personality 实例，回退 data/last_form.json"""
    try:
        if _LAST_FORM_PATH.exists():
            return json.loads(_LAST_FORM_PATH.read_text(encoding="utf-8")).get("current_form", "normal")
    except Exception:
        pass
    return "normal"


def get_persona_detail(name: str) -> Dict[str, Any]:
    """读取单张人设卡的表单字段 + YAML 源码"""
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", name):
        raise ValueError(f"非法的人设卡名称: {name}")
    path = _PERSONA_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"人设卡不存在: {name}")
    cfg = _load_yaml(path)
    speaking = cfg.get("speaking", {}) or {}
    return {
        "id": name,
        "name": cfg.get("name", name),
        "full_name": cfg.get("full_name", ""),
        "description": cfg.get("description", ""),
        "prompt": cfg.get("prompt", ""),
        "speaking_style": speaking.get("style", ""),
        "max_sentences": speaking.get("max_sentences", ""),
        "source": path.read_text(encoding="utf-8"),
        "path": str(path),
    }


_YAML_SAFE_SCALAR = re.compile(r"^\w[\w\-./、· ]*$")


def _yaml_scalar_repr(value: Any) -> str:
    """把标量序列化为安全的 YAML 字面量（str 含特殊字符时自动加引号，list 用流式数组）"""
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return '""'
    if isinstance(value, (int, float)):
        return str(value)
    import yaml

    if isinstance(value, list):
        return yaml.safe_dump(value, default_flow_style=True, allow_unicode=True).strip()
    s = str(value)
    if _YAML_SAFE_SCALAR.match(s):
        return s
    return yaml.safe_dump(s, default_flow_style=True, allow_unicode=True).strip()


def _replace_yaml_scalar(text: str, key: str, new_value: str, quoted: bool = False) -> Optional[str]:
    """替换顶层标量字段行（保留行内注释）；找不到返回 None（由调用方决定是否追加）。

    quoted=True 用于自由文本（description 等），强制加引号防内容中的标点破坏结构。
    """
    pattern = re.compile(rf"^{re.escape(key)}:[ \t]*(.*?)([ \t]+#.*)?$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return None
    value_repr = json.dumps(str(new_value), ensure_ascii=False) if quoted else _yaml_scalar_repr(new_value)
    replacement = f"{key}: {value_repr}"
    if match.group(2):  # 保留行内注释
        replacement += match.group(2)
    return text[: match.start()] + replacement + text[match.end() :]


def _replace_yaml_block(text: str, key: str, new_value: str) -> str:
    """替换 `key: |` 字面量块（到下一个顶层键为止）；不存在则追加到文件末尾。

    采用文本级替换而非 yaml dump，保留原文件的注释与其余字段格式。
    """
    lines = text.splitlines()
    start = end = None
    indent = "  "
    for i, line in enumerate(lines):
        if re.match(rf"^{re.escape(key)}:\s*\|", line):
            start = i
            break
    if start is not None:
        for j in range(start + 1, len(lines)):
            if lines[j].strip():
                m = re.match(r"^(\s+)", lines[j])
                indent = m.group(1) if m else "  "
                break
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if lines[j].strip() and not lines[j][0].isspace():
                end = j
                break
    else:
        start = end = len(lines)

    block = [f"{key}: |"]
    block.extend((indent + ln) if ln.strip() else "" for ln in new_value.splitlines())
    result = lines[:start] + block + lines[end:]
    return "\n".join(result) + "\n"


def save_persona_form(name: str, form: Dict[str, Any]) -> Dict[str, Any]:
    """保存人设卡表单字段（文本级替换，保留注释），返回新源码预览"""
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", name):
        raise ValueError(f"非法的人设卡名称: {name}")
    path = _PERSONA_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"人设卡不存在: {name}")

    text = path.read_text(encoding="utf-8")

    # 先做纯文本校验，任何字段非法都不落盘
    new_prompt = form.get("prompt")
    if new_prompt is not None and not str(new_prompt).strip():
        raise ValueError("prompt 不能为空")

    updates: List[str] = []
    for field in PERSONA_EDITABLE_SCALARS:
        val = form.get(field)
        if val is None or str(val).strip() == "":
            continue
        updated = _replace_yaml_scalar(text, field, str(val).strip(), quoted=(field == "description"))
        if updated is None:
            # 文件里本没有该字段：追加在文件头部 name 字段之后或文件末尾
            append_line = f'{field}: "{str(val).strip()}"' if field == "description" else f"{field}: {str(val).strip()}"
            text = text.rstrip("\n") + "\n" + append_line + "\n"
        else:
            text = updated
        updates.append(field)

    if new_prompt is not None:
        text = _replace_yaml_block(text, "prompt", str(new_prompt).rstrip())
        updates.append("prompt")

    # 校验改完还是合法 YAML，防止文本替换把结构弄坏
    import yaml

    try:
        yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ValueError(f"替换后 YAML 解析失败，已放弃写入: {e}")

    _backup_file(path)
    _atomic_write(path, text)
    logger.info(f"[ConfigPanel] 人设卡已保存: {name} ({', '.join(updates) or '无字段变更'})")

    # 改了形态名 → 同步两处 form_names 映射
    sync_result: Dict[str, Any] = {"synced_files": []}
    if "name" in updates:
        try:
            sync_result = _sync_form_names(name, str(form.get("name", "")).strip())
        except ValueError as e:
            raise ValueError(f"人设卡已保存，但 form_names 同步失败: {e}")
    return {"id": name, "updated_fields": updates, "source": text, **sync_result}


def create_persona(form: Dict[str, Any]) -> Dict[str, Any]:
    """新建人设卡：默认从 _template.yaml 派生，也可指定 template 复制现有角色卡。

    weights / emotions 等复杂结构由模板或源卡提供，调用方只填基础三样。
    """
    persona_id = str(form.get("id", "")).strip()
    if not re.fullmatch(r"[a-z0-9_\-]+", persona_id or ""):
        raise ValueError("人设卡 ID 只能是小写字母、数字、下划线或连字符（如 my_persona）")
    target = _PERSONA_DIR / f"{persona_id}.yaml"
    if target.exists():
        raise ValueError(f"人设卡已存在: {persona_id}")

    template_name = str(form.get("template", "")).strip()
    if template_name == persona_id:
        raise ValueError("模板不能是它自己")
    if template_name:
        source = _PERSONA_DIR / f"{template_name}.yaml"
        if not source.exists():
            raise FileNotFoundError(f"模板人设卡不存在: {template_name}")
    else:
        source = _PERSONA_DIR / "_template.yaml"
        if not source.exists():
            raise FileNotFoundError("config/personalities/_template.yaml 不存在，无法新建")

    text = source.read_text(encoding="utf-8")
    # 基础三字段文本级替换；源卡没有的字段追加（模板里的示例值占位会被覆盖）
    for field in PERSONA_EDITABLE_SCALARS:
        val = str(form.get(field, "")).strip()
        if not val:
            continue
        updated = _replace_yaml_scalar(text, field, val, quoted=(field == "description"))
        if updated is None:
            append_line = f'{field}: "{val}"' if field == "description" else f"{field}: {val}"
            text = text.rstrip("\n") + "\n" + append_line + "\n"
        else:
            text = updated

    import yaml

    try:
        yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ValueError(f"生成的人设卡 YAML 不合法: {e}")

    _atomic_write(target, text)
    sync = {"synced_files": []}
    try:
        sync = _sync_form_names(persona_id, str(form.get("name", "")).strip() or None)
    except ValueError as e:
        raise ValueError(f"人设卡已创建，但 form_names 同步失败: {e}")
    logger.info(f"[ConfigPanel] 人设卡已新建: {persona_id} (模板: {template_name or '_template'})")
    return {"id": persona_id, "template": template_name or "_template", **sync}


def delete_persona(name: str) -> Dict[str, Any]:
    """删除人设卡（默认卡 normal 与当前激活卡不可删；备份后删除）"""
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", name or ""):
        raise ValueError(f"非法的人设卡名称: {name}")
    if name == "normal":
        raise ValueError("normal 是默认人设卡，不能删除")
    if name == get_current_persona_id():
        raise ValueError("不能删除当前激活的人设卡，请先切换到其它形态")
    path = _PERSONA_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"人设卡不存在: {name}")
    _backup_file(path)
    path.unlink()
    try:
        _sync_form_names(name, None, remove=True)
    except ValueError as e:
        raise ValueError(f"人设卡已删除，但 form_names 清理失败: {e}")
    logger.info(f"[ConfigPanel] 人设卡已删除: {name}")
    return {"id": name}


def switch_persona(name: str, decision_hub: Any = None) -> Dict[str, Any]:
    """切换激活人设：优先热切换运行中的 Personality，回退写 last_form.json"""
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", name):
        raise ValueError(f"非法的人设卡名称: {name}")
    if not (_PERSONA_DIR / f"{name}.yaml").exists():
        raise FileNotFoundError(f"人设卡不存在: {name}")

    hot = False
    personality = getattr(decision_hub, "personality", None) if decision_hub else None
    if personality is not None:
        try:
            hot = bool(personality.set_form(name))
        except Exception as e:
            logger.warning(f"[ConfigPanel] 热切换失败，回退持久化文件: {e}")

    if not hot:
        state = {}
        if _LAST_FORM_PATH.exists():
            try:
                state = json.loads(_LAST_FORM_PATH.read_text(encoding="utf-8"))
            except Exception:
                state = {}
        state["current_form"] = name
        _atomic_write(_LAST_FORM_PATH, json.dumps(state, ensure_ascii=False, indent=2))

    return {"id": name, "hot_switched": hot, "message": "热切换成功，立即生效" if hot else "已写入启动配置，重启后生效"}


# ── 管理账号（超管） ──────────────────────────────────────

def load_superadmins() -> Dict[str, Any]:
    """读取 permissions.json 的 superadmins 节"""
    if not _PERMISSIONS_PATH.exists():
        return {}
    try:
        cfg = json.loads(_PERMISSIONS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"[ConfigPanel] 读取 permissions.json 失败: {e}")
        return {}
    return cfg.get("superadmins", {})


def save_superadmins(superadmins: Dict[str, Any]) -> Dict[str, Any]:
    """全量保存 superadmins 节（保留 permissions.json 其它部分）。

    统一权限引擎每次 check 都会重读文件，保存即生效。
    """
    if not _PERMISSIONS_PATH.exists():
        raise FileNotFoundError("config/permissions.json 不存在")
    cfg = json.loads(_PERMISSIONS_PATH.read_text(encoding="utf-8"))

    cleaned: Dict[str, Any] = {}
    for person, info in (superadmins or {}).items():
        if not isinstance(info, dict):
            continue
        ids = {}
        for platform, pid_list in (info.get("ids") or {}).items():
            if isinstance(pid_list, str):
                pid_list = [p.strip() for p in pid_list.split(",") if p.strip()]
            cleaned_ids = [str(p).strip() for p in (pid_list or []) if str(p).strip()]
            if cleaned_ids:
                ids[str(platform)] = cleaned_ids
        if not ids:
            continue
        cleaned[str(person)] = {"name": str(info.get("name", person)), "ids": ids}

    if not cleaned:
        raise ValueError("至少保留一个平台的管理账号，拒绝保存空配置")

    cfg["superadmins"] = cleaned
    _backup_file(_PERMISSIONS_PATH)
    _atomic_write(_PERMISSIONS_PATH, json.dumps(cfg, ensure_ascii=False, indent=2))
    # 双源联动：把第一个 qq 超管同步到 .env QQ_SUPERADMIN_QQ（config_loader 等 5 处消费方读它）
    env_synced = _sync_superadmin_to_env(cleaned)
    logger.info(f"[ConfigPanel] 管理账号已保存: {list(cleaned.keys())}（.env 联动: {'成功' if env_synced else '跳过'}）")
    return cleaned


# ── 模型池配置 (multi_model_config.json) ──────────────────

def _load_multi_model() -> Dict[str, Any]:
    return json.loads(_MULTI_MODEL_PATH.read_text(encoding="utf-8"))


def _save_multi_model(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """保存模型池配置（保留换行风格 + 备份 + 原子写），并尝试热重载单例池"""
    eol = _detect_eol(_read_text_raw(_MULTI_MODEL_PATH))
    _backup_file(_MULTI_MODEL_PATH)
    text = json.dumps(cfg, ensure_ascii=False, indent=2)
    if eol == "\r\n":
        text = text.replace("\n", "\r\n")
    _atomic_write(_MULTI_MODEL_PATH, text)

    hot = False
    try:
        from core.model_pool_manager import get_model_pool

        pool = get_model_pool()
        pool._load_config()
        hot = True
        logger.info("[ConfigPanel] 模型池已热重载")
    except Exception as e:
        logger.warning(f"[ConfigPanel] 模型池热重载失败（重启后生效）: {e}")
    return {"hot_reloaded": hot}


def list_models_data() -> Dict[str, Any]:
    """模型清单 + 当前激活 + 路由策略"""
    cfg = _load_multi_model()
    models = []
    for model_id, m in (cfg.get("models") or {}).items():
        if model_id.startswith("_"):
            continue
        raw_key = str(m.get("api_key", ""))
        models.append(
            {
                "id": model_id,
                "name": m.get("name", model_id),
                "provider": m.get("provider", ""),
                "base_url": m.get("base_url", ""),
                "env_key": m.get("env_key", ""),
                "description": m.get("description", ""),
                "type": m.get("type", "chat"),
                "disabled": bool(m.get("disabled", False)),
                "capabilities": m.get("capabilities", []),
                # Key 来源提示：直存 Key 掩码回显；env_key 只回显变量名
                "api_key_masked": _mask_secret(raw_key) if raw_key else "",
                "key_source": "inline" if raw_key else ("env" if m.get("env_key") else "none"),
            }
        )
    return {
        "active": cfg.get("active", ""),
        "models": models,
        "routing": cfg.get("routing_strategy", {}),
    }


def save_model_form(model_id: str, form: Dict[str, Any]) -> Dict[str, Any]:
    """新增/编辑模型条目（保留 capabilities 等非表单字段）"""
    if not re.fullmatch(r"[a-zA-Z0-9_\-]+", model_id):
        raise ValueError(f"非法的模型 ID: {model_id}")
    cfg = _load_multi_model()
    models = cfg.setdefault("models", {})

    existing = models.get(model_id, {})
    if model_id.startswith("_"):
        raise ValueError("下划线开头的 ID 保留给系统模板，请换一个")

    name = str(form.get("name", "")).strip()
    base_url = str(form.get("base_url", "")).strip()
    if not name or not base_url:
        raise ValueError("模型名与 base_url 不能为空")

    entry = {
        "name": name,
        "provider": str(form.get("provider", "")).strip() or "openai",
        "base_url": base_url,
        "env_key": str(form.get("env_key", "")).strip(),
        "description": str(form.get("description", "")).strip(),
    }
    mtype = str(form.get("type", "")).strip()
    if mtype:
        entry["type"] = mtype
    if form.get("disabled"):
        entry["disabled"] = True
    # 直存 API Key（中转站等非预设端点）：掩码占位 / 空值 = 不修改已有 Key
    api_key = str(form.get("api_key", "")).strip()
    if api_key and "****" not in api_key:
        entry["api_key"] = api_key
    elif "api_key" in existing:
        entry["api_key"] = existing["api_key"]
    # 非表单字段（capabilities/成本/延迟等）保留
    for keep in ("capabilities", "cost_per_1k_tokens", "latency", "quality"):
        if keep in existing:
            entry[keep] = existing[keep]
    if "capabilities" not in entry:
        entry["capabilities"] = ["simple_chat"]

    models[model_id] = entry
    result = _save_multi_model(cfg)
    return {"id": model_id, "created": not existing, **result}


def delete_model(model_id: str) -> Dict[str, Any]:
    cfg = _load_multi_model()
    models = cfg.get("models") or {}
    if model_id not in models:
        raise FileNotFoundError(f"模型不存在: {model_id}")
    if cfg.get("active") == model_id:
        raise ValueError("不能删除当前激活模型，请先切换到其它模型")
    del models[model_id]
    # 清理路由引用
    routing = cfg.get("routing_strategy") or {}
    for task, refs in routing.items():
        for role, ref in list(refs.items()):
            if ref == model_id:
                del refs[role]
    result = _save_multi_model(cfg)
    return {"id": model_id, **result}


def set_active_model(model_id: str) -> Dict[str, Any]:
    cfg = _load_multi_model()
    if model_id not in (cfg.get("models") or {}):
        raise FileNotFoundError(f"模型不存在: {model_id}")
    cfg["active"] = model_id
    result = _save_multi_model(cfg)
    return {"active": model_id, **result}


def save_routing(routing: Dict[str, Any]) -> Dict[str, Any]:
    """保存路由策略（primary/secondary/fallback，支持 @active 特殊值）"""
    cfg = _load_multi_model()
    known = set((cfg.get("models") or {}).keys()) | {"@active"}
    cleaned = {}
    for task, refs in (routing or {}).items():
        if not isinstance(refs, dict):
            continue
        entry = {}
        for role, ref in refs.items():
            if ref and ref in known:
                entry[role] = ref
        if entry:
            cleaned[str(task)] = entry
    if not cleaned:
        raise ValueError("路由策略不能为空")
    cfg["routing_strategy"] = cleaned
    result = _save_multi_model(cfg)
    return {"routing": cleaned, **result}


# ── 通用表单（高频 JSON/YAML 配置 schema 驱动） ──────────────

GENERIC_FORMS: Dict[str, Dict[str, Any]] = {
    "tts": {
        "label": "语音合成 (TTS)",
        "file": "tts_config.json",
        "format": "json",
        "effect": "instant",
        "hint": "保存后下一次语音合成即生效",
        "fields": [
            {"key": "enabled", "label": "启用 TTS", "type": "bool"},
            {"key": "preferred_engine", "label": "首选引擎", "type": "select", "options": ["gpt_sovits", "api_tts"]},
            {"key": "local_playback_enabled", "label": "桌面本地播放", "type": "bool"},
            {"key": "local_playback_volume", "label": "本地播放音量", "type": "float", "min": 0, "max": 1},
            {"key": "local_playback_engine", "label": "本地播放引擎", "type": "str"},
            {"key": "qq_default_mode", "label": "QQ 默认模式", "type": "select", "options": ["text", "voice"]},
            {"key": "qq_message_split", "label": "QQ 消息分段", "type": "bool"},
            {"key": "qq_max_message_length", "label": "QQ 单条最大字数", "type": "int", "min": 50, "max": 2000},
        ],
    },
    "web_search": {
        "label": "网页搜索",
        "file": "qq_config.yaml",
        "format": "yaml",
        "effect": "instant",
        "hint": "搜索工具链实际读取的 web_search 节（web_search.py / search_cache.py），保存后清缓存即生效",
        "fields": [
            {"key": "web_search.timeout", "label": "搜索超时（秒）", "type": "int", "min": 5, "max": 120},
            {"key": "web_search.crawl_timeout", "label": "网页抓取超时（秒）", "type": "int", "min": 5, "max": 300},
            {"key": "web_search.query_expansion.enabled", "label": "查询扩展", "type": "bool"},
            {"key": "web_search.query_expansion.max_queries", "label": "扩展查询数", "type": "int", "min": 1, "max": 8},
            {"key": "web_search.query_expansion.bilingual", "label": "中英双语查询", "type": "bool"},
            {"key": "web_search.result_cache.enabled", "label": "结果缓存", "type": "bool"},
            {"key": "web_search.result_cache.ttl_seconds", "label": "缓存 TTL（秒）", "type": "int", "min": 0},
            {"key": "web_search.result_cache.max_entries", "label": "缓存条目上限", "type": "int", "min": 1},
            {"key": "web_search.scihub.enabled", "label": "Sci-Hub 论文直链", "type": "bool"},
        ],
    },
    "tts_engines": {
        "label": "TTS 引擎细节",
        "file": "tts_config.json",
        "format": "json",
        "effect": "instant",
        "hint": "GPT-SoVITS 本地服务的地址与参考音频路径；参考文本需与参考音频内容一致",
        "fields": [
            {"key": "engines.gpt_sovits.enabled", "label": "启用 GPT-SoVITS", "type": "bool"},
            {"key": "engines.gpt_sovits.api_url", "label": "GPT-SoVITS API 地址", "type": "str"},
            {"key": "engines.gpt_sovits.reference_audio", "label": "参考音频路径（本地）", "type": "str"},
            {"key": "engines.gpt_sovits.reference_text", "label": "参考音频文本", "type": "str"},
            {"key": "engines.gpt_sovits.language", "label": "合成语言", "type": "select", "options": ["zh", "en", "ja", "auto"]},
            {"key": "engines.gpt_sovits.speed", "label": "语速", "type": "float", "min": 0.5, "max": 2},
            {"key": "engines.gpt_sovits.top_k", "label": "Top-K", "type": "int", "min": 1, "max": 50},
            {"key": "engines.gpt_sovits.temperature", "label": "Temperature", "type": "float", "min": 0, "max": 2},
            {"key": "engines.edge_tts.enabled", "label": "启用 Edge TTS", "type": "bool"},
            {"key": "engines.edge_tts.voice", "label": "Edge 音色", "type": "str"},
            {"key": "engines.api_tts.enabled", "label": "启用 API TTS", "type": "bool"},
            {"key": "engines.api_tts.api_url", "label": "API TTS 地址", "type": "str"},
            {"key": "engines.api_tts.api_key", "label": "API TTS Key", "type": "secret"},
            {"key": "engines.api_tts.voice", "label": "API 音色", "type": "str"},
        ],
    },
    "singing": {
        "label": "歌唱 / 变声（RVC · GPT-SoVITS）",
        "file": "singing_config.json",
        "format": "json",
        "effect": "instant",
        "hint": "本地工具根目录：留空则自动探测，填写后优先生效（绝对路径或相对项目根目录）",
        "fields": [
            {"key": "enabled", "label": "启用歌唱功能", "type": "bool"},
            {"key": "preferred_engine", "label": "首选引擎", "type": "str"},
            {"key": "paths.rvc_root", "label": "RVC 根目录", "type": "str"},
            {"key": "paths.gpt_sovits_root", "label": "GPT-SoVITS 根目录", "type": "str"},
            {"key": "paths.mdx_root", "label": "MDX（人声分离）根目录", "type": "str"},
            {"key": "paths.ffmpeg", "label": "FFmpeg 路径", "type": "str"},
            {"key": "playback_volume_vocal", "label": "人声音量", "type": "int", "min": 0, "max": 100},
            {"key": "playback_volume_accompany", "label": "伴奏音量", "type": "int", "min": 0, "max": 100},
        ],
    },
    "proactive": {
        "label": "主动聊天",
        "file": "proactive_chat.yaml",
        "format": "yaml",
        "effect": "restart",
        "hint": "修改后需重启弥娅生效",
        "fields": [
            {"key": "proactive_chat.enabled", "label": "启用主动聊天", "type": "bool"},
            {"key": "proactive_chat.check_interval", "label": "检查间隔（秒）", "type": "int", "min": 10},
            {"key": "proactive_chat.max_daily_messages", "label": "每日最大条数", "type": "int", "min": 1, "max": 100},
        ],
    },
    "qq_tools": {
        "label": "QQ 工具与下载",
        "file": "qq_config.yaml",
        "format": "yaml",
        "effect": "instant",
        "hint": "表情包工具开关与下载器行为（qq_config.yaml 的 tools / download_manager 节）",
        "fields": [
            {"key": "tools.qq_emoji.enabled", "label": "表情包工具", "type": "bool"},
            {"key": "tools.qq_emoji.standard_emojis", "label": "标准表情", "type": "bool"},
            {"key": "tools.qq_emoji.custom_emojis", "label": "自定义表情", "type": "bool"},
            {"key": "download_manager.timeout_seconds", "label": "下载超时（秒）", "type": "int", "min": 30, "max": 3600},
            {"key": "download_manager.max_retries", "label": "下载重试次数", "type": "int", "min": 0, "max": 10},
        ],
    },
    "knowledge_base": {
        "label": "知识库",
        "file": "qq_config.yaml",
        "format": "yaml",
        "effect": "instant",
        "hint": "向量知识库基础行为（qq_config.yaml 的 knowledge_base 节）",
        "fields": [
            {"key": "knowledge_base.enabled", "label": "启用知识库", "type": "bool"},
            {"key": "knowledge_base.default_category", "label": "默认分类", "type": "str"},
            {"key": "knowledge_base.embedding.max_text_length", "label": "向量化文本上限", "type": "int", "min": 500, "max": 50000},
        ],
    },
    "file_analysis": {
        "label": "文件分析",
        "file": "qq_config.yaml",
        "format": "yaml",
        "effect": "instant",
        "hint": "聊天文件解析的规模限制（qq_config.yaml 的 file_analysis 节）",
        "fields": [
            {"key": "file_analysis.enabled", "label": "启用文件分析", "type": "bool"},
            {"key": "file_analysis.limits.max_pdf_pages", "label": "PDF 最大页数", "type": "int", "min": 1, "max": 200},
            {"key": "file_analysis.limits.max_text_lines", "label": "文本最大行数", "type": "int", "min": 10, "max": 5000},
            {"key": "file_analysis.limits.max_content_length", "label": "内容最大字数", "type": "int", "min": 1000, "max": 100000},
        ],
    },
    "cognitive": {
        "label": "认知侧写",
        "file": "qq_config.yaml",
        "format": "yaml",
        "effect": "instant",
        "hint": "对用户的认知观察系统（qq_config.yaml 的 cognitive 节）",
        "fields": [
            {"key": "cognitive.enabled", "label": "启用认知侧写", "type": "bool"},
            {"key": "cognitive.storage.revision_keep", "label": "侧写版本保留数", "type": "int", "min": 1, "max": 50},
            {"key": "cognitive.storage.max_observations", "label": "观察记录上限", "type": "int", "min": 10, "max": 1000},
        ],
    },
    "ocr": {
        "label": "OCR 与图像处理",
        "file": "qq_config.yaml",
        "format": "yaml",
        "effect": "restart",
        "hint": "本地 OCR 引擎开关（PaddleOCR 启用后首次加载较慢；修改后需重启）",
        "fields": [
            {"key": "plugins.ocr.paddleocr.enabled", "label": "PaddleOCR", "type": "bool"},
            {"key": "plugins.ocr.paddleocr.use_gpu", "label": "OCR 使用 GPU", "type": "bool"},
            {"key": "plugins.image_processing.pillow.enabled", "label": "Pillow 图像处理", "type": "bool"},
            {"key": "plugins.image_processing.pillow.max_image_pixels", "label": "最大像素数", "type": "int", "min": 1000000, "max": 500000000},
        ],
    },
    "qq_behavior": {
        "label": "QQ 连接与消息",
        "file": "qq_config.yaml",
        "format": "yaml",
        "effect": "restart",
        "hint": "连接心跳与消息解析行为（修改后需重启 QQ 连接）",
        "fields": [
            {"key": "qq.connection.reconnect_interval", "label": "重连间隔（秒）", "type": "float", "min": 1, "max": 300},
            {"key": "qq.connection.ping_interval", "label": "心跳间隔（秒）", "type": "int", "min": 5, "max": 600},
            {"key": "qq.connection.ping_timeout", "label": "心跳超时（秒）", "type": "int", "min": 5, "max": 600},
            {"key": "qq.message_parsing.enable_reply_parsing", "label": "解析回复引用", "type": "bool"},
            {"key": "qq.message_parsing.enable_file_parsing", "label": "解析文件消息", "type": "bool"},
            {"key": "qq.message_parsing.enable_media_detection", "label": "媒体检测", "type": "bool"},
            {"key": "qq.message_parsing.show_placeholder_in_text", "label": "文本占位符", "type": "bool"},
            {"key": "qq.message_batching.enabled", "label": "消息合并窗口", "type": "bool"},
            {"key": "qq.message_batching.window_seconds", "label": "合并窗口（秒）", "type": "int", "min": 1, "max": 60},
            {"key": "qq.message_queue.default_interval", "label": "发送间隔（秒）", "type": "float", "min": 0.5, "max": 30},
        ],
    },
    "qq_features": {
        "label": "QQ 功能开关",
        "file": "qq_config.yaml",
        "format": "yaml",
        "effect": "restart",
        "hint": "戳一戳 / 表情 / 定时任务等功能行为（修改后需重启）",
        "fields": [
            {"key": "qq.features.poke_reply", "label": "戳一戳回复", "type": "bool"},
            {"key": "qq.features.emoji_request", "label": "表情包应答", "type": "bool"},
            {"key": "qq.features.welcome_new_member", "label": "新人欢迎", "type": "bool"},
            {"key": "qq.features.scheduled_tasks", "label": "定时任务", "type": "bool"},
            {"key": "qq.features.passive_chat", "label": "被动聊天", "type": "bool"},
            {"key": "qq.commands.prefix", "label": "命令前缀", "type": "str"},
            {"key": "qq.forward.enable_parsing", "label": "解析转发消息", "type": "bool"},
            {"key": "qq.forward.max_expand_depth", "label": "转发展开层数", "type": "int", "min": 1, "max": 10},
        ],
    },
    "qq_access": {
        "label": "QQ 访问控制",
        "file": "qq_config.yaml",
        "format": "yaml",
        "effect": "instant",
        "hint": "群/用户黑白名单，多个用英文逗号分隔；留空表示不限制",
        "fields": [
            {"key": "qq.access_control.enabled", "label": "启用访问控制", "type": "bool"},
            {"key": "qq.access_control.group_whitelist", "label": "群白名单", "type": "list"},
            {"key": "qq.access_control.group_blacklist", "label": "群黑名单", "type": "list"},
            {"key": "qq.access_control.user_whitelist", "label": "用户白名单", "type": "list"},
            {"key": "qq.access_control.user_blacklist", "label": "用户黑名单", "type": "list"},
        ],
    },
    "qq_multimedia": {
        "label": "QQ 图片与识别",
        "file": "qq_config.yaml",
        "format": "yaml",
        "effect": "instant",
        "hint": "收图尺寸限制与图像 AI 识别（OCR 需在 OCR 板块启用）",
        "fields": [
            {"key": "qq.multimedia.image.auto_resize", "label": "超大图自动缩放", "type": "bool"},
            {"key": "qq.multimedia.image.max_width", "label": "最大宽度（px）", "type": "int", "min": 480, "max": 8192},
            {"key": "qq.multimedia.image.max_height", "label": "最大高度（px）", "type": "int", "min": 480, "max": 8192},
            {"key": "qq.image_recognition.ocr.enabled", "label": "图片内嵌 OCR", "type": "bool"},
            {"key": "qq.image_recognition.ai_analysis.enabled", "label": "图片 AI 分析", "type": "bool"},
        ],
    },
    "persona_identity": {
        "label": "人设身份锚点",
        "file": "text_config.json",
        "format": "json",
        "style": "text-preserve",
        "effect": "restart",
        "hint": "注入每条系统提示词的身份/人称锚点，防止形态切换后身份混淆；修改后重启生效",
        "fields": [
            {"key": "identity_anchor", "label": "身份锚点", "type": "textarea"},
            {"key": "pronoun_disambiguation", "label": "人称指代消歧", "type": "textarea"},
        ],
    },
}


def _form_path(form_id: str) -> Path:
    if form_id not in GENERIC_FORMS:
        raise FileNotFoundError(f"未知配置表单: {form_id}")
    return _PROJECT_ROOT / "config" / GENERIC_FORMS[form_id]["file"]


def _get_nested(data: Dict[str, Any], dotted: str, default=None):
    node = data
    for part in dotted.split("."):
        if isinstance(node, dict):
            node = node.get(part)
        else:
            return default
        if node is None:
            return default
    return node


def _set_nested(data: Dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    node = data
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def _validate_field(form_id: str, field: Dict[str, Any], value: Any) -> Any:
    ftype = field.get("type", "str")
    label = field.get("label", field["key"])
    if ftype == "bool":
        if not isinstance(value, bool):
            raise ValueError(f"{label}: 需要布尔值")
        return value
    if ftype == "list":
        # 前端提交逗号分隔字符串（或字符串数组），统一为 list[str]
        if isinstance(value, str):
            items = [p.strip() for p in value.split(",") if p.strip()]
        elif isinstance(value, list):
            items = [str(p).strip() for p in value if str(p).strip()]
        else:
            raise ValueError(f"{label}: 需要逗号分隔的字符串")
        return items
    if ftype == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{label}: 需要整数")
    elif ftype == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{label}: 需要数字")
        value = float(value)
    else:  # str / select / textarea
        if not isinstance(value, str):
            raise ValueError(f"{label}: 需要字符串")
    if ftype == "select" and value not in field.get("options", []):
        raise ValueError(f"{label}: 只能是 {field.get('options')} 之一")
    if "min" in field and isinstance(value, (int, float)) and value < field["min"]:
        raise ValueError(f"{label}: 不能小于 {field['min']}")
    if "max" in field and isinstance(value, (int, float)) and value > field["max"]:
        raise ValueError(f"{label}: 不能大于 {field['max']}")
    return value


def _save_json_text_preserve(raw: str, cleaned: Dict[str, Any]) -> str:
    """JSON 文本级保存（仅顶层标量键）：只动目标行，不重排文件其余格式。

    适用于手写维护的混合风格文件（如 text_config.json）。
    """
    norm = raw.replace("\r\n", "\n")
    updated = norm
    for key, value in cleaned.items():
        if "." in key:
            raise ValueError(f"保格式模式只支持顶层键: {key}")
        serialized = json.dumps(value, ensure_ascii=False)
        pattern = re.compile(rf'^([ \t]*)"{re.escape(key)}"\s*:\s*(.*?)(\s*,)?\s*$', re.MULTILINE)
        match = pattern.search(updated)
        if match:
            trailing = "," if match.group(3) else ""
            line = f'{match.group(1)}"{key}": {serialized}{trailing}'
            updated = updated[: match.start()] + line + updated[match.end() :]
        else:
            # 追加到顶层对象末尾（最后一个右花括号前）
            last_brace = updated.rfind("}")
            if last_brace < 0:
                raise ValueError("文件结构异常，找不到顶层闭合")
            head = updated[:last_brace].rstrip()
            if head and not head.endswith(",") and not head.endswith("{"):
                head += ","
            indent_m = re.search(r'\n([ \t]+)"', updated)
            indent = indent_m.group(1) if indent_m else "    "
            updated = head + "\n" + indent + f'"{key}": {serialized}' + "\n" + updated[last_brace:]
    json.loads(updated)  # 校验，失败抛异常放弃
    return updated


def _replace_nested_yaml_scalar(text: str, dotted_key: str, value: Any) -> Optional[str]:
    """文本级替换嵌套标量（如 proactive_chat.enabled），保留注释与其它内容。

    Returns:
        替换后的全文；定位失败返回 None
    """
    parts = dotted_key.split(".")
    field = parts[-1]
    eol = _detect_eol(text)
    lines = text.replace("\r\n", "\n").split("\n")

    search_from = 0
    parent_idx = -1
    parent_indent = 0
    for depth, name in enumerate(parts[:-1]):
        pattern = re.compile(rf"^( *){re.escape(name)}:\s*(#.*)?$")
        found = -1
        for i in range(search_from, len(lines)):
            m = pattern.match(lines[i])
            if m and (depth == 0 or len(m.group(1)) > parent_indent):
                found = i
                parent_indent = len(m.group(1))
                break
        if found < 0:
            return None
        parent_idx = found
        search_from = found + 1

    scalar = _yaml_scalar_repr(value)
    for i in range(parent_idx + 1, len(lines)):
        line = lines[i]
        if line.strip() and not line[0].isspace():
            break  # 离开父块
        m = re.match(rf"^( +){re.escape(field)}:\s*(.*?)(\s+#.*)?$", line)
        if m:
            comment = m.group(3) or ""
            lines[i] = f"{m.group(1)}{field}: {scalar}{comment}"
            return eol.join(lines)
    return None


def get_forms_overview() -> List[Dict[str, Any]]:
    """所有通用表单 + 当前值"""
    result = []
    for form_id, schema in GENERIC_FORMS.items():
        path = _form_path(form_id)
        values: Dict[str, Any] = {}
        if path.exists():
            try:
                if schema["format"] == "json":
                    values = json.loads(path.read_text(encoding="utf-8"))
                else:
                    import yaml

                    values = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception as e:
                logger.warning(f"[ConfigPanel] 读取表单 {form_id} 失败: {e}")
        fields = []
        for f in schema["fields"]:
            value = _get_nested(values, f["key"])
            if f.get("type") == "secret":
                fields.append({**f, "value": _mask_secret(value) if value else "", "configured": bool(value)})
            elif f.get("type") == "list":
                fields.append({**f, "value": ", ".join(str(x) for x in value) if isinstance(value, list) else (value or "")})
            else:
                fields.append({**f, "value": value})
        result.append(
            {
                "id": form_id,
                "label": schema["label"],
                "effect": schema["effect"],
                "hint": schema.get("hint", ""),
                "fields": fields,
            }
        )
    return result


def save_form_values(form_id: str, values: Dict[str, Any]) -> Dict[str, Any]:
    """按 schema 校验并保存表单值。YAML 走文本级替换保注释，JSON 读改写保留未知节。"""
    if form_id not in GENERIC_FORMS:
        raise FileNotFoundError(f"未知配置表单: {form_id}")
    schema = GENERIC_FORMS[form_id]
    path = _form_path(form_id)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {schema['file']}")

    # 先整体校验，任何字段非法都不落盘
    cleaned: Dict[str, Any] = {}
    for field in schema["fields"]:
        key = field["key"]
        if key not in values:
            continue
        if field.get("type") == "secret":
            raw = values[key]
            # 掩码占位 / 空值 = 不修改该密钥
            if isinstance(raw, str) and raw.strip() and "****" not in raw:
                cleaned[key] = raw.strip()
            continue
        cleaned[key] = _validate_field(form_id, field, values[key])

    if not cleaned:
        return {"id": form_id, "updated_fields": []}

    if schema["format"] == "json":
        raw = _read_text_raw(path)
        if schema.get("style") == "text-preserve":
            # 手写混合风格文件（text_config.json 等）：文本级替换，绝不重排
            text = _save_json_text_preserve(raw, cleaned)
            if _detect_eol(raw) == "\r\n":
                text = text.replace("\n", "\r\n")
        else:
            data = json.loads(raw)
            for key, value in cleaned.items():
                _set_nested(data, key, value)
            eol = _detect_eol(raw)
            text = json.dumps(data, ensure_ascii=False, indent=2)
            if eol == "\r\n":
                text = text.replace("\n", "\r\n")
        _backup_file(path)
        _atomic_write(path, text)
    else:
        raw = _read_text_raw(path)
        updated = raw
        for key, value in cleaned.items():
            replaced = _replace_nested_yaml_scalar(updated, key, value)
            if replaced is None:
                raise ValueError(f"字段 {key} 定位失败，未做任何修改（文件结构可能已变化）")
            updated = replaced
        # 校验替换后仍是合法 YAML
        import yaml

        try:
            yaml.safe_load(updated)
        except yaml.YAMLError as e:
            raise ValueError(f"替换后 YAML 解析失败，已放弃写入: {e}")
        _backup_file(path)
        _atomic_write(path, updated)

    logger.info(f"[ConfigPanel] 表单已保存: {form_id} ({', '.join(cleaned) or '无字段变更'})")

    # qq_config / text_config 走 lru_cache，写后清缓存让即时生效成立
    if cleaned:
        try:
            from config.config_utils import reload_config

            reload_config()
        except Exception:
            pass
    return {"id": form_id, "updated_fields": list(cleaned)}


class ConfigPanelRoutes:
    """调谐「配置」板块路由

    职责:
    - API Key (.env) 分组掩码读取与单键更新
    - 人设卡列表 / 详情 / 表单保存 / 切换
    - 管理账号 (permissions.json superadmins) 读写
    """

    def __init__(self, web_net: Any, decision_hub: Any):
        self.web_net = web_net
        self.decision_hub = decision_hub

        if not FASTAPI_AVAILABLE:
            self.router = None
            return

        self.router = APIRouter(prefix="/api/config/panel", tags=["ConfigPanel"])
        self._setup_routes()
        logger.info("[ConfigPanelRoutes] 配置面板路由已初始化")

    def _setup_routes(self):

        @self.router.get("/overview")
        async def panel_overview():
            """一次性返回面板全部数据（密钥掩码 / 人设卡 / 当前人设 / 管理账号）"""
            try:
                env_values = _read_env_values()
                groups = []
                for g in ENV_KEY_GROUPS:
                    keys = []
                    for item in g["keys"]:
                        raw = env_values.get(item["key"], "")
                        keys.append(
                            {
                                **item,
                                "configured": bool(raw),
                                "masked": _mask_secret(raw) if raw else "",
                            }
                        )
                    groups.append({"group": g["group"], "effect": g["effect"], "keys": keys})

                personas = list_personas()
                current = get_current_persona_id()
                # 运行中的实例最真实，读取失败再回退文件
                personality = getattr(self.decision_hub, "personality", None)
                if personality is not None:
                    try:
                        current = getattr(personality, "current_form", current) or current
                    except Exception:
                        pass

                return {
                    "success": True,
                    "env_groups": groups,
                    "personas": personas,
                    "current_persona": current,
                    "superadmins": load_superadmins(),
                }
            except Exception as e:
                logger.error(f"[ConfigPanel] overview 失败: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        @self.router.post("/env")
        async def update_env_key(request: dict = None):
            """更新单个 .env 键（同步进程环境变量，立即生效组无须重启）"""
            request = request or {}
            key = str(request.get("key", "")).strip()
            value = str(request.get("value", "")).strip()
            if not key or not value:
                raise HTTPException(status_code=400, detail="缺少 key 或 value")
            try:
                update_env_value(key, value)
                return {"success": True, "key": key, "masked": _mask_secret(value), "message": "已保存"}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except OSError as e:
                logger.error(f"[ConfigPanel] 写入 .env 失败: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"写入 .env 失败: {e}")

        @self.router.get("/personas/{name}")
        async def persona_detail(name: str):
            """读取单张人设卡（表单字段 + 源码）"""
            try:
                return {"success": True, "persona": get_persona_detail(name)}
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail=f"人设卡不存在: {name}")
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.router.post("/personas/{name}")
        async def persona_save(name: str, request: dict = None):
            """保存人设卡表单字段（自动备份 + YAML 校验）"""
            try:
                result = save_persona_form(name, request or {})
                return {"success": True, **result}
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail=f"人设卡不存在: {name}")
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.router.post("/persona/switch")
        async def persona_switch(request: dict = None):
            """切换激活人设（优先热切换）"""
            request = request or {}
            name = str(request.get("name", "")).strip()
            if not name:
                raise HTTPException(status_code=400, detail="缺少 name")
            try:
                return {"success": True, **switch_persona(name, self.decision_hub)}
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail=f"人设卡不存在: {name}")
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.router.post("/personas")
        async def persona_create(request: dict = None):
            """新建人设卡（默认模板派生，可复制现有角色卡）"""
            try:
                result = create_persona(request or {})
                return {"success": True, **result, "message": f"人设卡 {result['id']} 已创建，可继续编辑内容"}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except FileNotFoundError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @self.router.post("/personas/{name}/delete")
        async def persona_delete(name: str):
            """删除人设卡（normal 与当前激活卡受保护，删除前自动备份）"""
            try:
                result = delete_persona(name)
                return {"success": True, **result, "message": f"人设卡 {name} 已删除（备份在 config/backup/panel/）"}
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail=f"人设卡不存在: {name}")
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.router.post("/superadmins")
        async def superadmins_save(request: dict = None):
            """保存管理账号配置（保存即生效）"""
            request = request or {}
            try:
                cleaned = save_superadmins(request.get("superadmins") or {})
                return {"success": True, "superadmins": cleaned, "message": "已保存，权限即时生效"}
            except FileNotFoundError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"[ConfigPanel] 保存管理账号失败: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"保存失败: {e}")

        # ── 模型池 ──（固定路径端点必须先于 /models/{model_id} 注册）

        @self.router.get("/models")
        async def models_list():
            """模型清单 + 激活模型 + 路由策略"""
            try:
                return {"success": True, **list_models_data()}
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail="multi_model_config.json 不存在")
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"[ConfigPanel] 读取模型配置失败: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"读取模型配置失败: {e}")

        @self.router.post("/models/active")
        async def model_set_active(request: dict = None):
            """切换激活模型（自动热重载模型池）"""
            request = request or {}
            model_id = str(request.get("model_id", "")).strip()
            if not model_id:
                raise HTTPException(status_code=400, detail="缺少 model_id")
            try:
                result = set_active_model(model_id)
                msg = "已切换并热重载" if result.get("hot_reloaded") else "已保存，重启后生效"
                return {"success": True, **result, "message": msg}
            except FileNotFoundError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @self.router.post("/models/routing")
        async def model_routing_save(request: dict = None):
            """保存任务路由策略"""
            request = request or {}
            try:
                result = save_routing(request.get("routing") or {})
                msg = "已保存并热重载" if result.get("hot_reloaded") else "已保存，重启后生效"
                return {"success": True, **result, "message": msg}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.router.post("/models/{model_id}")
        async def model_save(model_id: str, request: dict = None):
            """新增/编辑模型条目"""
            try:
                result = save_model_form(model_id, request or {})
                action = "新增" if result.get("created") else "更新"
                msg = f"模型已{action}，" + ("模型池已热重载" if result.get("hot_reloaded") else "重启后生效")
                return {"success": True, **result, "message": msg}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"[ConfigPanel] 保存模型失败: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"保存模型失败: {e}")

        @self.router.post("/models/{model_id}/delete")
        async def model_delete(model_id: str):
            """删除模型条目（同步清理路由引用）"""
            try:
                result = delete_model(model_id)
                return {"success": True, **result, "message": "模型已删除"}
            except FileNotFoundError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        # ── 通用表单 ──

        @self.router.get("/forms")
        async def forms_overview():
            """所有通用配置表单 + 当前值"""
            return {"success": True, "forms": get_forms_overview()}

        @self.router.post("/forms/{form_id}")
        async def form_save(form_id: str, request: dict = None):
            """保存表单值（schema 校验 + 备份 + YAML 保注释）"""
            request = request or {}
            try:
                result = save_form_values(form_id, request.get("values") or {})
                return {"success": True, **result, "message": "已保存"}
            except FileNotFoundError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"[ConfigPanel] 保存表单失败 {form_id}: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"保存失败: {e}")

    def get_router(self):
        return self.router
