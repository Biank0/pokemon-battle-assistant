#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 建队 CLI 入口。

用法：
  python scripts/generate_team.py --requirement "帮我建一支晴天队，打法激进" --format gen9bssregi
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pokemon_battle_assistant.harness.llm import LLMHarness  # noqa: E402
from pokemon_battle_assistant.team_builder import pipeline  # noqa: E402


def render_result(res) -> str:
    """结果 → 中文摘要（JOIN dex 取中文名）。"""
    conn = sqlite3.connect(f"file:{ROOT / 'data' / 'dex' / 'dex.db'}?mode=ro", uri=True)
    sp = {r[0]: (r[1] or r[2], r[3], r[4]) for r in conn.execute(
        "SELECT id,name_zh,name_en,type1,type2 FROM species")}
    mv = {r[0]: (r[1] or r[2]) for r in conn.execute("SELECT id,name_zh,name_en FROM moves")}
    it = {r[0]: (r[1] or r[2]) for r in conn.execute("SELECT id,name_zh,name_en FROM items")}
    conn.close()

    lines = [f"\n{'=' * 56}",
             f"队伍：{res.display_name}（{res.name}）",
             f"战术：{res.strategy}",
             f"{'=' * 56}"]
    for i, m in enumerate(res.team["members"], 1):
        name, t1, t2 = sp.get(m["species"], (m["species"], "", ""))
        types = "/".join(t for t in (t1, t2) if t)
        item = it.get(m.get("item")) if m.get("item") else None
        item = item or "无道具"
        moves = " / ".join(mv.get(x, x) for x in m["moves"])
        lines.append(f"  #{i} {name}（{types}）Lv{m.get('level', 100)}"
                     f" ｜ {m.get('nature', '-')} ｜ {m.get('ability', '-')}"
                     f" ｜ {item} ｜ 太晶 {m.get('tera_type', '-')}")
        lines.append(f"     招式：{moves} ｜ 定位：{m.get('slot_role', '-')}")
    lines.append(f"{'-' * 56}")
    lines.append(f"入库：teams.db（id={res.team_id[:8]}...）")
    lines.append(f"用量：{res.usage}")
    return "\n".join(lines)


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description="AI 建队（模块一）")
    ap.add_argument("--requirement", "-r", required=True, help="建队需求（自然语言）")
    ap.add_argument("--format", "-f", default="gen9bssregi",
                    help="赛制：gen9bssregi / gen9vgc2026regi / gen9ou")
    ap.add_argument("--skill", default="v1", help="skill 版本")
    args = ap.parse_args()

    harness = LLMHarness.from_env(ROOT / ".env")
    try:
        res = pipeline.generate_team(args.requirement, format_id=args.format,
                                     harness=harness, skill_version=args.skill)
    except Exception as e:
        print(f"\n[失败] {e}")
        return 1
    print(render_result(res))
    print(f"\n原始 JSON 已随队伍存入 teams.db；如需查看：")
    print(f"  sqlite3 data/teams/teams.db \"SELECT export_text FROM teams WHERE name='{res.name}'\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
