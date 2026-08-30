# 完整 Live2D 安装指南

## 🎯 目标

使用 **Live2D Cubism Web SDK** 实现完整的 3D Live2D 效果。

---

## 📋 前置要求

### 1. Live2D Cubism Core 文件

Live2D Cubism Web SDK 需要一个核心库文件：`live2dcubismcore.min.js`

**下载方式**：

```bash
# 自动打开下载页面
download_live2d_core.bat
```

**或手动访问**：
https://www.live2d.com/zh-CHS/download/cubism-sdk/download-web/

### 2. 下载步骤

1. 在官网页面勾选同意条款
2. 填写邮箱（可选）
3. 点击"下载"按钮
4. 选择 "Cubism Core for Web"
5. 解压下载的压缩包
6. 找到 `Core/live2dcubismcore.min.js` 文件
7. 复制到 `public/live2d/script/` 目录

---

## 🔧 安装步骤

### 步骤 1：下载 Live2D Cubism Core

```bash
# 自动打开下载页面
download_live2d_core.bat
```

### 步骤 2：复制核心文件

下载后，将文件复制到：

```
miya-desktop/
└── public/
    └── live2d/
        └── script/
            └── live2dcubismcore.min.js  ← 将文件复制到这里
```

### 步骤 3：安装 Live2D SDK

```bash
# 安装 Live2D Cubism Web SDK
npm install @live2d/live2d-cubism-web
```

### 步骤 4：启动应用

```bash
npm run dev
```

---

## 📂 文件结构

安装完成后，目录结构如下：

```
miya-desktop/
├── public/
│   └── live2d/
│       ├── ht/                          # Live2D 模型
│       │   ├── ht.model3.json
│       │   ├── ht.moc3
│       │   ├── ht.physics3.json
│       │   ├── ht.cdi3.json
│       │   ├── expression*.exp3.json
│       │   └── ht.8192/texture_00.png
│       └── script/
│           └── live2dcubismcore.min.js  ← 核心库文件
├── src/
│   └── components/
│       └── Live2DFull.vue              # 完整版 Live2D 组件
└── package.json
```

---

## 🎨 功能特性

### 完整版 Live2D 支持以下功能：

| 功能 | 说明 |
|-----|------|
| ✅ 3D 渲染 | 真实的 Live2D 3D 效果 |
| ✅ 物理动画 | 模型物理效果 |
| ✅ 呼吸动画 | 自然的呼吸效果 |
| ✅ 眼睛跟随 | 眼睛跟随鼠标移动 |
| ✅ 表情切换 | 8 种表情切换 |
| ✅ 自动情绪 | 根据对话自动切换表情 |
| ✅ 交互响应 | 点击模型有反应 |
| ✅ 高性能 | GPU 加速渲染 |

---

## 🚀 使用方式

### 自动模式（推荐）

启动应用后，Live2D 会：

1. **自动加载**：御姐猫猫头 3D 模型
2. **自动表情**：根据对话情绪切换表情
3. **交互响应**：点击模型有反应
4. **眼睛跟随**：眼睛跟随鼠标移动

### 手动模式

可以通过表情按钮手动切换表情：

```
😊 开心   💕 兴奋   😳 害羞   😢 悲伤
😠 生气   🎤 唱歌   🦊 调皮   🤫 嘘声
```

---

## 🔍 验证安装

### 1. 检查核心文件

```bash
# Windows
dir public\live2d\script\live2dcubismcore.min.js

# Linux/Mac
ls public/live2d/script/live2dcubismcore.min.js
```

应该看到文件存在。

### 2. 检查依赖

```bash
npm list @live2d/live2d-cubism-web
```

应该显示已安装。

### 3. 启动验证

运行 `npm run dev`，查看浏览器控制台（F12）：

**成功**：
```
Live2D Cubism Core 已加载
Live2D 模型加载成功
```

**失败**：
```
Live2D Cubism Core 未找到，使用简化版
```

---

## ❓ 常见问题

### Q: 找不到 live2dcubismcore.min.js

**A**: 需要从 Live2D 官网下载：

```bash
download_live2d_core.bat
```

按照说明下载并复制文件。

### Q: 模型加载失败

**A**: 检查以下几点：

1. 核心文件是否正确放置
2. 模型文件是否存在
3. 浏览器控制台是否有错误信息

### Q: 能否不下载核心文件？

**A**: 不可以。Live2D Cubism Web SDK 必须依赖核心库才能运行。

---

## 📚 相关资源

- [Live2D 官网](https://www.live2d.com/)
- [Live2D Cubism SDK 下载](https://www.live2d.com/zh-CHS/download/cubism-sdk/download-web/)
- [Live2D Cubism Web SDK 文档](https://www.live2d.com/download/cubism-sdk/download-web/)

---

## 🎯 下一步

1. **下载核心文件**：
   ```bash
   download_live2d_core.bat
   ```

2. **复制文件**到 `public/live2d/script/` 目录

3. **安装 SDK**：
   ```bash
   npm install @live2d/live2d-cubism-web
   ```

4. **启动应用**：
   ```bash
   npm run dev
   ```

---

## 📝 注意事项

- ⚠️ Live2D Cubism Core 是必需文件，无法跳过
- ⚠️ 核心文件需要从官网下载，不能通过 npm 安装
- ⚠️ 模型文件需要是 Live2D Cubism 3.0 格式
- ✅ 你的御姐猫猫头模型已经是 Cubism 3.0 格式，可以直接使用

---

## 🎉 完成后

安装完成后，你将获得：

- ✅ **完整的 3D Live2D 效果**
- ✅ **真实的物理动画**
- ✅ **自然的表情切换**
- ✅ **交互式体验**

---

最后更新：2026-03-08
