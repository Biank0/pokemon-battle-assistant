"""数据目录统一入口：三类数据的路径定义与队伍名解析。

数据三分法（data/ 下共三个顶层目录，职责互不重叠）：

① dex/    宝可梦及道具图鉴 —— 只读参考数据，由 Pokemon Showdown 提取
           （showdown_db.json + translations/ 中英对照表）

② rules/  对战规则 —— formats.json 结构化规则 + docs/ 人类可读的规则说明

③ teams/  队伍数据库 —— 按来源分两个子目录：
           - lab/       实验室队伍：用户手工预制、用来做对战实验的队伍
           - generated/ 生成队伍：系统（AI 建队模块）生成的队伍
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"

# ① 宝可梦及道具
DEX_DIR = DATA_DIR / "dex"
DEX_DB_PATH = DEX_DIR / "showdown_db.json"
DEX_TRANSLATIONS_PATH = DEX_DIR / "translations" / "zh_cn_names.json"

# ② 对战规则
RULES_DIR = DATA_DIR / "rules"
FORMATS_JSON_PATH = RULES_DIR / "formats.json"
RULES_DOCS_DIR = RULES_DIR / "docs"

# ③ 队伍数据库
TEAMS_DIR = DATA_DIR / "teams"
LAB_TEAMS_DIR = TEAMS_DIR / "lab"
GENERATED_TEAMS_DIR = TEAMS_DIR / "generated"

TEAM_SOURCES = ("lab", "generated")


def team_dir(source: str) -> Path:
    """来源名（lab / generated）→ 对应目录。"""
    if source == "lab":
        return LAB_TEAMS_DIR
    if source == "generated":
        return GENERATED_TEAMS_DIR
    raise ValueError(f"未知队伍来源：{source}（可选：lab / generated）")


def iter_team_files() -> list[tuple[str, Path]]:
    """列出全部队伍文件，返回 (source, path) 列表，按来源与文件名排序。"""
    result: list[tuple[str, Path]] = []
    for source in TEAM_SOURCES:
        directory = team_dir(source)
        directory.mkdir(parents=True, exist_ok=True)
        result.extend((source, path) for path in sorted(directory.glob("*.json")))
    return result


def available_team_names() -> list[str]:
    """全部队伍名（不含 .json 后缀），跨 lab / generated 两个目录。"""
    return sorted({path.stem for _, path in iter_team_files()})


def resolve_team_path(name_or_path: str) -> Path:
    """按名字或路径找队伍文件：先查 lab/，再查 generated/。

    接受以下写法（与旧版 resolve_trainer_path 行为一致）：
      - xiaobian
      - xiaobian.json
      - 相对/绝对路径的 JSON 文件
    找不到时返回 lab/ 下的推测路径（让上层报「文件不存在」而不是崩溃）。
    """
    candidate = Path(name_or_path)
    if candidate.exists():
        return candidate

    if candidate.suffix == ".json" and len(candidate.parts) == 1:
        for directory in (LAB_TEAMS_DIR, GENERATED_TEAMS_DIR):
            team_candidate = directory / candidate.name
            if team_candidate.exists():
                return team_candidate

    if candidate.suffix == ".json":
        return candidate

    return LAB_TEAMS_DIR / f"{name_or_path}.json"
