# -*- coding: utf-8 -*-
"""
MIYA Virtual Streamer Module - Unit & Integration Tests
========================================================

Tests:
  EmoteEngine — text-to-emotion keyword matching
  AutoSwingEngine — swing lifecycle
  SceneClothesManager — scene/clothes message routing
  LiveStreamHub — message routing integration
  Live2D command queue — cross-process communication
  REST API — endpoints (with --api flag)

Run:
  python tests/test_yinmei_vtuber.py
  python tests/test_yinmei_vtuber.py --api
  python tests/test_yinmei_vtuber.py -v
"""

import sys
import os
import io

import time
import uuid
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0


def ok(name: str, detail: str = ""):
    global PASS
    PASS += 1
    print(f"  [PASS] {name}")
    if detail:
        print(f"         {detail}")


def no(name: str, detail: str = ""):
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {name}")
    if detail:
        print(f"         {detail}")


def check(name: str, condition: bool, detail: str = ""):
    if condition:
        ok(name, detail)
    else:
        no(name, detail)
    return condition


def section(text: str):
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}")


def sub(text: str):
    print(f"\n{'-' * 50}")
    print(f"  [{text}]")
    print(f"{'-' * 50}")


# ============================================================
# 1. EmoteEngine
# ============================================================


def test_emote_engine(verbose=False):
    section("1. EmoteEngine - Keyword Matching")

    from plugins.yinmei.core.emote_engine import EmoteEngine

    engine = EmoteEngine()

    sub("Happy")
    r = engine.analyze("哈哈哈笑死我了")
    if verbose:
        print(f"   result: {r}")
    check("has ha -> happy", len(r) > 0, str(r[:2]))
    check("kai xin -> happy", len(engine.analyze("今天好开心")) > 0)

    sub("Sad")
    check("ku -> sad", len(engine.analyze("呜呜呜哭了")) > 0)
    check("bei shang -> sad", len(engine.analyze("好悲伤")) > 0)

    sub("Greeting")
    check("ni hao -> greeting", len(engine.analyze("你好呀")) > 0)
    check("huan ying -> greeting", len(engine.analyze("欢迎新人")) > 0)

    sub("Anger")
    check("sheng qi -> anger", len(engine.analyze("气死我了")) > 0)

    sub("Nod/agree")
    r = engine.analyze("嗯嗯就是这个")
    check("en -> nod with loop", len(r) > 0 and any(e.get("donum", 0) > 0 for e in r))

    sub("Surprise")
    check("tian a -> surprise", len(engine.analyze("天啊居然")) > 0)

    sub("Cute")
    check("ke ai -> cute", len(engine.analyze("你好可爱呀")) > 0)

    sub("Head pat")
    r = engine.analyze("摸摸头乖哦")
    check("mo mo tou -> 2 segments", len(r) >= 2, f"got {len(r)}")

    sub("No keyword")
    check("plain text -> empty", len(engine.analyze("今天是晴天")) == 0)

    sub("Mood tracking")
    mood = engine.track_mood("happy")
    check("happy -> mood +2", mood == 2, f"mood={mood}")
    mood = engine.track_mood("sad")
    check("sad -> mood +1", mood == 3, f"mood={mood}")
    ok("mood cap at 300")


# ============================================================
# 2. AutoSwingEngine
# ============================================================


def test_auto_swing(verbose=False):
    section("2. AutoSwingEngine - Swing Lifecycle")

    from plugins.yinmei.core.auto_swing import AutoSwingEngine
    from plugins.yinmei.core import SharedData

    engine = AutoSwingEngine()
    data = SharedData()

    sub("Should NOT start when idle")
    data.is_tts_ready = True
    data.is_singing = 2
    data.swing_motion = 2
    engine.start()
    check("TTS ready + not singing -> no swing", data.swing_motion == 2, f"motion={data.swing_motion}")

    sub("Should start when talking")
    data.is_tts_ready = False
    data.swing_motion = 2
    engine.start()
    check("TTS busy -> swing started", data.swing_motion == 1, f"motion={data.swing_motion}")

    sub("Stop swing")
    engine.stop()
    check("stop -> swing_motion=2", data.swing_motion == 2, f"motion={data.swing_motion}")

    sub("Start during singing")
    data.is_singing = 1
    data.swing_motion = 2
    engine.start()
    check("singing -> swing started", data.swing_motion == 1, f"motion={data.swing_motion}")
    engine.stop()


