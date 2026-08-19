import json
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = "http://127.0.0.1:8300"

def get(path):
    with urllib.request.urlopen(BASE + path) as r:
        return json.loads(r.read().decode("utf-8"))

# 1. 列表中文
teams = get("/api/teams")
print(f"[列表] {len(teams)} 支")
for t in teams[:3]:
    print(f"  {t['display_name']} | {t['format_zh']} | {t['source_zh']}")

# 2. 详情中文
d = get("/api/teams/xiaobian")
m = d["members"][0]
print(f"[详情] {d['display_name']} / {d['format_zh']}")
print(f"  #1 {m['name_zh']} {'/'.join(t['zh'] for t in m['types'])} "
      f"特性 {m['ability_zh']} 道具 {m['item_zh']} 性格 {m['nature_zh']} 太晶 {m['tera_zh']}")
print(f"  招式 {' / '.join(x['zh'] for x in m['moves'])}")

# 3. 发起真实生成任务（DeepSeek）
req = urllib.request.Request(
    BASE + "/api/generate",
    data=json.dumps({"requirement": "帮我建一支雨天队，稳一点", "format": "gen9bssregi"}).encode(),
    headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req) as r:
    job_id = json.loads(r.read().decode())["job_id"]
print(f"\n[任务] {job_id} 已发起，开始轮询...")

t0 = time.time()
while True:
    job = get(f"/api/generate/{job_id}")
    if job["status"] != "running":
        break
    time.sleep(2)
print(f"[耗时] {time.time() - t0:.0f}s")
print(f"[状态] {job['status']}")
for log in job["logs"]:
    print("  " + log)
if job["status"] == "done":
    print(f"[队伍] {job['team']['display_name']}（{job['team']['name']}）")
    print(f"[战术] {job['team']['strategy']}")
    print(f"[用量] {job['usage']}")
    detail = get(f"/api/teams/{job['team']['name']}")
    print(f"[复核] 详情页可查，{len(detail['members'])} 只成员全中文: "
          f"{'、'.join(x['name_zh'] for x in detail['members'])}")
else:
    print(f"[错误] {job['error']}")
