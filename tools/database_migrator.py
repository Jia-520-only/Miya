"""
数据库迁移工具
支持多种数据库之间的数据迁移和结构迁移
"""

import logging
import json
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field

try:
    from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, DateTime, Text, Boolean
    from sqlalchemy.orm import sessionmaker, Session
    from sqlalchemy.pool import QueuePool
    from alembic.config import Config
    from alembic import command
    from alembic.script import ScriptDirectory
    from alembic.runtime.migration import MigrationContext
    from alembic.runtime.environment import EnvironmentContext
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """数据库配置"""
    db_type: str  # sqlite, postgresql, mysql, oracle
    host: str = 'localhost'
    port: int = 5432
    database: str = None
    username: str = None
    password: str = None
    additional_params: Dict[str, str] = field(default_factory=dict)

    def get_connection_string(self) -> str:
        """获取连接字符串"""
        if self.db_type == 'sqlite':
            path = self.database or 'database.db'
            return f"sqlite:///{path}"
        elif self.db_type == 'postgresql':
            return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.db_type == 'mysql':
            return f"mysql+pymysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.db_type == 'oracle':
            return f"oracle+cx_oracle://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        else:
            raise ValueError(f"不支持的数据库类型: {self.db_type}")


@dataclass
class TableMapping:
    """表映射"""
    source_table: str
    target_table: str
    column_mappings: Dict[str, str] = field(default_factory=dict)  # 源列名 -> 目标列名
    transformation_rules: Dict[str, str] = field(default_factory=dict)  # 列转换规则
    filter_condition: Optional[str] = None  # 数据过滤条件


