"""队伍管理 API：列出 / 详情 / 创建 / 删除 / 本地校验。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class TeamCreateRequest(BaseModel):
    name: str
    template: dict[str, Any]


class TeamValidateRequest(BaseModel):
    format: str | None = None


class TeamsStore:
    """训练家队伍目录的极简封装（可注入自定义目录便于测试）。"""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        if not re.fullmatch(r"[0-9A-Za-z_\-]+", name):
            raise HTTPException(status_code=400, detail="队伍名只能包含字母、数字、下划线和连字符")
        return self.root / f"{name}.json"

    def list(self) -> list[dict[str, Any]]:
        teams: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("*.json")):
            try:
                template = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            members = template.get("team")
            teams.append(
                {
                    "name": path.stem,
                    "format": template.get("format"),
                    "pokemon_count": len(members) if isinstance(members, list) else 0,
                }
            )
        return teams

    def get(self, name: str) -> dict[str, Any] | None:
        path = self._path(name)
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=500, detail=f"队伍文件解析失败：{exc}") from exc

    def create(self, name: str, template: dict[str, Any]) -> dict[str, Any]:
        path = self._path(name)
        if path.exists():
            raise HTTPException(status_code=409, detail=f"队伍已存在：{name}")
        members = template.get("team")
        if not isinstance(members, list) or not members:
            raise HTTPException(status_code=400, detail="template.team 必须是非空列表")
        payload = dict(template)
        payload.setdefault("name", name)
        payload.setdefault("format", "gen9bssregi")
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return payload

    def delete(self, name: str) -> bool:
        path = self._path(name)
        if not path.is_file():
            return False
        path.unlink()
        return True


def create_teams_router(store: TeamsStore) -> APIRouter:
    router = APIRouter(prefix="/api/teams", tags=["teams"])

    @router.get("")
    def list_teams() -> dict[str, Any]:
        return {"teams": store.list()}

    @router.get("/{name}")
    def get_team(name: str) -> dict[str, Any]:
        template = store.get(name)
        if template is None:
            raise HTTPException(status_code=404, detail=f"队伍不存在：{name}")
        return {"name": name, "team": template}

    @router.post("")
    def create_team(request: TeamCreateRequest) -> dict[str, Any]:
        return store.create(request.name, request.template)

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
