# Live2D 完整版修复 - 快速指南

## 📋 问题诊断

您的错误：
```
Dynamic require of "url" is not supported
```

**原因**：`node_modules` 中的 `pixi.js` 还是旧版本（7.3.2），需要更新到 6.5.10

## ✅ 快速解决方案

### 第1步：右键以管理员身份运行

1. 找到文件 `ADMIN_INSTALL.bat`
2. **右键点击** → **"以管理员身份运行"**
3. 如果没有这个文件，继续下面的步骤

### 第2步：使用命令提示符（管理员）

1. 按 `Win + R`
2. 输入 `cmd`
3. 按 `Ctrl + Shift + Enter`（以管理员身份运行）
4. 执行以下命令：

```cmd
cd /d d:\AI_MIYA_Facyory\MIYA\Miya\miya-desktop
rmdir /s /q node_modules
del package-lock.json
npm install
```

### 第3步：启动应用

```cmd
npm run dev
```

然后在另一个终端：

```cmd
npm run dev:electron
```

## 🔍 验证是否成功

打开 `node_modules\pixi.js\package.json`，检查：
```json
{
  "name": "pixi.js",
  "version": "6.5.10",  // 应该是 6.5.10
  ...
}
```

## 📊 完整修复步骤

### 步骤1：清理旧依赖
```cmd
cd /d d:\AI_MIYA_Facyory\MIYA\Miya\miya-desktop
rmdir /s /q node_modules
del package-lock.json
```

### 步骤2：重新安装
```cmd
npm install
```

### 步骤3：清理Vite缓存
```cmd
rmdir /s /q node_modules\.vite
```

### 步骤4：启动
```cmd
npm run dev
```

## 🚀 使用新的启动脚本

修复完成后，使用：
```cmd
start_live2d_fixed.bat
```

## ❓ 如果遇到权限问题

### Windows 10/11：
1. 按 `Win + X`
2. 选择 "Windows PowerShell (管理员)" 或 "命令提示符 (管理员)"
3. 运行上述命令

### 或者：
1. 右键点击 `cmd.exe`
2. 选择 "以管理员身份运行"
3. 切换到项目目录并运行命令

## 🎯 最简单的方法

如果您不想手动执行命令，可以：

1. **关闭所有程序**（VS Code、浏览器等）
2. **以管理员身份打开 CMD**
3. **复制粘贴以下命令**：
```cmd
cd /d d:\AI_MIYA_Facyory\MIYA\Miya\miya-desktop && rmdir /s /q node_modules && del package-lock.json && npm install && npm run dev
```

## 📄 详细文档

查看 `MANUAL_FIX_GUIDE.md` 获取更详细的说明。

## 🎉 修复成功的标志

- ✅ 没有 "Dynamic require" 错误
- ✅ Vite 开发服务器正常运行（http://localhost:5173）
- ✅ Live2D 模型成功加载
- ✅ 8种表情可以切换
- ✅ 情绪实时响应

享受完整的Live2D体验！🎊
