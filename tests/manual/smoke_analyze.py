"""模块三端到端冒烟：真实 battles.db 会话 + 真实 LLM → 报告入库。

用法：python tests/manual/smoke_analyze.py [session_id]
不传 session_id 时自动选最近一个 completed 会话。
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from pokemon_battle_assistant.battle_analyzer import distiller, pipeline, repository  # noqa: E402
from pokemon_battle_assistant.harness.llm import LLMHarness  # noqa: E402


def main() -> None:
    session_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not session_id:
        conn = sqlite3.connect(f"file:{ROOT / 'data/battles/battles.db'}?mode=ro", uri=True)
        row = conn.execute(
            "SELECT id FROM battle_sessions WHERE status='completed' "
            "ORDER BY started_at DESC LIMIT 1").fetchone()
        conn.close()
        if not row:
            print("battles.db 没有 completed 会话，先跑一次对战实验室")
            sys.exit(1)
        session_id = row[0]

    print(f"目标会话: {session_id}")
    d = distiller.distill_session(session_id)
    sm = d["session_meta"]
    print(f"蒸馏: {sm['team_a']} vs {sm['team_b']} ｜ 比分 {sm['score']} ｜ "
          f"档案 {len(d['pokemon_profiles'])} 只 ｜ "
          f"prompt 文本 {len(distiller.to_prompt_text(d))} 字符")

    harness = LLMHarness.from_env(ROOT / ".env")
    res = pipeline.analyze_session(session_id, harness, focus="")

    print(f"\n报告: {res.title}")
    print(f"核心结论: {res.headline}")
    print(f"评分 {res.rating} ｜ 校验轮次 {res.attempts} ｜ {res.usage}")

    doc = repository.get_doc(res.analysis_id)
    print(f"\n入库 analysis_id={res.analysis_id}")
    print(f"高光跳转 {len(doc['highlight_links'])} 条 ｜ MD 已渲染")
    print("\n--- 报告 JSON 预览 ---")
    print(json.dumps(doc["report"], ensure_ascii=False, indent=1)[:1500])


if __name__ == "__main__":
    main()
