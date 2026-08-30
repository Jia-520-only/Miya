"""
弥娅身份归一解析器 (IdentityResolver) V1.0
===========================================

解决「记忆随平台/入口分裂」的核心模块：

各平台给同一个人不同的 user_id（QQ 号、desktop_user、default、微信 openid、飞书 lark id…），
导致弥娅的记忆被写进不同的「桶」，检索时只看到其中一桶，出现"记不起来"。

本模块以 config/permissions.json 为唯一身份事实来源：

1. superadmins.<person>.ids: {platform: [id...]} — 同一个人在各平台的 ID 列表，
   第一个非空 ID 作为该人的**规范 ID (canonical id)**。
2. users[].linked_to: 其他入口 ID → 规范 ID 的显式关联。
3. 管道占位 ID（"default"/"desktop_user"/"0"/"unknown" 等）→ 所有者规范 ID。

对外提供：
- canonicalize(user_id)  : 存储时把任意平台 ID 归一为规范 ID
- expand(user_id)        : 检索时展开为 [user_id, canonical, 全部别名]，用于 IN 查询
- owner_canonical_id     : 所有者（佳）的规范 ID

所有映射均可通过修改 config/permissions.json 调整，代码零硬编码。
"""

import json
import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("Miya.IdentityResolver")

# 管道级占位 ID：这些不是真实用户，是各入口在拿不到具体 ID 时的兜底值。
# 在当前"佳即所有者"的部署下，这些消息几乎全部来自佳；归一后统一进规范记忆桶。
# 若未来有多用户部署，请在 permissions.json 中为其他用户配置 linked_to，
# 或从 OWNER_PLACEHOLDER_IDS 中移除不再适用的项。
OWNER_PLACEHOLDER_IDS = (
    "default",
    "desktop",
    "desktop_user",
    "mobile_default",
    "terminal_default",
    "0",
    "unknown",
)


