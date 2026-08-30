"""
Miya 配置加密存储模块 - 安全加强
================================

该模块提供敏感配置(密码、Token、API密钥等)的加密存储功能。
支持多种加密算法(AES-256-GCM、ChaCha20-Poly1305)和密钥管理。

设计目标:
- 敏感配置加密存储
- 支持环境变量和密钥文件
- 密钥轮换和安全存储
- 符合安全最佳实践
"""

import base64
import hashlib
import logging
import os
from dataclasses import dataclass
from enum import Enum

from config.config_utils import get_api_key
from pathlib import Path
from typing import Any, Dict, Optional, Set

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logging.warning("[配置加密] cryptography库未安装,加密功能将被禁用")

logger = logging.getLogger(__name__)


class EncryptionAlgorithm(Enum):
    """加密算法"""

    FERNET = "fernet"  # AES-128-CBC
    AES256_GCM = "aes256_gcm"  # AES-256-GCM
    CHACHA20 = "chacha20"  # ChaCha20-Poly1305


@dataclass
class EncryptionConfig:
    """加密配置"""

    algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES256_GCM
    key_derivation_iterations: int = 100000  # PBKDF2迭代次数
    salt_length: int = 16
    enable_env_fallback: bool = True  # 启用环境变量回退


@dataclass
class EncryptedValue:
    """加密值"""

    algorithm: str
    ciphertext: str
    salt: str = ""
    nonce: str = ""
    key_id: str = ""


