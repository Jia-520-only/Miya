"""测试Neo4j连接"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(Path(__file__).parent / 'config' / '.env')

neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
neo4j_password = os.getenv('NEO4J_PASSWORD')
neo4j_database = os.getenv('NEO4J_DATABASE', 'neo4j')

print(f"=== Neo4j 连接测试 ===")
print(f"URI: {neo4j_uri}")
print(f"用户: {neo4j_user}")
print(f"密码: {'已配置' if neo4j_password else '未配置'}")
print(f"数据库: {neo4j_database}")
print()

try:
    from storage.neo4j_client import Neo4jClient
    
    print("尝试连接Neo4j...")
    client = Neo4jClient(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password,
        database=neo4j_database
    )
    
    if client.is_mock_mode():
        print("[ERROR] 连接失败，进入模拟模式")
        print()
        print("可能的原因：")
        print("1. Neo4j服务未启动")
        print("2. 端口7687未开放")
        print("3. 密码不正确")
        print("4. Neo4j需要首次登录修改密码")
    else:
        print("[SUCCESS] Neo4j连接成功！")
        
        # 测试查询
        result = client.query("RETURN 1 as test")
        print(f"测试查询结果: {result}")
        
except ImportError:
    print("[ERROR] neo4j包未安装")
    print("请运行: pip install neo4j")
except Exception as e:
    print(f"[ERROR] 连接失败: {e}")
    print()
    print("详细错误信息：")
    import traceback
    traceback.print_exc()
