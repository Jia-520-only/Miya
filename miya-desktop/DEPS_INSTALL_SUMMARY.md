# Live2D 依赖安装 - 完整解决方案

## ❌ 问题

Live2D SDK 依赖包未安装：
- ✗ `pixi.js@^7.3.2` - 未安装
- ✗ `pixi-live2d-display@^0.4.0` - 未安装

**显示状态**：
```
Live2D模型信息
• 模型: 御姐猫猫头
• 表情数量: 8个
• 状态: 🟡 SDK 未安装（使用简化版）
```

---

## ✅ 解决方案（按推荐顺序）

### 🥇 方法1：使用修复脚本（最推荐）

```bash
install_deps_fix.bat
```

**优点**：
- ✅ 自动处理权限问题
- ✅ 使用本地缓存避免写入系统目录
- ✅ 一次性安装所有依赖
- ✅ 自动验证安装结果

**流程**：
1. 配置 npm 使用本地缓存
2. 清理旧的 node_modules
3. 安装所有依赖（包括 Live2D SDK）
4. 验证安装结果

---

### 🥈 方法2：使用 yarn（推荐备选）

```bash
# 安装 yarn（如果还没有）
npm install -g yarn

# 进入项目目录
cd miya-desktop

# 安装依赖
yarn install
```

**优点**：
- ✅ 更快的安装速度
- ✅ 更好的依赖解析
- ✅ 更少的权限问题
- ✅ 更稳定的版本管理

---

### 🥉 方法3：单独安装 Live2D SDK

```bash
install_live2d_only.bat
```

**适用场景**：
- 只需要安装 Live2D SDK
- 其他依赖已安装

---

### 🚀 方法4：使用 pnpm

```bash
# 安装 pnpm（如果还没有）
npm install -g pnpm

# 进入项目目录
cd miya-desktop

# 安装依赖
pnpm install
```

**优点**：
- ✅ 最快的安装速度
- ✅ 最严格的依赖隔离
- ✅ 最节省磁盘空间

---

## 📊 方案对比

| 方法 | 速度 | 稳定性 | 推荐度 | 说明 |
|-----|------|--------|--------|------|
| install_deps_fix.bat | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ 最佳 | 自动处理所有问题 |
| yarn | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ✅ 推荐 | 最稳定快速 |
| pnpm | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ✅ 备选 | 最快但稍复杂 |
| install_live2d_only.bat | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ✅ 备选 | 只安装 Live2D |
| npm install | ⭐⭐ | ⭐⭐ | ⚠️ 不推荐 | 可能有权限问题 |

---

## 🚀 推荐操作流程

### 首次安装（完整）

```bash
# 步骤1：进入项目目录
cd miya-desktop

# 步骤2：运行修复脚本
install_deps_fix.bat

# 步骤3：验证安装
dir node_modules\pixi.js
dir node_modules\pixi-live2d-display

# 步骤4：启动应用
npm run dev
```

### 快速安装（已安装其他依赖）

```bash
# 方法A：只安装 Live2D
install_live2d_only.bat

# 方法B：使用 yarn
yarn add pixi.js@^7.3.2 pixi-live2d-display@^0.4.0

# 方法C：使用 pnpm
pnpm add pixi.js@^7.3.2 pixi-live2d-display@^0.4.0
```

### npm 失败时的备选方案

```bash
# 安装 yarn
npm install -g yarn

# 使用 yarn 安装依赖
cd miya-desktop
yarn install

# 启动应用
npm run dev
```

---

## ✅ 验证安装

### 1. 检查 node_modules

```bash
cd miya-desktop
dir node_modules | findstr pixi
```

**预期输出**：
```
pixi.js
pixi-live2d-display
```

### 2. 检查 package.json

```bash
type package.json | findstr pixi
```

**预期输出**：
```
"pixi-live2d-display": "^0.4.0",
"pixi.js": "^7.3.2",
```

### 3. 启动应用验证

运行 `npm run dev` 后：

**Live2D 区域应该显示**：
- ✅ 状态：🟢 SDK 已安装（而不是"🟡 SDK 未安装"）
- ✅ 御姐猫猫头像正常显示
- ✅ 8 个表情按钮可以点击
- ✅ 情绪会实时更新

---

## 🔍 故障排查

### 问题 1：权限错误 EPERM

**错误信息**：
```
npm error code EPERM
npm error syscall mkdir
npm error path d:\
```

**原因**：
npm 试图在系统根目录创建缓存，权限不足。

**解决方案**：
1. **使用修复脚本**（推荐）：
   ```bash
   install_deps_fix.bat
   ```