class ConfigEncryption:
    """配置加密管理器"""

    # 需要加密的配置键
    SENSITIVE_KEYS: Set[str] = {
        "password",
        "token",
        "api_key",
        "secret",
        "private_key",
        "access_token",
        "refresh_token",
        "client_secret",
        "smtp_password",
        "mongodb_password",
        "mysql_password",
        "postgres_password",
    }

    def __init__(
        self,
        master_key: Optional[str] = None,
        key_file: Optional[Path] = None,
        config: Optional[EncryptionConfig] = None,
    ):
        self.config = config or EncryptionConfig()
        self.master_key = master_key
        self.key_file = key_file
        self._key_cache: Dict[str, bytes] = {}
        self._key_store: Dict[str, bytes] = {}

        if not CRYPTO_AVAILABLE:
            raise RuntimeError("加密功能需要cryptography库")

        # 加载主密钥
        self._load_master_key()

        logger.info(f"[配置加密] 初始化完成, 算法={self.config.algorithm.value}")

    def _load_master_key(self):
        """加载主密钥"""
        # 优先级: master_key参数 > key_file > 环境变量 > 自动生成

        if self.master_key:
            # 使用提供的主密钥
            key_bytes = self.master_key.encode()
            key_hash = hashlib.sha256(key_bytes).digest()
            self._key_store["master"] = key_hash
            logger.debug("[配置加密] 使用提供的主密钥")
            return

        if self.key_file and self.key_file.exists():
            # 从密钥文件加载
            with open(self.key_file, "rb") as f:
                key_data = f.read()
            self._key_store["master"] = key_data
            logger.debug(f"[配置加密] 从密钥文件加载: {self.key_file}")
            return

        # 尝试从环境变量获取
        env_key = get_api_key("MIYA_ENCRYPTION_KEY")
        if env_key:
            key_bytes = env_key.encode()
            key_hash = hashlib.sha256(key_bytes).digest()
            self._key_store["master"] = key_hash
            logger.debug("[配置加密] 从环境变量加载主密钥")
            return

        # 自动生成主密钥(并保存)
        import secrets

        new_key = secrets.token_bytes(32)
        self._key_store["master"] = new_key
        self._save_master_key(new_key)
        logger.info("[配置加密] 自动生成并保存主密钥")

    def _save_master_key(self, key: bytes):
        """保存主密钥到文件"""
        if self.key_file:
            self.key_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.key_file, "wb") as f:
                f.write(key)
            logger.info(f"[配置加密] 主密钥已保存: {self.key_file}")

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """从密码派生密钥"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self.config.key_derivation_iterations,
        )
        return kdf.derive(password.encode())

    def _get_encryption_key(self, key_id: str = "master") -> bytes:
        """获取加密密钥"""
        if key_id in self._key_cache:
            return self._key_cache[key_id]

        if key_id in self._key_store:
            key = self._key_store[key_id]
            self._key_cache[key_id] = key
            return key

        raise ValueError(f"密钥不存在: {key_id}")

    def encrypt(self, value: str, key_id: str = "master") -> EncryptedValue:
        """加密值"""
        if not value:
            return EncryptedValue(algorithm=self.config.algorithm.value, ciphertext="")

        key = self._get_encryption_key(key_id)

        try:
            if self.config.algorithm == EncryptionAlgorithm.FERNET:
                encrypted = self._encrypt_fernet(value, key)
            elif self.config.algorithm == EncryptionAlgorithm.AES256_GCM:
                encrypted = self._encrypt_aes256_gcm(value, key)
            elif self.config.algorithm == EncryptionAlgorithm.CHACHA20:
                encrypted = self._encrypt_chacha20(value, key)
            else:
                raise ValueError(f"不支持的加密算法: {self.config.algorithm}")

            logger.debug(f"[配置加密] 加密成功, 算法={self.config.algorithm.value}")
            return encrypted

        except Exception as e:
            logger.error(f"[配置加密] 加密失败: {e}")
            raise

    def _encrypt_fernet(self, value: str, key: bytes) -> EncryptedValue:
        """使用Fernet加密"""
        fernet = Fernet(base64.urlsafe_b64encode(key))
        ciphertext = fernet.encrypt(value.encode())
        return EncryptedValue(
            algorithm=EncryptionAlgorithm.FERNET.value,
            ciphertext=base64.b64encode(ciphertext).decode(),
            key_id="master",
        )

    def _encrypt_aes256_gcm(self, value: str, key: bytes) -> EncryptedValue:
        """使用AES-256-GCM加密"""
        import secrets

        aesgcm = AESGCM(key)
        nonce = secrets.token_bytes(12)  # GCM推荐96位nonce
        ciphertext = aesgcm.encrypt(nonce, value.encode(), None)

        return EncryptedValue(
            algorithm=EncryptionAlgorithm.AES256_GCM.value,
            ciphertext=base64.b64encode(ciphertext).decode(),
            nonce=base64.b64encode(nonce).decode(),
            key_id="master",
        )

    def _encrypt_chacha20(self, value: str, key: bytes) -> EncryptedValue:
        """使用ChaCha20-Poly1305加密"""
        import secrets

        chacha = ChaCha20Poly1305(key)
        nonce = secrets.token_bytes(12)
        ciphertext = chacha.encrypt(nonce, value.encode(), None)

        return EncryptedValue(
            algorithm=EncryptionAlgorithm.CHACHA20.value,
            ciphertext=base64.b64encode(ciphertext).decode(),
            nonce=base64.b64encode(nonce).decode(),
            key_id="master",
        )

    def decrypt(self, encrypted: EncryptedValue, key_id: str = "master") -> str:
        """解密值"""
        if not encrypted.ciphertext:
            return ""

        key = self._get_encryption_key(key_id)

        try:
            if encrypted.algorithm == EncryptionAlgorithm.FERNET.value:
                return self._decrypt_fernet(encrypted, key)
            elif encrypted.algorithm == EncryptionAlgorithm.AES256_GCM.value:
                return self._decrypt_aes256_gcm(encrypted, key)
            elif encrypted.algorithm == EncryptionAlgorithm.CHACHA20.value:
                return self._decrypt_chacha20(encrypted, key)
            else:
                raise ValueError(f"不支持的加密算法: {encrypted.algorithm}")

        except Exception as e:
            logger.error(f"[配置加密] 解密失败: {e}")
            raise

    def _decrypt_fernet(self, encrypted: EncryptedValue, key: bytes) -> str:
        """使用Fernet解密"""
        fernet = Fernet(base64.urlsafe_b64encode(key))
        ciphertext = base64.b64decode(encrypted.ciphertext.encode())
        plaintext = fernet.decrypt(ciphertext)
        return plaintext.decode()

    def _decrypt_aes256_gcm(self, encrypted: EncryptedValue, key: bytes) -> str:
        """使用AES-256-GCM解密"""
        aesgcm = AESGCM(key)
        nonce = base64.b64decode(encrypted.nonce.encode())
        ciphertext = base64.b64decode(encrypted.ciphertext.encode())
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode()

    def _decrypt_chacha20(self, encrypted: EncryptedValue, key: bytes) -> str:
        """使用ChaCha20-Poly1305解密"""
        chacha = ChaCha20Poly1305(key)
        nonce = base64.b64decode(encrypted.nonce.encode())
        ciphertext = base64.b64decode(encrypted.ciphertext.encode())
        plaintext = chacha.decrypt(nonce, ciphertext, None)
        return plaintext.decode()

    def encrypt_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """加密配置字典中的敏感值"""
        encrypted_config = {}

        for key, value in config.items():
            if self._is_sensitive_key(key):
                if isinstance(value, str) and value:
                    # 检查是否已经是加密值
                    if self._is_encrypted_value(value):
                        encrypted_config[key] = value
                    else:
                        # 检查环境变量回退
                        env_value = self._try_env_fallback(key)
                        if env_value:
                            encrypted_config[key] = env_value
                        else:
                            encrypted = self.encrypt(value)
                            encrypted_config[key] = encrypted.ciphertext
                            logger.debug(f"[配置加密] 加密配置键: {key}")
                else:
                    encrypted_config[key] = value
            else:
                encrypted_config[key] = value

        return encrypted_config

    def decrypt_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """解密配置字典中的敏感值"""
        decrypted_config = {}

        for key, value in config.items():
            if self._is_sensitive_key(key):
                if isinstance(value, str) and value:
                    # 检查是否是加密值
                    if self._is_encrypted_value(value):
                        # 尝试解密
                        try:
                            encrypted = EncryptedValue(algorithm=self.config.algorithm.value, ciphertext=value)
                            decrypted = self.decrypt(encrypted)
                            decrypted_config[key] = decrypted
                        except Exception:
                            logger.warning(f"[配置加密] 解密失败,使用原值: {key}")
                            decrypted_config[key] = value
                    else:
                        decrypted_config[key] = value
                else:
                    decrypted_config[key] = value
            else:
                decrypted_config[key] = value

        return decrypted_config

    def _is_sensitive_key(self, key: str) -> bool:
        """检查是否是敏感键"""
        key_lower = key.lower()
        return any(sensitive_key in key_lower for sensitive_key in self.SENSITIVE_KEYS)

    def _is_encrypted_value(self, value: str) -> bool:
        """检查是否是加密值(启发式)"""
        # 检查是否是base64编码
        try:
            decoded = base64.b64decode(value)
            # 检查长度是否合理(加密后通常会变长)
            return len(decoded) > len(value) * 0.8
        except:
            return False

    def _try_env_fallback(self, key: str) -> Optional[str]:
        """尝试从环境变量获取敏感值"""
        if not self.config.enable_env_fallback:
            return None

        # 尝试多种环境变量格式
        env_var_names = [
            f"MIYA_{key.upper()}",
            f"MIYA_{key.upper().replace('_', '.')}",
            key.upper(),
            f"{key.upper()}_SECRET",
        ]

        for env_name in env_var_names:
            env_value = os.getenv(env_name)
            if env_value:
                logger.debug(f"[配置加密] 从环境变量获取: {env_name}")
                return env_value

        return None

    def rotate_key(self, old_key_id: str, new_key_id: str, new_key: bytes):
        """轮换密钥"""
        logger.info(f"[配置加密] 开始密钥轮换: {old_key_id} -> {new_key_id}")

        # 保存新密钥
        self._key_store[new_key_id] = new_key
        self._key_cache.clear()

        logger.info("[配置加密] 密钥轮换完成")

    def export_key(self, key_id: str = "master", password: Optional[str] = None) -> str:
        """导出密钥(加密)"""
        key = self._get_encryption_key(key_id)

        if password:
            # 使用密码加密导出
            import secrets

            salt = secrets.token_bytes(self.config.salt_length)
            derived_key = self._derive_key(password, salt)

            # 使用AES-GCM加密密钥
            aesgcm = AESGCM(derived_key)
            nonce = secrets.token_bytes(12)
            encrypted = aesgcm.encrypt(nonce, key, None)

            return base64.b64encode(salt + nonce + encrypted).decode()
        else:
            # 直接base64编码(不推荐)
            return base64.b64encode(key).decode()

    def import_key(self, key_data: str, password: Optional[str] = None, key_id: str = "master"):
        """导入密钥"""
        if password:
            # 使用密码解密
            raw = base64.b64decode(key_data)
            salt = raw[: self.config.salt_length]
            nonce = raw[self.config.salt_length : self.config.salt_length + 12]
            encrypted = raw[self.config.salt_length + 12 :]

            derived_key = self._derive_key(password, salt)
            aesgcm = AESGCM(derived_key)
            key = aesgcm.decrypt(nonce, encrypted, None)
        else:
            # 直接base64解码
            key = base64.b64decode(key_data)

        self._key_store[key_id] = key
        self._key_cache.clear()
        logger.info(f"[配置加密] 密钥已导入: {key_id}")


# 全局配置加密实例
_global_encryption: Optional[ConfigEncryption] = None


def get_global_encryption() -> ConfigEncryption:
    """获取全局配置加密实例"""
    global _global_encryption
    if _global_encryption is None:
        _global_encryption = ConfigEncryption()
    return _global_encryption


def set_global_encryption(encryption: ConfigEncryption):
    """设置全局配置加密实例"""
    global _global_encryption
    _global_encryption = encryption


# 示例使用
if __name__ == "__main__":
    # 创建加密器
    encryption = ConfigEncryption(key_file=Path("test_key.bin"))

    # 加密值
    encrypted = encryption.encrypt("my_secret_password")
    print(f"加密值: {encrypted.ciphertext}")

    # 解密值
    decrypted = encryption.decrypt(encrypted)
    print(f"解密值: {decrypted}")

    # 加密配置
    config = {"username": "admin", "password": "secret123", "api_key": "abc123def456"}

    encrypted_config = encryption.encrypt_config(config)
    print(f"加密配置: {encrypted_config}")

    # 解密配置
    decrypted_config = encryption.decrypt_config(encrypted_config)
    print(f"解密配置: {decrypted_config}")
