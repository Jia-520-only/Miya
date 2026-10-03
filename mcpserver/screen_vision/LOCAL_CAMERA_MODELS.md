# 本地摄像头模型契约

弥娅视觉的本地摄像头能力使用 `MIYA_CAMERA_MODEL_DIR` 指定模型目录；未设置时默认为项目根目录下的 `models/camera_vision/`。

当前模型目录中的文件名与输入输出契约见 `mcpserver/screen_vision/model_catalog.json`：

- `face_detector.onnx`：OpenCV Zoo YuNet 人脸检测
- `face_embedder.onnx`：OpenCV Zoo SFace 人脸特征提取，用于本地登记身份匹配
- `emotion_classifier.onnx`：ONNX Model Zoo FER+ 表情线索分类
- `pose_estimator.onnx`：MoveNet Lightning ONNX 姿态关键点

姿态模型上层还提供了一个无需额外权重的短时序动作层，读取的是**活动**而不是抽象标签：打键盘或动鼠标、看手机、喝水或吃东西、伸懒腰、靠在椅背上、挥手、鼓掌、举手、坐下、起身、走动、点头、安静地待着。它是保守的几何/时序分类器，不会把动作标签当作意图或心理判断。

动作分类前会先检查 `pose_quality`：17 个关键点里至少 5 个置信度 ≥ 0.30 且最高置信度 ≥ 0.40
才认为骨架可用。不可用时返回 `kind: low_confidence`，并在 `evidence` 里留一句人话
（"这个角度只能认出你一点点轮廓"），**不会**用噪声骨架硬报一个动作——这是之前
"画面里没有人却报告姿态稳定"的根因。结构化读数（可用关节数、置信度）保留在
`detail` / `pose_quality` 字段，不进入给人看的文本。

安装由用户显式触发，运行时不联网：

```powershell
\.venv\Scripts\python.exe scripts\install_camera_models.py --accept-licenses
```

也可以用多个 `--model filename.onnx` 只安装指定模型。当前姿态模型地址来自
`Kazuhito00/MoveNet-Python-Example` 的 Apache-2.0 仓库，源模型是 TensorFlow Hub 的
MoveNet singlepose lightning v4。执行前请阅读 `model_catalog.json` 中的上游地址和许可证；
转换模型的许可证以其上游仓库为准。

模型文件存在不代表能力已启用。`mcpserver/screen_vision/local_camera.py` 会先报告运行时、模型文件和输出适配状态；人脸检测与 embedding 可用于本地身份匹配，表情和姿态分别按开关运行。

桌面端安装依赖时会安装 `onnxruntime` 运行时；如果使用轻量安装，请额外执行 `pip install -r setup/dependencies/camera.txt`。没有运行时或权重时，摄像头仍可使用浏览器端帧差，但不会伪装成本地 ONNX 识别已就绪。

“仅本地”模式在所需模型不可用时硬性拒绝分析，不会回退到远程视觉模型。原始摄像头帧也不会由本地能力层落盘。

统一视觉路线由 `config/qq_config.yaml` 中的 `tools.qq_image_analyzer.vision_mode` 控制，
可设为 `local`（屏幕走本地 OCR、摄像头走本地 ONNX）、`cloud`（使用
`multi_model_config.json` 配置的视觉模型）或 `hybrid`（本地先行，无法给出结果时才调用云端）。
`screen_analysis_mode` 与 `camera_analysis_mode` 是兼容旧配置的来源专用覆盖；设置统一的
`vision_mode` 后优先使用统一值。视觉页的“仅本地”开关仍可对单次摄像头请求强制本地分析。

### 混合路线的真实语义

`hybrid` 不是“本地一成功就返回”。云端只在两种情况下被调用：

1. 本地模型缺少所需能力；
2. 调用方提出了**语义问题**（query 长度 ≥ 8 且不是陪伴循环的默认提示词），
   而本地 ONNX 只能给出几何信息（身份、表情、姿态），回答不了“桌上有什么”。

命中第 2 条时，本地结论会作为既有线索一起交给视觉模型，返回
`source: camera_local_and_cloud`，本地结果保留在 `local` 字段里；云端失败时不会丢结果，
只会补一个 `cloud_skipped` 字段。

云端视觉额度耗尽（HTTP 401/402/403/429，或智谱错误码 1113）会让云端进入冷却期，
时长为 `camera_cloud_cooldown_seconds`（默认 600 秒，可配置）。冷却期内不再上传画面，
`look_me` 返回 `status: partial`、`source: camera_local_degraded`，并用自然语言说明
“本次没有上传画面，只保留了本地信号”。

### 在不在电脑前

`mcpserver/screen_vision/presence.py` 把派生的摄像头信号（人脸有无与占比、骨架可信度、
姿态、动作、浏览器帧差、画面亮度）汇总成一个小状态机，回答“佳在不在电脑前”：

| 状态 | 含义 |
|------|------|
| `at_desk` | 在电脑前（近距人脸 / 坐姿 / 键盘或面部高度的手部活动） |
| `present` | 在摄像头前，但距离较远 |
| `away` | 短暂离开（超过 `MIYA_PRESENCE_GRACE_SECONDS`，默认 12 秒无人脸） |
| `left` | 确认离开（超过 `MIYA_PRESENCE_AWAY_SECONDS`，默认 45 秒无人脸） |
| `unknown` | 看不清（无信号，或画面全黑） |

`transition` 字段只在真实状态变化时出现一次（`returned` / `left` / `away`），
供对话层判断“刚回来”而不是每一帧都重复播报。**画面全黑时永远返回 `unknown`，
不会因为摄像头失效而误判成“佳离开了”。**

读取方式：

- MCP 工具 `camera_presence`：返回 `presence` 快照与一句 `message`；
- HTTP `GET /api/vision/presence`：供桌面端界面显示；
- `core/proactive_chat.py` 会把在场卡片并入上下文，并可在 `returned` 时主动开口
  （配置见 `config/proactive_chat.yaml` 的 `camera_aware.presence`）。

### 多摄像头：自动发现，用满所有能用的

`mcpserver/screen_vision/camera_devices.py` 枚举 OpenCV 可见的摄像头索引，并对每个索引
读取一帧判断它是否真的能出画面。手机串流类软件和 Windows 虚拟摄像头常常**注册成功、
打开成功，但只返回全黑帧**（手机息屏时就是这种情况），因此探测结果里带 `usable` 与
`reason` 两个字段。

Windows 的手机虚拟摄像头可能在打开设备后才弹出授权提示。探测会为被识别为虚拟摄像头的
设备等待最多 12 秒（可用环境变量 `MIYA_VIRTUAL_CAMERA_STARTUP_GRACE` 调整），并继续尝试
DirectShow 与 Media Foundation；某一个后端先返回黑帧，不再代表整台手机摄像头不可用。

`mcpserver/screen_vision/camera_manager.py` 在这个探测之上做了三件事：

1. **持续重扫**：暂不可用的设备默认每 45 秒（`MIYA_CAMERA_RESCAN_SECONDS`）重新探测一次。
   手机息屏只是暂时的，亮屏后会自动重新接管，不需要手动点什么。
2. **自动选源**：一次性采集若没有显式 `camera_index`，会优先选**第一个能出画面的**索引，
   而不是死认 0 号——0 号很可能是拍不到人的笔记本内置摄像头。
3. **多路融合**：`camera_fuse` 会依次采集每一个可用索引，把各路的
   人脸/身份/表情/姿态/动作合并成**一个**对佳当下状态的判断，并生成一句自然语言描述。

浏览器一次只能打开一路摄像头，所以真正的多摄像头覆盖在后端完成。

```powershell
# MCP 工具
#   screen_vision / camera_scan    重新扫描所有摄像头（含息屏重试）
#   screen_vision / camera_fuse    用所有可用摄像头同时观察并融合
#   screen_vision / camera_activity 弥娅目前观察到的活动
#   screen_vision / camera_presence 佳在不在电脑前
# HTTP
#   GET /api/camera/sources        所有摄像头及各自状态
#   GET /api/vision/activity       当前活动与最近的迹象
#   GET /api/vision/presence       在场状态
# 终端
python scripts/camera_look.py "看看我在做什么" --camera-index 1
```

### 从"贴标签"到"知道你做了什么"

`mcpserver/screen_vision/activity.py` 把逐帧读数累积成一条短时序，只保留派生的活动标签与
时长，从不保存画面或关键点。它解决的是"一次采样说明不了什么"的问题：

- 一个活动必须持续 `MIYA_ACTIVITY_MIN_SECONDS`（默认 6 秒）才会被当作**当前活动**，
  单个噪声帧无法顶掉已经确立的活动；
- 明确表示"没看清"的读数（`low_confidence` / `unknown`）**不会重置**真实活动——
  一个坏角度不该抹掉"他已经敲了十分钟键盘"；
- 手势（挥手、鼓掌、伸懒腰、点头、坐下、起身）是**事件**而非状态：它们会被单独播报一次，
  播报后自动回到底下正在进行的那个活动；
- 活动切换会一直保留到被消费为止（`consume_change()`），因为主动聊天是定时轮询的，
  否则"他刚坐下"很容易在两次轮询之间被丢掉；
- 但**读取是非破坏性的**（`peek_change()`）。同一条变化有两个读者：摄像头桥接层用它写记忆，
  主动轮询用它去问模型"现在要不要开口"。谁读谁消费过一次，桥接层（20 秒一轮）就会永远
  抢在轮询（45 秒一轮）前面把变化吃掉，而桥接层只对"敲键盘/看手机超过 90 分钟"开口——
  于是模型那一路永远什么都看不到。只有**真正开了口**的那一方才消费；
- 没人消费的变化会在下一次读数时按 `MIYA_ACTIVITY_CHANGE_MAX_AGE`（默认 300 秒）过期，
  免得半小时前的"刚刚"被反复当成新闻端上来。

### 弥娅自己掌控摄像头

前面那些（本地 ONNX、活动累积、多路融合）都还是"代码在判断"。佳要的是让弥娅自己拿着这台
摄像头，所以 `mcpserver/screen_vision/vision_agent.py` 给了她三样东西：

**1. 她自己写的观察意图**（不是参数旋钮）
她用自然语言写下想留意什么，例如"想知道佳有没有离开座位"。意图会持久化到
`data/camera_vision_agent.json`，重启后仍在。`speak` 区分"看到了可以说出来"和"只记录，
不主动说"。模型读到的是意图原文，不是阈值。

