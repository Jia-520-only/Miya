# SystemDetector 快速参考

## 导入

```python
from core.system_detector import SystemDetector, get_system_detector

# 方法1: 直接使用
detector = SystemDetector()
info = detector.detect()

# 方法2: 使用全局单例
detector = get_system_detector()
info = detector.detect()
```

## 基本使用

### 获取系统信息

```python
detector = SystemDetector()
info = detector.detect()

print(f"操作系统: {info.os_name}")
print(f"Shell: {info.shell}")
print(f"Python: {info.python_version}")
print(f"包管理器: {info.package_managers}")
```

### 判断系统类型

```python
info = detector.detect()

if info.is_windows():
    print("Windows 系统")
elif info.is_linux():
    print(f"Linux 系统 ({info.distro})")
elif info.is_macos():
    print("macOS 系统")
```

### 获取最佳包管理器

```python
info = detector.detect()
best_pm = info.get_best_package_manager()

if best_pm:
    print(f"推荐使用: {best_pm}")
```

### 转换为字典

```python
info = detector.detect()
info_dict = info.to_dict()

# 可以用于存储或传递给其他组件
import json
print(json.dumps(info_dict, indent=2, ensure_ascii=False))
```

## 缓存机制

```python
detector = SystemDetector()

# 第一次检测（执行所有检测）
info1 = detector.detect()

# 第二次检测（使用缓存，快速）
info2 = detector.detect()

# 强制刷新（重新检测）
info3 = detector.detect(force_refresh=True)
```

## 在 Miya 系统中集成

### 在 `run/main.py` 中

```python
from core.system_detector import get_system_detector

class Miya:
    def __init__(self):
        # 系统检测
        self.system_detector = get_system_detector()
        self.system_info = self.system_detector.detect()

        # 打印系统信息
        self.logger.info(f"操作系统: {self.system_info.os_name}")
        self.logger.info(f"Shell: {self.system_info.shell}")
        self.logger.info(f"Python: {self.system_info.python_version}")
```

### 传递给 DecisionHub

```python
self.decision_hub = DecisionHub(
    # ... 其他参数
    system_info=self.system_info  # 传递系统信息
)
```

## SystemInfo 数据结构

### 字段说明

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `os_name` | str | 操作系统名称 | "Windows", "Linux", "Darwin" |
| `os_version` | str | 操作系统版本 | "10.0.26200" |
| `distro` | str | Linux 发行版 | "ubuntu", "fedora", "arch" |
| `distro_version` | str | 发行版版本 | "22.04", "38" |
| `arch` | str | CPU 架构 | "AMD64", "x86_64", "arm64" |
| `shell` | str | Shell 类型 | "bash", "zsh", "powershell", "cmd" |
| `python_version` | str | Python 版本 | "3.11.9" |
| `node_version` | str | Node.js 版本 | "24.12.0" 或 "not_installed" |
| `package_managers` | List[str] | 可用包管理器列表 | ["pip", "npm", "winget"] |
| `current_path` | str | 当前工作目录 | "/home/user/project" |
| `home_dir` | str | 用户主目录 | "/home/user" |

### 方法说明

```python
# 判断系统类型
info.is_windows()  # bool
info.is_linux()    # bool
info.is_macos()    # bool

# 获取最佳包管理器
info.get_best_package_manager()  # Optional[str]

# 转换为字典
info.to_dict()  # Dict[str, Any]
```

## 包管理器检测

### 支持的包管理器

#### Windows
- `pip` - Python 包管理器（总是可用）
- `npm` - Node.js 包管理器（如果安装了 Node.js）
- `winget` - Windows 包管理器（Windows 10/11）
- `choco` - Chocolatey（如果安装）
- `scoop` - Scoop（如果安装）

#### Linux
- `pip` - Python 包管理器（总是可用）
- `npm` - Node.js 包管理器（如果安装了 Node.js）
- `apt` - Debian/Ubuntu 系列
- `yum` / `dnf` - RedHat/CentOS/Fedora 系列
- `pacman` - Arch Linux 系列
- `apk` - Alpine Linux

#### macOS
- `pip` - Python 包管理器（总是可用）
- `npm` - Node.js 包管理器（如果安装了 Node.js）
- `brew` - Homebrew（如果安装）

## 实际应用示例

### 示例 1: 根据系统选择包管理器

```python
detector = SystemDetector()
info = detector.detect()

best_pm = info.get_best_package_manager()

if best_pm:
    # 根据包管理器生成安装命令
    install_commands = {
        'apt': 'sudo apt install -y git',
        'yum': 'sudo yum install -y git',
        'brew': 'brew install git',
        'winget': 'winget install git',
        'pip': 'pip install gitpython',
    }

    cmd = install_commands.get(best_pm, f'{best_pm} install git')
    print(f"推荐命令: {cmd}")
```

### 示例 2: 根据系统调整命令

```python
detector = SystemDetector()
info = detector.detect()

# 根据系统执行不同的命令
if info.is_windows():
    # Windows 特定命令
    os.system('dir')
elif info.is_linux() or info.is_macos():
    # Unix 特定命令
    os.system('ls -la')
```

### 示例 3: 环境检查

```python
def check_environment():
    """检查开发环境是否就绪"""
    detector = SystemDetector()
    info = detector.detect()

    issues = []

    # 检查 Python
    if not info.python_version.startswith("3."):
        issues.append("Python 3.x 未安装")

    # 检查 Node.js
    if info.node_version == "not_installed":
        issues.append("Node.js 未安装")

    # 检查包管理器
    if not info.get_best_package_manager():
        issues.append("未找到合适的包管理器")

    if issues:
        print("环境检查失败:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("环境检查通过!")
        return True

# 使用
check_environment()
```

### 示例 4: 自动配置脚本

```python
def auto_configure():
    """根据系统自动配置"""
    detector = SystemDetector()
    info = detector.detect()

    config = {
        'os': info.os_name,
        'shell': info.shell,
        'package_manager': info.get_best_package_manager(),
        'python': info.python_version,
        'node': info.node_version,
    }

    # 保存配置
    import json
    with open('system_config.json', 'w') as f:
        json.dump(config, f, indent=2)

    print("配置已保存到 system_config.json")

# 使用
auto_configure()
```

## 测试

运行测试脚本:

```bash
# 运行所有测试
python test_system_detector.py

# 运行集成测试
python test_integration_system_detector.py
```

## 注意事项

1. **缓存**: 检测结果会被缓存，使用 `force_refresh=True` 强制刷新
2. **错误处理**: 包管理器检测失败不会影响整体功能
3. **超时保护**: 所有 subprocess 调用都有 5 秒超时
4. **平台兼容**: 支持 Windows, Linux, macOS

## 故障排除

### 问题: 包管理器未检测到

**原因**: 命令行工具未安装或不在 PATH 中

**解决**:
```python
# 手动检查
import subprocess
try:
    subprocess.run(['winget', '--version'], timeout=5)
    print("winget 可用")
except:
    print("winget 不可用")
```

### 问题: Linux 发行版未识别

**原因**: 自定义发行版或 `/etc/os-release` 不存在

**解决**: 这是正常的，不影响其他功能

### 问题: Node.js 显示 "not_installed"

**原因**: Node.js 未安装或不在 PATH 中

**解决**: 安装 Node.js 或确保其在 PATH 中

## 相关文件

- `core/system_detector.py` - 主模块
- `test_system_detector.py` - 单元测试
- `test_integration_system_detector.py` - 集成测试
- `PHASE1_TEST_REPORT.md` - 测试报告
- `TERMINAL_AUTONOMY_ROADMAP.md` - 实施路线图
