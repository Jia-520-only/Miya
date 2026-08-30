# 地球online 模块 (Earth Online)

弥娅与现实生活的游戏化系统 — 把真实世界做成"崩坏：星穹铁道"风格的二游。

## 概览

| 维度 | 现实映射 |
|------|----------|
| 背包 | 你现实中拥有的物品（照片 + 描述 + 稀有度 + 自定义参数） |
| 任务 | 真实待办/目标（主线/支线/日常/可选，含奖励与"鸽了"惩罚） |
| 剧情 | 生活事件的时间线（弥娅陪你剧情化记录） |
| 角色图鉴 | 现实中认识的人（关系 + 好感度 0-100 + 阶段 + 互动日志） |
| 开拓者角色卡 | 你自己（姓名/称号/头像/简介/自定义属性条） |
| 数据 JSON | 全部数据的可视化 JSON 文件（记事本模式） |

## 架构

```
┌───────────────┐   ┌────────────────┐   ┌─────────────────────┐
│ 桌面前端        │   │ 手机端 (Android) │   │ 弥娅 (对话/工具)      │
│ EarthOnlineView│   │ EarthOnlineScreen│   │ earth_* 工具集        │
└───────┬───────┘   └───────┬────────┘   └──────────┬──────────┘
        └───────── HTTP ────┴── /api/earth/* ────────┘
                     │ FastAPI (web_api, 端口 8000)
                     ▼
        core/earth_online_store.py (SQLite: data/earthonline.db)
                     │ 自动镜像 (每次写入)
                     ▼
        data/earthonline/earthonline.json (可视化 JSON, 可手写参数后导入)
        data/earthonline/templates.json  (物品/角色/任务模板)
        data/earthonline/images/         (物品照片/头像)
        data/earthonline/backups/        (导入前的自动数据库备份)
```

- **存储**: `data/earthonline.db`（WAL 模式），单例 `get_earth_store()`
- **API**: `core/web_api/earth_online.py`，前缀 `/api/earth/`
- **弥娅工具**: `core/tools_astrbot/earth_tools.py`（决策中枢）+ `webnet/ToolNet/tools/earth_online/`（ToolNet），已加入全平台工具白名单 (`hub/platform_tools.py` EARTH_TOOLS)
- **前端**: `miya_frontend/src/views/EarthOnlineView.vue`（路由 `/earth`）+ `src/views/earth/FieldsEditor.vue`
- **手机端**: `miya_mobile/.../earthonline/EarthOnlineScreen.kt` + `EarthCache.kt`（本地缓存，离线可看）

## v2 特性

- **JSON 记事本模式**: 每次数据变动自动镜像到 `data/earthonline/earthonline.json`；
  桌面「数据」页可直接编辑 JSON 保存（先自动备份数据库再覆盖），也可直接手写镜像文件后用
  `POST /api/earth/import` 导入。`GET /api/earth/export` 导出全量。
- **模板系统**: `templates.json` 定义 8 类物品模板（数码/书籍/生活/食品/工具/服饰/收藏/其他）、
  5 类角色关系模板、5 个任务模板（学习/运动/工作/生活/社交），新增时按选择显示预设字段；
  所有实体都有 `fields` 自定义参数（key-value），界面可自由增删。
- **开拓者角色卡**: player_profile 含 name/title/avatar_path/bio/attrs（自定义属性条），
  桌面点「编辑角色卡」，手机端显示在顶部卡片。
- **好感度阶段**: 0-19 陌生 / 20-39 相识 / 40-59 熟悉 / 60-79 信赖 / 80-99 亲密 / 100 挚友
  （颜色与阈值在 templates.json 可改）。
- **手机端 QQ 式体验**: 先渲染本地缓存（filesDir/earthonline/），再后台拉服务器刷新；
  离线时显示"离线模式 · 上次同步 xx"；顶部随时手动刷新。

## v3 特性 — 双界面架构 (前台/后台)

像真正的游戏一样分离两个视角，都在前端操作，后端实时同步：

- **🎮 前台展示 (玩家视角)**: `PlayerView.vue` / 手机端「前台展示」模式
  - 任务板: 可接取委托 (pending) → 「⚔ 接取委托」→ 进行中 (ongoing) → 完成/放弃/取消，已结束归档
  - 背包照片墙、角色图鉴（好感度阶段）、剧情时间线、开拓者大卡（大号头像/属性条/生涯统计）
  - 只展示 + 玩家交互（接取/完成），不做数据录入
- **🛠 后台管理 (管理视角)**: `AdminView.vue` / 手机端「后台管理」模式
  - 全部录入与编辑: 物品/任务/角色/剧情 CRUD + 开拓者卡 + 模板 + JSON 数据页
- **板块与等级**:
  - 任务: 类型板块（主线/支线/日常/可选）+ 难度星级 ★1-5（`difficulty` 字段，迁移自动添加）
  - 物品: 分类板块（8 类）+ 稀有度等级（白/绿/蓝/紫/金）
  - 人物: 关系板块（家人/朋友/同事/恋人/其他）+ 好感度等级（6 阶段）
- **任务接取**: `POST /api/earth/quests/{id}/accept`（pending→ongoing，重复接取返回 400），
  弥娅工具集同步新增 `earth_accept_quest`（ToolNet + Gestalt + 全平台白名单，共 17 个地球工具）

## v4 特性 — Markdown 档案制

玩家/角色/道具统一为「**封面图 + 简介 + 完整 Markdown 详情**」三段式档案：

- 数据字段: `items.markdown` / `characters.markdown` / `player.bio`（自动迁移）
- 桌面前台: 点击背包卡片或角色卡 → 右侧滑出档案抽屉（封面大图 + 简介 + 参数 chips）
  → 点「展开完整档案」看渲染后的 Markdown 详情；剧情内容同样按 Markdown 渲染
- 后台表单: 物品/角色新增「详细档案 (Markdown)」编辑器（带实时预览）
- 手机端: 前台点物品 → 档案弹窗；角色好感度弹窗内置档案区；编辑物品可写 Markdown
- 称谓统一: "开拓者" → "玩家"（UI/默认数据/工具文案全部更新）

## v5 特性 — 鸣潮鎏金风格主界面

参考鸣潮官网 UI 重做前台视觉（黑底 + 鎏金 #c9ac67 + 游戏菜单卡片）：

