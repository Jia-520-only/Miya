"""
备份管理工具
支持文件、目录、数据库的备份和恢复
"""

import os
import shutil
import zipfile
import tarfile
import logging
import hashlib
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
import json
import subprocess
import platform

try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class BackupTask:
    """备份任务"""
    name: str
    source_path: str
    backup_type: str  # file, directory, database
    schedule: str = 'manual'  # manual, daily, weekly, monthly
    enabled: bool = True
    compression: bool = True
    encryption: bool = False
    retention: int = 7  # 保留天数
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class BackupRecord:
    """备份记录"""
    task_name: str
    backup_path: str
    size: int
    checksum: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = 'completed'


class BackupManager:
    """备份管理器"""

    def __init__(self, backup_dir: str = "backups"):
        """
        初始化备份管理器

        Args:
            backup_dir: 备份目录
        """
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        self.tasks: Dict[str, BackupTask] = {}
        self.records: List[BackupRecord] = []
        self.encryption_key: Optional[bytes] = None

        self._load_tasks()
        self._load_records()

    def _load_tasks(self) -> None:
        """加载备份任务"""
        tasks_file = self.backup_dir / "tasks.json"
        if tasks_file.exists():
            try:
                with open(tasks_file, 'r', encoding='utf-8') as f:
                    tasks_data = json.load(f)

                for name, task_data in tasks_data.items():
                    self.tasks[name] = BackupTask(**task_data)

                logger.info(f"加载了 {len(self.tasks)} 个备份任务")
            except Exception as e:
                logger.warning(f"加载备份任务失败: {e}")

    def _save_tasks(self) -> None:
        """保存备份任务"""
        tasks_file = self.backup_dir / "tasks.json"
        tasks_data = {
            name: task.__dict__
            for name, task in self.tasks.items()
        }

        with open(tasks_file, 'w', encoding='utf-8') as f:
            json.dump(tasks_data, f, ensure_ascii=False, indent=2)

    def _load_records(self) -> None:
        """加载备份记录"""
        records_file = self.backup_dir / "records.json"
        if records_file.exists():
            try:
                with open(records_file, 'r', encoding='utf-8') as f:
                    records_data = json.load(f)

                for record_data in records_data:
                    self.records.append(BackupRecord(**record_data))

                logger.info(f"加载了 {len(self.records)} 条备份记录")
            except Exception as e:
                logger.warning(f"加载备份记录失败: {e}")

    def _save_records(self) -> None:
        """保存备份记录"""
        records_file = self.backup_dir / "records.json"
        records_data = [record.__dict__ for record in self.records]

        with open(records_file, 'w', encoding='utf-8') as f:
            json.dump(records_data, f, ensure_ascii=False, indent=2)

    def add_task(self, task: BackupTask) -> None:
        """
        添加备份任务

        Args:
            task: 备份任务
        """
        self.tasks[task.name] = task
        self._save_tasks()
        logger.info(f"添加备份任务: {task.name}")

    def remove_task(self, task_name: str) -> None:
        """
        移除备份任务

        Args:
            task_name: 任务名称
        """
        if task_name in self.tasks:
            del self.tasks[task_name]
            self._save_tasks()
            logger.info(f"移除备份任务: {task_name}")

    def get_task(self, task_name: str) -> Optional[BackupTask]:
        """
        获取备份任务

        Args:
            task_name: 任务名称

        Returns:
            备份任务
        """
        return self.tasks.get(task_name)

    def list_tasks(self) -> List[BackupTask]:
        """列出所有备份任务"""
        return list(self.tasks.values())

    def run_task(self, task_name: str) -> BackupRecord:
        """
        运行备份任务

        Args:
            task_name: 任务名称

        Returns:
            备份记录
        """
        task = self.tasks.get(task_name)
        if not task:
            raise ValueError(f"备份任务不存在: {task_name}")

        if task.backup_type == 'file':
            return self._backup_file(task)
        elif task.backup_type == 'directory':
            return self._backup_directory(task)
        elif task.backup_type == 'database':
            return self._backup_database(task)
        else:
            raise ValueError(f"不支持的备份类型: {task.backup_type}")

    def _backup_file(self, task: BackupTask) -> BackupRecord:
        """备份文件"""
        source = Path(task.source_path)
        if not source.exists():
            raise FileNotFoundError(f"源文件不存在: {source}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{task.name}_{timestamp}.zip"
        backup_path = self.backup_dir / backup_filename

        # 创建zip文件
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(source, source.name)

        # 计算校验和
        checksum = self._calculate_checksum(backup_path)

        # 加密
        if task.encryption and self.encryption_key:
            self._encrypt_file(backup_path)

        record = BackupRecord(
            task_name=task.name,
            backup_path=str(backup_path),
            size=backup_path.stat().st_size,
            checksum=checksum
        )

        self.records.append(record)
        self._save_records()

        logger.info(f"文件备份完成: {source} -> {backup_path}")
        return record

    def _backup_directory(self, task: BackupTask) -> BackupRecord:
        """备份目录"""
        source = Path(task.source_path)
        if not source.exists():
            raise FileNotFoundError(f"源目录不存在: {source}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{task.name}_{timestamp}.tar.gz"
        backup_path = self.backup_dir / backup_filename

        # 创建tar.gz文件
        with tarfile.open(backup_path, 'w:gz') as tar:
            tar.add(source, arcname=source.name)

        # 计算校验和
        checksum = self._calculate_checksum(backup_path)

        # 加密
        if task.encryption and self.encryption_key:
            self._encrypt_file(backup_path)

        record = BackupRecord(
            task_name=task.name,
            backup_path=str(backup_path),
            size=backup_path.stat().st_size,
            checksum=checksum
        )

        self.records.append(record)
        self._save_records()

        logger.info(f"目录备份完成: {source} -> {backup_path}")
        return record

    def _backup_database(self, task: BackupTask) -> BackupRecord:
        """备份数据库"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{task.name}_{timestamp}.sql"
        backup_path = self.backup_dir / backup_filename

        # 这里简化实现，实际应该使用pg_dump、mysqldump等工具
        # 示例：SQLite备份
        source = Path(task.source_path)
        if source.exists():
            shutil.copy2(source, backup_path)

        # 计算校验和
        checksum = self._calculate_checksum(backup_path)

        record = BackupRecord(
            task_name=task.name,
            backup_path=str(backup_path),
            size=backup_path.stat().st_size,
            checksum=checksum
        )

        self.records.append(record)
        self._save_records()

        logger.info(f"数据库备份完成: {task.source_path} -> {backup_path}")
        return record

    def restore(self, backup_path: str, target_path: str) -> None:
        """
        恢复备份

        Args:
            backup_path: 备份文件路径
            target_path: 目标路径
        """
        backup_file = Path(backup_path)
        if not backup_file.exists():
            raise FileNotFoundError(f"备份文件不存在: {backup_file}")

        # 解密
        if self.encryption_key:
            self._decrypt_file(backup_file)

        # 根据文件类型恢复
        if backup_file.suffix == '.zip':
            self._restore_zip(backup_file, target_path)
        elif backup_file.suffixes == ['.tar', '.gz']:
            self._restore_tar(backup_file, target_path)
        elif backup_file.suffix == '.sql':
            self._restore_sql(backup_file, target_path)
        else:
            shutil.copy2(backup_file, target_path)

        logger.info(f"恢复完成: {backup_path} -> {target_path}")

    def _restore_zip(self, backup_path: Path, target_path: str) -> None:
        """恢复ZIP文件"""
        with zipfile.ZipFile(backup_path, 'r') as zipf:
            zipf.extractall(target_path)

    def _restore_tar(self, backup_path: Path, target_path: str) -> None:
        """恢复TAR文件"""
        with tarfile.open(backup_path, 'r:gz') as tar:
            tar.extractall(target_path)

    def _restore_sql(self, backup_path: Path, target_path: str) -> None:
        """恢复SQL文件"""
        # 实际实现应该连接数据库并执行SQL
        shutil.copy2(backup_path, target_path)

    def _calculate_checksum(self, file_path: Path) -> str:
        """
        计算文件校验和

        Args:
            file_path: 文件路径

        Returns:
            MD5校验和
        """
        md5_hash = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()

    def _encrypt_file(self, file_path: Path) -> None:
        """加密文件"""
        if not CRYPTO_AVAILABLE:
            logger.warning("加密功能不可用，未安装cryptography")
            return

        if not self.encryption_key:
            self.encryption_key = Fernet.generate_key()

        fernet = Fernet(self.encryption_key)

        # 读取、加密、写入
        with open(file_path, 'rb') as f:
            data = f.read()

        encrypted = fernet.encrypt(data)

        with open(file_path, 'wb') as f:
            f.write(encrypted)

    def _decrypt_file(self, file_path: Path) -> None:
        """解密文件"""
        if not CRYPTO_AVAILABLE or not self.encryption_key:
            return

        fernet = Fernet(self.encryption_key)

        # 读取、解密、写入
        with open(file_path, 'rb') as f:
            data = f.read()

        decrypted = fernet.decrypt(data)

        with open(file_path, 'wb') as f:
            f.write(decrypted)

    def list_backups(self, task_name: Optional[str] = None) -> List[BackupRecord]:
        """
        列出备份记录

        Args:
            task_name: 任务名称（可选）

        Returns:
            备份记录列表
        """
        if task_name:
            return [r for r in self.records if r.task_name == task_name]
        return self.records

    def delete_backup(self, backup_path: str) -> None:
        """
        删除备份

        Args:
            backup_path: 备份文件路径
        """
        backup_file = Path(backup_path)
        if backup_file.exists():
            backup_file.unlink()

        # 从记录中删除
        self.records = [r for r in self.records if r.backup_path != backup_path]
        self._save_records()

        logger.info(f"已删除备份: {backup_path}")

    def cleanup_old_backups(self) -> None:
        """清理过期备份"""
        now = datetime.now()
        to_delete = []

        for record in self.records:
            task = self.tasks.get(record.task_name)
            if task and task.retention > 0:
                backup_time = datetime.fromisoformat(record.timestamp)
                age_days = (now - backup_time).days

                if age_days > task.retention:
                    to_delete.append(record)

        for record in to_delete:
            self.delete_backup(record.backup_path)

        logger.info(f"清理了 {len(to_delete)} 个过期备份")

    def get_backup_info(self, backup_path: str) -> Dict[str, Any]:
        """
        获取备份信息

        Args:
            backup_path: 备份文件路径

        Returns:
            备份信息
        """
        record = next((r for r in self.records if r.backup_path == backup_path), None)
        if not record:
            raise ValueError(f"备份记录不存在: {backup_path}")

        backup_file = Path(backup_path)
        task = self.tasks.get(record.task_name)

        return {
            'task_name': record.task_name,
            'backup_path': record.backup_path,
            'size': record.size,
            'size_human': self._human_size(record.size),
            'checksum': record.checksum,
            'timestamp': record.timestamp,
            'status': record.status,
            'task_schedule': task.schedule if task else None,
            'encrypted': task.encryption if task else False
        }

    def _human_size(self, size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"

    def export_tasks(self, output_path: str) -> None:
        """
        导出任务配置

        Args:
            output_path: 输出文件路径
        """
        tasks_data = {
            name: task.__dict__
            for name, task in self.tasks.items()
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(tasks_data, f, ensure_ascii=False, indent=2)

        logger.info(f"任务配置已导出到: {output_path}")

    def import_tasks(self, input_path: str) -> None:
        """
        导入任务配置

        Args:
            input_path: 输入文件路径
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            tasks_data = json.load(f)

        for name, task_data in tasks_data.items():
            self.tasks[name] = BackupTask(**task_data)

        self._save_tasks()
        logger.info(f"从 {input_path} 导入了 {len(tasks_data)} 个任务")


# 便捷函数
def quick_backup(source_path: str, backup_dir: str = "backups") -> BackupRecord:
    """
    快速备份

    Args:
        source_path: 源路径
        backup_dir: 备份目录

    Returns:
        备份记录
    """
    source = Path(source_path)
    is_file = source.is_file()

    manager = BackupManager(backup_dir)

    task = BackupTask(
        name=f"quick_{source.name}",
        source_path=source_path,
        backup_type='file' if is_file else 'directory',
        compression=True
    )

    manager.add_task(task)
    return manager.run_task(task.name)


def schedule_auto_backup(task_name: str, manager: BackupManager,
                         schedule: str = 'daily') -> None:
    """
    设置自动备份计划

    Args:
        task_name: 任务名称
        manager: 备份管理器
        schedule: 调度类型
    """
    # 这里简化实现，实际应该使用APScheduler等调度工具
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler()

    if schedule == 'daily':
        scheduler.add_job(
            lambda: manager.run_task(task_name),
            'interval',
            hours=24
        )
    elif schedule == 'weekly':
        scheduler.add_job(
            lambda: manager.run_task(task_name),
            'interval',
            weeks=1
        )
    elif schedule == 'monthly':
        scheduler.add_job(
            lambda: manager.run_task(task_name),
            'interval',
            days=30
        )

    scheduler.start()
    logger.info(f"自动备份已设置: {task_name} ({schedule})")


if __name__ == "__main__":
    # 示例使用
    manager = BackupManager()

    # 添加文件备份任务
    file_task = BackupTask(
        name="重要文件备份",
        source_path="README.md",
        backup_type='file',
        schedule='daily',
        compression=True
    )
    manager.add_task(file_task)

    # 运行备份
    record = manager.run_task("重要文件备份")
    print(f"备份完成: {record.backup_path}")

    # 列出备份
    backups = manager.list_backups()
    print(f"备份列表: {len(backups)} 个")
    for backup in backups:
        print(f"  - {backup.backup_path} ({backup.size} bytes)")

    # 获取备份信息
    info = manager.get_backup_info(record.backup_path)
    print(f"备份信息: {info}")
