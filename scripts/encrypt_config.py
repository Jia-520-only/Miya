#!/usr/bin/env python3
"""
配置加密工具 - 加密 .env 文件中的敏感信息

用法:
    1. 加密配置:
       python encrypt_config.py --encrypt --input config/.env --output config/.env.encrypted

    2. 解密配置:
       python encrypt_config.py --decrypt --input config/.env.encrypted --output config/.env

    3. 生成加密密钥:
       python encrypt_config.py --generate-key
"""

import argparse
import base64
import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class ConfigEncryptor:
    """配置文件加密器"""

    SENSITIVE_KEYS = [
        "API_KEY",
        "SECRET",
        "PASSWORD",
        "TOKEN",
        "AUTH_KEY",
        "PRIVATE_KEY",
        "CLIENT_SECRET",
        "DATABASE_PASSWORD",
        "REDIS_PASSWORD",
        "NEO4J_PASSWORD",
    ]

    def __init__(self, master_password: str):
        """
        初始化加密器

        Args:
            master_password: 主密码
        """
        self.master_password = master_password
        self.fernet = self._create_fernet()

    def _create_fernet(self) -> Fernet:
        """从主密码创建Fernet实例"""
        # 使用PBKDF2从主密码派生密钥
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"miya_salt_value",  # 固定salt,实际应用中应该使用随机salt并保存
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_password.encode()))
        return Fernet(key)

    def encrypt_value(self, value: str) -> str:
        """
        加密单个值

        Args:
            value: 明文值

        Returns:
            加密后的值 (enc:base64格式)
        """
        if not value or value.startswith("enc:"):
            return value

        encrypted = self.fernet.encrypt(value.encode())
        return f"enc:{base64.urlsafe_b64encode(encrypted).decode()}"

    def decrypt_value(self, value: str) -> str:
        """
        解密单个值

        Args:
            value: 加密值 (enc:base64格式)

        Returns:
            明文值
        """
        if not value or not value.startswith("enc:"):
            return value

        try:
            encrypted_data = base64.urlsafe_b64decode(value[4:])
            decrypted = self.fernet.decrypt(encrypted_data)
            return decrypted.decode()
        except Exception as e:
            print(f"解密失败: {e}")
            return value

    def is_sensitive_key(self, key: str) -> bool:
        """检查是否为敏感配置项"""
        key_upper = key.upper()
        return any(sensitive in key_upper for sensitive in self.SENSITIVE_KEYS)

    def encrypt_config_file(self, input_path: Path, output_path: Path) -> None:
        """
        加密配置文件

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
        """
        print(f"正在加密配置文件: {input_path}")

        with open(input_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        encrypted_lines = []
        sensitive_count = 0

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                encrypted_lines.append(line + "\n")
                continue

            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                if self.is_sensitive_key(key):
                    encrypted_value = self.encrypt_value(value)
                    encrypted_line = f"{key}={encrypted_value}\n"
                    encrypted_lines.append(encrypted_line)
                    sensitive_count += 1
                    print(f"  ✓ 已加密: {key}")
                else:
                    encrypted_lines.append(line + "\n")
            else:
                encrypted_lines.append(line + "\n")

        with open(output_path, "w", encoding="utf-8") as f:
            f.writelines(encrypted_lines)

        print("\n加密完成!")
        print(f"  - 共加密 {sensitive_count} 个敏感配置项")
        print(f"  - 输出文件: {output_path}")

    def decrypt_config_file(self, input_path: Path, output_path: Path) -> None:
        """
        解密配置文件

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
        """
        print(f"正在解密配置文件: {input_path}")

        with open(input_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        decrypted_lines = []
        decrypted_count = 0

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                decrypted_lines.append(line + "\n")
                continue

            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                if value.startswith("enc:"):
                    decrypted_value = self.decrypt_value(value)
                    decrypted_line = f"{key}={decrypted_value}\n"
                    decrypted_lines.append(decrypted_line)
                    decrypted_count += 1
                    print(f"  ✓ 已解密: {key}")
                else:
                    decrypted_lines.append(line + "\n")
            else:
                decrypted_lines.append(line + "\n")

        with open(output_path, "w", encoding="utf-8") as f:
            f.writelines(decrypted_lines)

        print("\n解密完成!")
        print(f"  - 共解密 {decrypted_count} 个配置项")
        print(f"  - 输出文件: {output_path}")


def generate_key_file(output_path: Path) -> None:
    """生成加密密钥文件"""
    key = Fernet.generate_key()

    with open(output_path, "wb") as f:
        f.write(key)

    print(f"密钥已生成: {output_path}")
    print(f"密钥内容: {key.decode()}")
    print("\n请妥善保管此密钥文件!丢失后无法解密!")


def main():
    parser = argparse.ArgumentParser(description="配置文件加密工具")
    parser.add_argument("--encrypt", action="store_true", help="加密配置文件")
    parser.add_argument("--decrypt", action="store_true", help="解密配置文件")
    parser.add_argument("--input", type=str, help="输入文件路径")
    parser.add_argument("--output", type=str, help="输出文件路径")
    parser.add_argument("--password", type=str, help="主密码 (或从环境变量 ENCRYPTION_PASSWORD 读取)")
    parser.add_argument("--generate-key", action="store_true", help="生成加密密钥")

    args = parser.parse_args()

    if args.generate_key:
        generate_key_file(Path("config/encryption_key.bin"))
        return

    if not args.encrypt and not args.decrypt:
        parser.print_help()
        return

    # 获取主密码
    password = args.password or os.getenv("ENCRYPTION_PASSWORD")
    if not password:
        print("错误: 需要提供主密码")
        print("使用方式:")
        print("  1. --password 参数: python encrypt_config.py --password 'your_password'")
        print("  2. 环境变量: set ENCRYPTION_PASSWORD=your_password")
        sys.exit(1)

    if not args.input or not args.output:
        print("错误: 需要指定输入和输出文件")
        sys.exit(1)

    encryptor = ConfigEncryptor(password)

    if args.encrypt:
        encryptor.encrypt_config_file(Path(args.input), Path(args.output))
    elif args.decrypt:
        encryptor.decrypt_config_file(Path(args.input), Path(args.output))


if __name__ == "__main__":
    main()
