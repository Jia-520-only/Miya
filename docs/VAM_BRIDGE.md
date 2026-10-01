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

## 可用控制

`hello`、`get_status`、`list_atoms`、`inspect_person`、`get_person_state`、`set_person_params`、
`call_person_action`、`move_person`、`run_sequence`、`vam_autonomy_start`、`vam_autonomy_stop`、
`vam_autonomy_status`、`set_expression`、`look_at`、`stop_all`。

### 人物白名单

VaM 端使用动态白名单：自动允许当前场景中所有 `type == "Person"` 的 Atom，并拒绝灯光、相机、道具和其他非人物 Atom。因此不需要逐个填写人物 UID；从 `AddonPackages` 选择人物外观或预设并把它加载到场景后，`vam_list_atoms` 就会自动返回它。

`AddonPackages` 只是资源包库，未加载进场景的人物不是可控制对象。

### 人物自主控制

- `inspect_person`：当前版本主动禁用。复杂插件参数自动枚举会在部分场景触发 VaM/Mono `Too many heap sections`；不要调用它。
- `get_person_state`：只读读取指定人物一个插件当前公开的 float、bool、vector3、string、chooser 值及动作清单；必须传 `storable`，避免读取整棵插件树。它不包含参数范围元数据，也不会触发插件动作。
- `set_person_params`：设置该人物 storable 已公开的 float、bool、vector3、string 和 string-chooser 参数。float/vector3 会按 VaM 参数范围校验；chooser 值必须在该参数提供的选项中。单次最多 32 项。
- `call_person_action`：调用该人物 storable 已注册的动作。动作名需要由场景配置或固定安全接口提供。
- `run_sequence`：将最多 32 步的编排交给 VaM 主线程按帧推进；支持人物参数、人物动作、表情 Morph、视线、每步等待、Morph 过渡以及循环。循环可以被 `stop_all` 或另一段序列打断，进度和完成/失败事件会通过 `state_update` 推送。
- `set_expression`：操作人物 Morph，单次最多 16 个，值限制为 `-1..1`。
- 表情 Morph 的 `duration` 现在会在 VaM 主线程按时间平滑插值。
- `look_at`：切换人物内建 `EyesControl` 的 `Player`/`None` 模式。
- `move_person`：沿人物主控制点做相对位移平滑过渡；每轴单步最多 `0.25m`，时长最多 `5s`，不枚举第三方插件。
- 连续序列会自动等待位移或表情过渡完成后再进入下一步，避免动作互相覆盖。
- `stop_all`：恢复本桥接修改前的 Morph、视线和人物根位置，并停止人物内建动画时间线。

### 主动行为循环

- `vam_autonomy_start`：启动 Miya 侧后台循环。每个周期先读取 VAM 状态；如果 VAM 正在执行动作序列，循环等待，不抢占当前控制。空闲时提交一段短的表情和注视序列。
- `vam_autonomy_status`：返回循环是否启用、当前人物、模式、周期、最近一次决策和最近错误。
- `vam_autonomy_stop`：只停止 Miya 的主动循环；`vam_stop_all` 还会停止当前桥接动作并恢复桥接保存的状态。

主动循环默认间隔 45 秒，可设置为 15 到 900 秒；`ambient` 模式做低频自然活动，`responsive` 模式更偏向看向用户。手动提交 `vam_run_sequence` 会自动暂停主动循环，避免两个控制来源互相覆盖。启动时会先完成一次状态决策，之后从下一周期开始检查。

`vam_status` 的 `state.sceneState` 会包含当前玩家参考点和人物反馈：`user.available` 表示 VAM 是否提供玩家参考点；每个人物包含 `userDistance`（米）、`userGazeAngle`（玩家视线与人物方向夹角，度）、`userInView`、`userDistanceKnown` 和当前 `lookMode`。这些是只读反馈，距离和视线角度不可被网络请求写入。主动循环默认只读取轻量的场景状态，不自动扫描第三方插件参数；需要读取插件状态时，显式调用 `vam_get_person_state` 并指定一个 `storable`。Miya 会将场景反馈归纳为 `close_engaged`、`near_engaged`、`near_away`、`far` 或 `unknown`，再选择不同的动作节奏。

动作序列示例：

```json
{
  "atom": "Person",
  "loop": false,
  "steps": [
    {"action": "look_at", "target": "user", "wait": 0.4},
    {"action": "set_expression", "expression": "happy", "duration": 0.8, "wait": 1.2},
    {"action": "set_person_params", "storable": "headControl", "values": {"positionState": "Hold"}, "wait": 0.5},
    {"action": "call_person_action", "storable": "scenePlugin", "actionName": "start"}
  ]
}
```

循环模式会持续重复这些已提交的步骤，直到调用 `vam_stop_all` 或提交另一段序列。动作衔接间隔和每个步骤的 `wait` 应根据场景插件的行为调整；所有返回都包含执行 ID 或通过状态事件报告进度。

所有写入仍限制在当前场景中 `type == "Person"` 的人物 Atom，不接受网络传来的代码、任意 Atom UID 或任意参数类型。人物插件公开的动作本身可能具有场景特定效果；弥娅应先检查能力清单，再按当前场景可用的控制项行动。VaM 插件没有统一的机制来撤销所有第三方插件动作，因此 `stop_all` 可以停止当前动作序列、内建动画并恢复桥接管理的表情/视线，第三方持续动作需调用对应插件公开的停止动作。

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
`WebSocketSharp.dll`。安装后先调用 `vam_status` 和 `vam_list_atoms` 确认桥接与人物
状态，再使用固定的安全控制接口。人物控制接口不会自动加载场景或第三方插件；每个
场景所支持的活动由该场景实际加载的控制项决定。当前不要调用 `vam_inspect_person`，
以免触发复杂枚举导致 VaM/Mono 堆耗尽。
