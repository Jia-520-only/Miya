# VAM Bridge 接入协议

`mcpserver/vam_bridge` 是弥娅到 Virt-A-Mate（VAM）的本地控制桥。VAM 侧需要一个 Unity/C# 插件监听 WebSocket，默认地址为：

```text
ws://127.0.0.1:8765/miya-vam
```

可通过环境变量覆盖：

- `MIYA_VAM_WS_URL`：WebSocket 地址，必须是 `127.0.0.1` 的 `ws://` 或 `wss://` 地址
- `MIYA_VAM_TOKEN`：可选连接令牌；每条命令都会带上 `token`
- `MIYA_VAM_TIMEOUT`：请求超时，默认 8 秒，最大 30 秒

## 消息格式

弥娅发送：

```json
{
  "id": "请求唯一 ID",
  "type": "command",
  "action": "set_expression",
  "params": {"atom": "Person", "expression": "happy", "duration": 0.6},
  "token": "可选"
}
```

VAM 插件应返回：

```json
{"id": "请求唯一 ID", "type": "response", "ok": true, "data": {}}
```

失败时返回 `ok: false` 和 `error`。插件也可以推送状态：

```json
{"type": "state_update", "data": {"scene": "...", "atoms": []}}
```

## 第一版动作

`hello`、`get_status`、`list_atoms`、`set_expression`、`set_pose`、`play_animation`、`look_at`、`speak`、`stop_all`。

### 人物白名单

VaM 端使用动态白名单：自动允许当前场景中所有 `type == "Person"` 的 Atom，并拒绝灯光、相机、道具和其他非人物 Atom。因此不需要逐个填写人物 UID；从 `AddonPackages` 选择人物外观或预设并把它加载到场景后，`vam_list_atoms` 就会自动返回它。

`AddonPackages` 只是资源包库，未加载进场景的人物不是可控制对象。

### 已开放的安全动作

- `set_expression`：仅操作白名单 `Person` 的人物 Morph，单次最多 16 个，值限制为 `-1..1`。
- `look_at`：仅切换人物内建 `EyesControl` 的 `Player`/`None` 模式；`user`、`camera`、`player` 表示看向玩家，`none`、`neutral`、`forward` 表示取消跟随。
- `stop_all`：恢复本桥接修改前的 Morph 值和眼睛视线模式。

VAM 插件应自行实施角色白名单、动画白名单和参数范围检查。弥娅侧只允许本机连接，并限制文本长度和动作过渡时长；`vam_stop_all` 应映射到插件中的一键停止逻辑。

## 安装依赖

VAM 不运行时，弥娅也能正常启动。实际调用 VAM 工具时需要：

```powershell
python -m pip install "websockets>=12.0"
```

## VaM 本地安装

当前 VaM 安装已准备好目录：

```text
E:\Game\VAM\VAM\vamzhb\vamzhb\Custom\Scripts\Miya\MiyaVAMBridgeTcp.cs
```

同时已生成标准插件包：

```text
E:\Game\VAM\VAM\vamzhb\vamzhb\AddonPackages\Miya\Miya.MiyaVAMBridge.1.var
```

VaM 需要完整重启后才会扫描新加入的 `.var` 包。

在 VaM 当前场景中选择一个 Atom，打开 Plugins，使用 `Add Plugin -> C# ->
Custom Scripts -> Miya -> MiyaVAMBridgeTcp.cs`。编译并启用后，弥娅侧调用
`vam_status`；成功时会返回 `plugin: miya-vam-bridge` 和 `ready: true`。

这份脚本使用 VaM 自带的 `SimpleJSON` 和 .NET `TcpListener`，不需要安装
`WebSocketSharp.dll`。表情、姿态和动画动作在确认当前角色 Atom UID 及场景
插件后再接入，避免把任意 VaM storable 暴露给模型。
