"""分析文档仓储：结构化 JSON + 渲染 MD 写磁盘，索引/highlights 写 analysis.db。

写入契约（docs/analysis_db_schema.md）：先写文档文件、后写库行（同事务）；
读侧给 API：列表（不碰文件）、详情（读 JSON 文件）。
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ANALYSIS_DB = ROOT / "data" / "analysis" / "analysis.db"
DOCS_DIR = ROOT / "data" / "analysis" / "docs"


def save(report: dict, distilled: dict, session_meta: dict,
         model: str, skill_version: str) -> str:
    """落盘 + 落库，返回 analysis_id。"""
    aid = str(uuid.uuid4())
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = DOCS_DIR / f"{aid}.json"
    md_path = DOCS_DIR / f"{aid}.md"

    doc = {"id": aid, "report": report, "session_meta": session_meta,
           "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    json_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    md_path.write_text(_render_md(report, session_meta), encoding="utf-8")

    sm = session_meta
    wr = (sm.get("team_a_win_rate") or 0) / 100
    stats = {"battles": sm.get("rounds"), "score": sm.get("score"),
             "avg_turns": sm.get("avg_turns")}
    conn = sqlite3.connect(ANALYSIS_DB)
    try:
        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO analyses (id,scope_type,scope_id,title,summary,rating,win_rate,"
            "stats_json,model,skill_version,doc_json_path,doc_md_path,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (aid, "session", sm["session_id"], report["title"], report["headline"],
             report.get("rating"), wr, json.dumps(stats, ensure_ascii=False), model,
             skill_version, str(json_path.relative_to(ROOT)), str(md_path.relative_to(ROOT)),
             doc["generated_at"]))
        # 高光回合跳转行：round_no → battle_id 定位（从采样时间线反查）
        tl_by_round = {t["round_no"]: t for t in distilled.get("sample_timelines", [])}
        for seq, h in enumerate(report.get("highlights", []) or [], 1):
            tl = tl_by_round.get(h.get("round_no"))
            if tl:
                conn.execute(
                    "INSERT INTO analysis_highlights "
                    "(analysis_id,seq,battle_id,round_no,turn,side,description) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (aid, seq, tl["battle_id"], h["round_no"], h["turn"],
                     h.get("side"), h.get("what", "")))
        conn.commit()
    except Exception:
        conn.rollback()
        # 库失败回滚文档（保持"库行必有文件、文件可有孤儿"的单向干净）
        json_path.unlink(missing_ok=True)
        md_path.unlink(missing_ok=True)
        raise
    finally:
        conn.close()
    return aid


def list_analyses(limit: int = 50) -> list[dict]:
    """索引列表（不读文档文件，列表页秒开）。"""
    conn = _ro()
    try:
        rows = conn.execute(
            "SELECT id, scope_type, scope_id, title, summary, rating, win_rate, "
            "stats_json, model, skill_version, created_at FROM analyses "
            "ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [{
            "id": r[0], "scope_type": r[1], "scope_id": r[2], "title": r[3],
            "summary": r[4], "rating": r[5], "win_rate": r[6],
            "stats": json.loads(r[7]) if r[7] else {},
            "model": r[8], "skill_version": r[9], "created_at": r[10],
        } for r in rows]
    finally:
        conn.close()


def get_doc(analysis_id: str) -> dict | None:
    """读结构化文档 JSON（详情页数据源）。"""
    conn = _ro()
    try:
        r = conn.execute("SELECT doc_json_path FROM analyses WHERE id=?",
                         (analysis_id,)).fetchone()
        if not r:
            return None
    finally:
        conn.close()
    p = ROOT / r[0]
    if not p.exists():
        raise FileNotFoundError(f"文档文件缺失: {p}")
    doc = json.loads(p.read_text(encoding="utf-8"))
    # 附高光跳转信息（battle_id → 前端明细页路由）
    conn = _ro()
    try:
        hl = conn.execute(
            "SELECT seq, battle_id, round_no, turn, side, description "
            "FROM analysis_highlights WHERE analysis_id=? ORDER BY seq",
            (analysis_id,)).fetchall()
    finally:
        conn.close()
    doc["highlight_links"] = [{"seq": h[0], "battle_id": h[1], "round_no": h[2],
                               "turn": h[3], "side": h[4], "description": h[5]} for h in hl]
    return doc


def _ro() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{ANALYSIS_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------- MD 渲染
def _render_md(report: dict, sm: dict) -> str:
    """结构化 JSON → 可读 Markdown（本地查看/归档用，前端走 JSON 结构化渲染）。"""
    lines = [f"# {report['title']}", "",
             f"> {report['headline']}", "",
             f"- 评价档位：**{report.get('rating', '-')}** ｜ 比分：{sm.get('score')} ｜ "
             f"A 队胜率：{sm.get('team_a_win_rate')}%", "",
             "## 战绩解读", "", report.get("win_loss_read", ""), ""]

    lines += ["## 阵容表现", ""]
    for p in report.get("pokemon_performance", []):
        side = "A 队" if p.get("side") == "a" else "B 队"
        moves = "、".join(f"{m['move_zh']}×{m['count']}"
                          for m in p.get("moves_used", [])[:6]) or "-"
        lines.append(f"### {p['species_zh']}（{side} · {p.get('role', '?')}）")
        lines.append(f"- 出场 {p.get('appearance', '?')} 次；招式：{moves}")
        lines.append(f"- {p.get('verdict', '')}")
        for i in p.get("issues", []) or []:
            lines.append(f"- ⚠ {i}")
        lines.append("")

    if report.get("matchups"):
        lines += ["## 对位分析", ""]
        for m in report["matchups"]:
            lines.append(f"- **{m['attacker_zh']} → {m['defender_zh']}**：{m.get('read', '')}")
        lines.append("")
    if report.get("threats"):
        lines += ["## 威胁识别", ""]
        for t in report["threats"]:
            lines.append(f"- **{t['from_zh']}**：{t.get('why', '')} → 应对：{t.get('counter', '')}")
        lines.append("")
    if report.get("highlights"):
        lines += ["## 关键回合", ""]
        for h in report["highlights"]:
            lines.append(f"- 第 {h['round_no']} 场 回合 {h['turn']}：{h.get('what', '')}")
        lines.append("")
    lines += ["## 改进建议", ""]
    for r in report.get("recommendations", []):
        lines.append(f"- 【{r.get('priority')}】{r.get('target')}：{r.get('change')}"
                     f"（{r.get('reason')}）")
    return "\n".join(lines) + "\n"
