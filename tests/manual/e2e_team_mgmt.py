#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三个改进点的端到端验收：建→查（种族值）→改→删。跑完即清理。"""
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8300"

EXPORT = """Urshifu-Rapid-Strike @ Choice Scarf
Ability: Unseen Fist
Level: 50
Tera Type: Water
EVs: 252 Atk / 4 SpD / 252 Spe
Jolly Nature
- Surging Strikes
- Aqua Jet
- Close Combat
- U-turn

Indeedee-F @ Psychic Seed
Ability: Psychic Surge
Level: 50
Tera Type: Psychic
EVs: 252 HP / 252 SpA / 4 SpD
Quiet Nature
- Expanding Force
- Follow Me
- Helping Hand
- Protect

Incineroar @ Sitrus Berry
Ability: Intimidate
Level: 50
Tera Type: Ghost
EVs: 252 HP / 4 Atk / 252 SpD
Careful Nature
- Flare Blitz
- Darkest Lariat
- Close Combat
- Earthquake

Rillaboom @ Assault Vest
Ability: Grassy Surge
Level: 50
Tera Type: Grass
EVs: 252 Atk / 4 SpD / 252 Spe
Adamant Nature
- Wood Hammer
- Solar Blade
- Drain Punch
- Earthquake

Amoonguss @ Rocky Helmet
Ability: Regenerator
Level: 50
Tera Type: Water
EVs: 252 HP / 4 Def / 252 SpD
Calm Nature
- Spore
- Rage Powder
- Pollen Puff
- Protect

Arcanine-Hisui @ Choice Band
Ability: Intimidate
Level: 50
Tera Type: Rock
EVs: 4 HP / 252 Atk / 252 Spe
Jolly Nature
- Flare Blitz
- Rock Slide
- Extreme Speed
- Close Combat
"""


def req(method, path, body=None, expect=200):
    r = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
        method=method)
    try:
        with urllib.request.urlopen(r) as resp:
            code, data = resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        code, data = e.code, e.read().decode()
    return code, data


ok = 0

# 1. 创建
code, d = req("POST", "/api/teams", {
    "display_name": "E2E验收·雨天水熊",
    "format": "gen9bssregi",
    "export_text": EXPORT,
})
assert code == 201, f"创建失败 {code}: {d}"
name = d["name"]
print(f"[1] 创建成功 name={name}")
ok += 1

# 2. 详情带种族值
code, d = req("GET", f"/api/teams/{name}")
assert code == 200, f"详情失败 {code}: {d}"
m0 = d["members"][0]
assert m0["stats"] and m0["stats"]["bst"] > 0, "缺少种族值"
assert m0["stats"]["spe"] > 0, "速度种族值缺失"
print(f"[2] 详情含种族值：{m0['name_zh']} HP{m0['stats']['hp']}/攻{m0['stats']['atk']}/速{m0['stats']['spe']} BST={m0['stats']['bst']}")
ok += 1

# 3. 改名
code, d = req("PUT", f"/api/teams/{name}", {"display_name": "E2E验收·已改名"})
assert code == 200, f"改名失败 {code}: {d}"
code, d = req("GET", f"/api/teams/{name}")
assert d["display_name"] == "E2E验收·已改名", "改名未生效"
print("[3] 改名成功")
ok += 1

# 4. 列表 source=manual
code, teams = req("GET", "/api/teams")
hit = [t for t in teams if t["name"] == name]
assert hit and hit[0]["source"] == "manual", "列表未显示 manual 来源"
print("[4] 列表显示 source=manual")
ok += 1

# 5. 删除
code, d = req("DELETE", f"/api/teams/{name}", expect=200)
assert code == 200, f"删除失败 {code}: {d}"
code, d = req("GET", f"/api/teams/{name}")
assert code == 404, "删除后仍可访问"
print("[5] 删除成功（404 确认）")
ok += 1

# 6. 校验闸门：非法 EV 必须被拦
bad = EXPORT.replace("EVs: 252 Atk / 4 SpD / 252 Spe", "EVs: 999 Atk / 999 Spe", 1)
code, d = req("POST", "/api/teams", {
    "display_name": "非法队", "format": "gen9bssregi", "export_text": bad})
assert code in (400, 422), f"非法 EV 未被拦截: {code}"
print(f"[6] 非法 EV 被拦截（HTTP {code}）")
ok += 1

# 7. 解析错误提示友好
code, d = req("POST", "/api/teams", {
    "display_name": "x", "format": "gen9bssregi", "export_text": "Pikachuuu @ Nothing"})
assert code == 400 and "不认识" in str(d), f"错误提示不友好: {code} {d}"
print(f"[7] 解析错误中文提示：{json.loads(d)['detail'][:50]}")
ok += 1

print(f"\n全部通过 {ok}/7")
