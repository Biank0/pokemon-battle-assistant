"""分析 skill 加载器 —— 与 team_building/skill.py 同构的版本化知识包。

    skills/battle_analysis/v1/
        method.md            # 分析方法论（五层：战绩/阵容/对位/威胁/建议）
        report_contract.md   # 输出 JSON 契约（validator 共用同一份文本）
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class AnalysisSkill:
    version: str
    method_md: str
    contract_md: str

    def prompt(self, distilled_text: str, focus: str = "") -> list[dict]:
        """完整 messages：方法论 + 契约 + 蒸馏数据（+ 用户关注点）。"""
        focus_block = (f"\n\n# 用户特别关注\n{focus}\n（优先回应此关注点，其余照常分析）"
                       if focus.strip() else "")
        return [
            {"role": "system", "content":
                "你是宝可梦对战复盘分析师。严格按输出契约返回纯 JSON。\n\n"
                + self.method_md + "\n\n" + self.contract_md},
            {"role": "user", "content":
                "# 跑量会话蒸馏数据\n```json\n" + distilled_text + "\n```"
                + focus_block},
        ]

    def repair_prompt(self, distilled_text: str, focus: str, report_json: str,
                      errors: list[str]) -> list[dict]:
        """修复轮：原 prompt + 已产出 + 校验错误清单。"""
        msgs = self.prompt(distilled_text, focus)
        msgs.append({"role": "assistant", "content": report_json})
        msgs.append({"role": "user", "content":
                     "校验未通过，错误清单如下（逐条修复，输出修正后的完整报告 JSON）：\n- "
                     + "\n- ".join(errors)})
        return msgs


def load(version: str = "v1") -> AnalysisSkill:
    d = SKILL_ROOT / version
    if not d.is_dir():
        raise FileNotFoundError(f"skill 版本不存在: {d}")
    return AnalysisSkill(
        version=version,
        method_md=(d / "method.md").read_text(encoding="utf-8"),
        contract_md=(d / "report_contract.md").read_text(encoding="utf-8"),
    )
