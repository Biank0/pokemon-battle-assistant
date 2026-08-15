"""team_validator 工具：包装本地校验与 Showdown 权威校验。"""

from __future__ import annotations

from typing import Any

from pokemon_battle_assistant.showdown_validator import validate_showdown_team
from pokemon_battle_assistant.team_converter import template_to_showdown_text
from pokemon_battle_assistant.validators import validate_trainer_data

DEFAULT_FORMAT = "gen9bssregi"


def validate_team(
    team: Any,
    format: str = DEFAULT_FORMAT,
    *,
    run_showdown: bool = True,
) -> dict[str, Any]:
    """校验队伍模板，返回统一的工具结果 dict。"""
    template: dict[str, Any]
    if isinstance(team, list):
        template = {"team": team}
    elif isinstance(team, dict) and isinstance(team.get("team"), list):
        template = dict(team)
    else:
        return {
            "ok": False,
            "valid": False,
            "format": format,
            "errors": ["team 参数需要是包含 team 列表的模板 dict，或直接传宝可梦列表"],
            "warnings": [],
            "local": None,
            "showdown": None,
        }

    template.setdefault("format", format)
    local = validate_trainer_data(template)
    errors = list(local.errors)
    warnings = list(local.warnings)
    result: dict[str, Any] = {
        "ok": local.ok,
        "valid": local.ok,
        "format": format,
        "errors": errors,
        "warnings": warnings,
        "local": local.to_dict(),
        "showdown": None,
    }
    if local.ok and run_showdown:
        showdown = validate_showdown_team(template_to_showdown_text(template), format)
        result["showdown"] = showdown.to_dict()
        warnings.extend(showdown.warnings)
        if showdown.checked and not showdown.ok:
            result["ok"] = False
            result["valid"] = False
            errors.extend(showdown.errors)
    return result