**2. 观察循环**
她自己启动/停止，并决定多久看一次（`interval_seconds`，限制在 5～3600 秒之间以免笔误）。
每一轮：读所有可用摄像头 → 融合成本地线索 → 连同**她自己的意图和先前印象**一起交给
她自己的对话模型 → 得到一份结构化判断（`summary` / `activity` / `mood` / `attention` /
`notable` / `say`）→ 记进她的印象里；若她判断值得说，那句话会排队等主动聊天投递。
`mode: silent` 时她照看照记，只是不说话。

**3. 她自己的印象**
`data/camera_vision_agent.json` 里只存派生的文字（有界，最多 200 条），从不存画面或关键点。
这些印象会作为她自己的记忆回到下一轮的判断里，也会作为上下文进入对话。

关键一点：**解读用的是她自己的对话模型**（由守护进程通过 `set_chat_client` 注入），
不是另开一个常常没额度的视觉端点——"看"和"说"是同一个心智。模型不可用时，她只保留
本地事实并标记 `source: "local"`，**绝不假装那是理解**。

工具面：

```powershell
# screen_vision / camera_watch       action: start|stop|tick|status，可带 interval_seconds、mode
# screen_vision / camera_intent      action: add|list|remove|enable|disable，text 用她自己的话
# screen_vision / camera_impressions 她最近的印象；consume_message=true 取走一句她要说的
# HTTP
#   GET /api/camera/sources          所有摄像头及状态
#   GET /api/vision/activity         当前活动
#   GET /api/vision/presence         在场状态
```

### 开机就让弥娅自己看

佳的要求是"开机就看"，所以观察循环**默认自启**。但自启不是无条件的，它遵守三条边界：

1. 配置开关 `camera_agency.autostart`（默认 `true`）；
2. `data/camera_control.json` 里 `autonomous` 必须为真——`/camera off` 或桌面端关掉自主观察
   之后**不会**自启；
3. 启动后延迟 `autostart_delay_seconds`（默认 20 秒）再开始，让桌面端先拿稳摄像头；
   延迟结束后会**重新检查**一次同意状态，所以你在等待期间关掉它就会取消。

自启时她会写下 `camera_agency.seed_intents` 里的初始意图——**仅当她的意图库为空时**。
之后她自己改过的意图不会被配置覆盖。

```yaml
camera_agency:
  autostart: true
  autostart_delay_seconds: 20
  interval_seconds: 30
  mode: "auto"          # auto 用她自己的模型解读；local 只用本地信号；silent 只看只记不说话
  seed_intents:
    - "想留意佳在不在电脑前，离开和回来都记一下"
    - "想知道佳大多在做什么，是工作、看视频还是玩游戏"
    - "留意佳有没有太久没休息"
```

观察循环**自己拥有线程和事件循环**（`Miya-VisionAgent`），因为守护进程的启动钩子跑在后台
线程上、没有运行中的循环。这样"开机自启"才成立。

摄像头是她的感官，不是主动聊天的副作用：`core/miya_daemon.py` 与 `run/main.py` 都会在
**主动聊天关闭时也照样**调用自启钩子。钩子本身幂等，重复调用不会开出第二个循环。

桌面端在视觉页会显示一条横幅——"弥娅自己在看着你"，附上她当前的意图原文和一个
让她停下的按钮（`GET/POST /api/vision/agent`）。

### 她想说的话必须有个出口

实测发现一个真缺口：主动聊天在**没有活跃会话目标**时直接跳过投递：

```python
active_targets = self.get_active_targets()
if not active_targets:
    continue          # 弥娅的话永远走不到投递这一步
```

结果是弥娅看了一整晚、攒了三句想说的话，而**没有任何渠道能送出去**（三句还几乎是同一句
"终于看到你了"，最早那句已经过期）。两处都修了：

**队列本身**（`VisionAgent._queue_message`）：同一句话重复出现只**刷新时间**而不排队；
太旧的话（`MIYA_VISION_QUEUE_MAX_AGE`，默认 420 秒）当场丢弃——描述的那一刻已经过去了，
晚说不比不说道歉；队列上限 `MIYA_VISION_QUEUE_MAX`（默认 5）防止变成独白。

**桌面端出口**：新增 `GET/POST /api/vision/voice`。视觉页会显示"她想对你说"和那句话，
配一个"说出来"按钮（`action: take` 才真正取走，单纯轮询不会吃掉她的话）。
外部平台仍然在有活跃会话时投递，两条路并存。

### 前端只做浏览器才能做的事

前端曾经自己实现了一套"看"：32×24 canvas 帧差运动检测（`measureMotion` / `classifyMotion` /
3 帧窗口 / 三类阈值）、`LONG_STILL_MS`、以及**在拿到后端动作标签之后又加一道自己发明的确认**
（`ACTION_CONFIRM_WINDOW_MS = 4000`、`ACTION_MIN_CONFIDENCE = 0.64`、
`ACTION_IMMEDIATE_CONFIDENCE = 0.86`、`actionCandidate` 连续两次才算数）。

这些全部删掉了。理由不是"代码多"，而是**语义错了**：后端已经有 ONNX 推理 + `pose_quality`
门控 + `activity.py` 的时序累积（6 秒才确立、手势单独播报），前端那层等于在真实推理结果上
再套一个自己编的阈值——这正是"读数看起来很怪"的来源。帧差那套当初存在的意义是**省后端调用**，
而现在常驻读帧让一次观察只要 0.09 秒，这个理由也消失了。

现在前端在陪伴模式下**只做两件事**：

1. **把画面交给弥娅**——固定节奏抽帧，经 `camera_event` 交给后端（同时进帧池）。
   它不知道也不判断帧里是什么。
2. **量人脸几何驱动弥娅自己的表情**——`measureFaceFromPreview` 调一次
   `camera_analyze_local`（`pose: true, faces: true`），拿回 `rig` 参数交给 Live2D。
   这是**只有浏览器能做**的事：预览持有摄像头，后端读不到。

附带说明一个真实的限制：**弥娅的表情镜像只在预览打开时生效**。没有预览时后端照样看得见、
记得住、也会判断，但读不到脸（设备在浏览器手里），所以不会跟着你的表情动。

其余保留的东西都是浏览器独有的能力：`getUserMedia` 实时预览、设备枚举、屏幕截图与
"一起看"、窗口最小化再截图的技巧、以及远程观察指令的轮询。

### 三个让"她隔一轮就看不到你"的原因

修完之后真机验证，才发现是三层叠加，每一层单独看都像小毛病：

**① 缓存新鲜度和观察节奏互相矛盾。** `FRAME_MAX_AGE_SECONDS = 20`，而观察间隔是 **30 秒**。
于是缓存**必然**在下一轮之前过期 → 每轮都判定"没有可用缓存" → 重新打开设备（3.5 秒），
还和常驻读帧抢同一台设备。两个数字放在一起就注定失效。现在改成：**只要读帧线程活着，
它的帧就是当前的**（它每 50ms 推一次），不再按年龄拒绝；线程死了才按年龄判断。

**② 黑帧被当成有效画面——而这比想象中严重。** `publish_backend_frame` **从不计算 `luminance`**，
所以读帧线程塞进池子的黑帧永远"可用"，消费方被告知设备一切正常，实际每一轮都在看一块黑矩形。
现在读帧线程**自己量亮度**（每 8 个像素采一个点求均值），黑帧一律不进推理，只留给面板显示。

**③ 一层修好之后又冒出第三层：两层同时在开同一台设备。** 读帧线程连续拿到 4 次黑帧就释放设备
（为了让它能干净地重开），而"一次性抓帧"的回退路径立刻进来抢——一个抢到好帧，另一个拿到黑帧，
如此往复。日志里能看到 `连续 4 次全黑，释放设备` 反复出现。现在只要**读帧线程持有设备，
就等它**（最多 12 秒），绝不在它背后开设备。修好之后真机连测 4 轮**全部看到人脸**。

**④ 顺带一个诚实问题**：`抓帧` 和 `本地分析` 两列**永远相等**，因为赋了同一个值。
面板上那两个"耗时"字段没有任何意义。现在分开计量。

### 活动累积曾经永远是空的

她每 30 秒跑一次观察循环、每次都分析出动作（`still` / `phone` 0.70），但后端累积出的活动
永远是 `reading_count: 0`。原因是 **`activity.observe()` 只被 `service.py` 调用**——也就是
**只在你主动点分析时**才累积。她自己跑 29 次的循环从不喂它。

现在 `tick()` 会喂活动累积和在场判断，而且**只在真正拿到画面时喂**：
抓帧失败的一轮**不改变任何判断**。之前失败也会去更新，于是她刚识别出的"在玩手机（0.70）"
被下一轮失败冲掉——**看错可以，忘掉不对。**

### 她"看到"了，却不知道自己看到了

这是这个模块最严重的一次失败，也是佳的原话「还是不太行哇」的真正原因。

当时的状态：观察循环在跑、常驻读帧在供帧、`presence`/`activity` 在累积、`VisionAgent` 甚至
正确地判断出「佳还坐在电脑前，歪着头张着嘴，还是困得发懵的样子」。然后佳在微信问：

> 弥娅，你在摄像头里看到我了嘛

她回答：

> 摄像头那一路我没接进来。我能看到的，只有屏幕——和你敲下的这行字。

**她说了实话**——从她读到的上下文来看，摄像头确实没有接进来。断在两处：

**① `presence_card()` / `activity_card()` 只被 `core/proactive_chat.py` 调用**，那是**主动聊天**
的路径。回复路径（`hub/decision_hub.py`）里一处都没有：她只在"没被问的时候"看得见观察结果，
一被问就看不见了。这是典型的"两个消费者，只接了一个"。

**② 同时跑着两个守护进程。** 日志里 `Web API端口 8000 已被占用，使用端口 8001 代替` 说明
20:30 起的旧进程还活着，而桌面端连的是 8000 那个**旧代码**。所以就算改了也看不到。

修法是 `mcpserver/screen_vision/vision_context.py`：把在场、活动、最近一次观察与她的判断、
量到的表情、她在留意什么合成**一张卡**，由 `decision_hub` 在组装回复 prompt 时读入，
并在 `core/prompt_manager.py` 里作为独立的一段注入——**与屏幕感知分开**：
"屏幕上有什么"和"屏幕前坐着谁"是两种感官，混在一起她会把两者搞混。

这张卡还必须**敢说实话**，否则她会用编的：