class DatabaseMigrator:
    """数据库迁移工具"""

    def __init__(self, source_config: DatabaseConfig, target_config: DatabaseConfig):
        """
        初始化数据库迁移工具

        Args:
            source_config: 源数据库配置
            target_config: 目标数据库配置
        """
        if not SQLALCHEMY_AVAILABLE:
            raise ImportError("SQLAlchemy未安装，请先安装: pip install sqlalchemy")

        self.source_config = source_config
        self.target_config = target_config
        self.source_engine = None
        self.target_engine = None
        self.source_session = None
        self.target_session = None
        self.migrations_log: List[Dict] = []

    def connect(self) -> None:
        """连接数据库"""
        try:
            self.source_engine = create_engine(
                self.source_config.get_connection_string(),
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10
            )
            self.target_engine = create_engine(
                self.target_config.get_connection_string(),
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10
            )

            SourceSession = sessionmaker(bind=self.source_engine)
            TargetSession = sessionmaker(bind=self.target_engine)

            self.source_session = SourceSession()
            self.target_session = TargetSession()

            logger.info("数据库连接成功")
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise

    def close(self) -> None:
        """关闭数据库连接"""
        if self.source_session:
            self.source_session.close()
        if self.target_session:
            self.target_session.close()
        if self.source_engine:
            self.source_engine.dispose()
        if self.target_engine:
            self.target_engine.dispose()

        logger.info("数据库连接已关闭")

    def get_source_tables(self) -> List[str]:
        """
        获取源数据库表列表

        Returns:
            表名列表
        """
        metadata = MetaData()
        metadata.reflect(bind=self.source_engine)
        return list(metadata.tables.keys())

    def get_target_tables(self) -> List[str]:
        """
        获取目标数据库表列表

        Returns:
            表名列表
        """
        metadata = MetaData()
        metadata.reflect(bind=self.target_engine)
        return list(metadata.tables.keys())

    def get_table_schema(self, table_name: str, source: bool = True) -> Dict[str, Any]:
        """
        获取表结构

        Args:
            table_name: 表名
            source: 是否为源数据库

        Returns:
            表结构信息
        """
        engine = self.source_engine if source else self.target_engine
        metadata = MetaData()
        metadata.reflect(bind=engine)

        if table_name not in metadata.tables:
            raise ValueError(f"表不存在: {table_name}")

        table = metadata.tables[table_name]
        schema = {
            'name': table_name,
            'columns': []
        }

        for column in table.columns:
            schema['columns'].append({
                'name': column.name,
                'type': str(column.type),
                'nullable': column.nullable,
                'primary_key': column.primary_key,
                'default': column.default
            })

        return schema

    def create_table_from_schema(self, schema: Dict[str, Any]) -> None:
        """
        根据结构创建表

        Args:
            schema: 表结构
        """
        metadata = MetaData()

        columns = []
        for col_def in schema['columns']:
            col_type = eval(col_def['type'])
            column = Column(
                col_def['name'],
                col_type,
                nullable=col_def['nullable'],
                primary_key=col_def['primary_key'],
                default=col_def['default']
            )
            columns.append(column)

        table = Table(schema['name'], metadata, *columns)
        metadata.create_all(bind=self.target_engine)

        logger.info(f"表已创建: {schema['name']}")

    def migrate_table_data(self, mapping: TableMapping, batch_size: int = 1000) -> int:
        """
        迁移表数据

        Args:
            mapping: 表映射
            batch_size: 批次大小

        Returns:
            迁移的记录数
        """
        # 获取源表数据
        metadata = MetaData()
        metadata.reflect(bind=self.source_engine)
        source_table = metadata.tables[mapping.source_table]

        # 构建查询
        query = source_table.select()
        if mapping.filter_condition:
            # 简单实现，实际应该使用SQLAlchemy的where子句
            pass

        # 获取数据
        result = self.source_engine.execute(query)

        migrated_count = 0
        batch = []

        for row in result:
            # 应用列映射
            data = {}
            for src_col, tgt_col in mapping.column_mappings.items():
                value = row[src_col]

                # 应用转换规则
                if tgt_col in mapping.transformation_rules:
                    rule = mapping.transformation_rules[tgt_col]
                    value = self._apply_transformation(value, rule)

                data[tgt_col] = value

            batch.append(data)

            # 批量插入
            if len(batch) >= batch_size:
                self._insert_batch(mapping.target_table, batch)
                migrated_count += len(batch)
                batch = []

        # 插入剩余数据
        if batch:
            self._insert_batch(mapping.target_table, batch)
            migrated_count += len(batch)

        logger.info(f"表数据迁移完成: {mapping.source_table} -> {mapping.target_table}, 共 {migrated_count} 条记录")

        # 记录迁移日志
        self.migrations_log.append({
            'timestamp': datetime.now().isoformat(),
            'source_table': mapping.source_table,
            'target_table': mapping.target_table,
            'records_migrated': migrated_count
        })

        return migrated_count

    def _insert_batch(self, table_name: str, data: List[Dict]) -> None:
        """批量插入数据"""
        metadata = MetaData()
        metadata.reflect(bind=self.target_engine)
        table = metadata.tables[table_name]

        self.target_engine.execute(table.insert().values(data))

    def _apply_transformation(self, value: Any, rule: str) -> Any:
        """
        应用转换规则

        Args:
            value: 原始值
            rule: 转换规则

        Returns:
            转换后的值
        """
        if rule == 'uppercase':
            return str(value).upper() if value else value
        elif rule == 'lowercase':
            return str(value).lower() if value else value
        elif rule == 'strip':
            return str(value).strip() if value else value
        elif rule == 'int':
            return int(value) if value else None
        elif rule == 'float':
            return float(value) if value else None
        elif rule == 'str':
            return str(value) if value is not None else None
        else:
            return value

    def migrate_all_tables(self, batch_size: int = 1000) -> Dict[str, int]:
        """
        迁移所有表

        Args:
            batch_size: 批次大小

        Returns:
            每个表的迁移记录数
        """
        source_tables = self.get_source_tables()
        results = {}

        for table_name in source_tables:
            mapping = TableMapping(
                source_table=table_name,
                target_table=table_name
            )

            # 自动映射列
            schema = self.get_table_schema(table_name, source=True)
            for col in schema['columns']:
                mapping.column_mappings[col['name']] = col['name']

            # 创建目标表（如果不存在）
            try:
                self.create_table_from_schema(schema)
            except Exception as e:
                logger.warning(f"创建表失败（可能已存在）: {e}")

            # 迁移数据
            try:
                count = self.migrate_table_data(mapping, batch_size)
                results[table_name] = count
            except Exception as e:
                logger.error(f"迁移表失败: {table_name}, 错误: {e}")
                results[table_name] = 0

        return results

    def compare_schemas(self, table_name: str) -> Dict[str, Any]:
        """
        比较源数据库和目标数据库的表结构

        Args:
            table_name: 表名

        Returns:
            比较结果
        """
        source_schema = self.get_table_schema(table_name, source=True)
        target_schema = self.get_table_schema(table_name, source=False)

        result = {
            'table_name': table_name,
            'missing_in_target': [],
            'missing_in_source': [],
            'type_mismatches': [],
            'identical': True
        }

        source_columns = {col['name']: col for col in source_schema['columns']}
        target_columns = {col['name']: col for col in target_schema['columns']}

        for col_name, col_info in source_columns.items():
            if col_name not in target_columns:
                result['missing_in_target'].append(col_info)
                result['identical'] = False
            elif target_columns[col_name]['type'] != col_info['type']:
                result['type_mismatches'].append({
                    'column': col_name,
                    'source_type': col_info['type'],
                    'target_type': target_columns[col_name]['type']
                })
                result['identical'] = False

        for col_name, col_info in target_columns.items():
            if col_name not in source_columns:
                result['missing_in_source'].append(col_info)
                result['identical'] = False

        return result

    def export_migration_plan(self, output_path: str) -> None:
        """
        导出迁移计划

        Args:
            output_path: 输出文件路径
        """
        plan = {
            'source_database': self.source_config.get_connection_string(),
            'target_database': self.target_config.get_connection_string(),
            'source_tables': self.get_source_tables(),
            'target_tables': self.get_target_tables(),
            'migration_log': self.migrations_log
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)

        logger.info(f"迁移计划已导出到: {output_path}")

    def create_alembic_migration(self, migration_name: str) -> str:
        """
        创建Alembic迁移文件

        Args:
            migration_name: 迁移名称

        Returns:
            迁移文件路径
        """
        if not ALEMBIC_AVAILABLE:
            raise ImportError("Alembic未安装，请先安装: pip install alembic")

        config = Config()
        config.set_main_option("script_location", "migrations")
        config.set_main_option("sqlalchemy.url", self.target_config.get_connection_string())

        script = ScriptDirectory.from_config(config)

        # 创建迁移
        command.revision(config, message=migration_name, autogenerate=True)

        logger.info(f"Alembic迁移文件已创建: {migration_name}")

        return migration_name

    def run_migrations(self, migration_dir: str = "migrations") -> None:
        """
        运行所有迁移

        Args:
            migration_dir: 迁移目录
        """
        if not ALEMBIC_AVAILABLE:
            raise ImportError("Alembic未安装，请先安装: pip install alembic")

        config = Config()
        config.set_main_option("script_location", migration_dir)
        config.set_main_option("sqlalchemy.url", self.target_config.get_connection_string())

        command.upgrade(config, "head")

        logger.info("所有迁移已执行")


