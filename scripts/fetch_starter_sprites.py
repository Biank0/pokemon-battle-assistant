"""生成入场精灵图包清单并触发下载：全部队伍成员 ∪ 对战出现的宝可梦。"""
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

slugs: set[str] = set()

conn = sqlite3.connect(ROOT / "data" / "teams" / "teams.db")
for (s,) in conn.execute("SELECT DISTINCT species_id FROM team_members"):
    slugs.add(s)
conn.close()

conn = sqlite3.connect(ROOT / "data" / "battles" / "battles.db")
for (s,) in conn.execute(
        "SELECT DISTINCT actor_species FROM battle_turns WHERE actor_species IS NOT NULL "
        "UNION SELECT DISTINCT target_species FROM battle_turns "
        "WHERE target_species IS NOT NULL"):
    slugs.add(s)
conn.close()

print(f"入场包物种数：{len(slugs)}")
subprocess.run(
    [sys.executable, str(ROOT / "scripts" / "download_sprites.py"),
     "--slugs", ",".join(sorted(slugs))], check=False)
