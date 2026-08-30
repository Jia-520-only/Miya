"""
缓存系统迁移脚本

将旧的缓存管理器迁移到统一缓存系统
"""
import os
import re
from pathlib import Path

# 迁移规则
CACHE_MIGRATION_RULES = [
    # 旧的导入 -> 新的导入
    (r'from core\.cache_manager import ([\w\s,]*)', r'from core.unified_cache import get_cache, unified_cache_get, unified_cache_set, unified_cache_delete, cached'),
    (r'from core\.prompt_cache import ([\w\s,]*)', r'from core.unified_cache import get_cache, cached'),
    
    # 旧的类名 -> 新的函数名
    (r'CacheManager\(', 'get_cache('),
    (r'get_cache_manager\(', 'get_cache('),
    (r'PromptCache\(', 'get_cache("prompt")'),
    (r'get_global_prompt_cache\(\)', 'get_cache("prompt")'),
    
    # 旧的方法 -> 新的异步方法
    (r'(\w+)\.get\(', r'await \1.get('),
    (r'(\w+)\.set\(', r'await \1.set('),
    (r'(\w+)\.delete\(', r'await \1.delete('),
    (r'(\w+)\.clear\(', r'await \1.clear('),
]

def migrate_cache_file(file_path: Path) -> bool:
    """迁移单个缓存文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 添加async导入
        if 'asyncio' not in content and 'await' in content:
            content = 'import asyncio\n' + content
        
        # 应用迁移规则
        for pattern, replacement in CACHE_MIGRATION_RULES:
            content = re.sub(pattern, replacement, content)
        
        # 添加async到使用缓存的函数
        # 查找使用cache操作但不是async的函数
        lines = content.split('\n')
        modified_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            # 检查是否是函数定义且使用缓存
            if re.match(r'def [a-z_]+', line) and 'async' not in line:
                # 查看接下来的几行是否使用缓存
                j = i + 1
                uses_cache = False
                while j < min(i + 10, len(lines)):
                    if any(op in lines[j] for op in ['await cache.', 'await get_cache', '@cached']):
                        uses_cache = True
                        break
                    j += 1
                
                if uses_cache:
                    # 添加async
                    line = line.replace('def ', 'async def ')
            
            modified_lines.append(line)
            i += 1
        
        content = '\n'.join(modified_lines)
        
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
        project_root / 'memory' / 'vector_cache.py',
        project_root / 'hub' / 'memory_engine.py',
    ]
    
    print("开始缓存系统迁移...")
    print(f"项目根目录: {project_root}")
    
    migrated_count = 0
    for file_path in files_to_migrate:
        if file_path.exists():
            if migrate_cache_file(file_path):
                print(f"✓ 已迁移: {file_path}")
                migrated_count += 1
            else:
                print(f"- 无需迁移: {file_path}")
        else:
            print(f"✗ 文件不存在: {file_path}")
    
    print(f"\n迁移完成! 共迁移 {migrated_count} 个文件")
    print("\n注意事项:")
    print("1. 所有缓存操作现在都需要使用await")
    print("2. 使用装饰器: @cached(cache_type='memory', ttl=60)")
    print("3. 手动缓存: await unified_cache_set('type', key, value, ttl)")

if __name__ == '__main__':
    main()
