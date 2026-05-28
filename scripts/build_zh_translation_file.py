"""Build a local full Chinese name table from PokéAPI.

This script needs internet access only when rebuilding the cache.  Runtime report
generation reads the generated local file and does not call the network.

Run:
    cd ~/Bian-workspace/pokemon-battle-assistant
    .venv/bin/python scripts/build_zh_translation_file.py
"""

from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "data" / "translations" / "zh_cn_names.json"
POKEAPI = "https://pokeapi.co/api/v2"
LANGUAGE_PRIORITY = ("zh-hans", "zh-hant")
MAX_WORKERS = 24

_ID_RE = re.compile(r"[^a-z0-9]+")

RESOURCES = {
    "pokemon": "pokemon-species",
    "moves": "move",
    "items": "item",
    "abilities": "ability",
}


def normalize_id(value: Any) -> str:
    text = str(value).strip().lower()
    return _ID_RE.sub("", text)


def fetch_json(url: str, *, retries: int = 3) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": "pokemon-battle-assistant/0.1"})
            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def list_resource_urls(resource: str) -> list[dict[str, str]]:
    data = fetch_json(f"{POKEAPI}/{resource}?limit=100000&offset=0")
    return data["results"]


def pick_chinese_name(names: list[dict[str, Any]]) -> str | None:
    by_lang = {entry.get("language", {}).get("name"): entry.get("name") for entry in names}
    for lang in LANGUAGE_PRIORITY:
        if by_lang.get(lang):
            return by_lang[lang]
    return None


def fetch_name_entry(result: dict[str, str]) -> tuple[str, str] | None:
    data = fetch_json(result["url"])
    zh_name = pick_chinese_name(data.get("names", []))
    if not zh_name:
        return None
    key_candidates = [
        data.get("name"),
        result.get("name"),
    ]
    # Add common display-name fallback for resources that expose a canonical name.
    for entry in data.get("names", []):
        if entry.get("language", {}).get("name") == "en" and entry.get("name"):
            key_candidates.append(entry["name"])
    normalized_keys = [normalize_id(key) for key in key_candidates if key]
    if not normalized_keys:
        return None
    return normalized_keys[0], zh_name


def build_category(category: str, resource: str) -> dict[str, str]:
    print(f"Fetching list: {category} / {resource}")
    results = list_resource_urls(resource)
    print(f"  {category}: {len(results)} entries")

    translations: dict[str, str] = {}
    failures = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_result = {executor.submit(fetch_name_entry, result): result for result in results}
        for index, future in enumerate(as_completed(future_to_result), start=1):
            try:
                entry = future.result()
            except Exception as exc:  # keep generating even if a few entries fail
                failures += 1
                result = future_to_result[future]
                print(f"  warn: failed {category}:{result.get('name')} - {exc}", file=sys.stderr)
                continue
            if entry:
                key, zh_name = entry
                translations[key] = zh_name
            if index % 200 == 0 or index == len(results):
                print(f"  {category}: {index}/{len(results)} done")

    print(f"  {category}: translated={len(translations)}, failures={failures}")
    return dict(sorted(translations.items()))


def main() -> None:
    started = time.time()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    data: dict[str, Any] = {
        "metadata": {
            "source": "https://pokeapi.co/api/v2",
            "language_priority": list(LANGUAGE_PRIORITY),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "normalize_rule": "lowercase and remove non-alphanumeric characters",
        }
    }

    for category, resource in RESOURCES.items():
        data[category] = build_category(category, resource)

    data["metadata"]["counts"] = {
        category: len(data.get(category, {})) for category in RESOURCES
    }
    data["metadata"]["elapsed_seconds"] = round(time.time() - started, 2)

    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    print(json.dumps(data["metadata"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