class IdentityResolver:
    """跨平台用户身份归一（单例，配置热加载）"""

    def __init__(self, config_path: str = "config/permissions.json"):
        self._config_path = Path(config_path)
        self._config_mtime: float = 0.0
        # platform_specific_id / placeholder → canonical id
        self._alias_to_canonical: Dict[str, str] = {}
        # canonical id → 全部别名（含自身）
        self._canonical_to_aliases: Dict[str, List[str]] = {}
        self._owner_canonical: str = ""
        self._lock = threading.Lock()
        self._reload()

    # ==================== 配置加载 ====================

    def _reload(self):
        try:
            if not self._config_path.exists():
                self._alias_to_canonical = {}
                self._canonical_to_aliases = {}
                return

            mtime = self._config_path.stat().st_mtime
            if mtime == self._config_mtime and self._alias_to_canonical:
                return

            with open(self._config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            self._config_mtime = mtime
            self._build_maps(config)
            logger.info(
                f"[IdentityResolver] 身份映射已加载: {len(self._alias_to_canonical)} 个别名, "
                f"所有者规范ID: {self._owner_canonical or '未配置'}"
            )
        except Exception as e:
            logger.warning(f"[IdentityResolver] 加载身份配置失败: {e}")

    def _build_maps(self, config: dict):
        alias_to_canonical: Dict[str, str] = {}
        owner_canonical = ""

        # 1) superadmins.<person>.ids → 每人一个规范 ID + 平台别名
        superadmins = config.get("superadmins", {})
        for person_key, info in superadmins.items():
            if not isinstance(info, dict):
                continue
            ids = info.get("ids", {})
            if not isinstance(ids, dict):
                continue

            # 按配置顺序取第一个非空 ID 作为规范 ID
            canonical = ""
            platform_ids: List[str] = []
            for platform, raw_ids in ids.items():
                if isinstance(raw_ids, str):
                    raw_ids = [raw_ids] if raw_ids else []
                for raw_id in raw_ids or []:
                    rid = str(raw_id).strip()
                    if not rid:
                        continue
                    if not canonical:
                        canonical = rid
                    platform_ids.append(rid)

            if not canonical:
                continue

            for rid in platform_ids:
                alias_to_canonical[rid] = canonical
                # 兼容 platform_userid 拼接形式 (qq_1523878699 等)
            if not owner_canonical:
                owner_canonical = canonical

        # 2) users[].linked_to → 入口 ID 关联到规范 ID
        for user in config.get("users", []):
            if not isinstance(user, dict):
                continue
            uid = str(user.get("user_id", "") or "").strip()
            linked = str(user.get("linked_to", "") or "").strip()
            if not uid or not linked:
                continue
            # linked_to 指向的可能是规范 ID 本身，也可能是另一别名
            alias_to_canonical.setdefault(uid, linked)

        # 3) 所有者占位 ID → 所有者规范 ID
        if owner_canonical:
            for placeholder in OWNER_PLACEHOLDER_IDS:
                alias_to_canonical.setdefault(placeholder, owner_canonical)

        # 4) 解析间接链接 (linked_to 指向别名时，追到最终规范 ID)
        resolved: Dict[str, str] = {}
        for rid, target in alias_to_canonical.items():
            seen = set()
            cur = target
            while cur in alias_to_canonical and cur not in seen:
                seen.add(cur)
                cur = alias_to_canonical[cur]
            resolved[rid] = cur if cur else target
        alias_to_canonical = resolved

        # 5) 构建反向索引 canonical → aliases
        canonical_to_aliases: Dict[str, List[str]] = {}
        for rid, canonical in alias_to_canonical.items():
            canonical_to_aliases.setdefault(canonical, [])
            if rid not in canonical_to_aliases[canonical]:
                canonical_to_aliases[canonical].append(rid)
        for canonical in canonical_to_aliases:
            if canonical not in canonical_to_aliases[canonical]:
                canonical_to_aliases[canonical].append(canonical)

        with self._lock:
            self._alias_to_canonical = alias_to_canonical
            self._canonical_to_aliases = canonical_to_aliases
            self._owner_canonical = owner_canonical

    # ==================== 查询 API ====================

    def refresh(self):
        """强制重载配置（外部调用）"""
        self._config_mtime = 0.0
        self._reload()

    @property
    def owner_canonical_id(self) -> str:
        """所有者（佳）的规范 ID，未配置时为空串"""
        self._reload()
        with self._lock:
            return self._owner_canonical

    def canonicalize(self, user_id: str) -> str:
        """存储归一：任意平台 ID → 规范 ID。未知 ID 原样返回。"""
        if not user_id:
            return user_id
        self._reload()
        uid = str(user_id).strip()
        with self._lock:
            canonical = self._alias_to_canonical.get(uid, "")
            if not canonical:
                # 兼容 platform_userid 前缀形式 (qq_1523878699 / aiocqhttp_1523878699)
                for alias, canon in self._alias_to_canonical.items():
                    if uid.endswith(f"_{alias}") or uid.endswith(alias):
                        canonical = canon
                        break
        return canonical or uid

    def expand(self, user_id: Optional[str]) -> List[str]:
        """检索展开：返回该用户的所有等价 ID（规范 ID + 全部平台别名）。

        用于把 user_id 硬过滤替换为 user_id IN (...) 过滤，
        从而跨平台检索到同一人的全部记忆。

        Args:
            user_id: 任一平台 ID（或规范 ID）。为空/None 时返回空列表（表示不过滤）。

        Returns:
            等价 ID 列表（去重、保序）；未知 ID 返回 [user_id]。
        """
        if not user_id:
            return []
        self._reload()
        uid = str(user_id).strip()

        with self._lock:
            # 1) 直接命中规范 ID
            if uid in self._canonical_to_aliases:
                return list(self._canonical_to_aliases[uid])
            # 2) 是某个规范 ID 的别名
            canonical = self._alias_to_canonical.get(uid, "")
            if canonical and canonical in self._canonical_to_aliases:
                aliases = list(self._canonical_to_aliases[canonical])
                if uid not in aliases:
                    aliases.append(uid)
                return aliases
            # 3) platform_userid 前缀形式
            for alias, canon in self._alias_to_canonical.items():
                if uid.endswith(f"_{alias}"):
                    aliases = list(self._canonical_to_aliases.get(canon, [canon]))
                    if uid not in aliases:
                        aliases.append(uid)
                    return aliases
        return [uid]


# ==================== 全局单例 ====================

_global_resolver: Optional[IdentityResolver] = None
_resolver_lock = threading.Lock()


def get_identity_resolver() -> IdentityResolver:
    """获取全局身份解析器单例"""
    global _global_resolver
    with _resolver_lock:
        if _global_resolver is None:
            _global_resolver = IdentityResolver()
        return _global_resolver


def reset_identity_resolver():
    """重置单例（测试用）"""
    global _global_resolver
    with _resolver_lock:
        _global_resolver = None