2. **使用 yarn/pnpm**：
   ```bash
   npm install -g yarn
   yarn install
   ```
3. **以管理员身份运行**：
   右键 → 以管理员身份运行

---

### 问题 2：网络错误

**错误信息**：
```
npm ERR! network request failed
npm ERR! errno ETIMEDOUT
```

**解决方案**：
1. 检查网络连接
2. 使用淘宝镜像：
   ```bash
   npm config set registry https://registry.npmmirror.com
   ```
3. 使用 VPN 或代理

---

### 问题 3：依赖冲突

**错误信息**：
```
npm ERR! peer dep missing: pixi.js@^7.x
```

**解决方案**：
使用 `--legacy-peer-deps` 标志：
```bash
npm install --legacy-peer-deps
```

或使用 yarn（自动处理 peer deps）：
```bash
yarn install
```

---

### 问题 4：安装后仍然显示"未安装SDK"

**可能原因**：
1. 浏览器缓存未清除
2. Vite 开发服务器未重启
3. Live2D SDK 检测逻辑不准确

**解决方案**：
1. **重启开发服务器**：
   ```bash
   # Ctrl+C 停止
   npm run dev
   ```
2. **清除浏览器缓存**：
   - 按 F12 打开开发者工具
   - 右键刷新按钮 → 清空缓存并硬性重新加载
3. **手动验证**：
   - 打开浏览器控制台
   - 输入：`typeof PIXI`
   - 应该返回 `"object"`（已安装）或 `"undefined"`（未安装）

---

## 📝 已创建的脚本

| 脚本 | 用途 | 推荐度 |
|-----|------|--------|
| `install_deps_fix.bat` | 完整依赖安装（推荐）| ⭐⭐⭐⭐⭐ |
| `install_live2d_only.bat` | 只安装 Live2D | ⭐⭐⭐⭐ |
| `start_dev.bat` | 开发模式启动 | ⭐⭐⭐⭐ |
| `quick_start.bat` | 快速启动 | ⭐⭐⭐⭐ |
| `fix_electron.bat` | 修复 Electron | ⭐⭐⭐ |

---

## 📚 相关文档

| 文档 | 内容 |
|-----|------|
| `DEPS_INSTALL_GUIDE.md` | 详细安装指南 |
| `DEPS_INSTALL_SUMMARY.md` | 本文档，安装总结 |
| `LIVE2D_INSTALL_GUIDE.md` | Live2D 专用指南 |
| `PRELOAD_FIX.md` | preload.js 修复 |
| `ERROR_FIX_SUMMARY.md` | 错误修复总结 |

---

## 🎯 快速参考

### 安装命令

| 任务 | 命令 |
|-----|------|
| 完整安装（推荐）| `install_deps_fix.bat` |
| 只安装 Live2D | `install_live2d_only.bat` |
| 使用 yarn | `yarn install` |
| 使用 pnpm | `pnpm install` |
| 手动安装 | `npm install` |

### 验证命令

| 任务 | 命令 |
|-----|------|
| 检查 pixi.js | `dir node_modules\pixi.js` |
| 检查 Live2D | `dir node_modules\pixi-live2d-display` |
| 检查 package.json | `type package.json \| findstr pixi` |
| 启动应用 | `npm run dev` |

---

## 🎉 完成后的效果

### 安装前
```
Live2D模型信息
• 模型: 御姐猫猫头
• 表情数量: 8个
• 状态: 🟡 SDK 未安装（使用简化版）
```

### 安装后
```
Live2D模型信息
• 模型: 御姐猫猫头
• 表情数量: 8个
• 状态: 🟢 SDK 已安装
```

### 功能变化

| 功能 | 安装前 | 安装后 |
|-----|--------|--------|
| Live2D 显示 | 简化版（静态头像）| 完整版（3D 模型）|
| 表情切换 | 手动按钮 | 自动 + 手动 |
| 动画效果 | 简单呼吸动画 | 完整物理动画 |
| 性能 | 低（静态渲染）| 高（GPU 加速）|

---

## ✅ 总结

| 项目 | 状态 |
|-----|------|
| 问题识别 | ✅ 已完成 |
| 解决方案 | ✅ 已提供 4 种方法 |
| 脚本创建 | ✅ 已创建 2 个脚本 |
| 文档编写 | ✅ 已创建 3 个文档 |
| 故障排查 | ✅ 已覆盖常见问题 |

---

## 🚀 现在开始吧！

推荐使用最简单的方法：

```bash
cd miya-desktop
install_deps_fix.bat
```

安装完成后运行：

```bash
npm run dev
```

享受完整的 Live2D 体验！🎉

---

最后更新：2026-03-08