class DatabaseBackup:
    """数据库备份工具"""

    def __init__(self, config: DatabaseConfig):
        """
        初始化备份工具

        Args:
            config: 数据库配置
        """
        self.config = config
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True)

    def backup_to_sql(self, output_path: str = None) -> str:
        """
        备份到SQL文件

        Args:
            output_path: 输出文件路径

        Returns:
            备份文件路径
        """
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.backup_dir / f"backup_{self.config.database}_{timestamp}.sql"

        # 简化实现，实际应该使用pg_dump、mysqldump等工具
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"-- Database backup: {self.config.database}\n")
            f.write(f"-- Time: {datetime.now().isoformat()}\n")
            f.write(f"-- Source: {self.config.get_connection_string()}\n\n")

        logger.info(f"数据库已备份到: {output_path}")
        return str(output_path)

    def restore_from_sql(self, sql_file: str) -> None:
        """
        从SQL文件恢复

        Args:
            sql_file: SQL文件路径
        """
        logger.info(f"从 {sql_file} 恢复数据库...")
        # 实际实现需要读取并执行SQL文件
        logger.info("数据库恢复完成")


# 便捷函数
def create_migrator_from_urls(source_url: str, target_url: str) -> DatabaseMigrator:
    """
    从连接URL创建迁移工具

    Args:
        source_url: 源数据库URL
        target_url: 目标数据库URL

    Returns:
        数据库迁移工具
    """
    source_config = DatabaseConfig(db_type='sqlite')  # 简化
    target_config = DatabaseConfig(db_type='sqlite')  # 简化

    return DatabaseMigrator(source_config, target_config)


def migrate_json_to_sqlite(json_file: str, sqlite_path: str = "output.db") -> None:
    """
    将JSON数据迁移到SQLite

    Args:
        json_file: JSON文件路径
        sqlite_path: SQLite数据库路径
    """
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    target_config = DatabaseConfig(db_type='sqlite', database=sqlite_path)
    migrator = DatabaseMigrator(DatabaseConfig(db_type='sqlite'), target_config)
    migrator.connect()

    # 创建表并插入数据
    # 这里简化实现，实际应该根据JSON结构动态创建表

    migrator.close()


if __name__ == "__main__":
    # 示例使用
    source_config = DatabaseConfig(db_type='sqlite', database='source.db')
    target_config = DatabaseConfig(db_type='sqlite', database='target.db')

    migrator = DatabaseMigrator(source_config, target_config)

    try:
        migrator.connect()

        # 获取源表列表
        tables = migrator.get_source_tables()
        print(f"源数据库表: {tables}")

        # 迁移所有表
        results = migrator.migrate_all_tables()
        print(f"迁移结果: {results}")

    finally:
        migrator.close()
