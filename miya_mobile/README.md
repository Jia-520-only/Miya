# 弥娅手机APP (Miya Mobile)

> AI 虚拟化身弥娅的原生移动客户端
> 
> Kotlin Multiplatform + SwiftUI / Jetpack Compose

## 架构

```
miya_mobile/
├── shared/                     # KMP 共享业务逻辑层
│   └── src/
│       ├── commonMain/         # 跨平台：API 客户端、数据模型、仓库
│       ├── androidMain/        # Android：Ktor CIO 引擎
│       └── iosMain/            # iOS：Ktor Darwin 引擎
│
├── androidApp/                 # Android (Jetpack Compose)
│   └── src/main/kotlin/ai/miya/android/ui/
│       ├── chat/               # 聊天 (Live2D 角色 + 半透明浮层)
│       ├── hub/                # 状态中枢
│       ├── memory/             # 记忆回顾
│       └── settings/           # 设置 + 人格切换
│
└── iosApp/                     # iOS (SwiftUI)
    └── Miya/
        ├── Views/
        │   ├── Chat/           # 聊天视图
        │   ├── Hub/            # 中枢面板
        │   ├── Memory/         # 记忆搜索
        │   └── Settings/       # 设置
        └── Services/           # API 服务、应用状态
```

## 通信协议

| 协议 | 端点 | 用途 |
|------|------|------|
| REST | `http://{host}:8000/api/*` | 聊天、记忆、人格、状态 |
| SSE | `POST /api/chat` | 流式聊天回复 |
| WebSocket | `ws://{host}:9800/api/v1/ws` | 实时情感、消息推送 (管理 API) |

> **端口说明**：主 API 运行在 **8000**，WebSocket/管理 API 运行在 **9800**。

## 环境要求

### Android
- Android Studio Hedgehog (2024.1+)  
- JDK 17+
- Android SDK 35

### iOS
- Xcode 16.0+
- macOS 14.0+
- CocoaPods (可选)

## 快速开始

### 1. 构建 Shared 模块

```bash
cd miya_mobile

# Android
./gradlew :shared:assembleDebug

# iOS (macOS only)
./gradlew :shared:linkDebugFrameworkIosArm64
```

### 2. 运行 Android

用 Android Studio 打开 `miya_mobile/` 目录，运行 `androidApp`。

> **模拟器连接提示**：Android 模拟器中 `10.0.2.2` 映射到宿主机 localhost。  
> 真机需改为 PC 的局域网 IP。

### 3. 运行 iOS (macOS only)

1. 用 Xcode 创建新项目在 `miya_mobile/iosApp/` 目录
2. 添加所有 `Miya/` 下的 Swift 文件到项目
3. 在 Build Phases → Link Binary With Libraries 添加 `MiyaShared.framework`
4. 设置 Framework Search Paths 指向 `shared/build/XCFrameworks/release/`
5. Info.plist 已配置 App Transport Security 允许本地网络

**Build Script (推荐)**：在 Xcode Build Phase 中添加 Run Script：

```bash
cd "$SRCROOT/.."
./gradlew :shared:embedAndSignAppleFrameworkForXcode
```

### 4. 连接设置

- 确保弥娅守护进程在 PC 上运行：`python run/daemon.py --api-port 9800`
- 手机和 PC 在同一个 WiFi 网络
- 手机端输入 PC 的局域网 IP 即可连接
- 远程访问：使用 frp/nps 将 `9800` 端口映射到公网

## Live2D 集成 (后续)

当前使用系统图标占位。Live2D 模型文件位于：

```
miya_frontend/public/models/弥娅/Miya/
├── 01.model3.json
├── 01.moc3
├── 01.physics3.json
├── 01.cdi3.json
├── *.exp3.json
└── 01.8192/          # 纹理
```

接入 Live2D Cubism SDK Native 后将替换占位视图。详见 `docs/LIVE2D_INTEGRATION.md`。

## 开发计划

- [x] Phase 1: KMP 共享层 (API / 模型 / 仓库)
- [x] Phase 2: 聊天核心 (流式 + 多会话)
- [x] Phase 3: 中枢 + 记忆
- [ ] Phase 4: Live2D 角色渲染
- [ ] Phase 5: 语音输入
- [ ] Phase 6: 远程连接 (frp 文档)
- [ ] Phase 7: 打磨与发版