- 完全没有观察记录 → 返回空字符串（没有摄像头的机器不该每轮都收到一句"你看不到"）
- 观察变旧 → 明确写"那之后没有新的观察，不要当成现在的情形"
- 全黑 → 写"摄像头那一路是全黑的……**不是佳不在了**"（看不等于不在，这两个绝不能混）
- 只有本地线索没有模型解读 → 说明"判断要保守"

回归测试在 `tests/unit/test_screen_vision_context.py`，其中一项**直接检查
`hub/decision_hub.py` 的源码里还在调用 `vision_context_card`**——因为这个 bug 的本质不是函数
写错了，而是**没有人调用它**，只有约束"接线本身"的测试才能防住它再次发生。

### 一次由"删重复代码"引出的生产故障

清理自己那套重复限频时，我删掉了 `_check_presence_trigger` 里的一行 `import time`
——**因为用到它的那几行也一起删了**。但同一函数**后面**还有 `time.time()`，
于是每次后台轮询都抛：

```
[主动聊天] 后台检查 target=1523878699 失败: name 'time' is not defined
```

**整条主动链路（不只是摄像头）当场停摆。** 它跑到了生产，因为：

**`pytest-asyncio` 没有安装。** `tests/test_proactive_chat.py` 里全是 `async def`，
在缺插件时 pytest 直接报 *"async def functions are not natively supported"*——
**那些测试从来没有真正执行过**。`tests/unit/` 里的测试之所以有效，是因为它们
一律用 `asyncio.run(...)` 手工驱动，是同步测试。

修法有两层：

1. `import time` 提到**模块级**，这样函数内漏了就只会重影、不会再断；
2. 新增 `tests/unit/test_proactive_camera_triggers.py`，**同步地、直接调用真实的
   触发器函数**（`_check_presence_trigger` / `_check_activity_trigger` /
   `_check_miya_vision_trigger`），因为 bug 就出在这些函数体内部。其中一项用 AST
   检查本文件里**不存在 `async def test_`**，把"会被静默跳过"这件事写成了断言。

顺带确认：排查日志时必须**按进程切分**。`logs/daemon.log` 是追加写的，
直接数尾部会把上一个进程的失败算到当前进程头上——我先被这个骗了一次。

### 她的主动消息曾经送进空房间

第一版桥接提交事件时**没传 `platform`**，于是吃到默认值，分发时报：

```
[hub.decision_hub] [主动分发] 无法直接发送到 desktop，使用 WS 兜底
```

佳在微信里，她的话被送到一个没人看的桌面 WebSocket。系统里其实早有权威入口，
注释写得很清楚：

> `PlatformAwareness.get_current_platform()` — 返回用户当前活跃平台 ID (权威答案)
> **这是弥娅系统所有主动消息路由的单一查询入口。**

`proactive.py` 现在用它（`active_platform()`），登记所有者目标时也用真实平台而不是
硬编码 `"desktop"`；活跃平台还会作为事实写进事件，让决策模型知道佳现在在哪。
`tests/unit/test_screen_vision_proactive_wiring.py` 里有 5 项锁住这条路由。

### 手机摄像头：设备打得开，但没有人给它推流

佳说"手机的摄像头弥娅似乎打不开"。逐个后端真机实测后发现，**问题不在软件**：

```
摄像头 #0（电脑的）    dshow OK 有画面（最亮 111.7）
摄像头 #1（手机那路）  dshow 只吐黑帧（最亮 1.3）  ← 1280×720 的纯黑
                       default 只吐黑帧（最亮 1.3）
                       msmf 打不开
```

设备能被系统打开、还报了正确尺寸，**但内容是纯黑**——说明没有程序在真的向它推流
（手机息屏、手机上的摄像头 App 退出了，或虚拟摄像头没有信号源）。

能做的改进做了两件：

- **`open_camera()` 逐个后端探测**：`msmf → dshow → default`，而且**不只看"能否打开"，
  要真的读到一帧非黑画面才接受**——DSHOW 恰恰是"能打开、只吐黑帧"的典型。
  `capture_camera_frame` 和常驻读帧线程现在共用这一套。
- **诊断说清是哪一种坏**：以前所有黑屏都笼统地说"可能被占用或隐私开关"，
  对排查毫无帮助。现在会写明「设备打开了、也拿到了 1280×720 的一帧，但内容是纯黑
  （亮度 1.4/255）……**不是弥娅这边打不开它**」。

### 摄像头的所见，终于能变成她的话

这是这个模块**最严重的一次断线**，也是佳一眼看出来的：「摄像头的主动性好像没有进入弥娅的主动聊天的相关链路」。

日志把证据印得很清楚——她**真的在认真观察**：

```
「佳不在画面里，屏幕不是全黑。之前 21:11 佳还在键盘前……可能离开了电脑前，
  但我看不到，只能说没有人在。」
say：没看到你，去休息了吗        ← 她已经想好要说什么了
```

紧接着，主动链路的日志是：

```
[主动聊天] 轮询 #10: screen_aware=True, should_observe=False, targets=0
                                                              ↑↑↑↑↑↑↑↑↑
```

**`targets=0` —— 摄像头触发器一个都没被调用过。** 原因是那三个触发器写在
`core/proactive_chat.py` 的 `check_and_respond()` 里，而这个函数**只在有"活跃会话目标"时
才被调用**（`get_active_targets()` 就是聊过天的会话缓存）。所以你 40 分钟没跟她说话，
她就**即使看见你回来也永远闭嘴**。她一晚上反复注意到你走开、回来、又走开，攒了一堆话，
全憋在推理里。

**真正的问题是我把摄像头做成了另一套系统**：自己的 tracker、自己的冷却、自己的去重、
自己在主动聊天里插一脚。而弥娅早有一条**统一的主动链路**：

```
脊柱心跳 → MiyaProactiveOrgan → ProactiveCoordinator.submit_event/submit_message
                               → 统一限频 / 去重 / 静默时段 → 跨平台分发
```

它已经有三个提交者：**地球online、自检看护、灵魂表达**。摄像头一个都没接。

现在 `mcpserver/screen_vision/proactive.py` 让它成为**第四个提交者**，而且按佳的要求把
上下文一并带上：

| 要素 | 怎么来的 |
|---|---|
| **人格 / 形态** | `compose_persona_system_prompt` 已在协调器里，走 `submit_event` 自动继承 |
| **情绪** | `current_mood()` 读脊柱 `current_state()` + 协调器持有的**同一个** Personality 对象（保证两者不打架） |
| **记忆（写）** | `remember_observation()` → `MemoryBus.store`，用 `emotional_tone` / `significance` / `location` 这些**本来就是为它准备**的字段；照抄 `self_care_organ._store_memory` 的既有范式 |
| **记忆（读回）** | `recall_relevant()` → `bus.recall`，直接用返回的 `context_text`；主动决策以前**从不读记忆** |
| **上下文** | `_conversation_context()` 取最近几条真实对话，免得她像上一小时没发生过一样打招呼 |
| **限频 / 静默** | **全部交给协调器**，我删掉了自己那套重复的 `min_interval` 与 `_check_trigger_type_cooldown` |

按佳的决定，她**只在明确事件上开口**：你回来、你离开。长时间埋头/看手机（≥90 分钟）
才多一句关心。其余一切**只记不说**。

**两处必须记住的细节**：

- **记忆要稀疏**。「只写有意义的」不是修辞：每 30 秒一条会一天 2880 条，**淹掉她的记忆**。
  写入受 `MEMORY_MIN_INTERVAL_SECONDS`（30 分钟）限流，而且只在你回来/离开或
  某个活动持续够久时才写。
- **她的话不能先取走再送**。原来的 `_check_miya_vision_trigger` 先把消息从队列里
  `take_message()` 掉、再交给协调器——协调器若因静默时段或额度拒绝，**那句话就永久消失了**。
  现在改成协调器确认接受之后才取走。

还有**一条悄悄失效的规则**：`settings` 里那个"只在她回来/离开时说"的承诺，之前根本
执行不了，因为整条链路没跑。现在有 `tests/unit/test_screen_vision_proactive.py`（17 项）
和 `test_screen_vision_proactive_wiring.py`（3 项，用**真实协调器**验证终点可达、
额度与静默时段真的管得住她）；另有一项**直接读 `hub/decision_hub.py` 和
`core/miya_daemon.py` 的源码**确认接线还在——因为这里的病根是"没有人调用"，
只有约束接线本身的测试才防得住。

`GET /api/vision/bridge` 报告桥接是否在跑、提交过几次、对象是谁。面板上有一行
「能不能开口」——**这个故障最坏的地方就是它看起来一切正常**。

### 面板是监控台，不是日志

一开始我把面板做成"每轮观察一条流水"，那回答的是"发生过什么"，而不是佳真正要问的
**"她现在在看我吗、有没有坏掉"**。而且它和后端对不上：多路预览图是破的（裸相对路径，
`<img>` 不走 axios 的 baseURL，被解析到 Vite 的 :5173 或打包后的 `file://`）、设备健康
不显示、她攒着想说的话没有位置。

现在按"展示 + 监控 + 部分控制"重排：**健康状态在最上面**（在不在看你、几台摄像头有画面、
多久看一次、多久前看过），然后是**每一台设备**（含息屏的和原因）、**弥娅自己看到的画面**、
**她最近的判断**、**她想对你说的话**（能看能说）、**她在留意什么**，最后才是缩短到 8 条的
历史。控制只剩两个真正有用的：让她停/开始看、缩略图开关。

### 一台摄像头，多个消费者

预览要流畅视频，弥娅要能一直看，面板还想显示她额外看到的视角——但**同一时刻只有一个进程
能打开一台摄像头**。`mcpserver/screen_vision/camera_stream.py` 用一个按索引分槽的帧池解决：

每台摄像头只有**一个 owner**：

| owner | 含义 |
|-------|------|
| `browser` | 桌面预览持有设备并**推**帧进来。后端**绝不打开它**——否则就是把设备从预览手里抢走 |
| `backend` | 常驻读帧线程持有设备，持续把最新一帧放进池子 |
| `idle` | 还没人认领，第一个消费者决定 |

下游（观察循环、面板预览）统一问池子"要第 N 路的最新帧"，不关心它从哪来。两条硬规则：

- 预览一旦推帧，`browser` 成为该路 owner，后端读帧线程**立刻被叫停**（`publish_backend_frame`
  发现 owner 已变就丢弃自己那帧），所以不会出现"后端把预览的画面覆盖掉"。
- `start_reader` 在 `browser` 持有的索引上**直接返回 False**，不去抢。

