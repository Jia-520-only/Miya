# 智能路径修复功能 - 跨平台支持

## 概述

智能路径修复功能自动修正 AI 生成的错误用户名路径,确保在 Windows、Linux 和 MacOS 上都能正确访问文件,即使 AI 猜测了错误的用户名。

## 问题场景

当用户在桌面端询问查看"桌面上的文件"时,AI 模型可能会生成包含错误用户名的路径:
- Windows: `type "C:\Users\17728932\Desktop\弥娅.txt"` (实际用户是 luobo)
- Linux: `cat "/home/olduser/Desktop/file.txt"` (实际用户是 newuser)
- MacOS: `cat "/Users/olduser/Desktop/file.txt"` (实际用户是 newuser)

如果直接执行这些命令,会因为路径不存在而失败。

## 解决方案

### Windows 平台 (WindowsAdapter)

**路径格式**: `C:\Users\用户名\Desktop\文件.txt`

**修复逻辑**:
1. 匹配带引号的路径 `"C:\Users\任意用户名\Desktop\文件.txt"`
2. 替换为正确的用户名路径
3. 匹配不带引号的路径 `C:\Users\任意用户名\Desktop\文件.txt`
4. 使用负向后顾和负向前瞻断言,避免重复替换已在引号内的路径

**代码实现**:
```python
# 获取当前用户桌面路径
current_desktop = os.path.join(os.environ.get("USERPROFILE", "C:/Users/Default"), "Desktop")

# 替换带引号的路径
pattern = r'"C:\\Users\\[^\\]+\\Desktop\\([^"]+)"'
def fix_quoted_path(m):
    filename = m.group(1)
    new_path = os.path.join(current_desktop, filename)
    return f'"{new_path}"'
command = re.sub(pattern, fix_quoted_path, command)

# 替换不带引号的路径 (避免重复替换)
pattern = r"(?<!\")C:\\Users\\[^\\]+\\Desktop\\([^\\\"\\s]+)(?!\")"
command = re.sub(pattern, lambda m: '"' + os.path.join(current_desktop, m.group(1)) + '"', command)
```

### Linux 平台 (LinuxAdapter)

**路径格式**: `/home/用户名/Desktop/文件.txt`

**修复逻辑**:
1. 匹配带引号的路径 `"/home/任意用户名/Desktop/文件.txt"`
2. 匹配带引号的路径 `"/home/任意用户名/文件.txt"`
3. 匹配不带引号的路径 `/home/任意用户名/Desktop/文件.txt`
4. 匹配不带引号的路径 `/home/任意用户名/文件.txt`

**代码实现**:
```python
# 获取当前用户主目录和桌面目录
home_dir = os.path.expanduser('~')
desktop_dir = os.path.join(home_dir, 'Desktop')

# 替换带引号的桌面路径
pattern = r'"/home/[^/]+/Desktop/([^"]+)"'
def fix_quoted_path(m):
    filename = m.group(1)
    new_path = os.path.join(desktop_dir, filename)
    return f'"{new_path}"'
command = re.sub(pattern, fix_quoted_path, command)

# 替换带引号的主目录路径
pattern = r'"/home/[^/]+/([^"]+)"'
def fix_quoted_home(m):
    filename = m.group(1)
    new_path = os.path.join(home_dir, filename)
    return f'"{new_path}"'
command = re.sub(pattern, fix_quoted_home, command)

# 替换不带引号的路径
pattern = r'(?<!\")/home/[^/]+/Desktop/([^\"/\s]+)(?!\")'
command = re.sub(pattern, lambda m: '"' + os.path.join(desktop_dir, m.group(1)) + '"', command)

pattern = r'(?<!\")/home/[^/]+/([^\"/\s]+)(?!\")'
command = re.sub(pattern, lambda m: '"' + os.path.join(home_dir, m.group(1)) + '"', command)
```

### MacOS 平台 (MacOSAdapter)

**路径格式**: `/Users/用户名/Desktop/文件.txt`

**修复逻辑**:与 Linux 类似,但基础路径是 `/Users/` 而不是 `/home/`

