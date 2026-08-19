"""分析管线：distill → skill.prompt → LLM → validate（修复循环）→ repository。

与 team_builder/pipeline 同构：最多 2 轮修复，日志钩子供 API 回传。
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass

from ..harness.llm import LLMHarness
from ..skills.battle_analysis import skill as skill_pkg
from . import distiller, repository, validator

MAX_ATTEMPTS = 2

_local = threading.local()


def _log(msg: str) -> None:
    hook = getattr(_local, "hook", None)
    (hook or print)(msg)


@dataclass
class AnalysisResult:
    analysis_id: str
    title: str
    headline: str
    rating: str
    attempts: int
    usage: str


def analyze_session(session_id: str, harness: LLMHarness,
                    focus: str = "", skill_version: str = "v1") -> AnalysisResult:
    """对一个跑量会话生成分析报告并入库。"""
    _log("[分析] 蒸馏对战数据…")
    distilled = distiller.distill_session(session_id)
    sm = distilled["session_meta"]
    _log(f"[分析] {sm['team_a']} vs {sm['team_b']} ｜ 比分 {sm['score']} ｜ "
         f"档案 {len(distilled['pokemon_profiles'])} 只")

    skill = skill_pkg.load(skill_version)
    distilled_text = distiller.to_prompt_text(distilled)

    report_json = ""
    errors: list[str] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        _log(f"[分析] 调用 LLM 生成报告（第 {attempt} 次）…")
        if attempt == 1:
            msgs = skill.prompt(distilled_text, focus)
        else:
            msgs = skill.repair_prompt(distilled_text, focus, report_json, errors)
        report_json = harness.chat(msgs, json_mode=True, temperature=0.4)
        try:
            report = json.loads(report_json)
        except json.JSONDecodeError as e:
            errors = [f"输出不是合法 JSON: {e}"]
            _log(f"[分析] JSON 解析失败：{e}")
            continue
        errors = validator.validate_report(report, distilled)
        if not errors:
            break
        _log(f"[分析] 校验未通过（{len(errors)} 项），进入修复轮")
    if errors:
        raise ValueError("分析报告校验未通过: " + "; ".join(errors[:5]))

    _log("[分析] 报告通过校验，写入文档库…")
    aid = repository.save(report, distilled, sm, harness.model, skill_version)
    _log(f"[分析] 完成：{report['title']}（评分 {report.get('rating')}）")
    return AnalysisResult(analysis_id=aid, title=report["title"],
                          headline=report["headline"], rating=report.get("rating", "-"),
                          attempts=attempt, usage=harness.stats.summary())
