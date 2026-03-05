"""
弥娅 - 配置文件整合GRAG设置
"""

from typing import Optional
from pathlib import Path
import os
import json
import logging
from core.constants import Encoding

logger = logging.getLogger(__name__)


class GRAGConfig:
    """GRAG知识图谱配置"""
    
    def __init__(self):
        self.enabled: bool = True
        self.auto_extract: bool = True
        self.context_length: int = 20
        self.similarity_threshold: float = 0.7
        self.neo4j_uri: Optional[str] = None
        self.neo4j_user: Optional[str] = None
        self.neo4j_password: Optional[str] = None
        self.neo4j_database: str = "neo4j"
    
    def load_from_env(self):
        """从环境变量加载配置"""
        self.enabled = os.getenv('GRAG_ENABLED', 'true').lower() == 'true'
        self.auto_extract = os.getenv('GRAG_AUTO_EXTRACT', 'true').lower() == 'true'
        self.context_length = int(os.getenv('GRAG_CONTEXT_LENGTH', '20'))
        self.similarity_threshold = float(os.getenv('GRAG_SIMILARITY_THRESHOLD', '0.7'))
        self.neo4j_uri = os.getenv('NEO4J_URI')
        self.neo4j_user = os.getenv('NEO4J_USER')
        self.neo4j_password = os.getenv('NEO4J_PASSWORD')
        self.neo4j_database = os.getenv('NEO4J_DATABASE', 'neo4j')
    
    def load_from_config_file(self, config_path: Path):
        """从配置文件加载GRAG设置"""
        try:
            if config_path.exists():
                with open(config_path, 'r', encoding=Encoding.UTF8) as f:
                    config = json.load(f)
                
                grag_cfg = config.get('grag', {})
                self.enabled = grag_cfg.get('enabled', True)
                self.auto_extract = grag_cfg.get('auto_extract', True)
                self.context_length = grag_cfg.get('context_length', 20)
                self.similarity_threshold = grag_cfg.get('similarity_threshold', 0.7)
                self.neo4j_uri = grag_cfg.get('neo4j_uri')
                self.neo4j_user = grag_cfg.get('neo4j_user')
                self.neo4j_password = grag_cfg.get('neo4j_password')
                self.neo4j_database = grag_cfg.get('neo4j_database', 'neo4j')
                
                logger.info(f"从配置文件加载GRAG设置: enabled={self.enabled}")
        except Exception as e:
            logger.error(f"加载GRAG配置失败: {e}")
    
    def validate(self) -> bool:
        """验证配置有效性"""
        if not self.enabled:
            return True  # 禁用时不验证
        
        if not self.neo4j_uri or not self.neo4j_user or not self.neo4j_password:
            logger.warning("GRAG已启用但Neo4j配置不完整，将使用文件存储")
            return False
        
        return True
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "enabled": self.enabled,
            "auto_extract": self.auto_extract,
            "context_length": self.context_length,
            "similarity_threshold": self.similarity_threshold,
            "neo4j_uri": self.neo4j_uri,
            "neo4j_user": self.neo4j_user,
            "neo4j_password": "***",  # 隐藏密码
            "neo4j_database": self.neo4j_database
        }
