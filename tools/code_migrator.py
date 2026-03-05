"""
代码逐步迁移工具

帮助将旧代码逐步迁移到新接口
"""
import ast
import os
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional


class CodeMigrator:
    """代码迁移器"""
    
    def __init__(self, project_root: Path):
        """初始化迁移器
        
        Args:
            project_root: 项目根目录
        """
        self.project_root = project_root
        self.migration_rules = self._get_migration_rules()
        self.migration_stats = {
            "files_processed": 0,
            "files_modified": 0,
            "total_changes": 0,
            "errors": []
        }
    
    def _get_migration_rules(self) -> List[Dict]:
        """获取迁移规则"""
        return [
            # Redis客户端迁移
            {
                "type": "redis",
                "pattern": r'from core\.redis_config import',
                "replacement": 'from storage import RedisAsyncClient, initialize_redis, get_redis_client',
                "description": "Redis导入迁移"
            },
            {
                "type": "redis",
                "pattern": r'from storage import RedisClient',
                "replacement": 'from storage import RedisAsyncClient, initialize_redis, get_redis_client',
                "description": "Redis导入迁移"
            },
            {
                "type": "redis",
                "pattern": r'RedisClient\(',
                "replacement": 'RedisAsyncClient(',
                "description": "Redis类名迁移"
            },
            
            # 缓存系统迁移
            {
                "type": "cache",
                "pattern": r'from core\.cache_manager import',
                "replacement": 'from core.unified_cache import get_cache, cached',
                "description": "缓存导入迁移"
            },
            {
                "type": "cache",
                "pattern": r'from core\.prompt_cache import',
                "replacement": 'from core.unified_cache import cached',
                "description": "提示词缓存导入迁移"
            },
            {
                "type": "cache",
                "pattern": r'get_cache_manager\(',
                "replacement": 'get_cache(',
                "description": "缓存管理器迁移"
            },
            
            # 记忆系统迁移
            {
                "type": "memory",
                "pattern": r'from memory\.cognitive_memory_system import CognitiveMemorySystem',
                "replacement": 'from memory import get_memory_manager, MemoryItem, MemoryType',
                "description": "记忆系统导入迁移"
            },
        ]
    
    def analyze_file(self, file_path: Path) -> Dict:
        """分析文件，检测需要迁移的代码
        
        Args:
            file_path: 文件路径
        
        Returns:
            分析结果
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            results = {
                "file": str(file_path),
                "needs_migration": False,
                "migrations": [],
                "lines": content.count('\n'),
                "has_async": 'async def' in content
            }
            
            # 检查每个迁移规则
            for rule in self.migration_rules:
                matches = re.findall(rule["pattern"], content)
                if matches:
                    results["needs_migration"] = True
                    results["migrations"].append({
                        "type": rule["type"],
                        "description": rule["description"],
                        "count": len(matches),
                        "pattern": rule["pattern"]
                    })
            
            return results
        
        except Exception as e:
            return {
                "file": str(file_path),
                "error": str(e),
                "needs_migration": False
            }
    
    def find_files_to_migrate(self, extensions: Tuple = ('.py',)) -> List[Path]:
        """查找需要迁移的文件
        
        Args:
            extensions: 文件扩展名
        
        Returns:
            需要迁移的文件列表
        """
        files_to_migrate = []
        
        for ext in extensions:
            pattern = f"**/*{ext}"
            for file_path in self.project_root.rglob(pattern):
                # 跳过虚拟环境和测试文件
                if any(skip in str(file_path) for skip in ['venv', '.git', 'tests', '__pycache__']):
                    continue
                
                # 分析文件
                result = self.analyze_file(file_path)
                if result.get("needs_migration"):
                    files_to_migrate.append({
                        "path": file_path,
                        "analysis": result
                    })
        
        return files_to_migrate
    
    def generate_migration_plan(self) -> Dict:
        """生成迁移计划
        
        Returns:
            迁移计划
        """
        print("正在分析代码库...")
        files_to_migrate = self.find_files_to_migrate()
        
        # 按类型分组
        by_type = {
            "redis": [],
            "cache": [],
            "memory": []
        }
        
        for file_info in files_to_migrate:
            for migration in file_info["analysis"]["migrations"]:
                mtype = migration["type"]
                if mtype in by_type:
                    by_type[mtype].append(file_info["path"])
        
        # 去重
        for key in by_type:
            by_type[key] = list(set(by_type[key]))
        
        return {
            "total_files": len(files_to_migrate),
            "by_type": by_type,
            "files": files_to_migrate,
            "recommended_order": ["redis", "cache", "memory"]
        }
    
    def migrate_file(self, file_path: Path, dry_run: bool = True) -> Dict:
        """迁移文件
        
        Args:
            file_path: 文件路径
            dry_run: 是否只显示不实际修改
        
        Returns:
            迁移结果
        """
        result = {
            "file": str(file_path),
            "success": False,
            "changes": [],
            "dry_run": dry_run
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            content = original_content
            changes_made = 0
            
            # 应用迁移规则
            for rule in self.migration_rules:
                if re.search(rule["pattern"], content):
                    new_content = re.sub(rule["pattern"], rule["replacement"], content)
                    if new_content != content:
                        result["changes"].append({
                            "type": rule["type"],
                            "description": rule["description"],
                            "pattern": rule["pattern"]
                        })
                        content = new_content
                        changes_made += 1
            
            if changes_made > 0:
                result["success"] = True
                
                if not dry_run:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                
                self.migration_stats["total_changes"] += changes_made
        
        except Exception as e:
            result["error"] = str(e)
            self.migration_stats["errors"].append(str(file_path))
        
        return result
    
    def print_migration_plan(self, plan: Dict):
        """打印迁移计划"""
        print("\n" + "=" * 70)
        print("代码迁移计划")
        print("=" * 70)
        
        print(f"\n总计需要迁移的文件: {plan['total_files']}")
        
        print("\n按类型分类:")
        for mtype, files in plan["by_type"].items():
            print(f"  {mtype.upper()}: {len(files)} 个文件")
        
        print("\n推荐迁移顺序:")
        for i, mtype in enumerate(plan["recommended_order"], 1):
            files = plan["by_type"][mtype]
            print(f"  {i}. {mtype.upper()} - {len(files)} 个文件")
            for file_path in files[:3]:  # 只显示前3个
                print(f"     - {file_path.relative_to(self.project_root)}")
            if len(files) > 3:
                print(f"     - ... 还有 {len(files) - 3} 个文件")
        
        print("\n" + "=" * 70)
    
    def execute_migration(self, plan: Dict, dry_run: bool = True):
        """执行迁移
        
        Args:
            plan: 迁移计划
            dry_run: 是否只显示不实际修改
        """
        print(f"\n开始迁移 (dry_run={dry_run})...")
        
        for mtype in plan["recommended_order"]:
            files = plan["by_type"][mtype]
            
            if not files:
                continue
            
            print(f"\n{mtype.upper()} 迁移:")
            
            for file_path in files:
                result = self.migrate_file(file_path, dry_run)
                
                if result["success"]:
                    print(f"  ✓ {file_path.relative_to(self.project_root)}")
                    for change in result["changes"]:
                        print(f"    - {change['description']}")
                    
                    if not dry_run:
                        self.migration_stats["files_modified"] += 1
                else:
                    print(f"  ✗ {file_path.relative_to(self.project_path)}")
                    if "error" in result:
                        print(f"    错误: {result['error']}")
                
                self.migration_stats["files_processed"] += 1
        
        # 打印统计
        self.print_stats()
    
    def print_stats(self):
        """打印统计信息"""
        print("\n" + "=" * 70)
        print("迁移统计")
        print("=" * 70)
        print(f"处理的文件: {self.migration_stats['files_processed']}")
        print(f"修改的文件: {self.migration_stats['files_modified']}")
        print(f"总变更数: {self.migration_stats['total_changes']}")
        
        if self.migration_stats["errors"]:
            print(f"错误数: {len(self.migration_stats['errors'])}")
            for error in self.migration_stats["errors"]:
                print(f"  - {error}")
        
        print("\n" + "=" * 70)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="代码迁移工具")
    parser.add_argument("--dry-run", action="store_true", help="只分析不修改")
    parser.add_argument("--analyze-only", action="store_true", help="只分析文件")
    
    args = parser.parse_args()
    
    # 获取项目根目录
    project_root = Path(__file__).parent.parent
    
    # 创建迁移器
    migrator = CodeMigrator(project_root)
    
    # 生成迁移计划
    plan = migrator.generate_migration_plan()
    migrator.print_migration_plan(plan)
    
    if args.analyze_only:
        return
    
    # 执行迁移
    if not args.dry_run:
        response = input("\n是否执行迁移? (yes/no): ")
        if response.lower() != 'yes':
            print("取消迁移")
            return
    
    migrator.execute_migration(plan, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
