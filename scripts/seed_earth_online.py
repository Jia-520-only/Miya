"""地球online 开服播种 — 弥娅安排的新手任务与开服剧情 (幂等: 已有任务则跳过)"""
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8")

from core.earth_online_store import get_earth_store

store = get_earth_store()

# 清理冒烟测试残留
conn = store._connect()
conn.execute("DELETE FROM quests WHERE title = '测试任务'")
conn.execute("DELETE FROM quest_history WHERE title = '测试任务'")
conn.commit()
conn.close()
print("[cleanup] 测试任务已清理")

# 幂等检查: 已存在 source=miya 的任务则跳过播种
existing = store.list_quests()
if existing:
    print(f"[skip] 已存在 {len(existing)} 个任务，跳过播种")
else:
    quests = [
        dict(
            title="开服任务：认识你的地球online",
            description="打开桌面/手机端的「地球online」板块，逛一逛背包、任务、角色图鉴和剧情四个页面，回来告诉弥娅你的感想。",
            quest_type="main", must_complete=True,
            reward_currency=20, reward_exp=30, penalty_currency=30,
            source="miya",
            subtasks=[
                {"text": "打开桌面端的「地球online」板块", "done": 0},
                {"text": "逛一逛背包、委托、角色图鉴和剧情四个板块", "done": 0},
                {"text": "在首页完成一次每日签到", "done": 0},
                {"text": "回来告诉弥娅你的感想", "done": 0},
            ],
        ),
        dict(
            title="拍一张现实物品的照片，收录进背包",
            description="随便找一件你身边的东西——手机、键盘、一本书、一杯咖啡，拍张照，把它作为背包里的第一件收藏品。",
            quest_type="daily", must_complete=False,
            reward_currency=10, reward_exp=10, penalty_currency=10,
            source="miya",
            subtasks=[
                {"text": "找一件身边的小物品", "done": 0},
                {"text": "拍照并上传到背包", "done": 0},
            ],
        ),
        dict(
            title="给一位重要的人发句问候",
            description="从角色图鉴里想起一个人，给 TA 发条消息或打个招呼，然后把这次互动记进好感度。",
            quest_type="branch", must_complete=False,
            reward_currency=15, reward_exp=20, penalty_currency=15,
            source="miya",
            subtasks=[
                {"text": "给 TA 发一句问候", "done": 0},
                {"text": "在图鉴中记录这次互动", "done": 0},
            ],
        ),
        dict(
            title="睡前告诉弥娅：今天发生了什么",
            description="用一句话记录今天的剧情事件，让地球online 的时间线滚动起来。",
            quest_type="daily", must_complete=False,
            reward_currency=5, reward_exp=8, penalty_currency=5,
            source="miya",
            subtasks=[
                {"text": "睡前回想今天的一件事", "done": 0},
                {"text": "告诉弥娅并记录成剧情", "done": 0},
            ],
        ),
    ]
    for q in quests:
        created = store.create_quest(**q)
        print(f"[seed] 任务 #{created['id']} 「{created['title']}」 ({created['quest_type']})")

# 幂等补充: 已有任务没有子任务的, 补上默认子任务清单
DEFAULT_SUBTASKS_BY_TITLE = {
    "开服任务：认识你的地球online": [
        {"text": "打开桌面端的「地球online」板块", "done": 0},
        {"text": "逛一逛背包、委托、角色图鉴和剧情四个板块", "done": 0},
        {"text": "在首页完成一次每日签到", "done": 0},
        {"text": "回来告诉弥娅你的感想", "done": 0},
    ],
    "拍一张现实物品的照片，收录进背包": [
        {"text": "找一件身边的小物品", "done": 0},
        {"text": "拍照并上传到背包", "done": 0},
    ],
    "给一位重要的人发句问候": [
        {"text": "给 TA 发一句问候", "done": 0},
        {"text": "在图鉴中记录这次互动", "done": 0},
    ],
    "睡前告诉弥娅：今天发生了什么": [
        {"text": "睡前回想今天的一件事", "done": 0},
        {"text": "告诉弥娅并记录成剧情", "done": 0},
    ],
}
for q in existing:
    if not (q.get("subtasks") or []) and q["title"] in DEFAULT_SUBTASKS_BY_TITLE:
        store.update_quest(q["id"], {"subtasks": DEFAULT_SUBTASKS_BY_TITLE[q["title"]]})
        print(f"[seed] 任务 #{q['id']} 「{q['title']}」已补子任务清单")

# 开服剧情 (幂等: 标题已存在则跳过)
stories = store.list_story(limit=100)
if any(s["title"] == "地球online 开服" for s in stories):
    print("[skip] 开服剧情已存在")
else:
    s = store.create_story(
        title="地球online 开服",
        content="今天起，现实生活正式接入游戏化系统。从此刻开始，每一件物品都有故事，每一段关系都有数值，每一天都是可以完成的委托。开拓之旅，由弥娅陪你一起走。",
        event_type="life",
    )
    print(f"[seed] 剧情 #{s['id']} 「{s['title']}」")

# 开服寄语 (幂等: 已有寄语则跳过)
notes = store.list_notes(limit=100)
if notes:
    print(f"[skip] 已存在 {len(notes)} 条寄语，跳过播种")
else:
    welcome = store.add_note(
        content="欢迎来到 **地球online**！我是弥娅～\n\n从今天起，你的每一件物品、每一个目标、每一位重要的人，都会在这片鎏金世界里有自己的档案。记得每天来首页签到领地球币哦 ✦",
        mood="excited",
        pinned=True,
    )
    print(f"[seed] 寄语 #{welcome['id']} 已置顶")

# 成就初始化 (store 已自动播种定义, 这里只刷新进度)
unlocked = store.refresh_achievements()
achievements = store.list_achievements()
print(f"[seed] 成就定义 {len(achievements)} 个, 已解锁 {len([a for a in achievements if a['unlocked_at']])} 个")
for u in unlocked:
    print(f"  ✦ 新解锁: {u['icon']} {u['title']}")

print("[summary]", store.summary())
print("SEED DONE")
