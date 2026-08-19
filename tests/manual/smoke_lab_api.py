"""API 集成测试：POST /api/lab/start（3 轮）→ 轮询至完成 → 校验聚合/明细。"""
import json
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = "http://127.0.0.1:8300/api"


def post(path, payload):
    req = urllib.request.Request(BASE + path, json.dumps(payload).encode(),
                                 {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def get(path):
    return json.loads(urllib.request.urlopen(BASE + path, timeout=30).read())


def main():
    r = post("/lab/start", {"team_a": "xiaobian", "team_b": "bss_balance",
                            "format": "gen9bssregi", "rounds": 3})
    sid = r["session_id"]
    print(f"session: {sid[:8]}")

    for _ in range(120):  # 最多 6 分钟
        time.sleep(3)
        s = get(f"/lab/session/{sid}")
        print(f"  进度 {s['rounds_done']}/{s['rounds_total']} status={s['status']}")
        if s["status"] in ("completed", "failed"):
            break

    assert s["status"] == "completed", f"未完成: {s['status']} {s.get('error')}"
    stats = s["stats"]
    print(f"\n[聚合] {stats['team_a_display']} {stats['team_a_wins']} - "
          f"{stats['team_b_wins']} {stats['team_b_display']} "
          f"(A胜率 {stats['team_a_win_rate']}% / 平均 {stats['avg_turns']} 回合)")
    print("[聚合] 招式热榜:", [(m["move_zh"], m["count"]) for m in stats["top_moves"][:5]])

    # 单场明细
    b = s["battles"][0]
    detail = get(f"/lab/battle/{b['id']}")
    print(f"\n[明细] 第{detail['round_no']}场 winner={detail['winner']} "
          f"{detail['team_a']} vs {detail['team_b']}")
    for t in detail["turns"][:8]:
        act = f"招式 {t['move_zh']}" if t["action_type"] == "move" else (
            f"换上 {t['target_zh']}" if t["action_type"] == "switch" else "选队")
        print(f"  回合{t['turn']} {'己方' if t['side'] == 'a' else '对手'} "
              f"{t['actor_zh']}: {act}")
    print("\nAPI 集成测试全部通过")


if __name__ == "__main__":
    main()