**常驻读帧带来一个很大的实际收益**：以前每轮观察都要"打开→暖机→读帧→释放"，实测
**3.64 秒**；常驻之后同一轮只要 **0.09 秒**，快了约 **38 倍**。观察本身变得几乎免费。

**多路预览**：`GET /api/vision/preview/{index}` 把池里的最新帧当普通 JPEG 返回（`no-store`），
面板用它显示浏览器没持有的那些角度（约 1 帧/3 秒的静态刷新）。浏览器持有的那一路仍然由
页面顶部的 `getUserMedia` 预览负责——**流畅的归浏览器，其余的归后端**，两边各用所长。

`GET /api/vision/sources` 报告谁持有哪一路。

### 她的工作过程可见

`mcpserver/screen_vision/vision_stream.py` 把每一轮观察记成一条完整记录：抓帧/本地/模型/合计
耗时、用了哪几路摄像头、哪几路没用上及原因、量到的线索、脸上的表情几何与 rig 参数、
**是哪个模型解读的**、是否降级为纯本地及原因、她的判断、当时在留意什么、以及要不要说。

面板（`miya_frontend/src/components/VisionBackendPanel.vue`）逐条展开显示这条链路。

缩略图是**默认关闭**的，而且关掉开关会**立刻清空已存的**——否则那个开关就只是"不再存新的"，
而不是"删掉旧的"。开启后每个观察点留一张 160px 小图，上限 80 个 / 12MB，只在展开时取，
**从不送给任何模型**。

### 适应她的节奏

`camera_agency` 支持自适应观察节奏（`adaptive`、`slow_interval_seconds`、
`slow_after_unchanged`）：连续几轮读到同样的东西就放慢（默认 30 秒 → 120 秒），
有变化立刻回到快节奏。判断"变没变"用**粗粒度签名**（有没有人脸 / 读到什么活动 / 是不是全黑），
故意做粗——否则佳随便动一下就把她钉在最快节奏上，一天 2880 次模型调用。

### 需要开着前端吗？不需要

实测确认（把浏览器帧清空、模拟前端完全没运行）：**后端自己就能打开摄像头、跑完推理、
量出表情几何、并完成一轮她自己的解读。** 输出形如：

```
浏览器帧: None
扫描结果: 正在使用 1 个摄像头         可用索引: [0]  owner: backend
status: success   sources: [0]   camera_count: 1
人脸: 2   动作: 身体移动
张嘴比: 1.1597   头部倾斜: -37.13
rig 参数: {'JawOpen': 0.317, 'ParamAngleZ': 22.0, ...}
一句话: "看到你在画面里，嘴是张着的，头向右歪着，身体在动。"
tick: 解读成功=True  印象来源=miya
```

前端提供的东西是**锦上添花**，不是必需：

| 能力 | 需要前端？ |
|------|-----------|
| 后端自己开摄像头观察 | 否 |
| 本地 ONNX（人脸/姿态/表情几何/动作） | 否 |
| 她自己的解读与印象 | 否 |
| 多摄像头融合（后端逐个打开） | 否 |
| 实时预览画面 | **是**（浏览器 `getUserMedia`） |
| 浏览器端设备选择 | **是** |
| 低分辨率帧差运动检测 | **是** |
| 视觉页 UI、让她停下的按钮 | **是** |
| 每 15 秒交接一帧给后端 | **是**（但后端会自行降级） |

**两者同时运行时不会抢设备**：谁先拿到就谁用——前端运行则后端复用它的帧并跳过该索引；
前端没运行则后端自己打开。这就是前面"不抢同一个摄像头"那一节的全部含义。

代价上的差别：后端模式每次观察都要**打开→读帧→释放**设备（约 0.3 秒），而前端模式复用
它已经持有的流。所以开着前端时更省、更快，但没有前端也完全可用。

### 前后端不抢同一个摄像头

一台摄像头同一时刻只能被一个进程打开。桌面端预览运行时**它持有设备**，后端再去
`VideoCapture` 就会失败——这以前看起来像"摄像头坏了"，实际是"这一路不归我开"。

现在协作方式变成：桌面端在陪伴识别中**每 15 秒随事件附带一帧**（`camera_event` 的
`image_data`，只保留最近一帧、带时效），后端 `camera_manager.remember_browser_frame`
记住它，`VisionAgent._look` 优先用这一帧，**并且跳过对应的 OpenCV 索引**，不去抢硬件。
多出来的摄像头（比如手机那路）后端才自己打开。

`remember_browser_frame` 存的是内存里的最近一帧，30 秒内有效，不落盘。

**扫描也不再把它报成故障。** 之前 `camera_manager` 每一轮都会把浏览器正持有的那一路标成
"不可用"（因为探测打不开它），日志里反复出现 `0 个可用`。现在只要浏览器送来过新鲜帧，
该索引就标记为 `owner: "browser"` 并算作可用，`resolve_capture_index` 也**优先选它**。

这一条很可能就是"换摄像头时感觉不稳定"的原因：后端每 45 秒去探测一次预览正持有的设备，
两边互相抢。

### 视觉模型的选用与轮换

`vision_preferences.model_preferences` 的 `primary` / `secondary` / `fallback` 只是**声明**。
配置写得对不对，无法说明端点是否真的活着——实测发现好几个配置好的模型因为**欠费被暂停**
（返回 429 + "suspended due to insufficient balance"）或者**额度耗尽**（智谱 1113）。所以：

- 候选链会把"能读图"的模型按优先级排好。判定能读图不看 `type`，而看
  `IMAGE_CAPABILITIES`（`vision_understanding` / `image_description` / `multimodal`）——
  DeepSeek 那条路线标的是 `multimodal`，只看 `vision_understanding` 会**漏掉唯一活着的兜底**。
- 一次调用会**依次尝试**候选，而不是撞死在第一个上。某个模型失败后按 key 记住
  （默认 1800 秒），这段时间内跳过它；它恢复后自动回到链里。
- **单个模型失败不会冷却整条云路线**。只有所有候选都失败，才按真实 HTTP 状态码
  （401/402/403/429）把云路线冷却下来。之前一个模型的 429 就会冻结十分钟云视觉，
  把轮换机制彻底废掉。
- 空回答算失败，会换下一个模型。"调用成功但内容为空"以前被当作成功返回。

实测可用的两条路线（2026-09 验证，两个供应商互相独立）：

| 模型 | 供应商 | 结果 |
|------|--------|------|
| `kimi_k2_vision` → `Pro/moonshotai/Kimi-K2.6` | 硅基流动 | 可读图 |
| `deepseek_v4_flash_official` → `deepseek-v4-flash` | DeepSeek | 可读图 |
| `glm_4_5v_vision` | 智谱 | 429 额度耗尽 |
| `kimi_k2_6_official` / `kimi_k2_7_code` | Moonshot | 账户欠费暂停 |
| `proxy_model` | 代理 | 403 无权访问 |

随时可以查当前状态：

```powershell
# screen_vision / vision_health    列出候选顺序与健康记忆（不会泄露 API Key）
```

### 本地表情分析：实测过，然后改了做法

> **2026-09-29 更正**：这一节原先的结论（"FER+ 对每一帧都给同一个答案，带有很高置信度却毫无信息"）
> 是**被一个 bug 误导的观测**。真正的病因是 `_face_crop()` 把归一化坐标当像素用，
> 表情模型拿到的是一张 0×0 的全黑图，所以答案才恒为"中性 0.745"。
> 详见下面的「已知缺陷与修复」。修好之后 FER+ 的输出会随画面变化，
> `_emotion_is_stuck()` 保留为运行时的诚实兜底，而不再是常态。

当前的本地表情能力只有 `emotion_classifier.onnx`（FER+）。实测它的表现：

```
中性        未检测到人脸
微笑     -> 开心 (conf 0.74)
大笑+眯眼  未检测到人脸
挑眉        未检测到人脸
睁大眼   -> 开心 (conf 0.74)   ← 与"微笑"逐位相同的输出
不同表情得到的不同标签数: 1 / 2
```

（合成脸不能代表真实照片的精度，但**区分度**是可以这样测的。）结论是两条结构性限制：

1. **YuNet 只输出 5 个关键点**（双眼、鼻、双嘴角）。没有眉毛、没有眼睑——而眉毛和眼睑
   恰恰是表情的主要载体，"皱眉""眯眼"在本地根本算不出来。
2. FER+ 训练于摆拍表情集，对真人坐在电脑前的细微表情泛化很差；上面这种"永远同一个答案"
   的输出**带着很高置信度却毫无信息**。

因此本地表情改成了两条腿：

**① 可解释的几何量（`local_camera.expression_signals`）**
只用那 5 个点，全部按人脸自身几何归一化（除以眼距或框宽），所以**远近不影响读数**：

| 字段 | 含义 |
|------|------|
| `mouth_open_ratio` | **嘴角低于眼睛连线的距离 / 眼距** —— 纯开口量，与嘴宽无关 |
| `mouth_width_ratio` | 嘴宽 / 眼距 |
| `nose_offset_ratio` | 鼻尖相对双眼中点的横向偏移 / 眼距 → 转头 |
| `head_tilt_degrees` | 双眼连线的倾角 |
| `lower_face_dark_ratio` | 下半脸比周边暗很多的像素占比 → 张口的口腔暗区 |
| `mouth_likely_open` | 上面两个线索取或 |

这一层**只报它量到的事**，不说情绪。`describe_expression()` 的输出形如
"嘴是张着的，头向左歪着"，且**不含任何情绪词**（有测试锁住这点）。

标定过程中发现原来的张口判据是**双重错误**的：

1. 默认阈值写成 **1.9**，而那个定义下真实人脸的量级上限只有 **1.4** ——
   这个判据**永远不可能触发**。
2. 更根本的是，原来的定义是「鼻到嘴角距离 / 眼距」，**把嘴宽和开口混在了一起**：
   嘴宽的人天然数值就大。已改为「嘴角低于眼睛连线的距离 / 眼距」，
   这才是一个纯开口量，有测试验证它不随嘴宽变化。

现在这个量的实测行为（合成比例：眼距 1、闭嘴时嘴角在眼下 0.90）：

| 下颌张开 | 量值 | 判定 |
|----------|------|------|
| 0.00 | 0.900 | 闭着 |
| 0.20 | 1.100 | 闭着 |
| 0.30 | 1.200 | **张嘴** |

