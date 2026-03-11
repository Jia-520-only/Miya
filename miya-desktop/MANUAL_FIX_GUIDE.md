# Live2D 手动修复指南

## 📋 当前状态

- ✅ `package.json` 已更新为 `pixi.js@6.5.10`
- ❌ `node_modules` 中的 `pixi.js` 还是旧版本（7.3.2）
- ❌ 导致 "Dynamic require" 错误

## 🔧 手动修复步骤

### 方法1：使用PowerShell（推荐）

1. **打开PowerShell（管理员）**
   - 按 `Win + X`，选择"Windows PowerShell (管理员)"

2. **切换到项目目录**
   ```powershell
   cd d:\AI_MIYA_Facyory\MIYA\Miya\miya-desktop
   ```

3. **卸载旧版本**
   ```powershell
   npm uninstall pixi.js
   ```

4. **安装正确版本**
   ```powershell
   npm install pixi.js@6.5.10 --save --legacy-peer-deps
   ```

5. **清理缓存**
   ```powershell
   Remove-Item -Recurse -Force node_modules\.vite -ErrorAction SilentlyContinue
   ```

6. **启动应用**
   ```powershell
   npm run dev
   ```

### 方法2：使用命令提示符（CMD）

1. **打开CMD（管理员）**
   - 按 `Win + X`，选择"命令提示符 (管理员)"

2. **切换到项目目录**
   ```cmd
   cd /d d:\AI_MIYA_Facyory\MIYA\Miya\miya-desktop
   ```

3. **完全重新安装**
   ```cmd
   rmdir /s /q node_modules
   del package-lock.json
   npm install
   ```

4. **启动应用**
   ```cmd
   npm run dev
   ```

### 方法3：使用VS Code终端

1. **在VS Code中打开项目**
   ```bash
   cd d:\AI_MIYA_Facyory\MIYA\Miya\miya-desktop
   ```

2. **安装依赖**
   ```bash
   npm install pixi.js@6.5.10 --save --legacy-peer-deps
   ```

3. **清理缓存**
   ```bash
   rm -rf node_modules/.vite
   ```

4. **启动开发服务器**
   ```bash
   npm run dev
   ```

## 🔍 验证修复

### 检查 package.json
打开 `package.json`，确认：
```json
"pixi.js": "^6.5.10"
```

### 检查 node_modules
检查 `node_modules\pixi.js\package.json`：
```json
"version": "6.5.10"
```

### 测试启动
```bash
npm run dev
```

如果看到以下内容，说明成功：
```
VITE v5.1.6  ready in xxx ms

➜  Local:   http://localhost:5173/
```

## ❌ 如果仍然报错

### 错误1：权限被拒绝
```
npm error EPERM: operation not permitted
```
**解决**：
- 使用管理员权限运行命令提示符
- 关闭所有文件编辑器和VS Code
- 禁用杀毒软件 temporarily

### 错误2：Dynamic require 错误
```
Dynamic require of "url" is not supported
```
**解决**：
- 确认 `pixi.js` 版本为 6.5.10
- 清理 `node_modules\.vite` 缓存
- 重启开发服务器

### 错误3：端口占用
```
Port 5173 is already in use
```
**解决**：
```powershell
# 查找占用端口的进程
netstat -ano | findstr :5173

# 终止进程（替换 <PID> 为实际进程ID）
taskkill /F /PID <PID>
```

## 🚀 完整启动流程

修复完成后，使用新的启动脚本：

```cmd
start_live2d_fixed.bat
```

这个脚本会：
- ✅ 检查 pixi.js 版本
- ✅ 自动清理端口 5173
- ✅ 清理 Vite 缓存
- ✅ 启动 Vite 和 Electron

## 📊 预期结果

成功启动后，您应该看到：

### Vite 终端
```
VITE v5.1.6  ready in xxx ms

➜  Local:   http://localhost:5173/
➜  Network: use --host to expose
```

### Electron 应用
```
弥娅桌面应用已启动
[安全警告] (可以忽略)
```

### 控制台（F12）
```
[Live2D] 组件挂载，模型路径: /live2d/ht/ht.model3.json
[Live2D] 模型URL: http://localhost:5173/live2d/ht/ht.model3.json
[Live2D] 模型加载成功: 御姐猫猫
```

## 🎨 测试Live2D功能

1. **查看模型**
   - 在聊天界面应该看到Live2D角色
   - 3D渲染，不是emoji

2. **测试表情**
   - 点击底部的表情按钮
   - 观察角色表情变化

3. **测试情绪响应**
   - 在聊天框发送消息
   - 观察角色根据内容改变表情

4. **检查控制台**
   - 按 `Ctrl+Shift+I` 打开开发者工具
   - 查看 `[Live2D]` 开头的日志

## 💡 技术要点

| 项目 | 值 |
|------|-----|
| pixi.js 版本 | 6.5.10 |
| pixi-live2d-display | 0.4.0 |
| live2dcubismcore | public/libraries/ |
| 导入方式 | 'pixi-live2d-display/cubism4' |
| 全局暴露 | window.PIXI = PIXI |

## 📞 需要帮助？

如果按照以上步骤仍然有问题：

1. 检查 `node_modules\pixi.js\package.json` 的版本
2. 清理所有缓存：`node_modules` 和 `.vite`
3. 使用管理员权限运行
4. 禁用杀毒软件 temporarily

## 🎉 成功标志

修复成功后，您将看到：
- ✅ 无 "Dynamic require" 错误
- ✅ Vite 开发服务器正常运行
- ✅ Live2D 模型成功加载
- ✅ 8种表情可以切换
- ✅ 情绪实时响应

享受完整的Live2D体验！🎊