**代码实现**:
```python
# 获取当前用户主目录和桌面目录
home_dir = os.path.expanduser('~')
desktop_dir = os.path.join(home_dir, 'Desktop')

# 替换带引号的桌面路径
pattern = r'"/Users/[^/]+/Desktop/([^"]+)"'
def fix_quoted_path(m):
    filename = m.group(1)
    new_path = os.path.join(desktop_dir, filename)
    return f'"{new_path}"'
command = re.sub(pattern, fix_quoted_path, command)

# 替换带引号的主目录路径
pattern = r'"/Users/[^/]+/([^"]+)"'
def fix_quoted_home(m):
    filename = m.group(1)
    new_path = os.path.join(home_dir, filename)
    return f'"{new_path}"'
command = re.sub(pattern, fix_quoted_home, command)

# 替换不带引号的路径
pattern = r'(?<!\")/Users/[^/]+/Desktop/([^\"/\s]+)(?!\")'
command = re.sub(pattern, lambda m: '"' + os.path.join(desktop_dir, m.group(1)) + '"', command)

pattern = r'(?<!\")/Users/[^/]+/([^\"/\s]+)(?!\")'
command = re.sub(pattern, lambda m: '"' + os.path.join(home_dir, m.group(1)) + '"', command)
```

## 关键技术点

### 1. 正则表达式中的负向断言

使用负向后顾 `(?<!\")` 和负向前瞻 `(?!\")` 避免重复替换已在引号内的路径:

```python
pattern = r"(?<!\")C:\\Users\\[^\\]+\\Desktop\\([^\\\"\\s]+)(?!\")"
```

这个正则表达式会:
- `(?<!\")`: 确保匹配位置前面没有双引号
- `C:\\Users\\[^\\]+\\Desktop\\`: 匹配路径
- `([^\\\"\\s]+)`: 捕获文件名
- `(?!\")`: 确保匹配位置后面没有双引号

### 2. 环境变量获取正确路径

- Windows: `os.environ.get("USERPROFILE")` → `C:\Users\当前用户`
- Linux/MacOS: `os.path.expanduser('~')` → `/home/当前用户` 或 `/Users/当前用户`

### 3. 路径拼接使用 `os.path.join()`

使用 `os.path.join()` 确保路径分隔符正确:
```python
new_path = os.path.join(desktop_dir, filename)  # 自动使用正确的分隔符
```

## 支持的场景

### Windows
- ✅ `type "C:\Users\olduser\Desktop\file.txt"` → `type "C:\Users\currentuser\Desktop\file.txt"`
- ✅ `cat "C:\Users\olduser\Documents\file.txt"` (需要扩展支持)

### Linux
- ✅ `cat "/home/olduser/Desktop/file.txt"` → `cat "/home/currentuser/Desktop/file.txt"`
- ✅ `cat "/home/olduser/file.txt"` → `cat "/home/currentuser/file.txt"`

### MacOS
- ✅ `cat "/Users/olduser/Desktop/file.txt"` → `cat "/Users/currentuser/Desktop/file.txt"`
- ✅ `cat "/Users/olduser/file.txt"` → `cat "/Users/currentuser/file.txt"`

## 测试验证

### Windows 测试
```python
from tools.terminal.platform_adapter import WindowsAdapter

adapter = WindowsAdapter()
cmd = r'type "C:\Users\17728932\Desktop\弥娅.txt"'
result = adapter.execute_command(cmd)
# 返回码: 0
# 输出: 文件内容
```

### Linux/MacOS 测试
```python
from tools.terminal.platform_adapter import LinuxAdapter

adapter = LinuxAdapter()
cmd = 'cat "/home/olduser/Desktop/file.txt"'
result = adapter.execute_command(cmd)
# 返回码: 0
# 输出: 文件内容
```

## 局限性

1. **只支持标准路径格式**:
   - Windows: `C:\Users\用户名\...`
   - Linux: `/home/用户名/...`
   - MacOS: `/Users/用户名/...`

2. **不处理自定义用户目录**:
   - Linux 某些发行版可能使用其他位置

3. **需要文件存在**:
   - 如果文件不存在,修复后仍会失败

## 未来改进方向

1. **扩展支持更多路径格式**:
   - Windows 文档目录 `C:\Users\用户名\Documents\`
   - Windows 下载目录 `C:\Users\用户名\Downloads\`
   - Linux/MacOS 其他用户目录

2. **智能检测桌面语言**:
   - 支持多语言桌面目录名
   - Windows 中文版: `桌面`
   - Linux 中文版: `桌面`

3. **缓存机制**:
   - 缓存正确的用户路径,避免重复计算

## 相关文件

- `tools/terminal/platform_adapter.py`: 主要实现文件
- `tools/terminal/platform_detector.py`: 平台检测
- `tools/terminal/terminal_tool.py`: 终端工具集成

## 更新日志

### 2026-03-07
- ✅ 添加 Windows 智能路径修复
- ✅ 修复双引号重复替换问题
- ✅ 添加 Linux 智能路径修复
- ✅ 添加 MacOS 智能路径修复
- ✅ 完善跨平台支持
