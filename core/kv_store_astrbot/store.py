"""Plugin KV Store"""

import json
from pathlib import Path
from typing import Any, Optional


class KVStore:
    """插件KV存储"""

    def __init__(self, store_path: Optional[str] = None):
        self.store_path = Path(store_path) if store_path else Path.home() / ".miya" / "kv_store.json"
        self._data: dict = {}
        self._load()

    def _load(self):
        if self.store_path.exists():
            self._data = json.loads(self.store_path.read_text())

    def _save(self):
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(json.dumps(self._data, indent=2))

    def set(self, namespace: str, key: str, value: Any):
        if namespace not in self._data:
            self._data[namespace] = {}
        self._data[namespace][key] = value
        self._save()

    def get(self, namespace: str, key: str, default: Any = None) -> Any:
        return self._data.get(namespace, {}).get(key, default)

    def delete(self, namespace: str, key: str):
        if namespace in self._data and key in self._data[namespace]:
            del self._data[namespace][key]
            self._save()

    def get_namespace(self, namespace: str) -> dict:
        return self._data.get(namespace, {}).copy()

    def delete_namespace(self, namespace: str):
        self._data.pop(namespace, None)
        self._save()


_kv_store: Optional[KVStore] = None


def get_kv_store(store_path: Optional[str] = None) -> KVStore:
    global _kv_store
    if _kv_store is None:
        _kv_store = KVStore(store_path)
    return _kv_store