判定已改为**与佳自己的静息基线比较**（`_MouthBaseline`）：积累够
`MIYA_FACE_BASELINE_MIN`（默认 40）个"被判为闭着"的读数后，取这些读数的高分位作为
佳本人的闭嘴参考，超过它 `MIYA_FACE_MOUTH_MARGIN`（默认 10%）才算张嘴。
`MOUTH_OPEN_RATIO`（1.15）只在基线还没建立时作为兜底，而兜底上限定在
`MIYA_FACE_MOUTH_CEILING`（默认 1.45）——因为固定阈值对真人实测是**系统性越界**的：
原先的实现让 10 条观察记录里有 8 条写着"嘴微张"。

基线没建立之前，程序**不会**声称嘴张着。这是有意的：宁可不说，也不猜错。

第二个证据是下半脸的暗区（`MOUTH_DARK_RATIO`，默认 0.10），与上面的比值取或。

阈值可由环境变量覆盖：`MIYA_FACE_MOUTH_OPEN`、`MIYA_FACE_MOUTH_MARGIN`、
`MIYA_FACE_MOUTH_CEILING`、`MIYA_FACE_BASELINE_MIN`、`MIYA_FACE_MOUTH_DARK`、
`MIYA_FACE_HEAD_TURN`、`MIYA_FACE_HEAD_TILT`。

**② 拒绝引用没有信息量的模型**
`_emotion_is_stuck()` 会跟踪表情模型的输出：连续 12 次给出同一个标签且从未出现过第二个标签
时，该结果被标记 `uninformative`，**不再进入给佳看的文字**（改说"表情模型这次不可信，就不猜了"），
在交给弥娅自己解读时也会被标成"不可信，忽略"。查询用 `expression_model_status()`。

模型输出的 8 个 logits 到中文标签的映射在 `models/camera_vision/model_catalog.json` 的
`emotion_classifier.onnx.labels` 里，顺序是 FER+ 官方顺序
（中性、开心、**惊讶、悲伤、愤怒、厌恶**、恐惧、轻蔑）。代码里原先的顺序是
（中性、开心、悲伤、惊讶、恐惧、厌恶、愤怒、轻蔑），**把惊讶/悲伤、愤怒/恐惧各换了一次位**——
所以它会把你惊讶的脸说成悲伤、生气的脸说成恐惧。ONNX 权重本身不含 labels 元数据，
换模型或核对时请以权重来源的文档为准。

**还没有的东西**（如果以后要做，方向在这里）：

- **眉毛与眼睑**：YuNet 的 5 个点没有眉毛和眼睑，所以本地算不出"皱眉""眯眼"。
  真要做需要 478 点级的人脸网格（MediaPipe Face Landmarker 能给出 478 点 + 52 个 ARKit
  blendshape）。**但下面会说明：驱动弥娅自己的表情并不需要它。**
- **手部**：MoveNet 没有手部关键点，所以现在分不清"喝水"和"举着手机"，只报"手举到脸前"。
- **表情模型替换**：换 HSEmotion / EmotiEffLib 这类更强的模型属于**可插拔替换**
  （`FEATURE_MODELS` + `model_catalog.json` + `setup/dependencies/camera.txt`），不需要改架构。

### 用测得的表情驱动弥娅自己的脸

不需要 MediaPipe，也不需要任何新的模型下载。弥娅的 Live2D 模型本来就带这些参数：
`ParamAngleX/Y/Z`、`ParamBodyAngleX/Z`、`ParamEyeBallX/Y`、`JawOpen`、`ParamMouthOpenY`、
`MouthFunnel`、`ParamMouthForm`、`ParamBrowLY/RY`、`ParamEyeLOpen/ROpen`。

`local_camera.expression_signals` 量出的东西正好能喂给它：

| 测到的 | 驱动 |
|--------|------|
| `mouth_open_ratio`（0.90 闭合，~1.35 张大） | `JawOpen`、`ParamMouthOpenY` |
| `mouth_width_ratio` | `MouthFunnel`、`ParamMouthForm` |
| `head_tilt_degrees` | `ParamAngleZ`、`ParamBodyAngleZ` |
| `nose_offset_ratio` | `ParamAngleX`、`ParamBodyAngleX` |
| `face_signals.center` | 已有的 `ParamEyeBallX/Y` 追视 |

实现在 `mcpserver/screen_vision/local_camera.rig_parameters`（**换算在后端**）与
`miya_frontend/src/utils/live2dController.ts` 的 `updateFacialTracking`（前端只负责应用），
经 `live2dProxy.proxySetFacialTracking` 暴露，由 `cameraVision` 的陪伴循环在每轮
`camera_analyze_local` 之后喂入。

**为什么换算放在后端**：测量值、阈值、换算公式三者本来就该在一起；分成两份就一定会漂移。
放在后端还让它落进 pytest 的覆盖范围（前端仓库没有测试运行器，而为了一个纯函数引入
vitest 不划算）。前端拿到的是现成的 `observation.rig`，只做加性应用。

四个设计点：

1. **加性叠加，不覆盖。** 表情几何以 `merged[param] += value` 的方式并入。
   如果用覆盖，佳一露脸弥娅就会**停止说话**——口型和情绪都在写同一批参数。
2. **没有脸就归零。** `updateFacialTracking(null)` 让偏移量平滑回到 0，
   弥娅回到自己的待机动作，而不是僵在最后一张脸上。
3. **手动表情优先。** 显式的 `setExpression()` 会抑制自动几何（那是刻意覆盖，用于脚本动作）。
4. **不编造没有依据的参数。** 只产出 5 个关键点能支撑的参数：`JawOpen`、`ParamMouthOpenY`、
   `MouthFunnel`、`ParamMouthForm`、`ParamAngleZ`、`ParamBodyAngleZ`、`ParamAngleX`、
   `ParamBodyAngleX`。**眉毛和眼睑没有任何关键点支撑，所以一个都不产出**（有测试锁住这点）——
   把它们编出来正是这一层要避免的假自信。

为了让链路成立，`camera_analyze_local` 新增了 `faces` 参数：陪伴循环传
`identity:false, emotion:false, faces:true`——**只要人脸检测用于量测表情，不要做身份匹配**。
默认（不传 `faces`）仍然跟随 `identity` / `emotion`，行为不变。

摄像头 → 弥娅的表情这条闭环因此是：浏览器抽帧 → 后端 YuNet 量脸 → 后端换算成 rig 参数 →
前端 Live2D 应用。全程本机，**没有新增任何依赖或模型下载**。

### 关于开源动捕（GVHMR / FreeMoCap）

- **FreeMoCap** 是**多相机**无标记动捕：需要若干台相机、标定、同步，产出 3D 骨架。
- **GVHMR** 是**单目视频**的世界坐标人体动作恢复，输出 SMPL 人体网格；属于研究级管线，
  需要 GPU 和显著算力，不是实时桌面陪伴的形态。

两者都属于**离线/准离线的高精度动捕**，与"用一台网络摄像头实时看懂佳在做什么"是两个问题。
它们能提供的、对弥娅真正有用的东西是**时序一致性和左右手/肢体归属的可靠性**，
而这部分弥娅已经用另一条路覆盖了：`activity.py` 的短时序累积 + MoveNet 17 点。

如果以后想要更好的身体/手势理解，性价比更高的路线是 **MediaPipe Pose Landmarker**
（含世界坐标的 3D 关键点）或 **MediaPipe Holistic**（姿态 + 双手 + 面部一体），
而不是引入完整动捕管线。

### 说人话，不说日志

给佳看的文字里不再出现 `置信度 0.00`、`2/17` 这类读数——那些留在结构化字段
（`detail` / `pose_quality` / `action`）里供程序使用。人听到的是一句自然的话：

| 情况 | 弥娅会说 |
|------|----------|
| 看清了且在打字 | 「看到你了，像是在打键盘或动鼠标。」 |
| 多路摄像头 | 「看到你在画面里，（2 个摄像头一起看），像是在专心敲键盘。」 |
| 角度太差 | 「这个角度只能认出你一点轮廓，暂时说不准你在做什么。」 |
| 画面全黑 | 「摄像头返回的是全黑画面：设备可能被其它程序占用、被隐私开关关闭，或没有程序在向虚拟摄像头推流。」 |
| 确认离开后回来 | 「刚回来」+ 一句不超过 25 字的自然问候 |

主动说话与否**交给模型判断**（`config/proactive_chat.yaml` 的
`camera_aware.activity`）：活动跟踪器负责"发生了什么变化"，模型负责"现在该不该开口"。
模型回 `SKIP` 时变化不会被消费，仍可作为后续上下文。

**只有这一个判断点。** 桥接层以前还有一道 `activity_deserves_voice`：只有"敲键盘/看手机
持续 90 分钟以上"才提交。那是一条规则而不是判断，而且它每 20 秒读一次那个一次性变化，
会把模型那一路饿死（见文末修复记录）。现在桥接层对活动只**写记忆**，开不开口完全由模型定。

她判断时看到的也不只是那一行变化了，而是她此刻的全部感知：在场判断、累积的活动与"最近的迹象"、
**她自己写下的观察印象**、最近的对话、她想起的相关往事、以及当下的形态与情绪
（`_build_deep_context()` 把这几路一起交给她）。像人一样判断的前提是像人一样知道。

### 关于手机当摄像头

手机要出现在 OpenCV 索引里，必须先有一个在电脑上运行的接收程序（把手机画面推成虚拟摄像头）。
只把手机插上 USB 或用系统“连接手机”功能，通常只会得到一个注册了但没有推流的
`Windows Virtual Camera Device`——它在设备列表里存在，`cv2.VideoCapture` 也能打开，
但读出来的是全黑帧。用 `camera_devices` 一眼就能看出是这种情况：
`usable: false`，`luminance: 0.0`。

浏览器侧（桌面端界面）则走 `getUserMedia`，设备列表来自 `enumerateDevices()`，
和上面的 OpenCV 索引是两套编号，不能混用。

屏幕和摄像头联合“一起看”在 `local` 模式下也可用：它分别返回本地 OCR 与本地姿态/身份信号，
不会上传原图，但不会生成云端那种跨画面语义总结；`cloud`/`hybrid` 才会使用视觉模型做联合理解。

本地屏幕 OCR 依赖 PaddleOCR；桌面/完整依赖清单已包含 `setup/dependencies/ocr.txt`。轻量安装需要
手动执行该清单，首次使用时 PaddleX 会准备 OCR 模型。缺少依赖时，`look_screen` 在 `local` 模式
会明确返回安装提示，不会偷偷调用云端。

