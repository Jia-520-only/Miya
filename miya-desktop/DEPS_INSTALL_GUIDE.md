# 弥娅依赖安装问题 - 完整解决方案

## ❌ 当前问题

```
Live2D模型信息
• 模型: 御姐猫猫头
• 表情数量: 8个
• 状态: 未安装SDK
```

Live2D SDK 依赖包未安装：
- ✗ `pixi.js@^7.3.2` - 未安装
- ✗ `pixi-live2d-display@^0.4.0` - 未安装

---

## 🔧 解决方案

### 方法1：使用修复脚本（推荐）

```bash
install_deps_fix.bat
```

这个脚本会：
1. 配置 npm 使用本地缓存
2. 清理旧的 node_modules
3. 安装所有依赖（包括 Live2D SDK）
4. 验证安装结果

**优点**：
- 自动处理权限问题
- 使用本地缓存避免写入系统目录
- 一次性安装所有依赖

---

### 方法2：单独安装 Live2D SDK

```bash
install_live2d_only.bat
```

这个脚本会：
1. 只安装 Live2D 相关的依赖
2. 使用本地缓存
3. 验证安装结果

**适用场景**：
- 只需要安装 Live2D SDK
- 其他依赖已安装

---

### 方法3：使用 yarn（推荐备选）

如果 npm 有问题，可以尝试使用 yarn：

```bash
# 安装 yarn（如果还没有）
npm install -g yarn

# 进入项目目录
cd miya-desktop

# 安装依赖
yarn install

# 只安装 Live2D SDK
yarn add pixi.js@^7.3.2 pixi-live2d-display@^0.4.0
```

**优点**：
- 更快的安装速度
- 更好的依赖解析
- 更少的权限问题

---

### 方法4：使用 pnpm

```bash
# 安装 pnpm（如果还没有）
npm install -g pnpm

# 进入项目目录
cd miya-desktop

# 安装依赖
pnpm install

# 只安装 Live2D SDK
pnpm add pixi.js@^7.3.2 pixi-live2d-display@^0.4.0
```

**优点**：
- 最快的安装速度
- 最严格的依赖隔离
- 更节省磁盘空间

---

### 方法5：手动安装（最后手段）

如果以上方法都失败，可以手动下载：

1. 下载 `pixi.js@7.3.2`：
   ```bash
   cd node_modules
   git clone https://github.com/pixijs/pixi.js.git
   cd pixi.js
   git checkout v7.3.2
   npm install
   cd ..
   ```

2. 下载 `pixi-live2d-display@0.4.0`：
   ```bash
   git clone https://github.com/guansss/pixi-live2d-display.git
   cd pixi-live2d-display
   git checkout v0.4.0
   npm install
   cd ..
   ```

3. 返回项目目录：
   ```bash
   cd ..
   ```

**不推荐**：这个方法比较复杂，只在其他方法都失败时使用。

---

## 📊 对比表

| 方法 | 速度 | 稳定性 | 推荐度 |
|-----|------|--------|--------|
| install_deps_fix.bat | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ 推荐 |
| install_live2d_only.bat | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ✅ 推荐 |
| yarn | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ✅ 备选推荐 |
| pnpm | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ✅ 备选推荐 |
| 手动安装 | ⭐ | ⭐⭐ | ⚠️ 最后手段 |

---

## 🚀 推荐步骤

### 首次安装

```bash
# 步骤1：运行修复脚本
install_deps_fix.bat

# 步骤2：验证安装
dir node_modules\pixi.js
dir node_modules\pixi-live2d-display

# 步骤3：启动应用
npm run dev
```

### 如果修复脚本失败

```bash
# 尝试使用 yarn
npm install -g yarn
yarn install

# 验证安装
dir node_modules\pixi.js
dir node_modules\pixi-live2d-display

# 启动应用
npm run dev
```

---

## ✅ 验证安装

安装完成后，检查以下内容：

### 1. 检查 node_modules

```bash
cd miya-desktop
dir node_modules | findstr pixi
```

应该看到：
```
pixi.js
pixi-live2d-display
```

### 2. 检查 package-lock.json

```bash
type package-lock.json | findstr pixi
```

应该看到相关的依赖条目。

### 3. 启动应用验证

运行 `npm run dev` 后，Live2D 区域应该显示：
- ✅ 状态：已安装SDK（而不是"未安装SDK"）
- ✅ 御姐猫猫头像正常显示
- ✅ 可以切换表情

---

## 🔍 故障排查

### 问题：权限错误 EPERM

**错误信息**：
```
npm error code EPERM
npm error syscall mkdir
npm error path d:\
```

**解决方案**：
1. 使用 `install_deps_fix.bat`（配置本地缓存）
2. 或使用 yarn/pnpm（避免权限问题）
3. 或以管理员身份运行

### 问题：网络错误

**错误信息**：
```
npm ERR! network request failed
```

**解决方案**：
1. 检查网络连接
2. 使用淘宝镜像：
   ```bash
   npm config set registry https://registry.npmmirror.com
   ```

### 问题：依赖冲突

**错误信息**：
```
npm ERR! peer dep missing
```

**解决方案**：
使用 `--legacy-peer-deps` 标志：
```bash
npm install --legacy-peer-deps
```

---

## 📝 相关文档

- `install_deps_fix.bat` - 依赖修复安装脚本
- `install_live2d_only.bat` - Live2D 单独安装脚本
- `LIVE2D_INSTALL_GUIDE.md` - Live2D 安装指南
- `PRELOAD_FIX.md` - preload.js 修复指南

---

## 🎯 快速参考

| 任务 | 命令 |
|-----|------|
| 安装所有依赖 | `install_deps_fix.bat` |
| 只安装 Live2D | `install_live2d_only.bat` |
| 使用 yarn | `yarn install` |
| 使用 pnpm | `pnpm install` |
| 验证安装 | `dir node_modules\pixi*` |
| 启动应用 | `npm run dev` |

---

## ✅ 完成后

安装成功后：
- ✅ Live2D 状态显示"已安装SDK"
- ✅ 可以看到御姐猫猫头像
- ✅ 可以切换 8 种表情
- ✅ 情绪会实时更新

---

最后更新：2026-03-08
