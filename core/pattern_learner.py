"""
模式学习器
第四阶段核心模块 - 从历史数据中学习模式
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import defaultdict
import json


logger = logging.getLogger(__name__)


class PatternType(Enum):
    """模式类型"""
    FIX_PATTERN = "fix_pattern"           # 修复模式
    ERROR_PATTERN = "error_pattern"       # 错误模式
    SUCCESS_PATTERN = "success_pattern"   # 成功模式
    USER_PATTERN = "user_pattern"         # 用户模式


@dataclass
class Pattern:
    """模式"""
    id: str
    type: PatternType
    pattern_key: str           # 模式键
    features: Dict[str, Any]   # 特征
    success_rate: float        # 成功率
    total_occurrences: int    # 总出现次数
    confidence: float         # 置信度
    last_seen: datetime
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'id': self.id,
            'type': self.type.value,
            'pattern_key': self.pattern_key,
            'features': self.features,
            'success_rate': self.success_rate,
            'total_occurrences': self.total_occurrences,
            'confidence': self.confidence,
            'last_seen': self.last_seen.isoformat(),
            'created_at': self.created_at.isoformat(),
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Pattern':
        """从字典创建"""
        data = data.copy()
        data['type'] = PatternType(data['type'])
        data['last_seen'] = datetime.fromisoformat(data['last_seen'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)


@dataclass
class PatternMatch:
    """模式匹配结果"""
    pattern: Pattern
    similarity: float         # 相似度
    confidence: float         # 置信度
    recommendation: str       # 建议


class PatternLearner:
    """模式学习器"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # 模式存储
        self.patterns: Dict[str, Pattern] = {}

        # 按类型分类
        self.by_type: Dict[PatternType, List[Pattern]] = defaultdict(list)

        # 模式索引
        self.by_key: Dict[str, Pattern] = {}

        # 学习参数
        self.min_occurrences = 3        # 最少出现次数
        self.min_confidence = 0.7       # 最小置信度
        self.confidence_decay = 0.95    # 置信度衰减

        # 统计
        self.stats = {
            'total_patterns': 0,
            'high_confidence_patterns': 0,
            'matches_found': 0,
            'learning_cycles': 0,
        }

    def learn_from_fix(
        self,
        problem_type: str,
        severity: str,
        file_path: str,
        fix_action: str,
        success: bool,
        execution_time: float
    ) -> Optional[Pattern]:
        """
        从修复中学习模式

        Args:
            problem_type: 问题类型
            severity: 严重程度
            file_path: 文件路径
            fix_action: 修复动作
            success: 是否成功
            execution_time: 执行时间

        Returns:
            学习到的模式
        """
        # 生成模式键
        from pathlib import Path
        pattern_key = self._generate_pattern_key(
            problem_type,
            severity,
            Path(file_path).suffix if file_path else 'unknown'
        )

        # 提取特征
        features = {
            'problem_type': problem_type,
            'severity': severity,
            'file_extension': Path(file_path).suffix if file_path else 'unknown',
            'fix_action_type': self._classify_fix_action(fix_action),
            'file_pattern': self._extract_file_pattern(file_path),
        }

        # 更新或创建模式
        pattern = self._update_or_create_pattern(
            pattern_type=PatternType.FIX_PATTERN,
            pattern_key=pattern_key,
            features=features,
            success=success,
            execution_time=execution_time,
        )

        return pattern

    def _generate_pattern_key(self, *parts: str) -> str:
        """生成模式键"""
        return ":".join(str(p) for p in parts)

    def _classify_fix_action(self, action: str) -> str:
        """分类修复动作"""
        action_lower = action.lower()

        if any(word in action_lower for word in ['delete', 'remove', 'rm']):
            return 'delete'
        elif any(word in action_lower for word in ['add', 'create', 'insert', 'new']):
            return 'add'
        elif any(word in action_lower for word in ['modify', 'change', 'update', 'edit']):
            return 'modify'
        elif any(word in action_lower for word in ['replace', 'substitute']):
            return 'replace'
        elif any(word in action_lower for word in ['move', 'rename', 'copy']):
            return 'move'
        else:
            return 'unknown'

    def _extract_file_pattern(self, file_path: str) -> str:
        """提取文件模式"""
        from pathlib import Path
        path = Path(file_path)

        # 获取目录结构
        if len(path.parts) > 1:
            return "/".join(path.parts[-2:])
        else:
            return path.name

    def _update_or_create_pattern(
        self,
        pattern_type: PatternType,
        pattern_key: str,
        features: Dict[str, Any],
        success: bool,
        execution_time: float
    ) -> Pattern:
        """
        更新或创建模式

        Args:
            pattern_type: 模式类型
            pattern_key: 模式键
            features: 特征
            success: 是否成功
            execution_time: 执行时间

        Returns:
            模式对象
        """
        import hashlib

        if pattern_key in self.by_key:
            # 更新现有模式
            pattern = self.by_key[pattern_key]

            # 更新统计
            pattern.total_occurrences += 1

            # 更新成功率（加权平均）
            new_rate = 1.0 if success else 0.0
            old_weight = 0.8
            pattern.success_rate = (
                pattern.success_rate * old_weight +
                new_rate * (1 - old_weight)
            )

            # 更新置信度
            pattern.confidence = min(1.0, pattern.confidence * 1.05)

            # 更新最后出现时间
            pattern.last_seen = datetime.now()

            # 更新元数据
            if 'avg_execution_time' not in pattern.metadata:
                pattern.metadata['avg_execution_time'] = execution_time
            else:
                pattern.metadata['avg_execution_time'] = (
                    pattern.metadata['avg_execution_time'] * 0.9 +
                    execution_time * 0.1
                )

        else:
            # 创建新模式
            pattern_id = hashlib.md5(
                f"{pattern_key}_{datetime.now().isoformat()}".encode()
            ).hexdigest()[:16]

            pattern = Pattern(
                id=pattern_id,
                type=pattern_type,
                pattern_key=pattern_key,
                features=features,
                success_rate=1.0 if success else 0.0,
                total_occurrences=1,
                confidence=0.5,  # 初始置信度较低
                last_seen=datetime.now(),
                created_at=datetime.now(),
                metadata={
                    'avg_execution_time': execution_time,
                },
            )

            # 添加到存储
            self.patterns[pattern_id] = pattern
            self.by_type[pattern_type].append(pattern)
            self.by_key[pattern_key] = pattern

            self.stats['total_patterns'] += 1

        return pattern

    def find_matching_patterns(
        self,
        problem_type: str,
        severity: str,
        file_path: str
    ) -> List[PatternMatch]:
        """
        查找匹配的模式

        Args:
            problem_type: 问题类型
            severity: 严重程度
            file_path: 文件路径

        Returns:
            匹配的模式列表
        """
        from pathlib import Path

        matches = []

        for pattern in self.patterns.values():
            if pattern.total_occurrences < self.min_occurrences:
                continue

            if pattern.confidence < self.min_confidence:
                continue

            # 计算相似度
            similarity = self._calculate_similarity(
                problem_type=problem_type,
                severity=severity,
                file_path=file_path,
                pattern=pattern,
            )

            if similarity > 0.5:  # 相似度阈值
                matches.append(PatternMatch(
                    pattern=pattern,
                    similarity=similarity,
                    confidence=pattern.confidence,
                    recommendation=self._generate_recommendation(pattern),
                ))

                self.stats['matches_found'] += 1

        # 按相似度排序
        matches.sort(key=lambda m: m.similarity, reverse=True)

        return matches

    def _calculate_similarity(
        self,
        problem_type: str,
        severity: str,
        file_path: str,
        pattern: Pattern
    ) -> float:
        """
        计算相似度

        Args:
            problem_type: 问题类型
            severity: 严重程度
            file_path: 文件路径
            pattern: 模式

        Returns:
            相似度 (0.0-1.0)
        """
        from pathlib import Path

        score = 0.0
        max_score = 3.0

        features = pattern.features

        # 问题类型匹配
        if features.get('problem_type') == problem_type:
            score += 1.0

        # 严重程度匹配
        if features.get('severity') == severity:
            score += 0.5
        elif self._severity_compatible(features.get('severity'), severity):
            score += 0.3

        # 文件扩展名匹配
        file_ext = Path(file_path).suffix if file_path else 'unknown'
        if features.get('file_extension') == file_ext:
            score += 1.0

        # 文件模式匹配
        file_pattern = self._extract_file_pattern(file_path)
        if file_pattern in features.get('file_pattern', ''):
            score += 0.5

        return min(1.0, score / max_score)

    def _severity_compatible(self, severity1: str, severity2: str) -> bool:
        """判断严重程度是否兼容"""
        severity_order = ['info', 'low', 'medium', 'high', 'critical']

        if severity1 not in severity_order or severity2 not in severity_order:
            return False

        # 允许相邻严重程度匹配
        idx1 = severity_order.index(severity1)
        idx2 = severity_order.index(severity2)

        return abs(idx1 - idx2) <= 1

    def _generate_recommendation(self, pattern: Pattern) -> str:
        """生成建议"""
        if pattern.success_rate >= 0.9:
            return f"高成功率模式（{pattern.success_rate:.1%}），建议使用相同的修复方式"
        elif pattern.success_rate >= 0.7:
            return f"中等成功率模式（{pattern.success_rate:.1%}），可以参考"
        else:
            return f"成功率较低（{pattern.success_rate:.1%}），谨慎使用"

    def get_best_patterns(
        self,
        pattern_type: Optional[PatternType] = None,
        min_confidence: Optional[float] = None,
        limit: int = 10
    ) -> List[Pattern]:
        """
        获取最佳模式

        Args:
            pattern_type: 模式类型（可选）
            min_confidence: 最小置信度（可选）
            limit: 限制数量

        Returns:
            模式列表
        """
        patterns = self.patterns.values()

        if pattern_type:
            patterns = [p for p in patterns if p.type == pattern_type]

        if min_confidence is not None:
            patterns = [p for p in patterns if p.confidence >= min_confidence]

        # 按置信度和成功率排序
        patterns = sorted(
            patterns,
            key=lambda p: (p.confidence, p.success_rate),
            reverse=True
        )

        return list(patterns)[:limit]

    def analyze_patterns(self) -> Dict[str, Any]:
        """
        分析模式

        Returns:
            分析结果
        """
        self.stats['learning_cycles'] += 1

        # 高置信度模式
        high_conf = [p for p in self.patterns.values() if p.confidence >= self.min_confidence]
        self.stats['high_confidence_patterns'] = len(high_conf)

        # 按类型统计
        by_type = {
            pt.value: len([p for p in self.patterns.values() if p.type == pt])
            for pt in PatternType
        }

        # 成功率分布
        success_rates = [p.success_rate for p in self.patterns.values()]

        return {
            'total_patterns': len(self.patterns),
            'high_confidence_patterns': len(high_conf),
            'by_type': by_type,
            'avg_success_rate': sum(success_rates) / len(success_rates) if success_rates else 0.0,
            'max_success_rate': max(success_rates) if success_rates else 0.0,
            'min_success_rate': min(success_rates) if success_rates else 0.0,
        }

    def forget_old_patterns(self, days: int = 30):
        """
        忘记旧模式

        Args:
            days: 天数
        """
        cutoff = datetime.now() - timedelta(days=days)

        to_forget = [
            pid for pid, pattern in self.patterns.items()
            if pattern.last_seen < cutoff
        ]

        for pid in to_forget:
            pattern = self.patterns[pid]
            del self.patterns[pid]
            self.by_type[pattern.type].remove(pattern)
            del self.by_key[pattern.pattern_key]

        if to_forget:
            self.logger.info(f"忘记 {len(to_forget)} 个旧模式")

    def save(self, file_path: str = ".memory/patterns.json"):
        """保存模式"""
        try:
            data = {
                'patterns': [p.to_dict() for p in self.patterns.values()],
                'stats': self.stats,
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            self.logger.info(f"模式已保存: {file_path}")

        except Exception as e:
            self.logger.error(f"保存模式失败: {e}")

    def load(self, file_path: str = ".memory/patterns.json"):
        """加载模式"""
        try:
            path = Path(file_path)
            if not path.exists():
                return

            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 恢复模式
            self.patterns = {}
            self.by_type = defaultdict(list)
            self.by_key = {}

            for p_data in data.get('patterns', []):
                pattern = Pattern.from_dict(p_data)
                self.patterns[pattern.id] = pattern
                self.by_type[pattern.type].append(pattern)
                self.by_key[pattern.pattern_key] = pattern

            # 恢复统计
            self.stats.update(data.get('stats', {}))

            self.logger.info(f"模式已加载: {file_path}")

        except Exception as e:
            self.logger.error(f"加载模式失败: {e}")


# 单例
_learner_instance: Optional[PatternLearner] = None


def get_pattern_learner() -> PatternLearner:
    """获取模式学习器单例"""
    global _learner_instance
    if _learner_instance is None:
        _learner_instance = PatternLearner()
    return _learner_instance