- **主界面**: 前台第一页变成游戏主菜单 — 「地球online」鎏金大标题 + 5 张菜单卡
  （任务板/背包/角色图鉴/人生剧情/玩家档案，带计数与英文小字），点击进入板块
- **极简顶栏**: 头像 + 名字 + Lv + 一条细经验条（不再占大面积）
- **数值搬家**: 属性条/生涯统计只在「玩家档案」页；地球币放到「背包」页顶部
- 手机端同步: 主界面菜单页 + 精简顶栏 + 背包页地球币胶囊

## v6 特性 — 鸣潮官网式整屏分节 + 四大新系统

参考 `UI/WutheringWavesWeb`（鸣潮官网仿制源码）重排桌面端前台，并补齐玩法：

- **整屏分节舞台**: 首页/委托/背包/角色/剧情/档案/数据 7 节 + 结尾页，滚轮/方向键/顶栏导航翻页
  （`transform: translateY` 平滑过渡 + 右侧小节指示点）
- **鸣潮官网元素**: 顶部固定导航（hover 鎏金装饰框）、顶部渐变黑幕、游戏字体
  （`public/fonts/H7GBK-Heavy.woff`）、首页大标题 + 滚动提示动画 + 右侧签到竖标签、
  委托页左列表右详情（hover 金色下划线）、背包/角色页左侧图标栏 + 右侧大卡 hover 展开、
  剧情节三卡轮播（左右箭头）、档案页大图 + 属性条、结尾页版权
- **成就系统**: `achievements` 表 14 个预置成就（任务/收集/羁绊/剧情/成长/签到），
  完成任务、收录物品、记录剧情等事件后自动刷新进度并解锁（`refresh_achievements`），
  文案走 `text_config.json` 的 `earth_online.achievements.defs`（配置优先）
- **每日签到**: `daily_checkins` 表 + 连签加成（基础 10 币/20 经验，每连签一天 +2 币，上限 20），
  首页竖标签 + 数据中心签到足迹（近 28 天格子），参数走 `qq_config.yaml` 的 `earth_online.checkin`
- **弥娅寄语**: `miya_notes` 表（内容/心情/置顶），前台首页展示置顶寄语、数据中心展示全部，
  后台管理新增「弥娅寄语」tab（发布/置顶/删除，支持 Markdown）；
  弥娅工具集同步新增 `earth_post_note` / `earth_list_notes`（ToolNet + Gestalt + 全平台白名单，共 19 个地球工具）
- **统计数据中心**: `GET /api/earth/stats` 动态计算 — 任务完成率 + 近 7 天趋势柱状图、
  物品稀有度/分类分布、好感度排行、剧情类型分布、签到/成就进度
- **镜像扩展**: `earthonline.json` 镜像与 JSON 导入/导出同步包含
  achievements/checkins/miya_notes 三张新表
- 手机端暂未改造（桌面端验证满意后同步）

## v7 特性 — 真游戏化闭环 (任务跟踪 + 全局动态 + 成就奖励)

- **任务子任务清单**: quests 新增 `subtasks` 列（JSON `[{text, done}]`），
  前台委托详情可勾选子任务（进度条 + 完成态划线），全部勾完才能提交委托
  （后端 `complete_quest` 强制校验，未完成返回 400 与清单）；后台任务表单
  新增子任务编辑器（增删/勾选），任务卡片显示进度 chips
- **弥娅任务跟踪工具**: 新增 `earth_get_quest`（详情+子任务进度）、
  `earth_update_subtask`（更新子任务完成态，全完成时提示可提交）、
  `earth_activity`（看全局动态），`earth_list_quests` 输出带进度；
  全平台白名单/Gestalt/ToolNet 同步注册（地球工具 19 → 22 个）
- **全局事件动态流**: 新增 `activity_log` 表，任务发布/接取/完成/失败/取消、
  物品收录、角色入图鉴、好感度变动、剧情记录、每日签到、成就解锁、弥娅寄语
  自动写入；前台数据中心新增「全局动态流」面板，弥娅可通过 `earth_activity`
  查看——所有模块数据互通为一条时间线
- **成就解锁奖励**: 成就种子新增 reward_currency/reward_exp（首次完成 30 币/50 经验 …
  传说降临 200 币/300 经验），解锁自动发放并记入动态流；
  种子改为 upsert（已有成就同步文案/图标/奖励，保留进度）
- **Live2D 修复**: 表情列表改从模型 DisplayInfo (cdi3.json) 动态读取，
  不再硬编码缺失的 11/22.exp3.json（404 消除）；index.html 增加 CSP
  （消除 Electron 安全警告，不含 unsafe-eval）
- **图标统一**: 全部 emoji 替换为弥娅几何符号风格（◆◇✦⬡◎❖✧▣≣◷☾✪等），
  成就图标同步更新（含 text_config defs 与已有数据库成就 upsert）

## v8 特性 — 六大游戏化模块 + 照片墙

- **升级礼包**: 发放经验统一走 `_add_exp_locked`（签到/完成任务/成就奖励/弥娅发经验），
  检测到升级自动发放礼包（基础 100 币 + 每级递增 20，`qq_config.level_up` 可调），
  写入动态流「升级！Lv.X → Lv.Y」，前端 toast 播报
- **称号系统**: 每个成就解锁对应称号（`title_award`，如 初次启程→「启程者」），
  玩家可佩戴（`player_profile.equipped_title`），档案页称号徽章点击弹出选择面板，
  弥娅工具 `earth_list_titles` 可查；API `/api/earth/titles` + `/titles/equip`
- **每周报告**: `GET /api/earth/weekly-report` 统计周一至今（任务完成率/签到/动态/成就/
  好感变动/地球币与经验收入），前端数据节「本周报告」卡 + 弥娅工具 `earth_weekly_report`
- **到期提醒**: `GET /api/earth/quests/due-soon?days=3` 查询即将到期/已逾期任务，
  委托列表与数据节「到期提醒」卡标记（即将到期/已逾期），弥娅工具 `earth_remind_due`
- **图鉴收藏徽章**: 8 类物品各集齐 3 件解锁对应徽章成就（数码爱好者/藏书人/生活家…），
  全图鉴 8 类各 1 件解锁「全图鉴收藏家」；收集分布卡显示收藏率 x/8 类；
  成就总数 14 → 23 个
