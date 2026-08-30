# 桌宠修复说明

## 问题诊断

根据日志分析，发现以下问题：

### 1. 桌宠窗口路由问题
- 桌宠窗口加载的不是 `/live2d` 路由
- 导致 Live2DStandalone.vue 组件未挂载
- 控制按钮和交互功能无法使用

### 2. 鼠标事件问题
- 窗口初始设置了鼠标穿透，导致所有事件被忽略
- 需要在正确时机启用/禁用穿透

### 3. 主窗口悬浮球恢复问题
- 最大化后需要点击还原按钮
- 悬浮球模式需要点击悬浮球按钮

## 已完成的修复

### 1. electron/modules/live2d-window.ts
- 移除了立即设置鼠标穿透的代码
- 在窗口显示后才设置初始穿透状态
- 添加了路由验证，自动重定向到正确路由
- 添加了详细的日志输出

### 2. src/views/Live2DStandalone.vue
- 为控制按钮添加了鼠标事件监听
- 提高了按钮的 z-index
- 添加了详细调试日志
- 简化了透明样式，避免影响交互

### 3. src/components/Live2DFull.vue
- 改用 `pointerover/pointerout` 事件
- 添加了模型交互的鼠标穿透控制
- 添加了滚轮缩放的穿透控制
- 添加了详细日志

## 启动步骤

### 方式 1: 使用独立启动脚本（推荐）

1. 双击运行 `miya-desktop\start_desktop.bat`

### 方式 2: 手动启动

1. 打开命令行，进入 miya-desktop 目录
2. 运行 `npm run dev`

### 方式 3: 使用主菜单

1. 运行主菜单 `start.bat`
2. 选择选项 4
3. 确保没有其他程序占用端口

## 测试要点

启动后打开桌宠，检查控制台日志：

### 必须看到的日志：
```
Live2D window: Loading URL (dev): http://127.0.0.1:5173#/live2d
Live2D window page loaded
Live2D window: Current URL: ...
Live2D window: Current hash: #/live2d
Live2D Standalone: 组件挂载
Live2D Standalone: 控制按钮元素: <div>...
Live2D window: Initial mouse passthrough enabled
Live2D window shown
```

### 功能测试：

1. **背景透明**
   - ✅ 桌宠背景完全透明，没有青蓝色
   - ✅ 只有模型和控制按钮可见

2. **控制按钮**
   - ✅ 右上角的最小化按钮可以点击
   - ✅ 右上角的关闭按钮可以点击
   - ✅ 点击后窗口响应

3. **模型拖动**
   - ✅ 鼠标悬停在模型上可以拖动
   - ✅ 拖动时模型跟随鼠标
   - ✅ 控制台显示 `[Live2D] 开始拖动`

4. **滚轮缩放**
   - ✅ 鼠标在模型上滚轮可以缩放
   - ✅ 控制台显示 `[Live2D] 滚轮事件`
   - ✅ 模型大小变化

5. **桌面穿透**
   - ✅ 鼠标不在模型或按钮上时穿透到桌面
   - ✅ 可以点击桌面图标

## 主窗口功能测试

1. **悬浮球模式**
   - 点击标题栏圆形图标进入悬浮球模式
   - 窗口缩小为球体
   - 点击球体展开面板

2. **从悬浮球恢复**
   - 点击悬浮球按钮恢复窗口模式
   - 窗口动画恢复到之前大小

3. **最大化/还原**
   - 点击方块图标最大化
   - 再次点击还原到窗口模式

## 故障排除

### 问题：桌宠无法控制
**检查：**
- 控制台是否有 `[Live2D Standalone]` 日志
- 如果没有，说明路由加载错误
- 查看是否有 `Live2D window: Current URL` 日志

**解决：**
- 重启应用
- 清除编译文件后重新启动

### 问题：背景不透明
**检查：**
- 控制台是否有错误
- 窗口配置是否正确

**解决：**
- 检查 electron/modules/live2d-window.ts 配置
- 确保 backgroundColor: '#00000000'
- 确保 transparent: true

### 问题：端口被占用
**检查：**
- 运行 `netstat -ano | findstr :5173`
- 查看是否有进程占用

**解决：**
- 运行 `taskkill /F /IM electron.exe`
- 运行 `taskkill /F /IM node.exe`

## 调试日志说明

### Live2D window 日志
- `Loading URL`: 桌宠窗口加载的 URL
- `page loaded`: 页面加载完成
- `Current URL`: 当前页面 URL
- `Current hash`: 当前路由哈希
- `Initial mouse passthrough enabled`: 初始鼠标穿透已启用
- `shown`: 窗口已显示

### Live2D Standalone 日志
- `组件挂载`: Live2DStandalone 组件已挂载
- `控制按钮元素`: 找到的控制按钮元素
- `进入控制按钮区域`: 鼠标进入按钮区域
- `离开控制按钮区域`: 鼠标离开按钮区域

### Live2D 模型日志
- `鼠标悬停在模型上，禁用穿透`: 鼠标在模型上
- `鼠标离开模型，启用穿透`: 鼠标离开模型
- `开始拖动`: 开始拖动模型
- `停止拖动`: 停止拖动
- `滚轮事件`: 滚轮缩放事件

## 代码改动摘要

### electron/modules/live2d-window.ts
- 移除立即设置的 `setIgnoreMouseEvents`
- 在窗口显示后设置初始状态
- 添加路由验证和日志

### src/views/Live2DStandalone.vue
- 简化透明样式
- 添加按钮鼠标事件监听
- 提高按钮 z-index

### src/components/Live2DFull.vue
- 改用 `pointerover/pointerout` 事件
- 添加模型交互穿透控制
- 添加滚轮缩放穿透控制
- 添加详细日志