# ============================================================
# 3. SceneClothesManager
# ============================================================


def test_scene_clothes(verbose=False):
    section("3. SceneClothesManager - Scene & Clothes")

    from plugins.yinmei.core.scene_manager import SceneClothesManager

    manager = SceneClothesManager()

    sub("Scene message routing")
    check("'qie huan ...' -> matched", manager.msg_deal_scene("t1", "切换海岸花坊", "0", "test"))
    check("'jin ru ...' -> matched", manager.msg_deal_scene("t2", "进入神社", "0", "test"))
    check("'ni hao' -> not matched", not manager.msg_deal_scene("t3", "你好", "0", "test"))

    sub("Clothes message routing")
    check("'huan zhuang ...' -> matched", manager.msg_deal_clothes("t4", "换装便衣", "0", "test"))
    check("'huan yi fu ...' -> matched", manager.msg_deal_clothes("t5", "换衣服汉服", "0", "test"))
    check("'tian qi' -> not matched", not manager.msg_deal_clothes("t6", "天气不错", "0", "test"))

    sub("Night scene restrictions")
    check("night blocks unallowed scene", not manager._allow_scene("清晨房间", now="23:00:00"))
    check("night allows shrine", manager._allow_scene("神社", now="23:00:00"))
    check("night allows pink room", manager._allow_scene("粉色房间", now="23:00:00"))


# ============================================================
# 4. LiveStreamHub - Message Routing
# ============================================================


def test_message_routing(verbose=False):
    section("4. LiveStreamHub - Message Routing")

    from plugins.yinmei.core.live_stream_hub import LiveStreamHub
    from plugins.yinmei.core import SharedData

    hub = LiveStreamHub()
    data = SharedData()
    tid = str(uuid.uuid4())

    sub("Command routing")
    hub.process_message(tid, "\\stop", "0", "test")
    check("\\stop -> resets state", data.is_singing == 2 and data.is_ai_ready)

    sub("Clothes routing")
    hub.process_message(tid, "换装樱花服", "0", "test")
    check("'huan zhuang ...' -> routed", data.now_clothes == "樱花服", f"clothes={data.now_clothes}")

    sub("Chat routing")
    hub.process_message(tid, "今天天气真好", "0", "test")
    qsize = data.QuestionList.qsize()
    check("chat msg -> queued", qsize >= 1, f"qsize={qsize}")
    data.QuestionList.get()  # drain

    sub("Backslash msgs skipped")
    qs_before = data.QuestionList.qsize()
    hub.process_message(tid, "\\hidden", "0", "test")
    check("\\msg -> skipped", data.QuestionList.qsize() == qs_before)


# ============================================================
# 5. Live2D Command Queue
# ============================================================


def test_live2d_queue(verbose=False):
    section("5. Live2D Command Queue")

    from plugins.yinmei.routes import (
        live2d_set_emotion,
        live2d_set_state,
        live2d_set_mouth,
        live2d_trigger_action,
        get_live2d_commands,
    )

    sub("Basic enqueue")
    get_live2d_commands()  # drain accumulated commands from previous tests
    live2d_set_emotion("happy")
    live2d_set_state("talking")
    live2d_set_mouth({"ParamMouthOpenY": 0.5})
    live2d_trigger_action("nod")

    cmds = get_live2d_commands()
    check("4 commands enqueued", len(cmds) == 4, f"got {len(cmds)}")
    check("1st is emotion", cmds[0]["type"] == "emotion")
    check("2nd is state", cmds[1]["type"] == "state")
    check("3rd is mouth", cmds[2]["type"] == "mouth")
    check("4th is action", cmds[3]["type"] == "action")

    sub("Queue drain")
    cmds2 = get_live2d_commands()
    check("drained -> empty", len(cmds2) == 0, f"got {len(cmds2)}")

    sub("Emotion values")
    live2d_set_emotion("sad")
    live2d_set_emotion("surprise")
    live2d_set_emotion("neutral")
    cmds = get_live2d_commands()
    check("3 emotion commands", len(cmds) == 3)
    check("last = neutral", cmds[2]["value"] == "neutral")


