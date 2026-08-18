"""队伍管理 API：列出 / 详情 / 创建 / 删除 / 本地校验。

队伍数据库按来源分两个目录（见 data_paths.py 的三分法）：
- lab/       实验室队伍：用户手工预制、用于对战实验
- generated/ 生成队伍：AI 建队模块产出
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...data_paths import TEAM_SOURCES
from ...translation import translate_ability, translate_item, translate_move, translate_pokemon

# 英文属性 → 中文属性
TYPE_ZH_NAMES: dict[str, str] = {
    "Normal": "一般", "Fire": "火", "Water": "水", "Electric": "电",
    "Grass": "草", "Ice": "冰", "Fighting": "格斗", "Poison": "毒",
    "Ground": "地面", "Flying": "飞行", "Psychic": "超能力", "Bug": "虫",
    "Rock": "岩石", "Ghost": "幽灵", "Dragon": "龙", "Dark": "恶",
    "Steel": "钢", "Fairy": "妖精",
}

# 25 性格英文 → 中文
NATURE_ZH_NAMES: dict[str, str] = {
    "Hardy": "勤奋", "Lonely": "怕寂寞", "Brave": "勇敢", "Adamant": "固执", "Naughty": "顽皮",
    "Bold": "大胆", "Docile": "温顺", "Relaxed": "悠闲", "Impish": "淘气", "Lax": "乐天",
    "Timid": "胆小", "Hasty": "急躁", "Serious": "认真", "Jolly": "爽朗", "Naive": "天真",
    "Modest": "内敛", "Mild": "慢吞吞", "Quiet": "冷静", "Bashful": "害羞", "Rash": "马虎",
    "Calm": "温和", "Gentle": "温柔", "Sassy": "自大", "Careful": "慎重", "Quirky": "浮躁",
}


class TeamCreateRequest(BaseModel):
    name: str
    template: dict[str, Any]
    source: str = "lab"  # lab / generated
    display_name: str | None = None


class TeamValidateRequest(BaseModel):
    format: str | None = None


class TeamsStore:
    """队伍数据库（lab/ + generated/ 双目录）封装，可注入自定义根目录便于测试。"""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        for source in TEAM_SOURCES:
            (self.root / source).mkdir(parents=True, exist_ok=True)

    def _dir(self, source: str) -> Path:
        if source not in TEAM_SOURCES:
            raise HTTPException(status_code=400, detail=f"未知队伍来源：{source}（可选：lab / generated）")
        return self.root / source

    def _validate_name(self, name: str) -> None:
        if not re.fullmatch(r"[0-9A-Za-z_\-]+", name):
            raise HTTPException(status_code=400, detail="队伍名只能包含字母、数字、下划线和连字符")

    def _find(self, name: str) -> Path | None:
        self._validate_name(name)
        for source in TEAM_SOURCES:
            candidate = self._dir(source) / f"{name}.json"
            if candidate.is_file():
                return candidate
        return None

    def list(self, source: str | None = None) -> list[dict[str, Any]]:
        sources: list[str] = [source] if source else list(TEAM_SOURCES)
        teams: list[dict[str, Any]] = []
        for src in sources:
            for path in sorted(self._dir(src).glob("*.json")):
                try:
                    template = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                members = template.get("team")
                teams.append(
                    {
                        "name": path.stem,
                        "display_name": template.get("display_name") or path.stem,
                        "source": src,
                        "format": template.get("format"),
                        "pokemon_count": len(members) if isinstance(members, list) else 0,
                    }
                )
        return teams

    def get(self, name: str) -> dict[str, Any] | None:
        path = self._find(name)
        if path is None:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=500, detail=f"队伍文件解析失败：{exc}") from exc

    def create(
        self,
        name: str,
        template: dict[str, Any],
        *,
        source: str = "lab",
        display_name: str | None = None,
    ) -> dict[str, Any]:
        self._validate_name(name)
        path = self._dir(source) / f"{name}.json"
        if path.exists():
            raise HTTPException(status_code=409, detail=f"队伍已存在：{name}（{source}）")
        members = template.get("team")
        if not isinstance(members, list) or not members:
            raise HTTPException(status_code=400, detail="template.team 必须是非空列表")
        payload = dict(template)
        payload.setdefault("name", name)
        payload.setdefault("format", "gen9bssregi")
        payload["source"] = source
        if display_name:
            payload.setdefault("display_name", display_name)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return payload

    def delete(self, name: str) -> bool:
        path = self._find(name)
        if path is None:
            return False
        path.unlink()
        return True


def _pokemon_types(species: Any) -> list[str]:
    """从本地图鉴查属性；模板自带 types 时优先用模板的。"""
    if not species:
        return []
    from ...showdown_db import get_pokemon

    entry = get_pokemon(str(species))
    types = entry.get("types") if entry else None
    return [str(t) for t in types] if isinstance(types, list) else []


def translate_member_zh(member: dict[str, Any]) -> dict[str, Any]:
    """把队伍模板里的一只宝可梦转成中文摘要（保留英文回退）。"""
    species = member.get("species")
    types = [str(t) for t in member.get("types") or []] or _pokemon_types(species)
    item = member.get("item")
    ability = member.get("ability")
    nature = member.get("nature")
    tera_type = member.get("tera_type")
    return {
        "species": species,
        "species_zh": translate_pokemon(species),
        "level": member.get("level"),
        "types": types,
        "types_zh": [TYPE_ZH_NAMES.get(t, t) for t in types],
        "item": item,
        "item_zh": translate_item(item) if item else None,
        "ability": ability,
        "ability_zh": translate_ability(ability) if ability else None,
        "nature": nature,
        "nature_zh": NATURE_ZH_NAMES.get(str(nature), nature) if nature else None,
        "tera_type": tera_type,
        "tera_type_zh": TYPE_ZH_NAMES.get(str(tera_type), tera_type) if tera_type else None,
        "moves": list(member.get("moves") or []),
        "moves_zh": [translate_move(move) for move in member.get("moves") or []],
    }


def translate_team_zh(template: dict[str, Any]) -> list[dict[str, Any]]:
    """整支队伍的中文摘要，顺序与 template.team 一致。"""
    members = template.get("team")
    if not isinstance(members, list):
        return []
    return [translate_member_zh(m) if isinstance(m, dict) else {} for m in members]


def create_teams_router(store: TeamsStore) -> APIRouter:
    router = APIRouter(prefix="/api/teams", tags=["teams"])

    @router.get("")
    def list_teams(source: str | None = None) -> dict[str, Any]:
        return {"teams": store.list(source)}

    @router.get("/{name}")
    def get_team(name: str) -> dict[str, Any]:
        template = store.get(name)
        if template is None:
            raise HTTPException(status_code=404, detail=f"队伍不存在：{name}")
        return {
            "name": name,
            "display_name": template.get("display_name") or name,
            "team": template,
            "team_zh": translate_team_zh(template),
        }

    @router.post("")
    def create_team(request: TeamCreateRequest) -> dict[str, Any]:
        return store.create(
            request.name,
            request.template,
            source=request.source,
            display_name=request.display_name,
        )

    @router.delete("/{name}")
    def delete_team(name: str) -> dict[str, Any]:
        if not store.delete(name):
            raise HTTPException(status_code=404, detail=f"队伍不存在：{name}")
        return {"deleted": name}

    @router.post("/{name}/validate")
    def validate_team_endpoint(name: str, request: TeamValidateRequest) -> dict[str, Any]:
        template = store.get(name)
        if template is None:
            raise HTTPException(status_code=404, detail=f"队伍不存在：{name}")
        from ...tools.team_validator import validate_team

        battle_format = request.format or template.get("format") or "gen9bssregi"
        return validate_team(template, battle_format, run_showdown=False)

    return router
