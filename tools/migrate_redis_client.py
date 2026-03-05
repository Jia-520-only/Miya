"""
Redis客户端迁移脚本

将旧的Redis客户端使用替换为新的统一异步Redis客户端
"""
import asyncio
import os
from pathlib import Path
import re

# 迁移规则
MIGRATION_RULES = [
    # 旧的导入 -> 新的导入
    (r'from core\.redis_config import (.*)', r'from storage import RedisAsyncClient, RedisConfig, get_redis_client, initialize_redis'),
    (r'from storage import RedisClient', r'from storage import RedisAsyncClient, RedisConfig, get_redis_client, initialize_redis'),
    
    # 旧的初始化 -> 新的初始化
    (r'RedisClient\(', 'RedisAsyncClient('),
    (r'get_redis_client\(', 'get_redis_client('),
    (r'redis = RedisClient\([^)]*\)', 'await initialize_redis()\n    redis = await get_redis_client()'),
    
    # 添加async标记
    (r'def ([a-z_]+)\([^)]*redis[^)]*\):', r'async def \1(*args, **kwargs):'),
]

def migrate_file(file_path: Path) -> bool:
    """迁移单个文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 应用迁移规则
        for pattern, replacement in MIGRATION_RULES:
            content = re.sub(pattern, replacement, content)
        
        # 如果内容有变化，写回文件
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
    
    except Exception as e:
        print(f"错误: 迁移文件 {file_path} 失败: {e}")
        return False

def main():
    """主函数"""
    project_root = Path(__file__).parent.parent
    
    # 需要迁移的文件列表
    files_to_migrate = [
        project_root / 'run' / 'main.py',
        project_root / 'run' / 'health.py',
        project_root / 'tests' / 'archive' / 'test_database_connection.py',
    ]
    
    print("开始Redis客户端迁移...")
    print(f"项目根目录: {project_root}")
    
    migrated_count = 0
    for file_path in files_to_migrate:
        if file_path.exists():
            if migrate_file(file_path):
                print(f"✓ 已迁移: {file_path}")
                migrated_count += 1
            else:
                print(f"- 无需迁移: {file_path}")
        else:
            print(f"✗ 文件不存在: {file_path}")
    
    print(f"\n迁移完成! 共迁移 {migrated_count} 个文件")
    print("\n注意事项:")
    print("1. 所有使用Redis的函数现在都需要标记为async")
    print("2. 初始化Redis时使用: await initialize_redis()")
    print("3. 获取客户端使用: redis = await get_redis_client()")
    print("4. 所有Redis操作都需要使用await")

if __name__ == '__main__':
    main()