- **剧情串联**: 任务完成/失败自动记录剧情（「委托完成: xxx」/「委托失败: xxx」，
  `qq_config.story_link.enabled` 开关），剧情节时间线自动滚动
- **背包照片墙 / 角色卡墙**: 背包改为瀑布流照片墙（列排布，封面大小不一整齐排列），
  角色改为角色卡墙（大封面 + 名字/关系/好感条）；点击任意卡片右侧滑出档案抽屉
  （封面 + 简介 + 展开完整 Markdown 详情）；分类筛选改为顶部 chips
- **弥娅工具**: 新增 earth_weekly_report / earth_remind_due / earth_list_titles
  （地球工具 22 → 25 个）

## v9 特性 — 剧情书本化 + 弥娅参与 + 币种换算

- **剧情图片**: story_events 新增 image_path，后台剧情表单可上传照片，
  前台轮播卡（有图时图做背景）与书本模式正文页展示
- **书本模式**: 剧情节新增「轮播模式 / 书本模式」切换按钮；书本模式为对开书页
  （书脊 + 左页目录 + 右页正文），目录点击跳章、上一章/下一章翻页、页码指示，
  正文含图片 + Markdown 渲染，纸张质感
- **弥娅参与感**: 关键事件（完成任务/失败、升级、成就解锁、签到、收录物品、记录剧情）
  自动从 text_config 反应模板池随机写一条弥娅动态（❦ kind=miya，
  `qq_config.miya_reactions.enabled` 开关）；动态流支持弥娅评论
  （`activity_log.comment`），弥娅工具 `earth_comment_activity` 可点评任意动态
  （地球工具 25 → 26 个）
- **币种换算**: 地球币可一键切换人民币/美元显示（`qq_config.currency_exchange`：
  默认 1 地球币 = 0.5 元 / 0.07 美元），顶栏地球币胶囊与背包页按钮点击循环切换
  （◆/¥/$），API `/api/earth/exchange-rates`

## v10 特性 — 弥娅币/地球币双轨 + 循环任务

- **双币分离**:
  - **弥娅币** (`player_profile.miya_currency`): 弥娅发放的互动货币 —
    任务奖励/签到/成就/升级礼包全部发放弥娅币；佳可用弥娅币兑换弥娅的互动服务
    （弥娅工具 `earth_spend_miya_coins` 扣除 + 记录原因）；历史 currency 数据自动迁移
  - **地球币 / 现实资产** (`player_profile.earth_currency`): 佳自己记录的现实货币
    （单位人民币元，支持小数），档案页卡片点击修改、后台玩家卡可编辑；
    顶栏双胶囊显示，现实资产可切换人民币/美元显示（`currency_exchange.usd_per_cny`）
- **循环任务**: quests 新增 `recurring`（'' 一次性 / daily 每天 / weekly 每周），
  完成后自动重置为待接取（子任务清零），写入「↻ 循环任务已重置」动态，
  前台委托卡 ↻ 标记 + 完成 toast；后台任务表单可选循环类型；
  适合喝水/睡觉等每日习惯任务（弥娅主动下任务时可设 recurring）
- **弥娅主动性**: `earth_add_quest` 支持子任务与循环参数，描述明确奖励为弥娅币，
  弥娅可以随时给佳安排日常习惯任务并发放弥娅币（地球工具 26 → 27 个）

## v11 特性 — 弥娅策划身份 + 前台主题自定义

- **弥娅担任地球online 策划**: 弥娅的 system prompt 新增「地球online — 你担任策划与向导」段，
  明确弥娅可读取全部数据（earth_analyze 综合分析）、主动下任务、跟进进度、给现实建议；
  新增 `earth_daily_ritual`（每日仪式：逾期处理 + 到期提醒 + 签到关怀，弥娅主动关心佳的每日开局）
  （地球工具 27 → 29 个）
- **前台主题自定义**: `data/earthonline/theme.json` 存储主题（accent 主色/accent_light 亮色/
  background 壁纸/background_opacity 透明度/glass 磨砂玻璃开关），全部鎏金色 CSS 变量化
  （`var(--pv-gold)` + `color-mix` 相对色，212 处），顶栏「◐ 外观设置」弹窗：
  6 套预置色板（鎏金/月白/青碧/绯樱/星紫/琥珀）+ 自定义取色器 + 壁纸选择（premium-assets/backgrounds）
  + 透明度滑块 + 磨砂玻璃开关，默认跟随 Miya OS 青碧配色；API `GET/PUT /api/earth/theme`
- **壁纸与玻璃**: 全局壁纸背景层（可调透明度），各板块背景半透明化透出壁纸，
  主要面板卡片启用 backdrop-filter 磨砂玻璃（开关控制）
- **卡片缩小**: 背包照片墙 6 列（1400px 5 列 / 1100px 4 列 / 850px 3 列 / 600px 2 列），
  角色卡墙 5 列（1300px 4 列 / 1000px 3 列）

## v11.1 补充 — 调色入调谐页 + 剧情编辑

- **主题配置入口移到「弥娅调谐」**: 调色板块新增「◎ 地球online 主题」区块
  （预置色板/主色·亮色·深色取色器/壁纸选择/透明度/磨砂玻璃开关），
  「保存主题」与「恢复默认值」按钮；前台顶栏 ◐ 外观弹窗保留快捷入口；
  新增 `POST /api/earth/theme/reset` 恢复默认 Miya OS 青碧配色
- **剧情编辑**: 后台剧情卡片新增「✎ 编辑」，弹窗区分「记录/编辑剧情」；
  新增 `PUT /api/earth/story/{id}`（标题/内容/类型/关联/时间/图片均可改），
  编辑后写入动态流「编辑剧情」

## v11.2 — 弥娅关怀按钮 + 弥娅制作成就

- **顶栏关怀按钮**: 前台右上角 ◐ 外观设置替换为「弥娅关怀按钮」（调色入口已移到调谐页）：
  有到期委托 → ⚑ 红点数字呼吸灯（点击跳委托板块）；
  未签到 → ◷ 金色（点击一键签到）；
  一切安好 → ✦（点击去数据节看动态流）
