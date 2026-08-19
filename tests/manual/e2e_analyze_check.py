"""模块三 API 端到端检查：发起分析任务 → 轮询 → 报告列表/详情。

用法：python tests/manual/e2e_analyze_check.py [base_url] [session_id]
默认 base_url http://127.0.0.1:8300；session_id 不传时自动取最近 completed 会话。
"""
import json
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8300"


def get(path):
    with urllib.request.urlopen(BASE + path) as r:
        return json.loads(r.read().decode("utf-8"))


def post(path, body):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> None:
    # 1. 报告列表
    before = get("/api/analyses")["analyses"]
    print(f"[列表] 已有 {len(before)} 份报告")

    # 2. 目标会话
    session_id = sys.argv[2] if len(sys.argv) > 2 else None
    if not session_id:
        conn = sqlite3.connect(f"file:{ROOT / 'data/battles/battles.db'}?mode=ro", uri=True)
        row = conn.execute(
            "SELECT id FROM battle_sessions WHERE status='completed' "
            "ORDER BY started_at DESC LIMIT 1").fetchone()
        conn.close()
        session_id = row[0]
    print(f"[会话] {session_id}")

    # 3. 发起异步分析（带关注点）
    job_id = post("/api/analyze", {"session_id": session_id,
                                   "focus": "重点看看快龙是不是该换招"})["job_id"]
    print(f"[任务] {job_id} 已发起，轮询…")

    t0 = time.time()
    while True:
        job = get(f"/api/analyze/{job_id}")
        if job["status"] != "running":
            break
        time.sleep(2)
    print(f"[耗时] {time.time() - t0:.0f}s ｜ 状态 {job['status']}")
    for log in job["logs"]:
        print("  " + log)
    if job["status"] != "done":
        print(f"[错误] {job['error']}")
        sys.exit(1)

    # 4. 列表刷新 + 详情复核
    res = job["result"]
    after = get("/api/analyses")["analyses"]
    print(f"\n[列表] 现在 {len(after)} 份（新增 1 份应为 {res['analysis_id'][:8]}…）")
    doc = get(f"/api/analyses/{res['analysis_id']}")
    r = doc["report"]
    print(f"[详情] {r['title']} ｜ 评分 {r['rating']}")
    print(f"  核心结论：{r['headline']}")
    print(f"  阵容表现 {len(r['pokemon_performance'])} 条 ｜ "
          f"建议 {len(r['recommendations'])} 条 ｜ "
          f"高光跳转 {len(doc['highlight_links'])} 条")
    assert any(x["id"] == res["analysis_id"] for x in after), "新报告未出现在列表"
    assert doc["highlight_links"], "高光跳转为空"
    print("\n[结论] 分析 API 端到端通过 ✔")


if __name__ == "__main__":
    main()
