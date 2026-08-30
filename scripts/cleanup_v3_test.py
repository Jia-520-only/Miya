"""清理 v3 接取流程测试残留"""
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.earth_online_store import get_earth_store

s = get_earth_store()
conn = s._connect()
conn.execute("DELETE FROM quests WHERE title = 'V3接取测试'")
conn.execute("DELETE FROM quest_history WHERE title = 'V3接取测试'")
conn.execute("UPDATE player_profile SET exp = MAX(0, exp - 8), total_completed = MAX(0, total_completed - 1), currency = MAX(0, currency - 5) WHERE id = 1")
conn.commit()
conn.close()
s._write_mirror()
print("cleanup ok")