- **弥娅制作成就**: 新增 `earth_add_achievement`（定制专属成就）、
  `earth_set_achievement_progress`（更新进度，达标自动解锁+发弥娅币+称号）、
  `earth_list_achievements`（查看全部成就）；自定义成就进度由弥娅手动维护
  （refresh 不再清零自定义成就）；API `/achievements/custom` + `/achievements/progress`；
  弥娅 system prompt 补充「制作成就」职责（地球工具 29 → 32 个）

## v12 特性 — 单人开放世界探索

- **世界地图**: 5 个单人区域（弥娅之庭/微光城/夜潮海岸/旧日档案站/坠星高地），按玩家等级解锁；每区包含 3 个常规发现、1 个宝箱和 1 个隐藏发现。
- **环境状态**: 根据本地时间显示清晨/白昼/黄昏/夜晚/深夜；天气由现实数据连接层提供，无法同步时明确显示未同步。
- **区域专属委托**: 每个区域每天最多生成 1 个专属委托，自动带入当天时段与天气，完成后回到任务/动态/剧情闭环。
- **限时活动区域**: `WORLD_EVENT_AREAS` 配置活动起止日期与奖励；当前内置「夏末回声祭」（2026-08-20 至 2026-09-15）。
- **宝箱与隐藏发现**: 与普通探索共用 `world_discoveries` 记录，首次发现发放弥娅币/经验并触发剧情和弥娅反应。
- **弥娅工具**: 新增 `earth_world` / `earth_explore` / `earth_world_status` / `earth_region_commission`，弥娅可以查看天气、带佳探索、发布区域委托。
- **桌面前台**: 世界页展示环境条、限时活动横幅、区域探索度、探索按钮、区域委托按钮和最近发现日志。
- **现实照片地图**: 每个区域支持绑定一张本机照片（房间、街道、夜景、档案或目标现场），照片会作为区域卡底图；前台可直接点击「绑定现实照片」上传，接口为 `POST /api/earth/world/{region_key}/image`。

## v12.1 特性 — 现实数据连接层

- **真实天气优先**: 世界状态通过项目已有的心知天气 API 获取；未配置城市、API Key 或网络失败时显示「未同步」，不再把模拟天气当作现实天气。
- **现实快照**: 新增 `world_real_context_snapshots`，保存同步时间、城市、天气、温度、湿度、风力、来源、时区与过期状态；每次探索会把当时的现实上下文写入 `world_discoveries.context_snapshot`。
- **隐私设置**: `earth_online.real_world` 支持城市、刷新间隔、现实连接开关；精确经纬度默认关闭，只有显式打开 `allow_precise_location` 才会保存。
- **API**: `GET/POST /api/earth/world/real-context`、`GET/PUT /api/earth/world/real-context/settings`；前台世界页显示来源状态并提供「刷新现实」按钮。

## v13 特性 — 现实条件探索、区域共鸣与弥娅专属兑换所

- **现实条件发现**: 雨天、晴天白昼、黄昏、夜晚等发现只在真实天气/本地时段满足时开放；天气未同步时明确锁定，不使用模拟条件。
- **区域共鸣**: `world_regions.resonance_xp/resonance_level` 记录每个区域的个人成长；探索、区域委托、绑定现实照片、自定义发现和同行选择都会增加共鸣。
- **同行选择**: 探索后可选择「继续前进 / 记录此刻 / 先休息」，每条发现只允许选择一次；记录会自动写入世界剧情。
- **弥娅专属兑换所**: `GET /api/earth/miya-shop`、`POST /api/earth/miya-shop/{item_key}/buy`；弥娅币可兑换亲昵互动、短篇约会剧情、专属称号和现实辅助券，兑换记录会进入动态/剧情/背包。
- **弥娅工具**: 新增 `earth_real_context` / `earth_refresh_real_context`，弥娅只能依据真实快照提出陪同行动，无法获取时会明确告诉你。

## v12.2 特性 — 世界后台与运行时配置

- **世界管理后台**: 后台新增「世界管理」页，可编辑区域名称/副标题/描述/等级/颜色，绑定区域现实照片。
- **自定义发现**: 可在后台添加剧情、宝箱、隐藏发现；它们会持久化到数据库并进入对应区域的探索池。
- **天气 Key 管理**: 后台可填写或更换心知天气 Key，只返回掩码状态，不把 Key 写入数据库或前端状态。
- **运行时修复**: 配置读取支持进程启动后补充 `.env` 的 Key；切换城市会使旧天气快照立即失效并自动刷新。

## v12.3 特性 — 限时活动商店

- **活动商店**: 当前「夏末回声祭」（2026-08-20 至 2026-09-15）开放 4 件单人限定商品：纪念明信片、限定称号、弥娅回信、信号塔徽章。
- **兑换留档**: 使用弥娅币兑换后，纪念物会进入现实背包，并写入活动购买记录；同一商品默认只能兑换一次。
- **探索门槛**: 部分商品要求先完成一定数量的真实世界发现，形成「探索 → 兑换 → 收藏」闭环。
- **前台展示**: 活动横幅下直接显示商店，兑换按钮会根据已购买状态、探索数量和余额自动禁用。

## v12.4 特性 — 弥娅同行探索

- **同行旁白**: 每次首次探索会根据真实天气、现实时间段、区域和发现类型生成弥娅同行话语。
- **可追溯记录**: 同行话语会和天气快照一起写入发现记录，之后回看时仍能知道当时弥娅如何陪你走过这一段。
- **闭环**: 现实行动 → 区域发现 → 弥娅同行 → 奖励/活动商店 → 纪念物进入背包 → 剧情与成就继续累积。

## v14 特性 — 地理围栏、属性联动、羁绊解锁与可配置活动