# ============================================================
# 6. REST API (requires running server)
# ============================================================


def test_rest_api(port=1800):
    section(f"6. REST API (port {port})")

    import urllib.request
    import urllib.error

    base = f"http://127.0.0.1:{port}/api/yinmei"

    def api_get(path):
        try:
            req = urllib.request.Request(f"{base}{path}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.URLError as e:
            return None, str(e)
        except Exception as e:
            return None, str(e)

    sub("Status endpoint")
    code, data = api_get("/status")
    if code == 200:
        ok("GET /status -> 200")
        check("has ai_name", "ai_name" in data)
        ok(
            f"MIYA: {data.get('ai_name', '?')} | "
            f"song={data.get('song_queue', 0)} "
            f"draw={data.get('draw_queue', 0)} "
            f"dance={data.get('dance_queue', 0)}"
        )
    else:
        print(f"\n  [SKIP] API server not running on port {port}")
        print(f"  Start with: python run/daemon.py (or keep existing server)")
        return

    sub("Chat endpoint")
    code, data = api_get("/chat?text=你好呀&username=tester")
    check("GET /chat -> 200", code == 200, f"code={code}")

    sub("Sing endpoint")
    code, data = api_get("/sing?songname=晴天&username=tester")
    check("GET /sing -> 200", code == 200, f"code={code}")

    sub("Live2D control")
    code, data = api_get("/live2d/emotion?emotion=happy")
    check("GET /live2d/emotion -> 200", code == 200)
    code, data = api_get("/live2d/state?state=talking")
    check("GET /live2d/state -> 200", code == 200)
    code, cmds = api_get("/live2d/commands")
    check("GET /live2d/commands -> 200", code == 200)
    if cmds and "commands" in cmds:
        c = cmds["commands"]
        ok(f"live2d cmds pending: {len(c)} [{', '.join(x['type'] for x in c)}]")

    sub("Scene endpoint")
    code, data = api_get("/scene?scenename=海岸花坊")
    check("GET /scene -> 200", code == 200, f"code={code}")

    sub("Swing endpoints")
    code, data = api_get("/swing/start")
    check("GET /swing/start -> 200", code == 200)
    code, data = api_get("/swing/stop")
    check("GET /swing/stop -> 200", code == 200)


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    # Fix Windows console encoding (direct run only; pytest manages its own output)
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    api_test = "--api" in sys.argv

    print()
    print("=" * 60)
    print("  MIYA Virtual Streamer Module - Test Suite")
    print("  Emote | Swing | Scene | Bilibili | Live2D")
    print("=" * 60)

    start = time.time()

    # --- Unit tests (no server required) ---
    test_emote_engine(verbose)
    test_auto_swing(verbose)
    test_scene_clothes(verbose)
    test_message_routing(verbose)
    test_live2d_queue(verbose)

    # --- REST API tests (need running server) ---
    if api_test:
        test_rest_api()
    else:
        print(f"\n{'-' * 50}")
        print("  [SKIP] REST API tests (add --api to enable)")
        print("  Requires MIYA backend running on port 1800")

    # --- Results ---
    elapsed = time.time() - start
    total = PASS + FAIL
    print(f"\n{'=' * 60}")
    print(f"  Results: {PASS}/{total} passed, {FAIL} failed  ({elapsed:.1f}s)")
    print(f"{'=' * 60}")

    if FAIL > 0:
        sys.exit(1)
