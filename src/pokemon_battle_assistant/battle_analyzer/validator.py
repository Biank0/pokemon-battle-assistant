"""分析报告反幻觉校验：报告里出现的名字/场次/回合必须真实存在于蒸馏数据。

闸门（对照 team_builder/validator 的思路，但规则简单得多——分析输出没有
合法性约束，只有事实性约束）：
  1. 结构：必填字段齐全、类型正确、rating/priority 枚举合法
  2. 名字：pokemon_performance.species_zh 必须在蒸馏档案里
  3. 招式：moves_used.move_zh 必须在该宝可梦的档案招式里
  4. 对位：matchups 的攻守方必须在档案宝可梦里
  5. 高光：round_no/turn/side 必须精确命中某条采样时间线的回合
"""
from __future__ import annotations

RATINGS = {"S", "A", "B", "C", "D"}
PRIORITIES = {"高", "中", "低"}
_SIDES = {"a", "b"}


def validate_report(report: dict, distilled: dict) -> list[str]:
    """返回错误清单（空 = 通过）。"""
    errs: list[str] = []

    def need(d, key, typ, ctx):
        if key not in d or d[key] is None:
            errs.append(f"{ctx} 缺少 {key}")
        elif typ is str and not isinstance(d[key], str):
            errs.append(f"{ctx}.{key} 应为字符串")
        elif typ is int and not isinstance(d[key], int):
            errs.append(f"{ctx}.{key} 应为整数")
        elif typ is list and not isinstance(d[key], list):
            errs.append(f"{ctx}.{key} 应为数组")

    for k, t in (("title", str), ("headline", str), ("win_loss_read", str),
                 ("rating", str)):
        need(report, k, t, "报告")
    if report.get("rating") not in RATINGS and isinstance(report.get("rating"), str):
        errs.append(f"rating 非法：{report['rating']}（应为 S/A/B/C/D）")

    # 档案名字 → 合法宝可梦集（side|zh 两键都建）
    profiles = distilled.get("pokemon_profiles", [])
    by_zh: dict[str, dict] = {p["species_zh"]: p for p in profiles}

    perf = report.get("pokemon_performance")
    if not isinstance(perf, list) or not perf:
        errs.append("pokemon_performance 缺失或为空")
    else:
        known = {p["species_zh"] for p in profiles}
        for i, p in enumerate(perf):
            ctx = f"pokemon_performance[{i}]"
            need(p, "species_zh", str, ctx)
            need(p, "side", str, ctx)
            need(p, "role", str, ctx)
            need(p, "verdict", str, ctx)
            if p.get("species_zh") not in known:
                errs.append(f"{ctx}.species_zh '{p.get('species_zh')}' 不在出场档案里（幻觉）")
                continue
            prof = by_zh[p["species_zh"]]
            if p.get("side") not in _SIDES:
                errs.append(f"{ctx}.side 应为 a/b")
            elif p["side"] != prof["side"]:
                errs.append(f"{ctx}: {p['species_zh']} 属于 {prof['side']} 方，不是 {p['side']}")
            legal_moves = {m["move_zh"] for m in prof["moves_used"]}
            for m in p.get("moves_used", []) or []:
                if isinstance(m, dict) and m.get("move_zh") not in legal_moves:
                    errs.append(f"{ctx}: {p['species_zh']} 未使用过招式 "
                                f"'{m.get('move_zh')}'（幻觉）")

    # 对位
    known = {p["species_zh"] for p in profiles}
    for i, m in enumerate(report.get("matchups", []) or []):
        if not isinstance(m, dict):
            errs.append(f"matchups[{i}] 结构错误")
            continue
        for k in ("attacker_zh", "defender_zh"):
            if m.get(k) not in known:
                errs.append(f"matchups[{i}].{k} '{m.get(k)}' 不在出场档案里（幻觉）")

    # 威胁
    for i, t in enumerate(report.get("threats", []) or []):
        if isinstance(t, dict) and t.get("from_zh") not in known:
            errs.append(f"threats[{i}].from_zh '{t.get('from_zh')}' 不在出场档案里（幻觉）")

    # 高光：必须命中真实 (round_no, turn, side)
    legal_moments = set()
    for tl in distilled.get("sample_timelines", []):
        for a in tl["actions"]:
            legal_moments.add((tl["round_no"], a["turn"], a["side"]))
    for i, h in enumerate(report.get("highlights", []) or []):
        if not isinstance(h, dict):
            errs.append(f"highlights[{i}] 结构错误")
            continue
        key = (h.get("round_no"), h.get("turn"), h.get("side"))
        if key not in legal_moments:
            errs.append(f"highlights[{i}] 回合定位 ({h.get('round_no')}, {h.get('turn')}, "
                        f"{h.get('side')}) 不在采样时间线里（幻觉或定位错）")

    # 建议
    recs = report.get("recommendations")
    if not isinstance(recs, list) or len(recs) < 2:
        errs.append("recommendations 至少 2 条")
    else:
        for i, r in enumerate(recs):
            if not isinstance(r, dict):
                errs.append(f"recommendations[{i}] 结构错误")
                continue
            if r.get("priority") not in PRIORITIES:
                errs.append(f"recommendations[{i}].priority 应为 高/中/低")
            for k in ("target", "change", "reason"):
                if not isinstance(r.get(k), str) or not r[k]:
                    errs.append(f"recommendations[{i}] 缺少 {k}")
    return errs