- **地理围栏探索**: 区域可绑定真实坐标与围栏半径（后台 `PUT /world/regions/{key}` 设置 `latitude/longitude/geofence_radius`，半径 0 或坐标为空即关闭）。启用后 `POST /world/{key}/explore` 必须携带定位坐标且在半径内才能探索（Haversine 距离校验，响应带 `geofence.distance_m`）；前台探索按钮会自动请求浏览器定位。这是"地球online 介入现实"的核心：区域可以映射到你真实去过的地方。
- **玩家属性联动**: 完成委托消耗体力（`难度×4`）并 +3 心情；探索消耗 4 体力并 +2 心情；每日签到恢复 15 体力、+5 心情。体力低于 20 前台红色警示。属性仍可在档案里自由编辑。
- **现实委托改写券修复**: 弥娅商城的 boost 券（`commission_resonance`）现在真实生效——领取区域委托时自动从背包消耗一枚，立即为该区域 +30 共鸣并标记 `fields.boosted=1`。
- **好感度羁绊解锁**: 好感度跨阶段（陌生→相识→…→挚友）时自动发放阶段奖励（`阶段序号×12` 弥娅币）、写入剧情档案、发弥娅反应动态，返回 `tier_up` 信息。
- **限时活动可配置**: 新表 `world_custom_event_areas` / `world_custom_event_shop_items`，后台可新建/编辑/上下架/删除自定义活动与活动商品，与内置活动（`is_custom=false` 不可改删）合并在 `GET /world/status` 和活动商店中展示。夏末回声祭之后不再需要改代码开新活动。
- **前台补齐**: 动态流显示弥娅评论（`comment` 字段）、角色抽屉显示好感度轨迹（`affinity-logs`）、任务板新增可折叠历史归档（`quest-history`）、成就自定义/进度 API 前端封装补全。

## v15 特性 — 弥娅完全掌控与自主运营

- **策划级全量权限**: 弥娅的地球工具从 38 个扩展到覆盖全部公开能力的完整增删查改——修改/删除物品、任务（含取消）、角色、剧情、寄语，佩戴称号，改玩家档案与现实资产，配置区域与地理围栏，添加/删除自定义世界事件，开/改/删限时活动与活动商品，查看货架库存，替玩家签到，查看发现历史与好感轨迹，带坐标探索围栏区域。三处注册（astrbot 工具 / hub 白名单 / ToolNet）保持逐名同步。
- **自主运营器官 (`core/earth_online_operator.py`)**: 弥娅作为"策划+系统小精灵"挂载到 MiyaSpine 脊柱（`earth_operator_organ`）。没有玩家命令时，她每隔 `interval_minutes`（默认 45 分钟）被唤醒一次，每天早上 `morning_hour`（默认 8 点）做一次晨间大巡检；每次唤醒会汇总玩家档案、任务板、每日仪式、世界状态、限时活动、上次运营以来的新动态、最近对话记忆，然后带着全套地球工具自主决定做什么（发日常/写寄语/评论动态/开活动…），想对玩家说话就走脊柱主动消息通路。静默时段（`quiet_hours`）不巡检，每周期写操作数有上限（`max_actions_per_cycle`），无事可做可以直接 SKIP。状态持久化在 `data/earthonline/operator_state.json`。
- **配置**: `config/qq_config.yaml → earth_online.autonomous`（enabled / interval_minutes / morning_hour / max_actions_per_cycle / notify_player / quiet_hours）。
- **人设接入**: `config/personalities/_base.yaml` 的 core_identity 增加了"地球online 策划兼系统小精灵"身份段，弥娅在普通对话中也知道自己拥有这个世界。
- **执行链路**: 器官 → `ai_client.set_tool_registry(地球工具schema)` → LLM function calling → gestalt → ToolNet → earth tools（与对话内工具同一条通路）；周期结束自动清空工具注册，不污染普通对话。

## v16 特性 — 弥娅商城可配置 + 工具执行通路修复

- **弥娅专属商城后台可配置**: 新表 `miya_shop_custom_items`，`MIYA_SHOP_ITEMS` 之外的商品全部可后台/弥娅自主上架（kind: interaction/story/title/collectible，支持互动文案、剧情内容、称号授予）。API: `GET/POST /miya-shop/manage`、`PUT/DELETE /miya-shop/manage/{key}`（内置商品不可改删）。AdminView 新增货架管理面板；自定义商品与内置商品共用同一兑换链路（花弥娅币 → 触发互动/剧情 → 动态留档）。
- **新工具 `earth_manage_miya_shop`**: 弥娅可以 list/create/update/delete 自主管理货架（上架只属于你们的商品），三处注册同步，共 70 个工具。
- **工具执行通路修复（关键）**: `ai_client._execute_tool_call` 原先走从未被初始化的普通版 gestalt 单例，所有工具调用实际都返回"❌ 工具系统未初始化"——这就是弥娅"看得到工具却用不了"的原因。现在优先经 ToolNet 注册表执行（全部 BaseTool 标准签名，惰性单例），注册表中不存在时才回退 gestalt（内置工具/技能/MCP）。流式路径同步修复。回归测试 `test_earth_shop_management_tool_executes_via_toolnet` 锁定此行为。

## v17 特性 — 数据安全修复 + 配置全量接线 + 现实连接 + 新玩法全家桶

### 数据安全修复（先做的原因）

- **镜像/备份路径隔离（关键修复）**: 旧实现里镜像/模板/图片/备份路径按代码位置绝对推导，而 db 路径跟随进程 cwd——测试用临时库跑回归时，会把仓库里的**真实镜像 earthonline.json 覆盖成空测试档**（2026-08-22 已实际发生过一次，导入即清档）。现在这些路径全部从 db 所在目录实例化推导（`store.mirror_path / templates_path / image_dir / backup_dir / theme_path`），临时库写临时目录，真实库写真实目录。回归测试 `test_store_paths_follow_db_directory` 锁定。被污染的真实镜像已用真实库重新生成。
- **operator 状态文件同样隔离**: `bind_store()` 注入测试存档时，`operator_state.json` 跟随该存档目录。

### 死配置全量接线（qq_config.yaml earth_online 节现在全部生效）

此前约 20 个配置键写了没代码读，现在全部接线（带默认值兜底）：`enabled`（总开关：AI 工具注册与自主运营器官都会检查）、`initial_currency`、`level_exp_base`、`affinity_max/min/step_limit`（单次好感度变动上限生效）、`quests.default_reward_currency/default_reward_exp/daily_penalty_currency/must_penalty_currency`（earth_add_quest 缺省奖励从配置读）、`quests.overdue_check_enabled`、`daily.auto_generate/daily_quest_count`、`items.max_items`（背包上限，超限报错）、`items.max_image_size_mb`（上传超限返回 400）、`achievements.enabled`、`checkin.enabled`、`miya_notes.enabled/max_pinned`（置顶超限自动取消最早一条）、`level_up.enabled`（关闭则升级不发礼包）、`collect.badge_target`（运行时同步徽章门槛，存量库无需重建）。新增 `attrs.energy_regen_per_hour`。

