"""建队 skill 加载器 —— 版本化知识包的拼装入口。

知识包结构（以 v1 为例）::

    skills/team_building/v1/
        rules.json             # 赛制机器约束（validator 共用）
        method.md              # 建队方法论
        blueprint_contract.md  # planner 阶段输出契约
        team_contract.md       # builder 阶段输出契约

设计要点：rules.json 一份两用——喂 LLM 的条款文本与 validator 的校验字段
同源，杜绝"讲的和查的不一致"。人类可读规则权威源是 data/rules/formats.json。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = SKILL_ROOT.parents[3]
FORMATS_JSON = PROJECT_ROOT / "data" / "rules" / "formats.json"

_STAT_ZH = {"hp": "HP", "atk": "攻击", "def": "防御", "spa": "特攻", "spd": "特防", "spe": "速度"}


@dataclass(frozen=True)
class Skill:
    version: str
    rules: dict            # rules.json 原文
    method_md: str
    blueprint_contract_md: str
    team_contract_md: str

    # ---------------- validator 侧：机器约束 ----------------
    def constraints(self, format_id: str) -> dict:
        """返回赛制的机器可校验约束（validator 用）。未知赛制报错。"""
        try:
            return self.rules["formats"][format_id]
        except KeyError:
            known = "、".join(self.rules["formats"])
            raise KeyError(f"未知赛制 {format_id}（skill v{self.version} 支持：{known}）")

    # ---------------- prompt 侧：文本拼装 ----------------
    def format_rules_text(self, format_id: str) -> str:
        """渲染赛制规则段（机器字段 + formats.json 人类条款）。"""
        c = self.constraints(format_id)
        lines = [f"## 赛制：{c['display_name']}（{format_id}）",
                 f"- 游戏模式：{'双打' if c['game_type'] == 'doubles' else '单打'}",
                 f"- 队伍规模：{c['team_size']} 只",
                 f"- 等级：{c['level']}",
                 f"- 道具子句：{'全队道具不可重复' if not c['allow_dup_items'] else '允许重复道具'}",
                 f"- 同族子句：{'不可重复物种' if not c['allow_dup_species'] else '允许重复物种'}"]
        # 并入 data/rules/formats.json 的人类条款（权威叙述）
        try:
            fmts = json.loads(FORMATS_JSON.read_text(encoding="utf-8"))
            for f in fmts.get("formats", []):
                if f.get("id") == format_id:
                    for r in f.get("rules", []):
                        lines.append(f"- {r}")
                    break
        except (OSError, json.JSONDecodeError):
            pass  # 条款文本缺失不阻断（机器字段已够）
        return "\n".join(lines)

    def blueprint_prompt(self, format_id: str, requirement: str) -> list[dict]:
        """planner 阶段的完整 messages。"""
        return [
            {"role": "system", "content":
                "你是宝可梦建队规划师。严格按输出契约返回纯 JSON。\n\n"
                + self.format_rules_text(format_id) + "\n\n" + self.blueprint_contract_md},
            {"role": "user", "content": f"用户建队需求：{requirement}"},
        ]

    def builder_prompt(self, format_id: str, blueprint: dict, pools_text: str) -> list[dict]:
        """builder 阶段的完整 messages（蓝图 + 候选池 + 全部知识）。"""
        return [
            {"role": "system", "content":
                "你是宝可梦对战队伍构筑师。严格按输出契约返回纯 JSON。\n\n"
                + self.format_rules_text(format_id) + "\n\n"
                + self.method_md + "\n\n" + self.team_contract_md},
            {"role": "user", "content":
                "# 队伍蓝图\n```json\n"
                + json.dumps(blueprint, ensure_ascii=False, indent=2)
                + "\n```\n\n# 候选宝可梦池（每只含种族值/特性/代表招，slug 原样使用）\n"
                + pools_text},
        ]

    def repair_prompt(self, format_id: str, blueprint: dict, pools_text: str,
                      team_json: str, errors: list[str]) -> list[dict]:
        """builder 修复轮：原 prompt + 已产出 + 错误清单。"""
        msgs = self.builder_prompt(format_id, blueprint, pools_text)
        msgs.append({"role": "assistant", "content": team_json})
        msgs.append({"role": "user", "content":
                     "校验未通过，错误清单如下（逐条修复，输出修正后的完整队伍 JSON）：\n- "
                     + "\n- ".join(errors)})
        return msgs


def load(version: str = "v1") -> Skill:
    """加载指定版本的知识包。"""
    d = SKILL_ROOT / version
    if not d.is_dir():
        raise FileNotFoundError(f"skill 版本不存在: {d}")
    return Skill(
        version=version,
        rules=json.loads((d / "rules.json").read_text(encoding="utf-8")),
        method_md=(d / "method.md").read_text(encoding="utf-8"),
        blueprint_contract_md=(d / "blueprint_contract.md").read_text(encoding="utf-8"),
        team_contract_md=(d / "team_contract.md").read_text(encoding="utf-8"),
    )
