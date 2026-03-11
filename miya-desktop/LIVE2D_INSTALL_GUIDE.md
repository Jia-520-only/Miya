# Live2D 安装完整指南

## 🔴 当前问题

`pixi-live2d-display` 依赖包尚未安装，导致Live2D功能无法使用。

## ✅ 解决方案

### 方法一：手动安装（推荐）

#### 步骤 1: 关闭应用

如果弥娅桌面应用正在运行，请先关闭。

#### 步骤 2: 运行安装脚本

在 `miya-desktop` 目录下双击运行：

```
install_live2d_manual.bat
```

这个脚本会：
- ✅ 检查环境
- ✅ 安装 `pixi.js@^7.3.2`
- ✅ 安装 `pixi-live2d-display@^0.4.0`
- ✅ 验证安装结果

#### 步骤 3: 重启应用

安装完成后，运行 `start.bat` 重新启动应用。

---

### 方法二：使用 npm 命令安装

如果脚本无法运行，可以手动执行：

```bash
# 进入目录
cd d:\AI_MIYA_Facyory\MIYA\Miya\miya-desktop

# 安装依赖
npm install pixi.js@^7.3.2 pixi-live2d-display@^0.4.0
```

**注意**：如果遇到权限错误，请：
1. 以管理员身份运行命令提示符
2. 或右键点击 PowerShell，选择"以管理员身份运行"

---

### 方法三：使用 PowerShell 安装

```powershell
# 设置编码为 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 进入目录
cd d:\AI_MIYA_Facyory\MIYA\Miya\miya-desktop

# 安装依赖
npm install pixi.js@^7.3.2 pixi-live2d-display@^0.4.0

# 验证安装
Test-Path node_modules\pixi.js
Test-Path node_modules\pixi-live2d-display
```

---

## 🔍 验证安装

### 检查安装结果

安装完成后，检查以下文件是否存在：

```
miya-desktop/
├── node_modules/
│   ├── pixi.js/              ✅ 应该存在
│   └── pixi-live2d-display/   ✅ 应该存在
└── package.json              ✅ 应该包含这两个依赖
```

### 验证 package.json

打开 `package.json`，确认 `dependencies` 中包含：

```json
{
  "dependencies": {
    "pixi.js": "^7.3.2",
    "pixi-live2d-display": "^0.4.0"
  }
}
```

---

## 🐛 常见问题

### 问题 1: 权限错误 EPERM

**错误信息**：
```
npm error code EPERM
npm error syscall mkdir
npm error path d:\
```

**解决方案**：

1. **以管理员身份运行**
   - 右键点击命令提示符或PowerShell
   - 选择"以管理员身份运行"
   - 然后运行安装命令

2. **关闭占用文件的程序**
   - 关闭任何文件管理器窗口
   - 关闭VS Code或其他编辑器
   - 关闭杀毒软件的实时扫描（临时）

3. **清理 npm 缓存**
   ```bash
   npm cache clean --force
   npm install
   ```

---

### 问题 2: 网络连接失败

**错误信息**：
```
npm ERR! network request failed
```

**解决方案**：

1. **检查网络连接**
   - 确保网络正常
   - 尝试访问其他网站

2. **使用国内镜像**
   ```bash
   # 使用淘宝镜像
   npm config set registry https://registry.npmmirror.com
   
   # 安装依赖
   npm install pixi.js@^7.3.2 pixi-live2d-display@^0.4.0
   
   # 恢复官方镜像（可选）
   npm config set registry https://registry.npmjs.org
   ```

3. **使用代理**
   ```bash
   npm config set proxy http://proxy-server:port
   npm install
   ```

---

### 问题 3: 依赖冲突

**错误信息**：
```
npm ERR! peer dep missing: ...
```

**解决方案**：

```bash
# 强制安装（不推荐，仅在必要时使用）
npm install pixi.js@^7.3.2 pixi-live2d-display@^0.4.0 --force

# 或使用 --legacy-peer-deps
npm install pixi.js@^7.3.2 pixi-live2d-display@^0.4.0 --legacy-peer-deps
```

---

### 问题 4: 安装后仍然报错

**现象**：安装成功，但应用启动时仍然报错。

**解决方案**：

1. **清理 Vite 缓存**
   ```bash
   # 删除缓存目录
   rmdir /s /q node_modules\.vite
   
   # 或使用 PowerShell
   Remove-Item -Recurse -Force node_modules\.vite
   ```

2. **重新安装依赖**
   ```bash
   # 删除 node_modules
   rmdir /s /q node_modules
   
   # 或使用 PowerShell
   Remove-Item -Recurse -Force node_modules
   
   # 重新安装
   npm install
   ```

3. **重启开发服务器**
   - 关闭当前运行的应用
   - 重新运行 `start.bat`

---

## 📋 安装检查清单

完成以下检查，确保安装成功：

- [ ] ✅ 已运行 `install_live2d_manual.bat`
- [ ] ✅ 安装过程无错误
- [ ] ✅ `node_modules/pixi.js` 目录存在
- [ ] ✅ `node_modules/pixi-live2d-display` 目录存在
- [ ] ✅ `package.json` 中包含这两个依赖
- [ ] ✅ 重启应用后Live2D可以加载
- [ ] ✅ 模型显示在右侧边栏
- [ ] ✅ 情绪切换时表情变化正常

---

## 🎯 安装后的功能

### 简化模式（未安装SDK时）

如果Live2D SDK未安装，会显示：
- 🐱 御姐猫猫头像图标
- 📊 当前情绪显示
- 🎭 8个表情按钮（可手动切换）
- 📝 模型信息说明
- 🔧 安装提示

### 完整模式（安装SDK后）

安装Live2D SDK后，将获得：
- ✨ 真实的Live2D 3D模型
- 🎨 流畅的动画效果
- 💨 自动呼吸动画
- 😊 自动表情切换
- 🎯 情绪响应系统

---

## 🔄 切换模式

### 从简化模式切换到完整模式

1. 运行 `install_live2d_manual.bat` 安装SDK
2. 重启应用
3. 自动切换到完整Live2D模式

### 从完整模式切换回简化模式

如果Live2D出现问题，可以暂时使用简化模式：

修改 `ChatView.vue`：

```vue
<!-- 注释掉完整版本 -->
<!-- Live2DViewer -->

<!-- 使用简化版本 -->
<Live2DViewerSimple
  model-path="/live2d/ht/ht.model3.json"
  :emotion="currentEmotion"
/>
```

---

## 📚 相关文档

- [Live2D使用指南](./live2d/README.md)
- [模型详细说明](./live2d/MODELS.md)
- [表情映射配置](./live2d/EXPRESSIONS.md)
- [配置说明](./live2d/CONFIG.md)

---

## 💡 提示

1. **首次安装可能需要几分钟**，请耐心等待
2. **保持网络稳定**，避免安装中断
3. **以管理员身份运行**可以避免权限问题
4. **使用国内镜像**可以加快下载速度
5. **安装后重启应用**确保更改生效

---

## 🆘 需要帮助？

如果仍然遇到问题：

1. 查看 `install_log.txt` 了解详细错误信息
2. 检查 `.npm-cache/_logs/` 目录中的npm日志
3. 在项目根目录运行诊断脚本
4. 联系技术支持

---

**Live2D 安装指南** - 完成安装，让弥娅更生动！
