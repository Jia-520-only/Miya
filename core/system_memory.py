"""
系统记忆模块
第四阶段核心模块 - 让弥娅记住系统配置、修复历史和最佳实践
"""
import logging
import json
import hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from collections import defaultdict


logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """记忆类型"""
    SYSTEM_CONFIG = "system_config"     # 系统配置
    FIX_HISTORY = "fix_history"         # 修复历史
    BEST_PRACTICE = "best_practice"     # 最佳实践
    PATTERN = "pattern"                 # 模式
    USER_PREFERENCE = "user_preference" # 用户偏好


@dataclass
class MemoryItem:
    """记忆项"""
    id: str
    type: MemoryType
    key: str                    # 唯一键
    value: Any                  # 值
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0     # 置信度 0.0-1.0
    access_count: int = 0       # 访问次数
    last_accessed: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        """转换为字典"""
        data = asdict(self)
        data['type'] = self.type.value
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        data['last_accessed'] = self.last_accessed.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'MemoryItem':
        """从字典创建"""
        data = data.copy()
        data['type'] = MemoryType(data['type'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        data['last_accessed'] = datetime.fromisoformat(data['last_accessed'])
        return cls(**data)


@dataclass
class FixRecord:
    """修复记录"""
    id: str
    problem_id: str
    problem_type: str
    severity: str
    file_path: str
    fix_action: str
    success: bool
    execution_time: float
    backup_path: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        """转换为字典"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'FixRecord':
        """从字典创建"""
        data = data.copy()
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


@dataclass
class SystemConfig:
    """系统配置记忆"""
    id: str
    config_type: str           # 配置类型：python, node, project, etc.
    config_path: str           # 配置文件路径
    config_hash: str           # 内容哈希
    config_value: Dict         # 配置内容
    detected_issues: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        """转换为字典"""
        data = asdict(self)
        data['timestamp'] = data['timestamp'].isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'SystemConfig':
        """从字典创建"""
        data = data.copy()
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


class SystemMemory:
    """系统记忆系统"""

    def __init__(self, memory_dir: str = ".memory"):
        self.logger = logging.getLogger(__name__)
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        # 记忆存储
        self.memories: Dict[str, MemoryItem] = {}

        # 按类型分类
        self.by_type: Dict[MemoryType, List[MemoryItem]] = defaultdict(list)

        # 按键索引
        self.by_key: Dict[str, MemoryItem] = {}

        # 修复历史
        self.fix_records: List[FixRecord] = []

        # 系统配置
        self.system_configs: Dict[str, SystemConfig] = {}

        # 统计
        self.stats = {
            'total_memories': 0,
            'total_fixes': 0,
            'successful_fixes': 0,
            'failed_fixes': 0,
            'config_snapshots': 0,
        }

        # 加载已有记忆
        self.load()

    def _generate_id(self) -> str:
        """生成唯一ID"""
        return hashlib.md5(
            datetime.now().isoformat().encode()
        ).hexdigest()[:16]

    def _generate_key(self, type: MemoryType, key_parts: List[str]) -> str:
        """生成记忆键"""
        return f"{type.value}:" + ":".join(key_parts)

    def remember(
        self,
        type: MemoryType,
        key_parts: List[str],
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
        confidence: float = 1.0
    ) -> str:
        """
        记住一个信息

        Args:
            type: 记忆类型
            key_parts: 键的部分
            value: 值
            metadata: 元数据
            confidence: 置信度

        Returns:
            记忆ID
        """
        key = self._generate_key(type, key_parts)
        memory_id = self._generate_id()

        memory = MemoryItem(
            id=memory_id,
            type=type,
            key=key,
            value=value,
            metadata=metadata or {},
            confidence=confidence,
        )

        self.memories[memory_id] = memory
        self.by_type[type].append(memory)
        self.by_key[key] = memory
        self.stats['total_memories'] += 1

        self.logger.debug(f"记住: {key}")
        return memory_id

    def recall(self, key_parts: List[str], type: Optional[MemoryType] = None) -> Optional[MemoryItem]:
        """
        回忆一个信息

        Args:
            key_parts: 键的部分
            type: 记忆类型（可选）

        Returns:
            记忆项
        """
        if type:
            key = self._generate_key(type, key_parts)
        else:
            # 尝试所有类型
            for t in MemoryType:
                key = self._generate_key(t, key_parts)
                if key in self.by_key:
                    memory = self.by_key[key]
                    memory.access_count += 1
                    memory.last_accessed = datetime.now()
                    return memory
            return None

        if key in self.by_key:
            memory = self.by_key[key]
            memory.access_count += 1
            memory.last_accessed = datetime.now()
            return memory

        return None

    def recall_by_type(self, type: MemoryType) -> List[MemoryItem]:
        """
        按类型回忆所有记忆

        Args:
            type: 记忆类型

        Returns:
            记忆列表
        """
        return self.by_type.get(type, [])

    def forget(self, key_parts: List[str], type: MemoryType) -> bool:
        """
        忘记一个信息

        Args:
            key_parts: 键的部分
            type: 记忆类型

        Returns:
            是否成功
        """
        key = self._generate_key(type, key_parts)

        if key not in self.by_key:
            return False

        memory = self.by_key[key]

        # 从所有索引中删除
        del self.memories[memory.id]
        self.by_type[type].remove(memory)
        del self.by_key[key]

        self.stats['total_memories'] -= 1

        self.logger.debug(f"忘记: {key}")
        return True

    def record_fix(
        self,
        problem_id: str,
        problem_type: str,
        severity: str,
        file_path: str,
        fix_action: str,
        success: bool,
        execution_time: float,
        backup_path: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> str:
        """
        记录修复历史

        Args:
            problem_id: 问题ID
            problem_type: 问题类型
            severity: 严重程度
            file_path: 文件路径
            fix_action: 修复动作
            success: 是否成功
            execution_time: 执行时间
            backup_path: 备份路径
            error_message: 错误消息

        Returns:
            记录ID
        """
        record_id = self._generate_id()

        record = FixRecord(
            id=record_id,
            problem_id=problem_id,
            problem_type=problem_type,
            severity=severity,
            file_path=file_path,
            fix_action=fix_action,
            success=success,
            execution_time=execution_time,
            backup_path=backup_path,
            error_message=error_message,
        )

        self.fix_records.append(record)
        self.stats['total_fixes'] += 1

        if success:
            self.stats['successful_fixes'] += 1
        else:
            self.stats['failed_fixes'] += 1

        # 记住这个修复模式
        self._learn_fix_pattern(record)

        self.logger.debug(f"记录修复: {problem_id}")
        return record_id

    def _learn_fix_pattern(self, record: FixRecord):
        """从修复记录中学习模式"""
        # 生成模式键
        pattern_key = [
            record.problem_type,
            record.severity,
            Path(record.file_path).suffix if record.file_path else 'unknown',
        ]

        # 计算成功率
        success_rate = self._calculate_success_rate(pattern_key)

        # 记住这个模式
        self.remember(
            type=MemoryType.PATTERN,
            key_parts=pattern_key,
            value={
                'success_rate': success_rate,
                'total_attempts': self._count_fixes(pattern_key),
                'last_success': record.success,
                'last_time': record.execution_time,
            },
            metadata={
                'file_pattern': str(record.file_path),
                'fix_action': record.fix_action,
            },
            confidence=min(1.0, success_rate)
        )

    def _calculate_success_rate(self, pattern_key: List[str]) -> float:
        """计算模式的成功率"""
        matching_records = [
            r for r in self.fix_records
            if (r.problem_type == pattern_key[0] and
                r.severity == pattern_key[1] and
                Path(r.file_path).suffix == pattern_key[2])
        ]

        if not matching_records:
            return 0.0

        success_count = sum(1 for r in matching_records if r.success)
        return success_count / len(matching_records)

    def _count_fixes(self, pattern_key: List[str]) -> int:
        """计算匹配的修复次数"""
        return len([
            r for r in self.fix_records
            if (r.problem_type == pattern_key[0] and
                r.severity == pattern_key[1] and
                Path(r.file_path).suffix == pattern_key[2])
        ])

    def get_fix_history(
        self,
        problem_type: Optional[str] = None,
        file_path: Optional[str] = None,
        limit: int = 100
    ) -> List[FixRecord]:
        """
        获取修复历史

        Args:
            problem_type: 问题类型（可选）
            file_path: 文件路径（可选）
            limit: 限制数量

        Returns:
            修复记录列表
        """
        records = self.fix_records

        if problem_type:
            records = [r for r in records if r.problem_type == problem_type]

        if file_path:
            records = [r for r in records if r.file_path == file_path]

        # 按时间倒序
        records = sorted(records, key=lambda r: r.timestamp, reverse=True)

        return records[:limit]

    def save_system_config(
        self,
        config_type: str,
        config_path: str,
        config_value: Dict,
        detected_issues: Optional[List[str]] = None
    ) -> str:
        """
        保存系统配置

        Args:
            config_type: 配置类型
            config_path: 配置路径
            config_value: 配置值
            detected_issues: 检测到的问题

        Returns:
            配置ID
        """
        config_id = self._generate_id()

        # 计算哈希
        config_str = json.dumps(config_value, sort_keys=True)
        config_hash = hashlib.md5(config_str.encode()).hexdigest()

        config = SystemConfig(
            id=config_id,
            config_type=config_type,
            config_path=config_path,
            config_hash=config_hash,
            config_value=config_value,
            detected_issues=detected_issues or [],
        )

        self.system_configs[config_id] = config
        self.stats['config_snapshots'] += 1

        # 记住配置
        self.remember(
            type=MemoryType.SYSTEM_CONFIG,
            key_parts=[config_type, config_path],
            value=config_value,
            metadata={
                'hash': config_hash,
                'detected_issues': detected_issues,
            }
        )

        self.logger.debug(f"保存配置: {config_type}:{config_path}")
        return config_id

    def get_system_config(
        self,
        config_type: str,
        config_path: Optional[str] = None
    ) -> Optional[SystemConfig]:
        """
        获取系统配置

        Args:
            config_type: 配置类型
            config_path: 配置路径（可选）

        Returns:
            配置对象
        """
        # 如果有路径，直接查找
        if config_path:
            for config in self.system_configs.values():
                if (config.config_type == config_type and
                    config.config_path == config_path):
                    return config
            return None

        # 否则返回该类型的最新配置
        configs = [
            c for c in self.system_configs.values()
            if c.config_type == config_type
        ]

        if not configs:
            return None

        # 按时间排序，返回最新的
        return max(configs, key=lambda c: c.timestamp)

    def get_best_practice(self, context: str) -> Optional[Dict]:
        """
        获取最佳实践

        Args:
            context: 上下文

        Returns:
            最佳实践
        """
        memory = self.recall([context], MemoryType.BEST_PRACTICE)

        if memory:
            return memory.value

        return None

    def save_best_practice(
        self,
        context: str,
        practice: Dict,
        confidence: float = 1.0
    ) -> str:
        """
        保存最佳实践

        Args:
            context: 上下文
            practice: 实践内容
            confidence: 置信度

        Returns:
            记忆ID
        """
        return self.remember(
            type=MemoryType.BEST_PRACTICE,
            key_parts=[context],
            value=practice,
            confidence=confidence
        )

    def get_user_preference(self, key: str) -> Optional[Any]:
        """
        获取用户偏好

        Args:
            key: 偏好键

        Returns:
            偏好值
        """
        memory = self.recall([key], MemoryType.USER_PREFERENCE)

        if memory:
            return memory.value

        return None

    def set_user_preference(self, key: str, value: Any) -> str:
        """
        设置用户偏好

        Args:
            key: 偏好键
            value: 偏好值

        Returns:
            记忆ID
        """
        return self.remember(
            type=MemoryType.USER_PREFERENCE,
            key_parts=[key],
            value=value
        )

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_memories': self.stats['total_memories'],
            'total_fixes': self.stats['total_fixes'],
            'successful_fixes': self.stats['successful_fixes'],
            'failed_fixes': self.stats['failed_fixes'],
            'success_rate': (
                self.stats['successful_fixes'] / self.stats['total_fixes']
                if self.stats['total_fixes'] > 0
                else 0.0
            ),
            'config_snapshots': self.stats['config_snapshots'],
            'memories_by_type': {
                t.value: len(self.by_type[t])
                for t in MemoryType
            },
        }

    def get_report(self) -> str:
        """生成报告"""
        lines = [
            "系统记忆报告",
            "=" * 60,
            "",
            "统计信息:",
        ]

        stats = self.get_statistics()

        for key, value in stats.items():
            if key == 'memories_by_type':
                lines.append(f"  {key}:")
                for type_name, count in value.items():
                    lines.append(f"    - {type_name}: {count}")
            else:
                lines.append(f"  {key}: {value}")

        lines.extend([
            "",
            "最近修复:",
        ])

        recent_fixes = self.fix_records[-5:] if self.fix_records else []
        if recent_fixes:
            for fix in recent_fixes:
                status = "✅" if fix.success else "❌"
                lines.append(
                    f"  {status} {fix.problem_type}/{fix.severity}: "
                    f"{fix.file_path or 'N/A'}"
                )
        else:
            lines.append("  暂无")

        return "\n".join(lines)

    def save(self, file_path: Optional[str] = None):
        """保存记忆到文件"""
        if file_path is None:
            file_path = self.memory_dir / "memory.json"

        try:
            data = {
                'memories': [m.to_dict() for m in self.memories.values()],
                'fix_records': [r.to_dict() for r in self.fix_records],
                'system_configs': [c.to_dict() for c in self.system_configs.values()],
                'stats': self.stats,
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            self.logger.info(f"记忆已保存: {file_path}")

        except Exception as e:
            self.logger.error(f"保存记忆失败: {e}")

    def load(self, file_path: Optional[str] = None):
        """从文件加载记忆"""
        if file_path is None:
            file_path = self.memory_dir / "memory.json"

        try:
            if not Path(file_path).exists():
                self.logger.info(f"记忆文件不存在: {file_path}")
                return

            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 恢复记忆
            self.memories = {}
            self.by_type = defaultdict(list)
            self.by_key = {}

            for m_data in data.get('memories', []):
                memory = MemoryItem.from_dict(m_data)
                self.memories[memory.id] = memory
                self.by_type[memory.type].append(memory)
                self.by_key[memory.key] = memory

            # 恢复修复记录
            self.fix_records = [
                FixRecord.from_dict(r_data)
                for r_data in data.get('fix_records', [])
            ]

            # 恢复系统配置
            self.system_configs = {
                c['id']: SystemConfig.from_dict(c)
                for c in data.get('system_configs', [])
            }

            # 恢复统计
            self.stats.update(data.get('stats', {}))

            self.logger.info(f"记忆已加载: {file_path}")

        except Exception as e:
            self.logger.error(f"加载记忆失败: {e}")


# 单例
_memory_instance: Optional[SystemMemory] = None


def get_system_memory() -> SystemMemory:
    """获取系统记忆单例"""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = SystemMemory()
    return _memory_instance
