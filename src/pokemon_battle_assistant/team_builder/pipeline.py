"""模块一编排：需求 → 蓝图 → 候选池 → 队伍 → 校验（修复≤3轮）→ 入库。"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field

from ..harness.llm import LLMHarness
from ..skills.team_building import skill as skill_pkg
from . import builder, planner, pool, repository, validator


def _p(msg: str) -> None:  # 进度输出（测试可 monkeypatch 静默；API 线程经 _local.hook 回传）
    print(msg)
    hook = getattr(_local, "hook", None)
    if hook:
        hook(msg)


_local = threading.local()  # API 后台线程注入日志钩子（线程隔离，互不串扰）


class TeamBuildError(Exception):
    """流水线最终失败（修复轮耗尽等），携带全部错误信息。"""


@dataclass
class BuildResult:
    team_id: str
    name: str
    display_name: str
    team: dict
    strategy: str
    attempts: int
    skill_version: str
    model: str
    pool_sizes: list = field(default_factory=list)
    usage: str = ""


def generate_team(requirement: str, format_id: str = "gen9bssregi",
                  harness: LLMHarness | None = None, skill_version: str = "v1") -> BuildResult:
    """端到端建队。CLI（scripts/generate_team.py）与未来 API 共用此入口。"""
    harness = harness or LLMHarness.from_env()
    skill = skill_pkg.load(skill_version)
    skill.constraints(format_id)  # 提前校验赛制合法性（未知赛制立刻报错）

    _p(f"[1/5] 解析需求 → 队伍蓝图（{skill_version}）")
    blueprint = planner.plan(harness, skill, requirement, format_id)
    _p(f"      战术主线：{blueprint['strategy']}")
    for i, s in enumerate(blueprint["slots"], 1):
        cond = "/".join(s["types"]) or "自由"
        mins = ",".join(f"{k}≥{v}" for k, v in s["stat_min"].items()) or "-"
        _p(f"      角色位{i} {s['role_zh']}（{cond}｜{mins}）")

    _p("[2/5] 生成候选池（SQL 查 dex）")
    pools, pools_text = pool.build_pools(blueprint)
    _p("      " + "｜".join(f"{s['role_zh']}:{len(p)}只"
                            for s, p in zip(blueprint["slots"], pools)))

    _p("[3/5] LLM 构筑队伍 + [4/5] 校验")
    team, raw = builder.build(harness, skill, format_id, blueprint, pools_text)
    errors = validator.validate(team, format_id, skill)
    attempts = 1
    while errors and attempts <= 3:
        _p(f"      第 {attempts} 轮校验失败（{len(errors)} 错），回喂修复")
        team, raw = builder.repair(harness, skill, format_id, blueprint, pools_text,
                                   raw, errors)
        errors = validator.validate(team, format_id, skill)
        attempts += 1
    if errors:
        raise TeamBuildError("修复 3 轮仍未通过校验：\n- " + "\n- ".join(errors))
    _p(f"      校验通过（{attempts} 轮）")

    _p("[5/5] 入库 teams.db")
    saved = repository.save_team(
        team, format_id=format_id, requirement=requirement,
        skill_version=skill_version, model=harness.model)

    return BuildResult(
        team_id=saved["id"], name=saved["name"], display_name=saved["display_name"],
        team=team, strategy=blueprint["strategy"], attempts=attempts,
        skill_version=skill_version, model=harness.model,
        pool_sizes=[len(p) for p in pools], usage=harness.stats.summary())
