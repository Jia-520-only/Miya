# Miya Setup 说明

## 依赖管理

所有依赖配置统一管理：

```
setup/
├── dependencies/           # 分层依赖（按模块分类）
│   ├── base.txt           # 基础核心
│   ├── ai.txt             # AI 模型
│   ├── database.txt       # 数据库 + ORM
│   ├── network.txt        # 网络通信
│   ├── office.txt         # 文档处理
│   ├── tts.txt            # 语音合成
│   ├── viz.txt            # 可视化
│   ├── qq_extras.txt      # QQ 扩展功能
│   ├── platform_adapters.txt  # 多平台适配器
│   ├── observability.txt      # 可观测性
│   ├── dev.txt            # 开发工具
│   └── win32.txt          # Windows 平台
├── requirements/           # 预设组合入口
│   ├── full.txt           # 完整安装
│   ├── minimal.txt        # 最小安装
│   ├── lightweight.txt    # 轻量级（Mock 模式）
│   ├── dev.txt            # 开发环境
│   └── desktop.txt        # 桌面应用
└── scripts/               # 安装检查脚本
    ├── quick_install.sh   # Linux/Mac
    ├── install.ps1        # Windows
    ├── check_deps.py      # 依赖检查（动态解析）
    └── verify_install.py  # 安装验证（动态解析）
```

## 快速安装

```bash
# Windows（默认安装到项目 .venv）
install.bat full

# Linux/macOS
./install.sh full

# 使用 uv 加速
install.bat uv full

# 检查现有环境
install.bat check
```

`setup/requirements/*.txt` 是依赖 profile 的唯一来源。安装器会递归解析这些文件，
并在安装后运行版本检查、`pip check` 与运行时导入验证。

详细文档见 `setup/INSTALL.md`
