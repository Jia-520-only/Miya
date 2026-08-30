# Live2D Cubism SDK 集成指南

## 当前状态

代码已全部就绪，采用**自动降级架构**：

```
MiyaLive2DGLView.kt (入口)
  ├── 检测 CubismFramework 类是否存在
  │   ├── 存在 → MiyaCubismRenderer.kt (真·Live2D)
  │   └── 不存在 → MiyaLive2DRenderer.kt (光晕占位)
```

当前编译使用光晕占位。接入 SDK 后自动切换为真正的弥娅 Live2D 渲染。

## 三步接入

### 第一步：下载 SDK

从 Live2D 官网获取 **Cubism SDK for Java**：
https://www.live2d.com/download/cubism-sdk/

需要注册账号并同意许可协议。

### 第二步：放入 AAR

解压下载的 ZIP，找到 `.aar` 文件（类似 `Live2D_SDK_Java_*.aar`），放入：

```
miya_mobile/androidApp/libs/
```

### 第三步：启用依赖

编辑 `miya_mobile/androidApp/build.gradle.kts`，取消注释这两行：

```kotlin
val cubismAar = fileTree("libs") { include("*.aar") }
implementation(cubismAar)
```

### 第四步：启用渲染代码

编辑 `miya_mobile/androidApp/src/main/kotlin/ai/miya/android/ui/live2d/MiyaCubismRenderer.kt`，
逐个取消注释标记为 `/* ... */` 的代码块。

然后编辑 `miya_mobile/androidApp/src/main/kotlin/ai/miya/android/ui/live2d/MiyaLive2DGLView.kt`，
在 `loadCubismModel()` 方法中取消注释 Cubism 初始化代码。

### 第五步：编译安装

```bash
gradlew :androidApp:assembleDebug
```

安装 APK，打开 APP 即可看到真正的弥娅 Live2D 角色。

## 关键文件

| 文件 | 作用 |
|------|------|
| `MiyaLive2DGLView.kt` | GLSurfaceView，自动检测 SDK |
| `MiyaLive2DRenderer.kt` | 光晕占位渲染（当前使用） |
| `MiyaCubismRenderer.kt` | Cubism 原生渲染（SDK 接入后启用） |
| `MiyaLive2DCompose.kt` | Compose 包装组件 |
| `assets/models/miya-model/` | 弥娅 Live2D 模型文件 |

## 表情映射

弥娅 6 种情感 → Live2D 参数的映射已在 `MiyaCubismRenderer.applyEmotionParameters()` 中定义：

| 情感 | 眉毛 | 眼睛 | 嘴巴 |
|------|------|------|------|
| happy | 放松 | 微眯 | 嘴角上扬 |
| sad | 下垂 | 半闭 | 嘴角下压 |
| angry | 紧锁 | 睁大 | 默认 |
| surprise | 上挑 | 大睁 | 微张 |
| neutral | 默认 | 默认 | 默认 |

## 眼球追踪 + 口型同步

- 触摸屏幕 → `setEyeTracking(x, y)` → ParamEyeBallX/Y
- TTS 音量 → `setMouthOpen(ratio)` → ParamMouthOpenY
- 接口已预留，接入音频/触摸输入即可启用
