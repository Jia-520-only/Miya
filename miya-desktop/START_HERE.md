# 弥娅桌面端 - 启动说明

## 快速启动

```batch
cd miya-desktop
start_dev.bat
```

## 如果 Vite 持续断开

### 问题症状
- `client:560 [vite] server connection lost`
- 导航按钮点击后报错 `ERR_CONNECTION_REFUSED`

### 解决方案

**方法 1: 使用浏览器访问**

1. 启动 Vite:
```batch
cd miya-desktop
npx vite
```

2. 在浏览器中访问: http://localhost:5173

3. 确认可以正常加载后,再启动 Electron

**方法 2: 检查端口占用**

```batch
cd miya-desktop
check_ports.bat
```

**方法 3: 重新启动服务**

1. 关闭所有命令窗口
2. 运行:
```batch
cd miya-desktop
start_dev.bat
```

## 已知问题

### 1. 代码编辑器
- 当前使用简化版本(纯 textarea)
- Monaco Editor 功能会导致 Vite 不稳定
- 后期会添加完整的代码编辑功能

### 2. 导航按钮
- 如果 Vite 断开,导航按钮会报错
- 请检查 "弥娅前端Vite" 窗口是否还在运行
- 如果窗口关闭,重新运行 `npm run dev`

### 3. 后端 API
- 代码编辑器的文件操作需要后端 API
- 如果后端未启动,文件功能不可用
- 启动后端: `python run/desktop_main.py`

## 当前状态

✅ 应用可以启动
✅ 聊天功能正常
✅ 导航标签页可见
⚠️ Vite 有时断开(正在优化)
⚠️ 代码编辑器使用简化版本

## 后续优化

- 修复 Monaco Editor 稳定性
- 添加文件系统功能
- 优化 Vite 配置
- 添加错误恢复机制
