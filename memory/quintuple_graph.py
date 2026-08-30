"""
弥娅 - 五元组图谱存储
整合NagaAgent的Neo4j图谱系统
"""

import json
import logging
import os
from typing import Optional
from core.constants import Encoding

try:
    from py2neo import Graph, Node, Relationship
    from py2neo.errors import ServiceUnavailable
except ImportError:
    Graph = None  # type: ignore[assignment,misc]
    Node = None  # type: ignore[assignment,misc]
    Relationship = None  # type: ignore[assignment,misc]
    ServiceUnavailable = Exception  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# Neo4j配置变量（全局）
NEO4J_URI: Optional[str] = None
NEO4J_USER: Optional[str] = None
NEO4J_PASSWORD: Optional[str] = None
NEO4J_DATABASE: Optional[str] = None
GRAG_ENABLED: bool = False

# 延迟加载的graph实例
_graph: Optional[Graph] = None
_graph_connection_failed: bool = False  # 连接失败标志，避免重复尝试

# 五元组文件存储路径
QUINTUPLES_FILE = "logs/knowledge_graph/quintuples.json"


def _load_config():
    """加载Neo4j配置"""
    global NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE, GRAG_ENABLED

    if NEO4J_URI is not None:
        return  # 已经加载过配置

    try:
        from config import Settings
        settings = Settings()
        GRAG_ENABLED = settings.get('grag.enabled', True)
        NEO4J_URI = settings.get('neo4j.uri')
        NEO4J_USER = settings.get('neo4j.user')
        NEO4J_PASSWORD = settings.get('neo4j.password')
        NEO4J_DATABASE = settings.get('neo4j.database', 'neo4j')
        print(f"[GRAG] 成功从config模块读取配置: enabled={GRAG_ENABLED}, uri={NEO4J_URI}")
        return
    except Exception as e:
        print(f"[GRAG] 无法从config模块读取Neo4j配置: {e}")

    # 兼容旧版本，从config.json读取
    try:
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding=Encoding.UTF8) as f:
                _cfg = json.load(f)

            grag_cfg = _cfg.get('grag', {})
            NEO4J_URI = grag_cfg.get('neo4j_uri')
            NEO4J_USER = grag_cfg.get('neo4j_user')
            NEO4J_PASSWORD = grag_cfg.get('neo4j_password')
            NEO4J_DATABASE = grag_cfg.get('neo4j_database', 'neo4j')
            GRAG_ENABLED = grag_cfg.get('enabled', True)
    except Exception as e:
        print(f"[GRAG] 无法从 config.json 读取Neo4j配置: {e}")
        GRAG_ENABLED = False


def get_graph():
    """获取graph实例（延迟加载）"""
    global _graph, GRAG_ENABLED, _graph_connection_failed

    # 已经连接失败过，不再重试
    if _graph_connection_failed:
        return None

    if _graph is None:
        if Graph is None:
            GRAG_ENABLED = False
            _graph_connection_failed = True
            return None
            
        # 直接从系统配置获取
        try:
            from config import Settings
            settings = Settings()
            grag_enabled = settings.get('grag.enabled', True)
            neo4j_uri = settings.get('neo4j.uri')
            neo4j_user = settings.get('neo4j.user')
            neo4j_password = settings.get('neo4j.password')
            neo4j_database = settings.get('neo4j.database', 'neo4j')

            if grag_enabled and neo4j_uri and neo4j_user and neo4j_password:
                try:
                    _graph = Graph(neo4j_uri, auth=(neo4j_user, neo4j_password), name=neo4j_database, timeout=NetworkTimeout.REDIS_CONNECT_TIMEOUT)
                    _graph.service.kernel_version
                    print("[GRAG] 成功连接到 Neo4j。")
                    GRAG_ENABLED = True
                except ServiceUnavailable:
                    print("[GRAG] 未能连接到 Neo4j，图数据库功能已禁用。请检查 Neo4j 是否正在运行以及配置是否正确。")
                    _graph = None
                    GRAG_ENABLED = False
                    _graph_connection_failed = True
                except Exception as e:
                    print(f"[GRAG] Neo4j连接失败: {e}")
                    _graph = None
                    GRAG_ENABLED = False
                    _graph_connection_failed = True
            else:
                print(f"[GRAG] GRAG未启用或配置不完整: enabled={grag_enabled}, uri={neo4j_uri}")
                GRAG_ENABLED = False
                _graph_connection_failed = True
        except Exception as e:
            print(f"[GRAG] 无法加载配置: {e}")
            GRAG_ENABLED = False
            _graph_connection_failed = True

    return _graph