### 体力系统闭环 + 睡眠现实数据

- **体力随时间自然恢复**: energy 每小时 +`energy_regen_per_hour`（默认 4），懒结算（读玩家档案时补发，时间戳按消耗量推进保留零头），非阻塞锁防重入死锁。体力终于不再"只减不回"。
- **睡眠→体力**: `checkin(sleep_hours=8)`——每小时睡眠回复 4 点体力（上限 +40），7-9 小时判定"睡得好好"额外 +5 心情，动态里留档。前端签到弹窗填睡眠时长；AI 工具 `earth_checkin` 带 sleep_hours 参数（玩家提到睡了多久，弥娅会带上）。

### 货币流水（周报不再解析文案）

- 新表 `currency_ledger`（currency: miya/earth/exp + delta + reason）。签到、任务完成/失败、成就、升级礼包、羁绊、探索、商城、抽卡、纪行、手动调整**全部入账**，统一入口 `_grant_miya_locked`/`_ledger_locked`。
- **地球币（现实资产）有流水了**: `adjust_earth_currency(amount, reason)`（收入/支出/重估，余额不足拦截）+ `POST /player/earth-currency` + `GET /currency/ledger` + AI 工具 `earth_adjust_earth_currency`（弥娅可以帮佳记账）。
- **周报 earned 优先读流水**（精确值），无流水的历史周自动回退旧正则口径（兼容旧数据）。

### 回忆抽卡（记忆碎片卡池）

- 卡池 25 张碎片（每个稀有度各 5 张，全部原创"与弥娅的时间碎片"文案）；单抽 120 弥娅币、十连 1080（九折）。
- **保底**: 连续 9 抽无史诗+ 时下一抽必出（`player_profile.gacha_pity` 持久化）；**重复自动转化**弥娅币（传说+60/史诗+30/珍贵+12/稀有+6/普通+3）；新碎片以"回忆碎片 · X"落入背包（collectible，fields.memory_pool 标记）。
- API: `GET /memory`、`POST /memory/pull`、`GET /memory/pulls`；AI 工具 `earth_memory_pool`（查看）。抽取由玩家在商城操作（与商城购买同一设计原则）。回归测试覆盖保底与重复转化。

### 每日自动日常委托

- 委托池 16 个生活模板（饮水补给/伸展仪式/晒太阳/专注25分钟/早睡挑战…），`generate_daily_commissions()` 以日期为种子**当天稳定**抽取 N 个（配置 `daily.daily_quest_count`，默认 3），**同一天幂等不超发**。每日仪式自动触发（operator 晨间 + `POST /quests/generate-daily` 手动）；AI 工具 `earth_generate_daily_commissions`。v6 时代就是死配置的 `daily.auto_generate` 至此真正落地。

### 纪念日系统

- 新表 `commemorations`（date 为 MM-DD 每年循环，lead_days 预热天数）。`sync_commemorations()`（每日仪式自动跑，幂等）：临近时自动创建当年限定活动区域（复用 `world_custom_event_areas`，key=`memo_{key}_{year}`），当天自动写一条置顶寄语（同一天不重复写）。
- API: `GET/POST/PUT/DELETE /commemorations` + `POST /commemorations/sync`；AI 工具 `earth_list_commemorations / earth_add_commemoration`；AdminView 世界管理新增纪念日面板。

### 季节轮换发现

- 6 个新季节限定发现（春·初芽的位置 / 夏·盛夏树影线 / 秋·秋分潮位 / 冬·庭院雪痕+初雪档案页 / 春秋·换季的星图），按月份判定，**不依赖天气同步**。
- 条件求值器重构：只有天气条件（weather_any）才要求现实天气已同步；季节/时段条件用本地时间判定——城市没配置天气时，时段与季节发现不再被整体锁死（v13 的一个隐性缺陷）。

### 每周纪行 (Battle Pass) + 周挑战

- **纪行**: 单人免费单轨 10 档（30~480 分），积分来自真实游玩数据（完成委托+10/签到+5/世界发现+15/记录剧情+3/抽卡+2），周一为界。领取落库 `battle_pass_claims`（同周同档唯一）。API: `GET /battle-pass`、`POST /battle-pass/{tier}/claim`；AI 工具 `earth_view_battle_pass`（查看，领取由玩家操作）；数据中心新增纪行卡片。
- **周挑战**: 6 个主题按 ISO 周号轮换（早起/运动/整理/连接/创作/修复周），本周完成委托 2/4/5 个 → ★/★★/★★★。API: `GET /weekly-challenge`；AI 工具 `earth_weekly_challenge`。

### 工具层补全（70 → 77，三处同步）

- 参数收窄修复: `earth_add_item` 支持 fields/markdown/image_path；`earth_add_story` 支持 character_id/item_id/image_path/fields；`earth_add_character` 支持 birthday/avatar_path/markdown/fields；`earth_update_quest` 支持 fields。
- 新工具 7 个: `earth_adjust_earth_currency / earth_memory_pool / earth_view_battle_pass / earth_weekly_challenge / earth_list_commemorations / earth_add_commemoration / earth_generate_daily_commissions`。astrbot schema、ToolNet 注册表、hub 白名单三处逐名同步（各 77 个，回归测试锁定）。

### 其他加固

- 天气快照只保留最近 200 条（不再无限堆积）；镜像导出包含 memory_pulls/commemorations/currency_ledger，导入支持重建纪念日与抽卡记录；operator 提示词知晓 v17 新能力；自主运营心跳受 `earth_online.enabled` 总开关约束。

## v17.1 特性 — 弥娅全权掌控 (策划 + 系统小精灵 + 助手)

### 工具死角清零（77 → 85，三层同步）

把"store 有能力、AI 工具没暴露"的最后 8 处补齐，弥娅现在对地球online 拥有**完整读权限 + 完整增删查改**：

