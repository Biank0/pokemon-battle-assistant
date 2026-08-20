"""像素精灵图下载管线：dex.db 物种 → frontend/vendor/sprites/{slug}.png。

图片源：PokeAPI/sprites 官方仓库（raw.githubusercontent），仓库按**图鉴编号**命名。
映射策略：
  - 基础形态（base_species IS NULL）→ {num}.png
  - 形态条目（mega/冠/地区形态等，仓库通常无图）→ 回退基础形态图（与 dex 校验同源）
  - 全部落盘为 {species.id}.png —— 前端零映射、零回退逻辑，直接 <img src=/sprites/九尾slug>
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEX_DB = ROOT / "data" / "dex" / "dex.db"
OUT_DIR = ROOT / "frontend" / "vendor" / "sprites"
SRC = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{num}.png"


def species_rows() -> list[tuple[str, int, str | None]]:
    """(species_id, num, base_species)"""
    conn = sqlite3.connect(f"file:{DEX_DB}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT id, num, base_species FROM species ORDER BY num").fetchall()
    conn.close()
    return rows


def resolve_target(rows: list[tuple[str, int, str | None]]
                   ) -> dict[str, tuple[int, str]]:
    """slug → (下载用 num, 来源 slug)。形态条目回退到基础形态的 num。"""
    num_of: dict[str, int] = {s: n for s, n, _ in rows}
    out: dict[str, tuple[int, str]] = {}
    for sid, num, base in rows:
        src_slug = base or sid
        out[sid] = (num_of.get(src_slug, num), src_slug)
    return out


def download(targets: dict[str, tuple[int, str]], *, force: bool = False) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    todo = {s: v for s, v in targets.items()
            if force or not (OUT_DIR / f"{s}.png").exists()}
    if not todo:
        print(f"已是最新：{len(targets)} 张精灵图全部在库，无需下载")
        return
    print(f"待下载 {len(todo)} / {len(targets)} 张 → {OUT_DIR}")

    # 按 num 去重下载（同图鉴编号的形态共用一张图）
    num_to_slugs: dict[int, list[str]] = {}
    slug_src: dict[str, str] = {}
    for slug, (num, src) in todo.items():
        num_to_slugs.setdefault(num, []).append(slug)
        slug_src[slug] = src

    ok, fail = 0, 0
    items = list(num_to_slugs.items())
    with httpx.Client(timeout=20.0) as client:
        for i, (num, slugs) in enumerate(items, 1):
            try:
                r = client.get(SRC.format(num=num))
                if r.status_code == 200 and r.content[:8].startswith(b"\x89PNG"):
                    for slug in slugs:
                        (OUT_DIR / f"{slug}.png").write_bytes(r.content)
                        ok += 1
                else:
                    print(f"  [{i}/{len(items)}] num={num} ({slugs[0]}…): "
                          f"HTTP {r.status_code}（{len(slugs)} 个 slug 跳过）")
                    fail += len(slugs)
            except httpx.HTTPError as e:
                print(f"  [{i}/{len(items)}] num={num}: {type(e).__name__}（跳过）")
                fail += len(slugs)
            if i % 100 == 0:
                print(f"  进度 {i}/{len(items)}（成功 {ok}）")
                time.sleep(0.5)  # 礼貌限速
    print(f"完成：成功 {ok}，跳过/失败 {fail}，目录现有 "
          f"{len(list(OUT_DIR.glob('*.png')))} 张")


def main() -> None:
    ap = argparse.ArgumentParser(description="下载官方像素精灵图到本地 vendor")
    ap.add_argument("--all", action="store_true", help="全量重下（默认增量补缺）")
    ap.add_argument("--slugs", type=str, default="", help="逗号分隔的指定 slug 列表")
    args = ap.parse_args()

    rows = species_rows()
    targets = resolve_target(rows)
    if args.slugs:
        wanted = {s.strip() for s in args.slugs.split(",") if s.strip()}
        targets = {s: v for s, v in targets.items() if s in wanted}
        missing = wanted - targets.keys()
        if missing:
            print(f"警告：dex 中不存在 {sorted(missing)}")
    download(targets, force=args.all)


if __name__ == "__main__":
    sys.exit(main())