def load_quintuples():
    """从文件加载五元组"""
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(QUINTUPLES_FILE), exist_ok=True)
        
        with open(QUINTUPLES_FILE, 'r', encoding=Encoding.UTF8) as f:
            return set(tuple(t) for t in json.load(f))
    except FileNotFoundError:
        return set()
    except Exception as e:
        logger.error(f"加载五元组失败: {e}")
        return set()


def save_quintuples(quintuples):
    """保存五元组到文件"""
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(QUINTUPLES_FILE), exist_ok=True)
        
        with open(QUINTUPLES_FILE, 'w', encoding=Encoding.UTF8) as f:
            json.dump(list(quintuples), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存五元组失败: {e}")


def store_quintuples(new_quintuples) -> bool:
    """存储五元组到文件和Neo4j，返回是否成功"""
    try:
        all_quintuples = load_quintuples()
        all_quintuples.update(new_quintuples)  # 集合自动去重

        # 持久化到文件
        save_quintuples(all_quintuples)

        # 获取graph实例（延迟加载）
        graph = get_graph()

        # 同步更新Neo4j图谱数据库（仅在graph可用时）
        success = True
        if graph is not None:
            success_count = 0
            for head, head_type, rel, tail, tail_type in new_quintuples:
                if not head or not tail:
                    logger.warning(f"跳过无效五元组，head或tail为空: {(head, head_type, rel, tail, tail_type)}")
                    continue

                try:
                    # 创建带类型的节点
                    h_node = Node("Entity", name=head, entity_type=head_type)
                    t_node = Node("Entity", name=tail, entity_type=tail_type)

                    # 创建关系，保存主体和客体类型信息
                    r = Relationship(h_node, rel, t_node, head_type=head_type, tail_type=tail_type)

                    # 合并节点时使用name和entity_type作为唯一标识
                    graph.merge(h_node, "Entity", "name")
                    graph.merge(t_node, "Entity", "name")
                    graph.merge(r)
                    success_count += 1
                except Exception as e:
                    logger.error(f"存储五元组失败: {head}-{rel}-{tail}, 错误: {e}")
                    success = False

            logger.info(f"成功存储 {success_count}/{len(new_quintuples)} 个五元组到Neo4j")
            # 如果至少成功存储了一个五元组，就认为是成功的
            if success_count > 0:
                return True
            else:
                return False
        else:
            logger.info(f"跳过Neo4j存储（未启用），保存 {len(new_quintuples)} 个五元组到文件")
            return True  # 文件存储成功也算成功
    except Exception as e:
        logger.error(f"存储五元组失败: {e}")
        return False


def get_all_quintuples():
    """获取所有五元组"""
    return load_quintuples()


def query_graph_by_keywords(keywords):
    """从Neo4j图谱中查询相关节点"""
    results = []
    graph = get_graph()
    if graph is not None:
        for kw in keywords:
            query = f"""
            MATCH (e1:Entity)-[r]->(e2:Entity)
            WHERE e1.name CONTAINS '{kw}' OR e2.name CONTAINS '{kw}' OR type(r) CONTAINS '{kw}'
               OR e1.entity_type CONTAINS '{kw}' OR e2.entity_type CONTAINS '{kw}'
            RETURN e1.name, e1.entity_type, type(r), e2.name, e2.entity_type
            LIMIT 5
            """
            res = graph.run(query).data()
            for record in res:
                results.append((
                    record['e1.name'],
                    record['e1.entity_type'],
                    record['type(r)'],
                    record['e2.name'],
                    record['e2.entity_type']
                ))
    return results


def get_graph_stats() -> dict:
    """获取图谱统计信息"""
    try:
        graph = get_graph()
        if graph is None:
            return {
                "neo4j_connected": False,
                "enabled": GRAG_ENABLED
            }
        
        # 查询节点数
        node_count = graph.run("MATCH (n:Entity) RETURN count(n) as count").data()[0]['count']
        
        # 查询关系数
        rel_count = graph.run("MATCH ()-[r]->() RETURN count(r) as count").data()[0]['count']
        
        # 查询实体类型分布
        type_dist = graph.run("""
            MATCH (n:Entity)
            RETURN n.entity_type as type, count(n) as count
            ORDER BY count DESC
            LIMIT 10
        """).data()
        
        # 查询关系类型分布
        rel_dist = graph.run("""
            MATCH ()-[r]->()
            RETURN type(r) as type, count(r) as count
            ORDER BY count DESC
            LIMIT 10
        """).data()
        
        return {
            "neo4j_connected": True,
            "enabled": GRAG_ENABLED,
            "node_count": node_count,
            "relationship_count": rel_count,
            "entity_types": type_dist,
            "relationship_types": rel_dist
        }
    except Exception as e:
        logger.error(f"获取图谱统计失败: {e}")
        return {
            "neo4j_connected": False,
            "enabled": GRAG_ENABLED,
            "error": str(e)
        }
