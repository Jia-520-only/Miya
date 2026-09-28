# 本地摄像头模型契约

弥娅视觉的本地摄像头能力使用 `MIYA_CAMERA_MODEL_DIR` 指定模型目录；未设置时默认为项目根目录下的 `models/camera_vision/`。

当前模型目录中的文件名与输入输出契约见 `mcpserver/screen_vision/model_catalog.json`：

- `face_detector.onnx`：OpenCV Zoo YuNet 人脸检测
- `face_embedder.onnx`：OpenCV Zoo SFace 人脸特征提取，用于本地登记身份匹配
- `emotion_classifier.onnx`：ONNX Model Zoo FER+ 表情线索分类
- `pose_estimator.onnx`：MoveNet Lightning ONNX 姿态关键点

姿态模型上层还提供了一个无需额外权重的短时序动作层：在本地关键点序列上识别挥手、举手、鼓掌、坐下、起身、站立、坐着、走动、点头和身体移动。它是保守的几何/时序分类器，不会把动作标签当作意图或心理判断；无法确认时返回“未识别”或“姿态稳定”。

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
屏幕和摄像头联合“一起看”在 `local` 模式下也可用：它分别返回本地 OCR 与本地姿态/身份信号，
不会上传原图，但不会生成云端那种跨画面语义总结；`cloud`/`hybrid` 才会使用视觉模型做联合理解。

本地屏幕 OCR 依赖 PaddleOCR；桌面/完整依赖清单已包含 `setup/dependencies/ocr.txt`。轻量安装需要
手动执行该清单，首次使用时 PaddleX 会准备 OCR 模型。缺少依赖时，`look_screen` 在 `local` 模式
会明确返回安装提示，不会偷偷调用云端。

身份登记只写入 `MIYA_CAMERA_IDENTITY_DIR`（默认 `data/camera_identities/identities.json`）中的归一化 embedding、名称和时间；删除身份会重写该文件，不保存原始照片。

自主观察：桌面端首次需要用户点击并授权摄像头，然后执行 `/camera auto`。此后模型可调用 `request_camera_observation` 请求单帧观察；请求只传递文字结果，原始帧不会写入控制文件。`/camera off` 会同时撤销自主观察。

不打开前端时，可以在项目根目录执行一次终端观察：

```powershell
python scripts/camera_look.py "看看我在做什么"
```

终端采集默认只使用本地模型；需要云端视觉语义时显式追加 `--allow-cloud`。可用
`--camera-index 1` 选择第二个摄像头，采集完成后设备会立即释放，原始帧不会落盘。

即使身份和表情模型未安装，陪伴模式仍可使用浏览器端的低分辨率帧差基线。它只报告“稳定、轻微移动、明显动作、画面突变”，不声称识别了具体的人或动作。
