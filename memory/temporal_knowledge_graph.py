"""
时序知识图谱
基于Graphiti和Memobase，支持时间维度的知识演化
"""
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum
from pathlib import Path
from core.constants import Encoding

logger = logging.getLogger(__name__)


class RelationType(Enum):
    """关系类型"""
    KNOWS = "knows"
    WORKS_WITH = "works_with"
    PART_OF = "part_of"
    RELATED_TO = "related_to"
    DEPENDS_ON = "depends_on"
    INFLUENCES = "influences"
    TEMPORAL_PRECEDES = "precedes"
    TEMPORAL_SUCCEEDS = "succeeds"


@dataclass
class TemporalEntity:
    """时序实体"""
    entity_id: str
    entity_type: str  # person, organization, event, concept
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    valid_from: Optional[float] = None  # 有效开始时间
    valid_until: Optional[float] = None  # 有效结束时间


@dataclass
class TemporalRelation:
    """时序关系"""
    relation_id: str
    source_id: str
    target_id: str
    relation_type: RelationType
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    strength: float = 1.0  # 关系强度（0-1）
    valid_from: Optional[float] = None
    valid_until: Optional[float] = None


class TemporalKnowledgeGraph:
    """时序知识图谱"""

    def __init__(self, storage_path: str = "data/temporal_kg"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)

        # 实体存储
        self.entities: Dict[str, TemporalEntity] = {}

        # 关系存储
        self.relations: Dict[str, TemporalRelation] = {}

        # 实体索引
        self.entity_index: Dict[str, Set[str]] = {}  # entity_type -> entity_ids

        # 关系索引
        self.relation_index: Dict[Tuple[str, RelationType], Set[str]] = {}  # (source_id, relation_type) -> target_ids

        # 统计信息
        self.stats = {
            'total_entities': 0,
            'total_relations': 0,
            'entity_types': {},
            'relation_types': {}
        }

    def add_entity(
        self,
        entity_id: str,
        entity_type: str,
        attributes: Optional[Dict[str, Any]] = None,
        valid_from: Optional[float] = None,
        valid_until: Optional[float] = None
    ) -> bool:
        """
        添加实体

        Args:
            entity_id: 实体ID
            entity_type: 实体类型
            attributes: 实体属性
            valid_from: 有效开始时间
            valid_until: 有效结束时间

        Returns:
            是否成功
        """
        try:
            if entity_id in self.entities:
                # 更新现有实体
                entity = self.entities[entity_id]
                entity.updated_at = time.time()

                if attributes:
                    entity.attributes.update(attributes)

                if valid_from:
                    entity.valid_from = valid_from
                if valid_until:
                    entity.valid_until = valid_until

                logger.debug(f"[TKG] 更新实体: {entity_id}")
            else:
                # 创建新实体
                entity = TemporalEntity(
                    entity_id=entity_id,
                    entity_type=entity_type,
                    attributes=attributes or {},
                    valid_from=valid_from,
                    valid_until=valid_until
                )

                self.entities[entity_id] = entity

                # 更新类型索引
                if entity_type not in self.entity_index:
                    self.entity_index[entity_type] = set()
                self.entity_index[entity_type].add(entity_id)

                # 更新统计
                self.stats['total_entities'] += 1
                self.stats['entity_types'][entity_type] = (
                    self.stats['entity_types'].get(entity_type, 0) + 1
                )

                logger.info(f"[TKG] 添加实体: {entity_id}, 类型: {entity_type}")

            return True

        except Exception as e:
            logger.error(f"[TKG] 添加实体失败: {e}")
            return False

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType,
        strength: float = 1.0,
        attributes: Optional[Dict[str, Any]] = None,
        valid_from: Optional[float] = None,
        valid_until: Optional[float] = None
    ) -> bool:
        """
        添加关系

        Args:
            source_id: 源实体ID
            target_id: 目标实体ID
            relation_type: 关系类型
            strength: 关系强度
            attributes: 关系属性
            valid_from: 有效开始时间
            valid_until: 有效结束时间

        Returns:
            是否成功
        """
        if source_id not in self.entities or target_id not in self.entities:
            logger.warning(f"[TKG] 实体不存在: {source_id}, {target_id}")
            return False

        try:
            relation_id = self._generate_relation_id(source_id, target_id, relation_type)

            relation = TemporalRelation(
                relation_id=relation_id,
                source_id=source_id,
                target_id=target_id,
                relation_type=relation_type,
                strength=strength,
                attributes=attributes or {},
                valid_from=valid_from,
                valid_until=valid_until
            )

            self.relations[relation_id] = relation

            # 更新关系索引
            index_key = (source_id, relation_type)
            if index_key not in self.relation_index:
                self.relation_index[index_key] = set()
            self.relation_index[index_key].add(target_id)

            # 更新统计
            self.stats['total_relations'] += 1
            self.stats['relation_types'][relation_type.value] = (
                self.stats['relation_types'].get(relation_type.value, 0) + 1
            )

            logger.info(f"[TKG] 添加关系: {source_id} -> {target_id}, 类型: {relation_type.value}")
            return True

        except Exception as e:
            logger.error(f"[TKG] 添加关系失败: {e}")
            return False

    def query_entities(
        self,
        entity_type: Optional[str] = None,
        time_point: Optional[float] = None,
        attributes_filter: Optional[Dict[str, Any]] = None
    ) -> List[TemporalEntity]:
        """
        查询实体

        Args:
            entity_type: 实体类型（可选）
            time_point: 时间点（可选）
            attributes_filter: 属性过滤器（可选）

        Returns:
            实体列表
        """
        results = []

        for entity in self.entities.values():
            # 类型过滤
            if entity_type and entity.entity_type != entity_type:
                continue

            # 时间点过滤
            if time_point:
                if entity.valid_from and time_point < entity.valid_from:
                    continue
                if entity.valid_until and time_point > entity.valid_until:
                    continue

            # 属性过滤
            if attributes_filter:
                match = True
                for key, value in attributes_filter.items():
                    if entity.attributes.get(key) != value:
                        match = False
                        break

                if not match:
                    continue

            results.append(entity)

        return results

    def query_relations(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        relation_type: Optional[RelationType] = None,
        time_point: Optional[float] = None,
        min_strength: float = 0.0
    ) -> List[TemporalRelation]:
        """
        查询关系

        Args:
            source_id: 源实体ID（可选）
            target_id: 目标实体ID（可选）
            relation_type: 关系类型（可选）
            time_point: 时间点（可选）
            min_strength: 最小关系强度

        Returns:
            关系列表
        """
        results = []

        for relation in self.relations.values():
            # 源过滤
            if source_id and relation.source_id != source_id:
                continue

            # 目标过滤
            if target_id and relation.target_id != target_id:
                continue

            # 类型过滤
            if relation_type and relation.relation_type != relation_type:
                continue

            # 时间点过滤
            if time_point:
                if relation.valid_from and time_point < relation.valid_from:
                    continue
                if relation.valid_until and time_point > relation.valid_until:
                    continue

            # 强度过滤
            if relation.strength < min_strength:
                continue

            results.append(relation)

        return results

    def track_relation_evolution(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType,
        time_range: Tuple[float, float]
    ) -> List[TemporalRelation]:
        """
        跟踪关系演化

        Args:
            source_id: 源实体ID
            target_id: 目标实体ID
            relation_type: 关系类型
            time_range: 时间范围（start, end）

        Returns:
            关系历史
        """
        base_id = self._generate_relation_id(source_id, target_id, relation_type)

        # 查找所有相关关系（可能包含时间戳后缀）
        related_relations = [
            r for r in self.relations.values()
            if (r.source_id == source_id and
                r.target_id == target_id and
                r.relation_type == relation_type)
        ]

        # 时间范围过滤
        results = []
        for relation in related_relations:
            created_at = relation.created_at

            if time_range[0] <= created_at <= time_range[1]:
                results.append(relation)

        # 按时间排序
        results.sort(key=lambda r: r.created_at)
        return results

    def get_entity_context(
        self,
        entity_id: str,
        depth: int = 2,
        time_point: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        获取实体上下文（邻居关系）

        Args:
            entity_id: 实体ID
            depth: 深度
            time_point: 时间点（可选）

        Returns:
            上下文字典
        """
        context = {
            'entity': self.entities.get(entity_id),
            'outgoing_relations': [],
            'incoming_relations': [],
            'neighbors': set()
        }

        if entity_id not in self.entities:
            return context

        # 查找出向关系
        outgoing = self.query_relations(
            source_id=entity_id,
            time_point=time_point
        )

        for relation in outgoing:
            target = self.entities.get(relation.target_id)
            if target:
                context['outgoing_relations'].append({
                    'relation': relation,
                    'target': target
                })
                context['neighbors'].add(relation.target_id)

        # 查找入向关系
        incoming = self.query_relations(
            target_id=entity_id,
            time_point=time_point
        )

        for relation in incoming:
            source = self.entities.get(relation.source_id)
            if source:
                context['incoming_relations'].append({
                    'relation': relation,
                    'source': source
                })
                context['neighbors'].add(relation.source_id)

        # 递归扩展邻居（如果depth > 1）
        if depth > 1:
            neighbor_context = {}
            for neighbor_id in context['neighbors']:
                neighbor_context[neighbor_id] = self.get_entity_context(
                    neighbor_id,
                    depth=depth - 1,
                    time_point=time_point
                )

            context['neighbor_context'] = neighbor_context

        return context

    def evolve_entity(
        self,
        entity_id: str,
        new_attributes: Dict[str, Any],
        evolution_time: Optional[float] = None
    ) -> bool:
        """
        演化实体

        Args:
            entity_id: 实体ID
            new_attributes: 新属性
            evolution_time: 演化时间（可选）

        Returns:
            是否成功
        """
        if entity_id not in self.entities:
            logger.warning(f"[TKG] 实体不存在: {entity_id}")
            return False

        entity = self.entities[entity_id]

        # 更新属性
        entity.attributes.update(new_attributes)
        entity.updated_at = evolution_time or time.time()

        logger.info(f"[TKG] 演化实体: {entity_id}")
        return True

    def evolve_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType,
        new_strength: float,
        evolution_time: Optional[float] = None
    ) -> bool:
        """
        演化关系

        Args:
            source_id: 源实体ID
            target_id: 目标实体ID
            relation_type: 关系类型
            new_strength: 新强度
            evolution_time: 演化时间（可选）

        Returns:
            是否成功
        """
        relation_id = self._generate_relation_id(source_id, target_id, relation_type)

        if relation_id not in self.relations:
            logger.warning(f"[TKG] 关系不存在: {relation_id}")
            return False

        relation = self.relations[relation_id]
        relation.strength = new_strength
        relation.updated_at = evolution_time or time.time()

        logger.info(f"[TKG] 演化关系: {relation_id}, 强度: {new_strength}")
        return True

    def delete_entity(self, entity_id: str) -> bool:
        """
        删除实体

        Args:
            entity_id: 实体ID

        Returns:
            是否成功
        """
        if entity_id not in self.entities:
            return False

        entity = self.entities[entity_id]

        # 从类型索引移除
        entity_type = entity.entity_type
        if entity_type in self.entity_index:
            self.entity_index[entity_type].discard(entity_id)

        # 删除实体
        del self.entities[entity_id]

        # 删除相关关系
        to_remove = [
            rid for rid, rel in self.relations.items()
            if rel.source_id == entity_id or rel.target_id == entity_id
        ]

        for rid in to_remove:
            del self.relations[rid]

        logger.info(f"[TKG] 删除实体: {entity_id}, 相关关系: {len(to_remove)}")
        return True

    def _generate_relation_id(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType
    ) -> str:
        """生成关系ID"""
        return f"{source_id}_{relation_type.value}_{target_id}"

    def save_to_disk(self):
        """保存到磁盘"""
        try:
            filepath = self.storage_path / "temporal_kg.json"

            data = {
                'entities': {
                    eid: {
                        'entity_id': e.entity_id,
                        'entity_type': e.entity_type,
                        'attributes': e.attributes,
                        'created_at': e.created_at,
                        'updated_at': e.updated_at,
                        'valid_from': e.valid_from,
                        'valid_until': e.valid_until
                    }
                    for eid, e in self.entities.items()
                },
                'relations': {
                    rid: {
                        'relation_id': r.relation_id,
                        'source_id': r.source_id,
                        'target_id': r.target_id,
                        'relation_type': r.relation_type.value,
                        'strength': r.strength,
                        'attributes': r.attributes,
                        'created_at': r.created_at,
                        'valid_from': r.valid_from,
                        'valid_until': r.valid_until
                    }
                    for rid, r in self.relations.items()
                },
                'statistics': self.stats,
                'saved_at': time.time()
            }

            with open(filepath, 'w', encoding=Encoding.UTF8) as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"[TKG] 保存到磁盘: {len(self.entities)}实体, {len(self.relations)}关系")

        except Exception as e:
            logger.error(f"[TKG] 保存失败: {e}")

    def load_from_disk(self) -> bool:
        """从磁盘加载"""
        try:
            filepath = self.storage_path / "temporal_kg.json"

            if not filepath.exists():
                return False

            with open(filepath, 'r', encoding=Encoding.UTF8) as f:
                data = json.load(f)

            # 加载实体
            for eid, e_data in data.get('entities', {}).items():
                self.entities[eid] = TemporalEntity(
                    entity_id=e_data['entity_id'],
                    entity_type=e_data['entity_type'],
                    attributes=e_data.get('attributes', {}),
                    created_at=e_data.get('created_at', time.time()),
                    updated_at=e_data.get('updated_at', time.time()),
                    valid_from=e_data.get('valid_from'),
                    valid_until=e_data.get('valid_until')
                )

                # 更新索引
                e_type = self.entities[eid].entity_type
                if e_type not in self.entity_index:
                    self.entity_index[e_type] = set()
                self.entity_index[e_type].add(eid)

            # 加载关系
            for rid, r_data in data.get('relations', {}).items():
                self.relations[rid] = TemporalRelation(
                    relation_id=r_data['relation_id'],
                    source_id=r_data['source_id'],
                    target_id=r_data['target_id'],
                    relation_type=RelationType(r_data['relation_type']),
                    strength=r_data.get('strength', 1.0),
                    attributes=r_data.get('attributes', {}),
                    created_at=r_data.get('created_at', time.time()),
                    valid_from=r_data.get('valid_from'),
                    valid_until=r_data.get('valid_until')
                )

                # 更新索引
                index_key = (r_data['source_id'], RelationType(r_data['relation_type']))
                if index_key not in self.relation_index:
                    self.relation_index[index_key] = set()
                self.relation_index[index_key].add(r_data['target_id'])

            # 加载统计
            self.stats = data.get('statistics', {})

            logger.info(f"[TKG] 从磁盘加载: {len(self.entities)}实体, {len(self.relations)}关系")
            return True

        except Exception as e:
            logger.error(f"[TKG] 加载失败: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_entities': len(self.entities),
            'total_relations': len(self.relations),
            'entity_types': dict(
                (k, len(v))
                for k, v in self.entity_index.items()
            ),
            'relation_types': self.stats['relation_types'],
            'avg_strength': (
                sum(r.strength for r in self.relations.values()) /
                max(len(self.relations), 1)
            ) if self.relations else 0.0
        }
