# -*- mode: python ; coding: utf-8 -*-
"""
弥娅 (MIYA) v4.1.11 - PyInstaller 编译配置 (onedir 模式)
用法: pyinstaller Miya.spec
     或: python build_release.py
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

# ── 项目根目录 ──
try:
    PROJECT_ROOT = Path(SPECPATH)
except NameError:
    PROJECT_ROOT = Path.cwd()

# ════════════════════════════════════════════════════════════════
# 1. 收集隐藏导入
# ════════════════════════════════════════════════════════════════

hiddenimports = []

# ── 自动发现大包的子模块 ──
for pkg in [
    'torch', 'torchvision', 'torchaudio',
    'transformers', 'sentence_transformers',
    'openai', 'anthropic',
    'faiss',
    'scipy', 'sklearn',
    'numpy',
    'sqlalchemy', 'sqlmodel',
    'uvicorn',
    'fastapi', 'starlette',
    'websockets',
    'aiohttp',
    'PIL',
    'playwright',
    'playwright_stealth',
    'jmcomic',
    'pandas',
    'opentelemetry',
    'botpy',
    'cryptography',
    'funasr', 'edge_tts',
    'loguru', 'jieba', 'tenacity',
    'apscheduler',
]:
    try:
        hiddenimports.extend(collect_submodules(pkg))
    except Exception:
        pass

# ── 手动指定关键隐藏导入 ──
hiddenimports.extend([
    'tiktoken', 'tiktoken_ext', 'tiktoken_ext.openai_public',
    'scipy.special._ufuncs', 'scipy.special.cython_special',
    'scipy.sparse.csgraph._validation',
    'sklearn.feature_extraction.text',
    'sklearn.utils._typedefs', 'sklearn.utils._heap',
    'faiss.swigfaiss', 'faiss.swigfaiss_avx2',
    'sentence_transformers.model_card',
    'uvicorn.loops.auto', 'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets.auto',
    'aiosqlite',
    'yaml', 'dotenv',
    'multipart', 'python_multipart',
    'watchdog.observers', 'watchdog.observers.polling',
    'PIL._imaging', 'PIL.Image',
    'torchaudio._backend', 'torchaudio.backend',
    'httpx', 'httpcore', 'jinja2.ext',
    'apscheduler.schedulers', 'apscheduler.triggers',
    'apscheduler.triggers.cron', 'apscheduler.triggers.interval',
    'simpleaudio',
    # ── 弥娅项目自身 ──
    'core',
    'core.management_api', 'core.config_loader',
    'core.model_pool_manager', 'core.prompt_manager',
    'core.proactive_chat', 'core.soul_generator',
    'core.text_loader', 'core.user_persona',
    'core.unified_permission',
    'core.personality_loader',
    'core.conversation_history',
    'core.awareness', 'core.autonomy_manager', 'core.autonomous_engine',
    'core.auto_fixer',
    'core.intelligent_executor',
    'core.runtime_api_server',
    'core.model_collaboration_engine',
    'core.multi_vision_analyzer',
    'core.problem_scanner',
    'core.audit_logger',
    'core.embedding_client',
    'core.ethics', 'core.identity',
    'core.mcp_client',
    'core.unified_platform_impl',
    'core.unified_platform_impl.message_mixin',
    'core.unified_platform_impl.onebot_platform',
    'core.constants', 'core.miya_config',
    'core.skills',
    'core.skills.slash_commands',
    'core.skills.anthropic_skills',
    'core.web_api', 'core.web_api.__init__',
    'core.web_api.miya_api', 'core.web_api.desktop',
    'core.web_api.tts_routes', 'core.web_api.system',
    'core.dashboard', 'core.dashboard.miya_dashboard',
    'config', 'config.settings', 'config.config_utils',
    'config.platforms_config',
    'hub', 'hub.decision_hub',
    'hub.emotion', 'hub.scheduler',
    'hub.response_generator',
    'hub.memory_manager', 'hub.session_handler',
    'hub.conversation_context',
    'hub.platform_adapters',
    'memory', 'memory.core', 'memory.sqlite_backend',
    'memory.working_memory', 'memory.cognitive_engine',
    'memory.historian', 'memory.diteng_listener',
    'memory.lifebook', 'memory.session_decay',
    'memory.temporal_parser',
    'webnet', 'webnet.miya_webui',
    'webnet.qq',
    'webnet.qq.unified_config',
    'webnet.qq.config_loader',
    'webnet.ToolNet',
    'webnet.EntertainmentNet',
    'mcpserver',
    'mlink',
    'astrbot',
    'utils', 'utils.emoji_manager',
])

# ════════════════════════════════════════════════════════════════
# 2. 收集数据文件 (使用已验证可工作的目录级格式)
#    .env 会在 build_release.py 中安全清理并替换为模板
# ════════════════════════════════════════════════════════════════

datas = [
    ('config', 'config'),
    ('config/.env.example', 'config'),
    ('models', 'models'),
]

# ── 排除列表 ──
excludes = [
    'tkinter', 'tcl', 'tk',
    'test',
    'setuptools', 'pip', 'pkg_resources',
    'matplotlib.tests', 'pandas.tests',
    'scipy.tests', 'numpy.tests',
    'torch.tests', 'torch.testing',
    'IPython', 'ipykernel', 'jupyter',
    'sphinx', 'docutils',
    'pytest', 'coverage', 'flake8',
    'black', 'isort', 'mypy', 'ruff',
]

# ════════════════════════════════════════════════════════════════
# 3. 编译
# ════════════════════════════════════════════════════════════════

a = Analysis(
    ['run\\daemon.py'],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

# 收集大包的动态库 (暂时禁用，排查 COLLECT 兼容性问题)
# for pkg in ['torch', 'torchvision', 'funasr', 'sentence_transformers']:
#     try:
#         libs = collect_dynamic_libs(pkg)
#         a.binaries.extend(libs)
#         print(f"[INFO] {pkg}: {len(libs)} 动态库")
#     except Exception:
#         pass

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Miya',
    icon='build_assets\\miya.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Miya',
)
