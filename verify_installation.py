"""
验证所有依赖包是否已正确安装
"""

import sys

def check_import(module_name, package_name=None):
    """检查模块是否可以导入"""
    try:
        __import__(module_name)
        print(f"[OK] {module_name} ({package_name or module_name})")
        return True
    except ImportError as e:
        print(f"[FAIL] {module_name} ({package_name or module_name}) - {e}")
        return False

print("=" * 50)
print("依赖包安装验证")
print("=" * 50)

all_ok = True

# 基础依赖
all_ok &= check_import('dotenv', 'python-dotenv')
all_ok &= check_import('numpy', 'numpy')
all_ok &= check_import('websockets', 'websockets')
all_ok &= check_import('httpx', 'httpx')
all_ok &= check_import('tiktoken', 'tiktoken')
all_ok &= check_import('chardet', 'chardet')
all_ok &= check_import('markdown', 'markdown')

# APScheduler
all_ok &= check_import('apscheduler', 'APScheduler')
all_ok &= check_import('croniter', 'croniter')

# Office处理
all_ok &= check_import('pypdf', 'pymupdf')
all_ok &= check_import('PyPDF2', 'PyPDF2')
all_ok &= check_import('docx', 'python-docx')
all_ok &= check_import('pptx', 'python-pptx')
all_ok &= check_import('openpyxl', 'openpyxl')

# 系统工具
all_ok &= check_import('psutil', 'psutil')
all_ok &= check_import('yaml', 'pyyaml')
all_ok &= check_import('pypinyin', 'pypinyin')

# 数据库
all_ok &= check_import('chromadb', 'chromadb')
all_ok &= check_import('numba', 'numba')
all_ok &= check_import('alembic', 'alembic')
all_ok &= check_import('sqlalchemy', 'sqlalchemy')

# Web框架
all_ok &= check_import('fastapi', 'fastapi')
all_ok &= check_import('uvicorn', 'uvicorn')
all_ok &= check_import('pydantic', 'pydantic')
all_ok &= check_import('openai', 'openai')

# GitHub API
all_ok &= check_import('jwt', 'pyjwt')

# Web搜索
all_ok &= check_import('duckduckgo_search', 'duckduckgo-search')

# 音频播放
all_ok &= check_import('pydub', 'pydub')
all_ok &= check_import('simpleaudio', 'simpleaudio')

# Embedding
all_ok &= check_import('sentence_transformers', 'sentence-transformers')

# 代码生成
all_ok &= check_import('jinja2', 'jinja2')

# API模拟
all_ok &= check_import('httpretty', 'httpretty')
all_ok &= check_import('responses', 'responses')

# 加密
all_ok &= check_import('cryptography', 'cryptography')

# 测试
all_ok &= check_import('selenium', 'selenium')

print("=" * 50)
if all_ok:
    print("[OK] 所有依赖包已正确安装！")
    sys.exit(0)
else:
    print("[FAIL] 部分依赖包未安装，请运行: pip install -r requirements.txt")
    sys.exit(1)