| 新工具 | 能力 |
|---|---|
| `earth_stats` | 数据中心总览（多维分布 + 7日趋势 + 汇率） |
| `earth_list_checkins` | 签到历史（含每晚睡眠时长） |
| `earth_currency_ledger` | 货币/经验流水查询（评估经济、发周报） |
| `earth_update_real_context` | 修改现实连接设置（城市/开关/精确定位/刷新间隔）——弥娅可自己把天气城市配好 |
| `earth_update_commemoration` / `earth_delete_commemoration` | 纪念日编辑/删除（v17 只有增查） |
| `earth_pull_memory` | 替玩家回忆抽卡（佳说想抽时她可以直接帮抽） |
| `earth_claim_battle_pass` | 领取纪行奖励档位 |

仍保持 Web 端专有的只有：图片文件上传（需 multipart）、JSON 全量导入/导出、模板库与主题编辑（纯管理操作）——弥娅通过相应的 update 工具一样能改到这些字段。

### 自主运营上下文全景化

`_build_context`（每次自主周期的输入）从 6 块扩到 **15 块**：玩家档案（双币+属性+称号）→ 背包（总量+最近入库）→ 角色图鉴（全名单+好感）→ 每日仪式（签到/逾期/到期/日常委托就位数）→ 任务板 → 羁绊/成就/剧情 → **纪行**（积分+可领档位）→ **周挑战**（星级+进度）→ **回忆卡池**（收集/保底垫数）→ **纪念日**（今天/临近）→ **现实资产近期流水** → 世界（**季节**+时段+天气+限时活动）→ 上次运营以来的新动态 → **与佳的最近真实对话记忆** → 上次运营状态。

### 记忆接入升级

`_recent_memory_lines` 双路取数：优先走统一记忆总线 `memory.get_dialogue_history()`（跨平台聚合与佳的全部真实对话），失败回退记忆管理器会话历史。自主运营不再只看游戏数据——**她同时带着"你们聊过的天"做决策**。

### 提示词升级

策划身份升级为"唯一策划、系统小精灵兼生活助手"，明确"这个世界全权的主人：读任何数据、增删查改任何实体、开任何活动，都不需要请示"，并列出 v17 全套玩法工具清单。写操作上限（`max_actions_per_cycle`）、静默时段、SKIP 机制不变——自主，但不打扰。

## v17.2 特性 — 关怀引擎 (弥娅用委托主动介入生活)

### 需求

弥娅不只是"被动运营游戏数据"——她在后台巡检、主动找佳聊天时，要真的用委托/任务/活动**照顾佳的日常生活**：喝水、吃饭、睡觉、休息。

### 规则驱动的关怀委托引擎 (不依赖 LLM 自觉)

`generate_care_commission()`（store 层，operator 每周期自动调用）按**真实时段/玩家属性/真实天气**从模板池选最贴切的一张落板：

| 模板 | 触发条件 | 优先级 |
|---|---|---|
| 去睡觉委托 | 夜晚/深夜 (22:00-次日5:00) | 90 |
| 早餐/午饭/晚饭委托 | 对应用餐时段 (7-10 / 11-14 / 17-20) | 80 |
| 休息补给委托 | 体力 < 30 | 70 |
| 心情修复委托 | 心情 < 30 | 65 |
| 听雨补给委托 | 真实天气为雨 | 55 |
| 远眺休息委托 | 下午 (14-17) | 40 |
| 喝水委托 | 兜底，随时可发 | 10 |

**防打扰规则**：同类模板冷却 `cooldown_hours`（默认 2 小时）；每天最多 `max_per_day`（默认 6 张）；**最高优先级匹配处于冷却时本轮静默**（深夜刚催过睡觉就不会再降级发喝水连着打扰）。签发时间写入 fields.issued_at，判断完全确定。配置：`earth_online.care.*`。

**完成反馈**：关怀委托完成后额外 +2 心情，并触发 `care_completed` 弥娅反应。

### 自主周期接线 (run_cycle)

每个周期的顺序变为：**关怀引擎先落委托 → 带着新委托的上下文唤醒 LLM（她会看到任务板上刚出现的关怀委托并顺势点评/追加定制委托）→ 若 LLM 沉默 (SKIP) 但关怀引擎放了委托，用关怀候选消息主动敲门**（经统一主动协调器发出，如"都23:30了哦，亲爱的。我在任务板上放了一张「去睡觉委托」……"）。关怀引擎是系统动作，不占 LLM 写操作额度。上下文新增 `[关怀引擎] 今日关怀委托 N 张 · 已完成 M 张`。

### 提示词升级

明确"**主动介入生活是你的核心职责**"：到饭点发吃饭委托、深夜发睡觉委托、体力心情低发休息委托、天气变化开限定事件；引导她在系统模板之上结合对话记忆追加更贴合此刻的定制委托——"用委托/任务/活动照顾他，而不是只在聊天里说多喝水"。

## v17.3 特性 — 规则只定时机，内容由弥娅现场创作 + 统一主动窗口接线

### 关怀委托不再是硬编码模板

