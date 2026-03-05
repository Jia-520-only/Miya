"""
Neo4j客户端 - 知识图谱/记忆五元组
管理图数据库存储和查询
支持真实Neo4j连接和模拟回退模式
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Neo4j客户端 - 支持真实连接和模拟回退"""

    def __init__(self, uri: str = 'bolt://localhost:7687',
                 user: str = 'neo4j', password: str = None,
                 database: str = 'neo4j', use_mock: bool = None):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self._driver = None
        self._use_mock = use_mock

        # 模拟图存储（回退模式）
        self._nodes = {}  # node_id -> node_data
        self._relationships = []  # List[relationship_data]
        self._labels_index = {}  # label -> List[node_id]

        # 尝试连接真实Neo4j
        if not self._use_mock:
            self._connect_real()

    def _connect_real(self) -> bool:
        """尝试连接真实Neo4j"""
        try:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )

            # 测试连接
            with self._driver.session(database=self.database) as session:
                session.run("RETURN 1")

            logger.info(f"✅ 已连接到真实Neo4j: {self.uri}")
            self._use_mock = False
            return True

        except ImportError:
            logger.warning("⚠️ neo4j包未安装，使用模拟模式")
            self._use_mock = True
            return False
        except Exception as e:
            logger.warning(f"⚠️ Neo4j连接失败: {e}，使用模拟模式")
            self._driver = None
            self._use_mock = True
            return False

    def is_mock_mode(self) -> bool:
        """是否为模拟模式"""
        return self._use_mock

    def connect(self) -> bool:
        """连接Neo4j"""
        if self._use_mock:
            return True

        if self._driver:
            try:
                with self._driver.session(database=self.database) as session:
                    session.run("RETURN 1")
                return True
            except Exception as e:
                logger.error(f"Neo4j连接失败: {e}")
                return False

        return self._connect_real()

    def create_node(self, labels: List[str], properties: Dict = None) -> str:
        """
        创建节点

        Returns:
            节点ID
        """
        if self._use_mock:
            return self._create_node_mock(labels, properties)

        try:
            with self._driver.session(database=self.database) as session:
                # 构建Cypher语句
                label_str = ":".join(labels)
                props_str = ""
                if properties:
                    props_str = ", ".join([f"{k}: {self._format_value(v)}"
                                          for k, v in properties.items()])

                cypher = f"CREATE (n:{label_str} {{{props_str}}}) RETURN id(n) as id"

                result = session.run(cypher)
                record = result.single()
                return str(record["id"])

        except Exception as e:
            logger.error(f"Neo4j create_node失败: {e}")
            return self._create_node_mock(labels, properties)

    def _create_node_mock(self, labels: List[str], properties: Dict = None) -> str:
        """模拟创建节点"""
        node_id = f"node_{len(self._nodes)}_{datetime.now().timestamp()}"

        node_data = {
            'id': node_id,
            'labels': labels,
            'properties': properties or {},
            'created_at': datetime.now().isoformat()
        }

        self._nodes[node_id] = node_data

        # 更新标签索引
        for label in labels:
            if label not in self._labels_index:
                self._labels_index[label] = []
            self._labels_index[label].append(node_id)

        return node_id

    def create_relationship(self, start_node: str, end_node: str,
                           rel_type: str, properties: Dict = None) -> str:
        """
        创建关系

        Returns:
            关系ID
        """
        if self._use_mock:
            return self._create_relationship_mock(start_node, end_node, rel_type, properties)

        try:
            with self._driver.session(database=self.database) as session:
                # 构建Cypher语句
                props_str = ""
                if properties:
                    props_str = ", ".join([f"{k}: {self._format_value(v)}"
                                          for k, v in properties.items()])

                cypher = f"""
                MATCH (a), (b)
                WHERE id(a) = {start_node} AND id(b) = {end_node}
                CREATE (a)-[r:{rel_type} {{{props_str}}}]->(b)
                RETURN id(r) as id
                """

                result = session.run(cypher)
                record = result.single()
                return str(record["id"])

        except Exception as e:
            logger.error(f"Neo4j create_relationship失败: {e}")
            return self._create_relationship_mock(start_node, end_node, rel_type, properties)

    def _create_relationship_mock(self, start_node: str, end_node: str,
                                  rel_type: str, properties: Dict = None) -> str:
        """模拟创建关系"""
        rel_id = f"rel_{len(self._relationships)}_{datetime.now().timestamp()}"

        relationship = {
            'id': rel_id,
            'start_node': start_node,
            'end_node': end_node,
            'type': rel_type,
            'properties': properties or {},
            'created_at': datetime.now().isoformat()
        }

        self._relationships.append(relationship)
        return rel_id

    def _format_value(self, value: Any) -> str:
        """格式化Cypher值"""
        if value is None:
            return "null"
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            escaped_value = value.replace("'", "\\'")
            return f"'{escaped_value}'"
        else:
            return f"'{str(value)}'"

    def get_node(self, node_id: str) -> Optional[Dict]:
        """获取节点"""
        if self._use_mock:
            return self._nodes.get(node_id)

        try:
            with self._driver.session(database=self.database) as session:
                cypher = f"MATCH (n) WHERE id(n) = {node_id} RETURN n"
                result = session.run(cypher)
                record = result.single()

                if record:
                    node = record["n"]
                    return {
                        'id': node_id,
                        'labels': list(node.labels),
                        'properties': dict(node)
                    }

        except Exception as e:
            logger.error(f"Neo4j get_node失败: {e}")

        return None

    def get_relationship(self, rel_id: str) -> Optional[Dict]:
        """获取关系"""
        if self._use_mock:
            for rel in self._relationships:
                if rel['id'] == rel_id:
                    return rel
            return None

        try:
            with self._driver.session(database=self.database) as session:
                cypher = f"MATCH ()-[r]->() WHERE id(r) = {rel_id} RETURN r"
                result = session.run(cypher)
                record = result.single()

                if record:
                    rel = record["r"]
                    return {
                        'id': rel_id,
                        'type': rel.type,
                        'start_node': str(rel.start_node.id),
                        'end_node': str(rel.end_node.id),
                        'properties': dict(rel)
                    }

        except Exception as e:
            logger.error(f"Neo4j get_relationship失败: {e}")

        return None

    def find_nodes_by_label(self, label: str) -> List[Dict]:
        """按标签查找节点"""
        if self._use_mock:
            node_ids = self._labels_index.get(label, [])
            return [self._nodes[nid] for nid in node_ids if nid in self._nodes]

        try:
            with self._driver.session(database=self.database) as session:
                cypher = f"MATCH (n:{label}) RETURN n"
                result = session.run(cypher)

                nodes = []
                for record in result:
                    node = record["n"]
                    nodes.append({
                        'id': str(node.id),
                        'labels': list(node.labels),
                        'properties': dict(node)
                    })

                return nodes

        except Exception as e:
            logger.error(f"Neo4j find_nodes_by_label失败: {e}")
            return []

    def find_nodes_by_property(self, property_name: str,
                               property_value: Any) -> List[Dict]:
        """按属性查找节点"""
        if self._use_mock:
            results = []
            for node in self._nodes.values():
                props = node.get('properties', {})
                if props.get(property_name) == property_value:
                    results.append(node)
            return results

        try:
            with self._driver.session(database=self.database) as session:
                cypher = f"""
                MATCH (n)
                WHERE n.{property_name} = {self._format_value(property_value)}
                RETURN n
                """
                result = session.run(cypher)

                nodes = []
                for record in result:
                    node = record["n"]
                    nodes.append({
                        'id': str(node.id),
                        'labels': list(node.labels),
                        'properties': dict(node)
                    })

                return nodes

        except Exception as e:
            logger.error(f"Neo4j find_nodes_by_property失败: {e}")
            return []

    def get_relationships(self, node_id: str,
                          direction: str = 'all') -> List[Dict]:
        """
        获取节点的关系

        Args:
            node_id: 节点ID
            direction: 'out', 'in', 或 'all'
        """
        if self._use_mock:
            return self._get_relationships_mock(node_id, direction)

        try:
            with self._driver.session(database=self.database) as session:
                if direction == 'out':
                    cypher = f"MATCH (n)-[r]->() WHERE id(n) = {node_id} RETURN r, startNode(r), endNode(r)"
                elif direction == 'in':
                    cypher = f"MATCH ()-[r]->(n) WHERE id(n) = {node_id} RETURN r, startNode(r), endNode(r)"
                else:  # all
                    cypher = f"MATCH (n)-[r]-(m) WHERE id(n) = {node_id} RETURN r, startNode(r), endNode(r)"

                result = session.run(cypher)

                relationships = []
                for record in result:
                    rel = record["r"]
                    relationships.append({
                        'id': str(rel.id),
                        'type': rel.type,
                        'start_node': str(record['startNode(r)'].id),
                        'end_node': str(record['endNode(r)'].id),
                        'properties': dict(rel)
                    })

                return relationships

        except Exception as e:
            logger.error(f"Neo4j get_relationships失败: {e}")
            return self._get_relationships_mock(node_id, direction)

    def _get_relationships_mock(self, node_id: str, direction: str = 'all') -> List[Dict]:
        """模拟获取节点的关系"""
        relationships = []

        for rel in self._relationships:
            if direction in ['out', 'all'] and rel['start_node'] == node_id:
                relationships.append(rel)
            elif direction in ['in', 'all'] and rel['end_node'] == node_id:
                relationships.append(rel)

        return relationships

    def query(self, cypher: str, params: Dict = None) -> List[Dict]:
        """
        执行Cypher查询

        Args:
            cypher: Cypher查询语句
            params: 查询参数
        """
        if self._use_mock:
            return self._query_mock(cypher, params)

        try:
            with self._driver.session(database=self.database) as session:
                result = session.run(cypher, params or {})

                results = []
                for record in result:
                    results.append(dict(record))

                return results

        except Exception as e:
            logger.error(f"Neo4j query失败: {e}")
            return self._query_mock(cypher, params)

    def _query_mock(self, cypher: str, params: Dict = None) -> List[Dict]:
        """
        执行Cypher查询（简化模拟实现）

        仅支持简单的MATCH查询
        """
        results = []

        # 解析简单查询
        if 'MATCH' in cypher and 'RETURN' in cypher:
            # 提取标签
            import re
            label_match = re.search(r':(\w+)', cypher)
            if label_match:
                node_label = label_match.group(1)
                results = self.find_nodes_by_label(node_label)
            else:
                results = list(self._nodes.values())

        return results

    def delete_node(self, node_id: str) -> bool:
        """删除节点"""
        if self._use_mock:
            return self._delete_node_mock(node_id)

        try:
            with self._driver.session(database=self.database) as session:
                # 先删除关系
                session.run(f"MATCH (n)-[r]-() WHERE id(n) = {node_id} DELETE r")
                # 删除节点
                session.run(f"MATCH (n) WHERE id(n) = {node_id} DELETE n")
                return True

        except Exception as e:
            logger.error(f"Neo4j delete_node失败: {e}")
            return self._delete_node_mock(node_id)

    def _delete_node_mock(self, node_id: str) -> bool:
        """模拟删除节点"""
        if node_id not in self._nodes:
            return False

        # 删除相关的关系
        self._relationships = [
            rel for rel in self._relationships
            if rel['start_node'] != node_id and rel['end_node'] != node_id
        ]

        # 删除标签索引
        labels = self._nodes[node_id]['labels']
        for label in labels:
            if label in self._labels_index and node_id in self._labels_index[label]:
                self._labels_index[label].remove(node_id)

        # 删除节点
        del self._nodes[node_id]
        return True

    def delete_relationship(self, rel_id: str) -> bool:
        """删除关系"""
        if self._use_mock:
            return self._delete_relationship_mock(rel_id)

        try:
            with self._driver.session(database=self.database) as session:
                session.run(f"MATCH ()-[r]->() WHERE id(r) = {rel_id} DELETE r")
                return True

        except Exception as e:
            logger.error(f"Neo4j delete_relationship失败: {e}")
            return self._delete_relationship_mock(rel_id)

    def _delete_relationship_mock(self, rel_id: str) -> bool:
        """模拟删除关系"""
        for i, rel in enumerate(self._relationships):
            if rel['id'] == rel_id:
                del self._relationships[i]
                return True
        return False

    def get_stats(self) -> Dict:
        """获取统计信息"""
        if self._use_mock:
            return {
                'mode': 'mock',
                'total_nodes': len(self._nodes),
                'total_relationships': len(self._relationships),
                'labels': list(self._labels_index.keys())
            }

        try:
            with self._driver.session(database=self.database) as session:
                # 统计节点
                node_count = session.run("MATCH (n) RETURN count(n) as count").single()["count"]

                # 统计关系
                rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]

                # 获取标签
                labels_result = session.run("MATCH (n) RETURN DISTINCT labels(n) as labels")
                labels = []
                for record in labels_result:
                    labels.extend(record["labels"])

                return {
                    'mode': 'real',
                    'total_nodes': node_count,
                    'total_relationships': rel_count,
                    'labels': labels
                }

        except Exception as e:
            logger.error(f"Neo4j get_stats失败: {e}")
            return {
                'mode': 'real',
                'total_nodes': len(self._nodes),
                'total_relationships': len(self._relationships),
                'labels': list(self._labels_index.keys())
            }

    def create_memory_quintuple(self, subject: str, predicate: str,
                               obj: str, context: str, emotion: str) -> str:
        """
        创建记忆五元组

        Args:
            subject: 主体
            predicate: 谓词/关系
            obj: 客体
            context: 上下文
            emotion: 情绪

        Returns:
            关系ID
        """
        if self._use_mock:
            return self._create_memory_quintuple_mock(subject, predicate, obj, context, emotion)

        try:
            with self._driver.session(database=self.database) as session:
                # 查找或创建主体节点
                cypher = f"""
                MERGE (s:Memory:Entity {{name: '{subject}'}})
                RETURN id(s) as id
                """
                result = session.run(cypher)
                subject_id = str(result.single()["id"])

                # 查找或创建客体节点
                cypher = f"""
                MERGE (o:Memory:Entity {{name: '{obj}'}})
                RETURN id(o) as id
                """
                result = session.run(cypher)
                obj_id = str(result.single()["id"])

                # 创建关系
                cypher = f"""
                MATCH (s), (o)
                WHERE id(s) = {subject_id} AND id(o) = {obj_id}
                CREATE (s)-[r:{predicate} {{
                    context: '{context}',
                    emotion: '{emotion}',
                    created_at: '{datetime.now().isoformat()}'
                }}]->(o)
                RETURN id(r) as id
                """
                result = session.run(cypher)
                return str(result.single()["id"])

        except Exception as e:
            logger.error(f"Neo4j create_memory_quintuple失败: {e}")
            return self._create_memory_quintuple_mock(subject, predicate, obj, context, emotion)

    def _create_memory_quintuple_mock(self, subject: str, predicate: str,
                                      obj: str, context: str, emotion: str) -> str:
        """模拟创建记忆五元组"""
        # 查找或创建主体节点
        subject_nodes = self.find_nodes_by_property('name', subject)
        if subject_nodes:
            subject_id = subject_nodes[0]['id']
        else:
            subject_id = self.create_node(
                labels=['Memory', 'Entity'],
                properties={'name': subject}
            )

        # 查找或创建客体节点
        obj_nodes = self.find_nodes_by_property('name', obj)
        if obj_nodes:
            obj_id = obj_nodes[0]['id']
        else:
            obj_id = self.create_node(
                labels=['Memory', 'Entity'],
                properties={'name': obj}
            )

        # 创建关系
        rel_id = self.create_relationship(
            start_node=subject_id,
            end_node=obj_id,
            rel_type=predicate,
            properties={
                'context': context,
                'emotion': emotion,
                'created_at': datetime.now().isoformat()
            }
        )

        return rel_id

    def query_memory_by_emotion(self, emotion: str) -> List[Dict]:
        """按情绪查询记忆"""
        if self._use_mock:
            results = []
            for rel in self._relationships:
                if rel.get('properties', {}).get('emotion') == emotion:
                    results.append(rel)
            return results

        try:
            with self._driver.session(database=self.database) as session:
                cypher = f"""
                MATCH (s)-[r]->(o)
                WHERE r.emotion = '{emotion}'
                RETURN s, r, o
                """
                result = session.run(cypher)

                memories = []
                for record in result:
                    memories.append({
                        'subject': record["s"]['name'],
                        'predicate': record["r"].type,
                        'object': record["o"]['name'],
                        'context': record["r"]['context'],
                        'emotion': record["r"]['emotion']
                    })

                return memories

        except Exception as e:
            logger.error(f"Neo4j query_memory_by_emotion失败: {e}")
            return []

    def close(self) -> None:
        """关闭连接"""
        if self._driver:
            try:
                self._driver.close()
                logger.info("Neo4j连接已关闭")
            except Exception as e:
                logger.error(f"关闭Neo4j连接失败: {e}")

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()