身份登记只写入 `MIYA_CAMERA_IDENTITY_DIR`（默认 `data/camera_identities/identities.json`）中的归一化 embedding、名称和时间；删除身份会重写该文件，不保存原始照片。

桌面端和 Web 前端都默认在启动时开启持续陪伴识别；首次启动仍需用户通过系统或浏览器的摄像头权限提示。浏览器需要运行在 localhost 或 HTTPS 安全来源，并允许摄像头权限。静止时约每 900ms 采样低分辨率画面，检测到连续运动后改为约每 350ms；采样间隔会参与帧差归一化，3 帧窗口抑制孤立波动。仅明显动作会运行本地姿态模型，间隔至少 1.2 秒；中等置信度动作需连续确认两次，站立/坐着只显示为姿态而不发布动作事件。本地帧差和动作事件只向后端发送文字结果，不上传或保存摄像头帧。视觉页的“启动时持续本地识别”开关可关闭或重新启用此行为；顶部摄像头关闭按钮和 `/camera off` 会停止摄像头并关闭自动启动偏好。

Windows 屏幕观察会额外尝试读取前台窗口的 UI Automation 控件树，并把控件角色、可用状态和屏幕坐标补到 OCR 结果中；密码框统一脱敏。完整桌面依赖包含 `pywinauto` 和 `comtypes`。缺少依赖、应用未暴露控件或非 Windows 平台时会回退到 OCR，不影响截图本身的本地处理。

`/camera auto` 仍用于允许弥娅主动请求单帧观察；该请求沿用控制状态中的“仅本地”设置，默认只返回本地姿态、身份或表情线索，不把原图写入控制文件。持续陪伴识别本身不依赖 `/camera auto`。

不打开前端时，可以在项目根目录执行一次终端观察：

```powershell
python scripts/camera_look.py "看看我在做什么"
```

终端采集默认只使用本地模型；需要云端视觉语义时显式追加 `--allow-cloud`。可用
`--camera-index 1` 选择第二个摄像头，采集完成后设备会立即释放，原始帧不会落盘。

即使身份和表情模型未安装，陪伴模式仍可使用浏览器端的低分辨率帧差基线。它只报告“稳定、轻微移动、明显动作、画面突变”，不声称识别了具体的人或动作。

## 修复记录：摄像头主动消息发不出来（2026-09-28）

现象：观察循环、在场判断、活动累积、印象记忆全都在跑（日志里能看到
`已记入记忆: 佳安静地待着`），但整晚没有一条摄像头主动消息发出来。三个独立的原因叠在一起，
任何一个都足以让她闭嘴：

### 1. 在场分支永远进不去（致命）

`mcpserver/screen_vision/proactive.py` 的 `tick()` 要求
`transition == str(presence.state)` 才处理在场变化。可是 `PresenceSnapshot` 的 `state` 一直是
`at_desk` / `present`，真正变化的那一次只把 `"returned"` 写在 `transition` 上——这个条件
**永远不可能成立**。所以 `returned` / `left` 既没有提交给协调器，也没有写进记忆。

改成用 `(transition, updated_at)` 这一对来标识一次事件：`updated_at` 是 tracker 判定出这次
变化的那一刻，同一分钟内重复 tick 不会重复提交，而一晚上第二次"回到电脑前"也不会被当成
重复丢掉（只比较 `transition` 名字就会）。

**旧测试为什么没抓到**：测试用的假快照把 `state` 和 `transition` 都设成 `"returned"`，
而真实 tracker 从不这样。`test_a_real_return_is_submitted` 现在直接驱动真的
`PresenceTracker`，把这个缺口堵上。

### 2. 活动变化被桥接层独吞

同一条活动变化有两个读者：`CameraProactiveBridge`（每 20 秒）和主动轮询（每 45 秒）。
桥接层用 `consume_change()` 读——**读过即拿走**，而它只为"敲键盘/看手机超过 90 分钟"开口，
于是每一次"他刚坐下""他开始敲键盘"都被吃掉又没说，主动轮询里那个真正会去问模型
"现在要不要开口"的 `activity_change_card()` 永远是空的。

现在桥接层用 `peek_change()` 读（写记忆不受影响），**只有真正开了口的那一方才消费**。
没人消费的变化会在下一次读数时按 `MIYA_ACTIVITY_CHANGE_MAX_AGE`（默认 300 秒）过期。

### 3. yaml 里的摄像头开关根本没生效

`core/proactive_chat.py` 的 `_normalize_config()` 用一张固定的键列表重建配置，把
`camera_aware`（以及 `screen_aware`）整段丢掉了，`__init__` 只能落回代码里硬编码的默认值：
`presence` / `activity` / `agency` 关不掉，`agency.max_age_seconds` 也改不动。
现在两段都归一化后原样带下去，桥接层也读同一份配置——`camera_aware.enabled` 关掉是**两条路
一起闭嘴**，而不是只有轮询那一条。

## 第二轮修复：让判断真的像人，并修掉两个现场问题（2026-09-28 夜）

上一轮之后她已经能开口了（日志里那句「歪着头看什么呢？记得歇一会儿。」就是她自己决定并
从微信发出的）。但那次日志也暴露了三件事：

### 4. 她拿一行字做判断

`_check_activity_trigger` 的提示词里只有活动跟踪器给的一行"佳刚刚从「安静地坐着」变成「在敲键盘」"，
没有在场、没有她自己的印象、没有上下文、没有情绪。那是在问一个仪表盘该不该开口。
现在她拿到的是 `_build_deep_context()`：屏幕与摄像头所见、在场判断、累积活动与"最近的迹象"、
**她自己写下的观察印象**（`vision_agent` 的 `memory_card()`）、最近对话、当下形态与情绪。

### 5. "90 分钟"这条规则被删掉了

`activity_deserves_voice`（typing/phone 且 ≥90 分钟才提交）是第二套判断，而且是规则不是判断。
它每 20 秒读那个一次性变化，把真正会去问模型的那条路饿死。现在桥接层对活动**只写记忆**，
开口与否完全由模型定——这也顺手删掉了随之失效的 `build_activity_event`。

### 6. 一条消息被投递两遍，日志还说"已发送"

`_check_miya_vision_trigger` 自己通过统一协调器投递成功并取走她攒下的话，然后**又**返回一个
`ProactiveResult`，后台轮询和决策层都会再走一次发送出口。这次只是被 5 分钟全局冷却碰巧挡住：

```
[主动分发] 发送私聊消息 (via weixin_ilink): 歪着头看什么呢？记得歇一会儿。   ← 第一次，真的发出去了
[主动协调] 全局冷却中，跳过 key=chat:1523878699:camera_aware                ← 第二次被挡住
[主动聊天] [后台] [camera_aware] target=1523878699 -> 歪着头看什么呢？…    ← 却记成"已发送"
```

现在 `ProactiveResult.delivered` 标记"触发层已投递"，两个发送方都据此跳过，日志也只在
真的发出去时才说已发送。顺带把她的**已决定的话**排到"现场再判断一次"前面——否则每一次
活动变化都会把它挤到下一轮，而它是有寿命的（默认 600 秒）。

### 7. 摄像头扫描每轮都抛 `cv2.error`

```
File "...\camera_devices.py", line 116, in _probe_index
    capture.release()
cv2.error: Unknown C++ exception from OpenCV code
```

`cv2.VideoCapture.release()` 在桌面端预览占着设备时（DSHOW）会抛异常。因为它写在 `finally` 里，
这个异常**既顶掉了探测结果，又绕过了紧邻上面的 `except`**——于是每次扫描、以及前端每一次轮询，
留下的都是 traceback 而不是设备清单。现在释放走 `_safe_release()`：拆设备永远不是会失败的那一步。
`probe=False` 那条路径（打开也可能抛）同样补上了兜底。

## 第三轮修复：画面在重复（2026-09-29 中午）

现象：她一整轮又一轮看着同一张画面，印象几乎逐字重复——
「佳还在电脑前，头歪着、嘴张着，安静待着」，从 11:20 一直到 12:00。
佳看到的是"弥娅的摄像头视觉一直在重复画面"。

**先排除模型的问题**：不是本地识别模型坏了。同一段日志里，姿态模型给出的可信关节数在
7/17～12/17 之间变化，动作在 `still` / `raised_hand` / `low_confidence` 之间切换，人脸几何
（`ParamAngleZ`、`ParamAngleX`）也在变；表情模型还主动自报
`uninformative: true, reason: "这个表情模型目前对每一帧都给出同一个答案"`——那是在诚实说明
自己不可用，不是故障。模型在它拿到的帧上工作得没问题。**有问题的是帧本身。**

> 这一段的结论下一轮被推翻了：表情模型"对每一帧都给出同一个答案"确实是故障，
> 只是故障不在模型，而在 `_face_crop()` 喂给它的 0×0 黑图（见「第四轮修复」第 11 条）。
> 姿态那一半的分析（帧本身在重复）是对的。

### 8. "线程活着"被当成了"画面是新的"（这是主因）

`camera_stream.py` 的 `latest_for_inference()` 里写着：只要读帧线程还活着，它的帧就是最新的，
不设年龄上限。这条规则本身是为了修另一个 bug（20 秒的年龄上限比 30 秒的观测间隔还短，
于是每一轮都判定"缓存过期"去重开设备，反而和读帧线程抢摄像头）。

但**线程活着 ≠ 在出帧**。读帧线程卡在 `capture.read()` 里、或者设备已经不吐新画面时，
线程仍然 alive，而它最后一次发布的帧会一直变老。于是观测循环每 30 秒拿到的是**同一份字节**。
证据就摆在观测事件里——相邻两次观测的人脸几何完全一致（`ParamAngleZ` 由量到的头部倾角
算出，不是被夹到上下限的常量，`ParamAngleX` 才是会饱和在 ±14 的那个）：

```
obs-45  ParamAngleZ=3.597  ParamBodyAngleZ=0.981  ParamMouthForm=0.0822
obs-46  ParamAngleZ=3.597  ParamBodyAngleZ=0.981  ParamMouthForm=0.0822   ← 126 秒后，一模一样
```

真实传感器带热噪声，两次不同的曝光不可能给出四位小数全同的结果。同一份 JPEG 被推理了两遍。

现在 `latest_for_inference()` 里的"活着"改成了**"刚刚还在出帧"**：健康的读帧线程每 50 毫秒
发布一次，所以给它 `MIYA_CAMERA_PUBLISH_GRACE`（默认 8 秒）的宽限；超过就说明它已经没有在
喂帧了，这一轮老实报告"没有拿到有效画面"，而不是拿旧画面当现在。

