# 开发环境配置指南

## Windows (Android 开发)

### 前置条件

1. **JDK 17+** (已通过 winget 安装)
   ```
   C:\Program Files\Microsoft\jdk-17.0.19.10-hotspot
   ```

2. **Android Studio** (推荐)
   - 下载：https://developer.android.com/studio
   - 安装时勾选 Android SDK、Android SDK Platform 35、Android SDK Build-Tools
   - 安装后自动设置 ANDROID_HOME

3. **或仅安装 Android SDK 命令行工具**
   ```powershell
   # 下载 cmdline-tools
   # https://developer.android.com/studio#command-line-tools-only
   
   # 解压到:
   %LOCALAPPDATA%\Android\Sdk\cmdline-tools\latest\
   
   # 安装 SDK 组件
   sdkmanager "platforms;android-35" "build-tools;35.0.0" "platform-tools"
   ```

### 设置环境变量

```powershell
# 已设置 JAVA_HOME（工具已自动完成）
$env:JAVA_HOME = "C:\Program Files\Microsoft\jdk-17.0.19.10-hotspot"

# 设置 ANDROID_HOME (替换为实际路径)
# 如果用 Android Studio，默认路径为 %LOCALAPPDATA%\Android\Sdk
[Environment]::SetEnvironmentVariable("ANDROID_HOME", "$env:LOCALAPPDATA\Android\Sdk", "User")
```

### 运行

```bash
cd miya_mobile

# Sync Gradle（首次自动下载 Gradle 8.10）
./gradlew :androidApp:assembleDebug

# 或直接用 Android Studio 打开 miya_mobile/ 目录运行
```

## macOS (iOS 开发)

### 前置条件

1. **Xcode 16.0+** (App Store 下载)
2. **JDK 17+** 
   ```bash
   brew install openjdk@17
   ```
3. **Gradle** (wrapper 自带，无需手动安装)

### 构建 Shared Framework

```bash
cd miya_mobile

# 构建 iOS framework
./gradlew :shared:linkDebugFrameworkIosArm64

# 输出位置:
# shared/build/bin/iosArm64/debugFramework/MiyaShared.framework/
```

### 创建 Xcode 项目

1. 用 Xcode 新建项目 → iOS → App
2. 项目位置设为 `miya_mobile/iosApp/`
3. 删除自动生成的 Swift 文件
4. 将 `Miya/` 下所有 `.swift` 文件拖入项目
5. 在 Build Phases → Link Binary With Libraries 添加 `MiyaShared.framework`
6. 设置 Framework Search Paths:
   ```
   $(SRCROOT)/../shared/build/XCFrameworks/debug/
   ```

### 自动化 Build Phase (推荐)

在 Xcode Target → Build Phases → 添加 Run Script Phase：

```bash
cd "$SRCROOT/.."
./gradlew :shared:embedAndSignAppleFrameworkForXcode
```

## 连接测试

### 启动弥娅后端

```bash
cd D:/AI_MIYA_Factory/MIYA/Miya
python run/daemon.py
```

后端启动后监听两个端口：
- **Web API (8000)**: 聊天、记忆、人格、状态接口
- **管理 API (9800)**: WebSocket 推送、平台管理

### 测试 API

```bash
curl http://localhost:8000/api/health
# → {"status": "ok"}

curl http://localhost:8000/api/status
# → {"running": true, "version": "8.0.0", ...}

curl http://localhost:9800/api/v1/health
# → {"status": "ok"}
```

### 手机连接

1. 确保手机和 PC 在同一 WiFi
2. 查看 PC 局域网 IP：
   - Windows: `ipconfig` → 找到 `192.168.x.x`
   - macOS: `ifconfig en0`
3. 在手机 APP 设置中输入 IP 和端口 **(8000)**

### 远程连接 (frp)

手机端需要转发两个端口：

```ini
# frpc.ini (PC 端)
[miya-web]
type = tcp
local_ip = 127.0.0.1
local_port = 8000
remote_port = 18000

[miya-ws]
type = tcp
local_ip = 127.0.0.1
local_port = 9800
remote_port = 19800
```

手机 APP 设置中填入 frp 服务器的公网 IP:**18000** (Web API 端口)。
