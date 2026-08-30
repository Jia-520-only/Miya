"""File Token Service"""

import time
import uuid
from typing import Any, Dict, Optional


class FileTokenService:
    """文件Token服务 - 管理临时文件访问"""

    def __init__(self, token_ttl: int = 3600):
        self.token_ttl = token_ttl
        self._tokens: Dict[str, Dict[str, Any]] = {}

    def create_token(self, file_path: str, user_id: str = "") -> str:
        token = str(uuid.uuid4())
        self._tokens[token] = {
            "file_path": file_path,
            "user_id": user_id,
            "created_at": time.time(),
            "expires_at": time.time() + self.token_ttl,
        }
        return token

    def validate_token(self, token: str) -> bool:
        if token not in self._tokens:
            return False

        token_data = self._tokens[token]
        if time.time() > token_data["expires_at"]:
            del self._tokens[token]
            return False
        return True

    def get_file_path(self, token: str) -> Optional[str]:
        if self.validate_token(token):
            return self._tokens[token]["file_path"]
        return None

    def revoke_token(self, token: str):
        self._tokens.pop(token, None)

    def cleanup_expired(self):
        current_time = time.time()
        expired = [t for t, data in self._tokens.items() if current_time > data["expires_at"]]
        for t in expired:
            del self._tokens[t]


_file_token_service: Optional[FileTokenService] = None


def get_file_token_service(token_ttl: int = 3600) -> FileTokenService:
    global _file_token_service
    if _file_token_service is None:
        _file_token_service = FileTokenService(token_ttl)
    return _file_token_service