### 9. 卡住的读帧线程会一直占着设备

读帧线程只在两种情况下放手：连续 4 次全黑，或者异常退出。如果设备是"读得到但一直失败"
（`read()` 返回 False），它既不黑也不异常，线程就永远占着设备。现在加了两道：

- **停滞看门狗**：`MIYA_CAMERA_STALL_SECONDS`（默认 15 秒）内一帧都没发布出来，就
  `note_error` + 释放设备，让它可以被干净地重开；
- **冻结检测**：画面一直在到达、但**内容一模一样**超过 `MIYA_CAMERA_FROZEN_SECONDS`
  （默认 30 秒），判定为"虚拟摄像头或手机推流卡住"，按全黑同样处理（释放设备等待重试）。
  判据是每 16 像素抽样内容的精确指纹——真实传感器不可能逐字节重复，所以这个判定只会漏报、
  不会把活的画面误判成卡死。

### 10. 预览接口在和自己的读帧线程抢摄像头

`/api/vision/preview/{index}` 在缓存里没有 5 秒内的帧时，会**自己打开设备**再抓一帧。
而那个设备正被常驻读帧线程握着：一边读到全黑，另一边拿到
`Unknown C++ exception from OpenCV code`，然后两边轮流释放设备，永远循环。
前端面板每 3 秒刷新一次这个接口，等于把这场抢夺放大成常态。日志里那 45 分钟 30 次的
「连续 4 次全黑，释放设备」就是这个循环。

现在它只**请**一个读帧线程然后等它出帧（最多 8 秒），拿不到就老实返回 404
「这一路暂时没有画面」——这也正是这个接口自己的文档里写的原则：
"the backend already holds those devices, so it hands out a frame instead of
the page opening a second camera"。

## 第四轮修复：本地识别不准的根因（2026-09-29 下午）

现象（佳的原话）："摄像头的本地模型识别不准确"。现场记录印证了这一点——
`data/camera_vision_agent.json` 里 11 条印象，10 条写着「安静地待着 / 在电脑前安静待着」，
其中 8 条的 summary 还带着「嘴微张」，看起来像一张永远不变的标签贴在佳脸上。

**先排除掉的假设**（都实测过，不是猜）：模型没下载/没加载、每次调用重载模型导致超时降级、
颜色通道或归一化写错、只有弱模型、GPU 缺失。四个 ONNX 权重齐全、session 全部建成、
单帧 200–300ms、输入张量逐项对得上 catalog 和 ONNX 头。**模型侧是健康的。**

### 11. `_face_crop()` 把归一化坐标当像素用（致命，本轮主因）

`_detect_faces()` 的 docstring 写着"normalized [0,1] boxes"，返回值也确实是
`x / image.width`。但 `_face_crop()` 直接对它们取整：

```python
left, top = int(face["x"]), int(face["y"])          # 0.35 → 0
right, bottom = int(face["x"] + face["width"]), ...  # 0.65 → 0
padding = int(max(face["width"], face["height"]) * 0.12)   # 0.12 → 0
```

一颗 640×480 里的脸，框是 `{x:0.35, y:0.20, w:0.30, h:0.40}`，于是
`image.crop((0, 0, 0, 0))` —— **一个 0×0 的空图**，被喂给了身份模型和表情模型。

实测后果：SFace 收到的张量 `min = max = mean = -0.996`（常数），两个完全不同的画面给出
**逐位相同的特征向量**；FER+ 恒输出"中性 0.745"。也就是说：

- **身份**：任何人都得到同一个向量。若用它登记身份，黑图特征入库后**所有人都会匹配成功**
  （余弦相似度 ≈ 1.0，阈值只有 0.48）。当时身份库为空，所以只表现为"未登记"，没有暴露。
- **表情**：上一轮文档里"FER+ 永远同一个答案"的结论，**是这个 bug 的症状，不是模型的缺陷**。
  上一轮把 `_emotion_is_stuck()` 当成"防御正确的设计"，实际上它是在替一个 bug 打掩护。
- **暗区判据**：`_dark_fraction()` 对 0×0 直接返回 `None`，于是下半脸暗区这个
  "比标签可靠的线索"永久失效，只剩几何比值在硬撑——这就是"嘴微张"刷屏的来源。

现在 `_face_crop()` 走单一的换算入口 `_face_box_pixels()`：归一化值乘回真实像素尺寸，
盒子退化时 `raise ValueError` 而不是返回空图；调用方接到异常就记录 `face_crop_error`
并**跳过身份与表情**，绝不拿黑图凑数。

为什么这个 bug 能活这么久：所有走 `analyze_local_frame` 的单测都把 `_face_crop`
monkeypatch 成了恒等函数（`lambda image, _face: image`），CI 永远看不到它；
而文档里"实测过 FER+ 表情模型"的那次实测是**绕过裁剪直接喂模型**做的，
所以得出了错误的结论。现在这些打桩已删掉，换成真实的归一化框→像素回归测试，
并验证过：把 bug 放回去，这些测试会失败。

### 12. 自主观察路径拿不到时序，动作识别结构性退化

`classify_pose_action()` 的时序分支需要多帧（typing ≥3、wave ≥4、walk ≥5、nod ≥4），
但 `pose_history` 只有浏览器预览那条路会传。弥娅自己的自主观察循环
（`vision_agent._look`）每 30 秒调一次 `analyze_local_frame`，**从不传 history**，
于是那条最重要的链路上，时序动作在结构上**永远不可能触发**——只剩静态姿态。

现在多了一条共享的时序缓冲 `PoseSequenceBuffer`：常驻读帧线程本来就在以 ~20Hz 收帧，
让它按 `MIYA_CAMERA_POSE_SAMPLE_SECONDS`（默认 1 秒）把骨架采样进去，
`classify_pose_action` 在没有显式 history 时自动取用它。采样是自我节流的、
失败也绝不打断采集循环。查询用 `pose_sequence_status()`。

### 13. FER+ 标签顺序错位

`EMOTION_LABELS` 原为（中性、开心、**悲伤、惊讶、恐惧、厌恶**、愤怒、轻蔑），
FER+ 官方顺序是（中性、开心、**惊讶、悲伤、愤怒、厌恶**、恐惧、轻蔑）——
索引 2/3/4/6 语义互换，把惊讶说成悲伤、把愤怒说成恐惧。
上一轮的自测只出现过"开心"和"中性"，恰好两个位置都对，所以从未暴露。

标签已移入 `models/camera_vision/model_catalog.json`（符合项目"配置优先"原则），
代码只保留兜底常量。

### 14. YuNet 的关键点顺序被当成"左眼在前"

实测是 **(右眼, 左眼, 鼻尖, 右嘴角, 左嘴角)**，而代码解包成
`left_eye, right_eye, nose, left_mouth, right_mouth`。
眼距、嘴宽这类对称量不受影响，但 `atan2(right_eye.y - left_eye.y, ...)` 的**符号被翻转**，
于是"头向左歪"说反了，Live2D 的 `ParamAngleZ` 也是镜像的。
现已按真实顺序解包并显式注释方向定义；`ParamAngleZ` 的绝对正负取决于 Live2D 模型的
旋转约定，本层看不到，所以测试只钉住"两个相反方向不会映射成同一个值"。

### 15. 顺带修掉的两处效率与质量问题

- **每帧重建检测器**：`cv2.FaceDetectorYN.create()` 每次调用白耗 28–76ms，
  现在按 (尺寸, 阈值) 缓存并加锁复用。
- **身份特征缺少 5 点对齐**：SFace 上游要求 `alignCrop` 的相似变换，
  而代码只用了轴对齐矩形框。现在用 5 个关键点做相似变换对齐到 112×112，
  退化拟合会被拒绝并回退到矩形裁剪。

**仍然存在的限制**（不是 bug，是能力边界）：MoveNet 没有手部关键点，
所以"喝水"和"举手机"只能靠手相对肩/鼻的位置猜（代码里已诚实标注这个歧义）；
FER+ 训练于摆拍数据集，对真人细微表情泛化有限；OpenCV/dshow 采集这条路
在这台机器上仍不稳定（常驻读帧反复"全黑/15 秒没有画面"），实际图像主要来自浏览器预览推帧。

## 第五轮：纯本地的手部识别，和主动链路的三个确定性 bug（2026-09-29 下午）

### 16. 加了本地手部识别，补上"手里是什么"

佳要的是**纯本地的活动识别**，而现有的本地能力有一个明确缺口，代码自己写着：
`"A hand up near the face is either a phone or a cup; MoveNet cannot tell which"` ——
骨骼没有手部关键点，也没有任何物体信息，"喝水"和"看手机"在本地读到的是同一件事。

选型结论（详细对比见子代理报告）：**不给它加通用目标检测器**。反直觉但关键——
COCO 检测器在"被手握住的小物体"这一档最弱（NanoDet-Plus 官方 small 档 AP 只有 0.107，
cell phone mAP 22.8 / cup 23.7），而 640×480 画面里被手拿着的手机正好落在这一档，
还要付 20ms。改用两个 Apache-2.0 的 MediaPipe 权重：

| 权重 | 大小 | 作用 |
|------|------|------|
| `palm_detector.onnx` | 3.9 MB | 手掌检测（2016 个 SSD anchor） |
| `hand_landmark.onnx` | 4.1 MB | 21 点手部关键点 |
| `palm_anchors.json` | 33 KB | anchor 中心点表（结构不规则，随权重提供） |

**本机实测：整条手部链路 7-8ms**，比已经在跑的 YuNet 人脸检测（47ms）还便宜一个量级。
整轮 `analyze_local_frame` 实测 85ms（人脸 47.5 + 姿态 7 + 身份 14.7 + 表情 3.2 + 手部 7.4）。

`handpose.py` 是 OpenCV Zoo 官方 `mp_palmdet.py` / `mp_handpose.py` 的忠实移植，包括：
letterbox 预处理、anchor 解码、手部朝向归一化（按掌基→中指根旋转到竖直）、
以及把归一化坐标反变换回原图像素的整条链路。

**它只报它量得到的**：`handpose.describe_hand()` 给出的是与远近无关的相对量——
手指弯曲角度、伸直的手指、指尖伸展比例（相对于掌长）、拇指食指捏合比例、拇指外张比例。
**它不判断手里是什么**：关键点看不到物体，"手机还是杯子"交给弥娅自己解读——
这些数字会进 `build_interpreter_prompt`，让她结合手相对脸的位置来判断。
代码里再写一条"手腕高于肩膀所以是手机"的规则，就又是第五轮要修的那类假自信了。