- **`detect_care_moment()`**: 规则层退化为纯"时机检测"——深夜/饭点/体力心情低/下雨/久坐时报告 `{moment, care_key, hint}`，**不生成任何内容**。防打扰规则（同类冷却 2h / 每日 6 张 / 最高优先级冷却时静默）在这一层统一执行。
- **`issue_care_commission()`** + 新工具 **`earth_issue_care_commission`**（第 86 个，三层同步）：委托的标题/描述/子任务/奖励/**想说的一句话(message)** 全部由弥娅结合此刻上下文与对话记忆**即兴创作**，工具只做限额校验与落板。message 存入 fields，作为主动敲门文案。
- 运营周期新流程：检测到时机 → 上下文给弥娅明确指令"[关怀时机·请现场创作]……不要照搬任何模板" → 她用工具发布 → 她的留言作为敲门候选；**她沉默(SKIP)或没调用工具时，才用固定模板兜底**（`care.fallback_to_templates`，默认开，可关成"只用她现场创作的"）。
- 规则没覆盖的时机她也能签发（`care_key=care_custom`）——比如对话记忆里佳说"有点累"，规则层毫不知情，她可以直接放一张抱抱委托。

### 统一主动窗口（回答"是否接入统一总结窗口"）

关怀敲门**本来就走** `ProactiveCoordinator`（统一主动性协调器）——所有后台主动消息（自检/主动聊天/地球online 巡检）的统一决策层：

- **AI 最终判断**: `_decide_message` 用 LLM 决定"这件事值不值得打扰佳"，SKIP 不消耗额度；
- **统一限频**: 每小时最多 3 条、全局最小间隔 300 秒、同类 key 冷却、事实指纹 1 小时去重；
- **静默时段**: 默认 23:00-次日 7:00 不发（睡觉委托 22 点档会敲门，23 点后只落板不吵）。

v17.3 起关怀敲门使用**独立的 `trigger_type="earth_care"` 与 key `earth_care:{care_key}`**——与普通运营消息分开计数去重，不会互相挤占额度，也不会重复轰炸。

## v17.4 特性 — 服务券制 + 寄语/自主性强化

### 弥娅兑换所：兑换后终于"有东西可用"了

互动类商品（晚安耳语/心跳靠近/约会剧本/抱抱券）从"买了即消耗成一条动态"改为**服务券制**：

- **兑换 → 得券**：购买互动商品后，背包里出现「服务券 · XXX」（collectible，fields 带 service_ticket 与互动文案，多张同名券自动叠加数量）。
- **使用 → 兑现**：两种方式——① 背包里点「使用服务券」（前端按钮）→ 展示互动文案；② **直接告诉弥娅**（"抱抱我""用一下晚安耳语"）→ 她调用新工具 `earth_redeem_service`（第 87 个，三层同步）取回文案，**用她此刻的语气亲口说出来，不照念**。使用会扣券、留动态（"使用服务券: X"）、触发弥娅反应。
- 剧情/称号/boost 券类不变（原本就有落点：剧情书/称号系统/区域委托加成）。

### 寄语与自主性强化

- 上下文新增 **[寄语]** 块：显示最新寄语内容与"已 N 天没写"提醒——公告栏空着会明说"你随时可以写下第一张"；超过一天没写会提示"今天值得写一张"。
- 上下文新增 **[动态]** 块：最近 15 条动态里有 ≥5 条没有她的评论时，提示挑一条值得回应的留言。
- 运营原则升级：**"巡检的默认预期是做点什么"**——哪怕小事（评论动态/补发奖励/写寄语/调价格），SKIP 只留给真的无事可做；**"寄语是你的温度"**——晨间仪式写晨间寄语，值得庆祝/情绪低落/特别天气的日子都适合写。

## v17.5 特性 — 游戏事件接入弥娅本体 (人格化投递 + 统一记忆)

### 新桥接层 `core/earth_online_bridge.py`

地球online 的事件从此可以流进弥娅的两个统一系统（全部吞异常，桥接失败不影响游戏主流程）：

- **`deliver_via_proactive(event, key, trigger_type)`** → 统一主动协调器：用弥娅**当前人格**把事件重新表达成一条消息（`candidate_message` 只是参考基调），经**活跃消息平台**发给佳；享受统一限频（每小时3条/最小间隔/指纹去重）与静默时段保护。
- **`remember(content)`** → `MemoryManager.store_unified_memory`（assistant 角色）：写入对话总线 + MemoryNet，记忆系统自动分析并可能升级为**长期自记忆**；运营周期的 [与佳的最近对话记忆] 也会读到——她真的记得。

### 服务券使用 = 三重兑现

在网页背包点「使用服务券」后（前端弹窗照常展示基调文案），后台异步完成：
1. **人格化平台回应**：提交 `service_ticket_redeemed` 事件（含券名/作用/基调文案 + "请基于券的作用用当前人格回应，不要照念"）→ 协调器用当前人格重写 → 发到佳正在用的消息平台（QQ/微信/终端…）；
2. **记忆**：`[地球online] 佳使用了服务券「X」，我的回应基调: …` 入统一记忆；
3. 聊天路径（跟弥娅说"用一下券"）：她用 `earth_redeem_service` 取回基调后**即兴创作**回应（工具指引已从"复述"改为"基于券的作用用当前人格创作"），对话本身自动入记忆。

### 其他记忆钩子

- 商城/活动商店兑换 → `[地球online] 佳在XX兑换了「X」`（只入记忆，不主动打扰）；
- 运营周期发布关怀委托 → `[地球online] 我发布了关怀委托「X」(我现场写的/模板兜底)`——她记得自己关心过什么。

## 关键约定

- 稀有度: common/uncommon/rare/epic/legendary（白/绿/蓝/紫/金）
- 任务类型: main 主线 / branch 支线 / daily 日常 / optional 可选
- 任务状态: pending/ongoing/completed/failed/cancelled；`source=miya` 表示弥娅安排的
- 经验曲线: 升到 Lv.L 需累计 `base×(1+2+...+(L-1))`，即 Lv.L 内升级需 `base×L`（base 默认 100，可配 `earth_online.level_exp_base`）
- 配置: `config/qq_config.yaml` 的 `earth_online` 节（v17 起全部键真实生效：总开关/初始货币/经验曲线/好感度上下限/签到/寄语/背包上限/日常生成/体力恢复…）
- 文案: `config/text_config.json` 的 `earth_online` 节（配置优先原则）

## 弥娅的职责

弥娅可以通过工具自由安排一切：查看总览、发任务（设奖励与惩罚）、发放地球币/经验、
检查逾期任务（`check_overdue`，deadline 过期自动失败扣币）、记录剧情、调整好感度。

## 手机端说明

- 手机端直连主机后端（设置页可配置主机 IP/端口），所有数据仍在主机上
- 支持拍照/相册上传物品照片与角色头像（`/api/earth/upload`，multipart）
- 图片通过 `/api/earth/images/{filename}` 静态服务
- 本地缓存目录: app 私有目录 `filesDir/earthonline/`（player/items/quests/characters/stories.json + meta.json）

## QQ / 微信接入（主机作服务器）

守护进程本身即服务器，已内置：
- **QQ**: 官方机器人（botpy，`QQ_APPID/QQ_SECRET`）+ OneBot（`QQ_ONEBOT_WS_URL`，需 NapCat）
- **微信**: 官方 iLink 通道（`weixin_ilink` 平台，登录脚本 `scripts/weixin_ilink_login.py`）

手机端无需直连 QQ/微信：它只要连上主机（局域网 IP 或公网穿透），弥娅在主机上
统一收发各平台消息，数据全部落盘在主机。