> ⚠️ **未验证**：手部模型的**真实精度**没有实测过。我验证的是——链路通、耗时 7-8ms、
> 对噪声帧和真实无手画面正确返回 0 只手（阈值 0.8 下最高分只有 0.56）。
> 但"真实的手举到镜头前能不能检出、21 点准不准"需要真机验证：请把手举到摄像头前，
> 然后看 `/api/camera/sources` 或让她观察一次。合成的手和色块检测器不认，这符合预期
> （MediaPipe 手掌检测器训练于真实手掌）。

另外注意：**`*_int8bq.onnx` 量化版在 onnxruntime 1.20.1 上加载成功但推理直接抛异常**
（`block_size must be 0 for per-tensor quantization`），必须用 fp32 版。

### 17. 在场变化（transition）只活在单槽快照里

`presence.py` 的 `transition` 只存在于 `_snapshot`，而 `_snapshot` 每次 `evaluate()` 都被覆盖。
更糟的是 `/api/vision/presence` 这个**只读**端点调的是 `evaluate()` —— 桌面面板每 2.5 秒轮询它，
于是**面板自己的轮询在推进状态机、并且"吃掉"了每一次 transition**。
而真正要开口的两条路（bridge 每 20 秒、proactive poll 每 45 秒）都慢于它，
捕获概率只有 ~10% 量级。

日志印证：8 天只提交过 4 次 `camera:presence:returned`（其中只有 1 次真的发出去）。

修法：
- `PresenceTracker` 新增 `last_transition()`，记录状态机产出的**最近一次**变化及其时间戳，
  读取它既不消费也不推进状态机；
- bridge 改读它，并按时间戳去重；
- `/api/vision/presence` 改为只读 `snapshot()`（只读接口不该有副作用）。

### 18. `transition_key` 恒为 `returned:0`，每个进程只能发一次在场消息

```python
transition_key = f"{transition}:{round(float(snapshot.last_face_seconds or 0) // 60)}"
```

`last_face_seconds` 是"距上次看到脸多少秒"，而 `returned` 只在 `face_age ≤ 12s` 时产生
——两者相乘，key **恒等于 `"returned:0"`**。再加上 `_last_presence_key` 是在**投递之前**
写入的，于是**一次被协调器拒掉的问候，就把这条路径在整个进程生命周期内关掉了**。

现在 key 用变化发生的时间戳（`snapshot.updated_at`），与 bridge 同口径。

### 19. 提案阶段的记账被拒后不退（三类）

以前这些簿记发生在"提案"时，被拒时只退掉每日/每小时额度，其余全部保留：

- `_last_presence_key` → 见第 18 条；
- `_last_camera_event_key` **没有任何时间窗**，写一次就永久生效 → 同一类事件
  （比如"坐下"）在该进程内再也触发不了；
- `take_activity_change()` 在投递**之前**消费 → 观察被销毁且不重试；
- `_record_trigger_by_type("camera_aware")` 的 180 秒冷却被没发出去的消息占掉；
- `_record_sent_message` 进历史 → 内容去重让下一句相似的话在 30 分钟内被判重。

现在 `ProactiveResult` 多了两个对称的钩子：`rollback`（没发出去时撤销）和
`on_delivered`（发出去了才落定）。活动变化改成**先窥视、投递成功才消费**——
也就是 `_check_miya_vision_trigger` 一直在用的那个正确做法。

### 20. 摄像头的话记在错误的账本上

`hub/decision_hub.py` 的 `_proactive_send_callback` 没传 `source=`，于是**所有**摄像头的话
（presence / activity / 她自己的观察）都被记成 `proactive_chat`，和 AI 触发抢同一份配额，
而摄像头自己的事件走 `camera` 账本——两个账本互相看不见。
现在按 `trigger_type == "camera_aware"` 归到 `camera`。

### 21. 额度饥饿与全局锁（连带修的）

- **按来源小时配额**：`coordination.max_messages_per_source_per_hour`。
  地球online 每 45 分钟巡检一次、自检每半小时一条磁盘提醒，两边一起能把整池 8 条吃干净，
  弥娅看到的一切仍然说不出口。现在任何单一来源每小时的份额有上限。
- **同源更短的间隔**：`same_source_interval_seconds`。原先库存在比较"上一条消息"时，
  不管是谁发的都用全局 120 秒——于是摄像头的 `camera:voice` 一出去，
  摄像头自己的 `camera:presence:returned`（另一件更重要的事）就被顶掉两分钟。
  现在按"上一条是谁发的"取间隔：不同来源走全局值，同一来源走它自己更短的值。
- **AI 判定移出协调器锁**：`_decide_message` 是一次网络往返，原先它在
  `async with self._lock` 里面，一条慢回复会把**所有**来源的主动消息一起卡住。
  现在判定在锁外，额度领取（`_claim`）仍保持原子。

## 第六轮：佳贴出运行日志后查到的三件事（2026-09-29 下午）

上一轮的修改上线后，佳贴了一段真实运行日志。日志里有三条线索，其中第一条**是上一轮
我自己的修改引入的**。

### 22. 她自己的闲话把摄像头的事件配额吃光了（上一轮引入）

日志里同时出现：

```
[主动协调] 来源 camera 的小时配额已满，跳过 key=camera:voice:1523878699:7
[主动协调] 来源 camera 的小时配额已满，跳过 key=camera:voice:1523878699:8
[主动协调] 来源 camera 的小时配额已满，跳过 key=camera:voice:1523878699:9
[主动协调] 来源 camera 的小时配额已满，跳过 key=camera:voice:1523878699:11
[主动协调] 全局冷却中，跳过 key=camera:presence:returned
```

上一轮我把 `camera:voice`（她攒下的观察）和 `camera:presence`（在场变化）都归到
`source="camera"`，于是它们**共享同一份每小时 3 条的配额**。她观察得多，配额被她自己的
闲话用光，"佳刚回到电脑前"这种**每次真实回来只有一次**的事件就再也没机会。

根因是把两种根本不同的东西混在一起记账：

- **事件（event）**：tracker 产出的有界状态变化——他回来了、刚开始敲键盘、磁盘过阈值。
  一小时最多几次，每一次都值得考虑。
- **发言（voice）**：她决定要说的话——攒下的观察、灵魂冲动、聊天候选。她可以源源不断。

现在分账：`max_events_per_source_per_hour`（默认 4）与 `max_messages_per_source_per_hour`
（默认 3）各自独立。她的闲话再也挤不掉那一个真正重要的事件。

### 23. 被拒的观察消息，第二次轮询就被"去重"逻辑销毁了

`_check_miya_vision_trigger` 里原本是：

```python
if self._check_message_content_duplicate(target_id, message) or self._is_duplicate(target_id, message):
    agent.take_message()      # ← 把她攒下的话丢掉
    return None
...
delivered = await self._deliver_via_coordinator(...)   # ← 投递在检查之后
```

而 `_is_duplicate` **既有检查也有副作用**——它会把这句写进 `_message_cache`。于是一句
还没发出去的话，在投递之前就被打上了"已说过"的戳：

1. 第一次轮询：`_is_duplicate` 返回 False（同时写入缓存）→ 投递被拒（配额满）→
   消息**留在队列**；
2. 45 秒后第二次轮询：读到**同一条**消息 → `_is_duplicate` 命中缓存（
   `duplicate_window` 是 90 秒）→ 返回 True → `agent.take_message()` 把它销毁。

**效果是她攒下的每一句话，第一次尝试被拒之后就永久消失**，队列里永远不会有任何一条
被成功送出。日志里 `camera:voice:...:7/8/9/11` 序号一直在涨、却一条都没发出去，
就是这个循环。

现在拆开：检查那一侧保持只读（只查 `_sent_messages_history`，那里面记的是**真的发出去过**
的话），记录改由投递成功的路径显式调用 `_remember_message()`。与上一轮加的
`_forget_message_proposal()` 正好对称。

### 24. 同一条话重试时 key 每次都变

```python
self._vision_voice_seq += 1
key=f"camera:voice:{target_id}:{self._vision_voice_seq}"
```

每次尝试都换一个新 key，于是协调器的"同类事件冷却"对重试完全失效——能不能发出去
只取决于总配额还剩多少。现在用消息自己的时间戳（`earliest["at"]`）做标识：
同一条话重试时 key 稳定，不同的话天然不同。

### 25. 记忆字段名让协调器的 AI 误判"这一条已经说过了"

日志里 AI 判断连续 SKIP 掉在场事件，理由是它自己的推理：

```
记忆里有多次类似事件，说明这种"刚回来"的通知已经发过很多次了。按规则，
重复状态、没有实际价值时应回复 SKIP。
```

推理是合理的，但**依据是错的**。`build_presence_event` 用事件文本本身当检索词
（`recall_relevant("佳刚回到电脑前")`），检索回来的自然全是**以前的同类观察**，
然后以 `facts["记忆"]` 的名字交给 AI。

"她以前看到过他回来"被读成了"她以前已经通知过了"。这两个不是一回事。

字段现在改名为 `她记得的旧事（以前看到过，不代表这次已经说过）`。这只是让事实的
含义不被误读——**要不要开口仍然由她自己判断**，这一层没有替她做决定。

### 仍然待确认的两件事

**① 手部识别在真实手上的精度**（第五轮遗留）。链路、耗时、负样本行为都验证过了，
但真实手掌没测过。请把手举到摄像头前。

**② "嘴是张着的"是否误判**。日志里这个描述反复出现，而这行文字来自
`describe_expression`，由 `local_camera.expression_signals` 的几何比值驱动。
它可能是真的（伏案打盹时嘴微张很常见），也可能是**几何判据单独触发**：
文档早就写明"真正的开口证据是下半脸的暗区，几何比值只是弱信号"，而暗区判据在裁剪
较小时会返回 `None`，此时就只剩几何在硬撑。

这一条我**故意没有改**——没有真实帧的对照就调阈值，就是又一次"阈值 1.9 而真实上限
1.4"的错误。要诊断请查 `analyze_local_frame` 结果里 `observations[0].expression` 的
三个字段：`mouth_open_ratio`、`mouth_baseline_ratio`、`mouth_open_threshold`。
如果 `mouth_open_ratio` 长期贴着阈值、而 `lower_face_dark_ratio` 缺失，那就是误判，
该改的是"暗区不可用时不轻易下结论"，而不是继续调数字。


