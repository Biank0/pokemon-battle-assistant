"""特性/道具效果查询工具：复用 showdown_db.py。

Showdown 数据只有名字没有效果文本，因此内置一份 BSS 常用特性/道具的中文说明表；
未收录的条目返回名字（含中文名），说明留空。
"""

from __future__ import annotations

from typing import Any

from ..showdown_db import get_item, get_pokemon
from ..translation import translate_ability, translate_item, translate_pokemon

KNOWN_ABILITY_NOTES: dict[str, str] = {
    "intimidate": "登场时降低对方全场攻击一级。",
    "protean": "使用招式前把自身属性变为该招式属性（每回合一次）。",
    "libero": "使用招式前把自身属性变为该招式属性（每回合一次）。",
    "sturdy": "满血时任何一击都不会直接击倒（保留1HP）。",
    "multiscale": "满血时受到的伤害减半。",
    "regenerator": "换下场时回复1/3最大HP。",
    "naturalcure": "换下场时治愈异常状态。",
    "levitate": "免疫地面属性招式。",
    "voltabsorb": "受到电属性招式时回复1/4最大HP并免疫伤害。",
    "waterabsorb": "受到水属性招式时回复1/4最大HP并免疫伤害。",
    "flashfire": "受到火属性招式时免疫并强化自身火招式。",
    "roughskin": "接触类攻击方受到1/8最大HP伤害。",
    "ironbarbs": "接触类攻击方受到1/8最大HP伤害。",
    "magicguard": "只受直接攻击伤害，免疫沙暴/毒等间接伤害。",
    "sandstream": "登场时召唤沙暴。",
    "drought": "登场时召唤大晴天。",
    "drizzle": "登场时召唤下雨。",
    "snowwarning": "登场时召唤下雪。",
    "speedboost": "每回合结束时速度提升一级。",
    "moxie": "击倒对方后攻击提升一级。",
    "chlorophyll": "大晴天时速度翻倍。",
    "swiftswim": "下雨时速度翻倍。",
    "sandrush": "沙暴时速度翻倍。",
    "slushrush": "下雪时速度翻倍。",
    "hugepower": "攻击能力值翻倍。",
    "purepower": "攻击能力值翻倍。",
    "technician": "威力<=60的招式威力提高1.5倍。",
    "sheerforce": "有效果附加的招式威力提高1.3倍但附加效果失效。",
    "adaptability": "本系加成从1.5倍提高到2倍。",
    "moldbreaker": "无视对方特性发动。",
    "teravolt": "无视对方特性发动。",
    "turboblaze": "无视对方特性发动。",
    "unaware": "无视对方的能力变化进行攻防计算。",
    "prankster": "变化类招式优先度+1。",
    "guts": "异常状态时攻击1.5倍且免疫灼伤减攻。",
    "marvelscale": "异常状态时防御1.5倍。",
    "poisonheal": "中毒时每回合回复1/8最大HP。",
    "magicbounce": "反弹对方的变化类招式。",
}

KNOWN_ITEM_NOTES: dict[str, str] = {
    "leftovers": "每回合结束回复1/16最大HP。",
    "lifeorb": "招式伤害提高1.3倍，每次攻击损失10%最大HP。",
    "choiceband": "物理招式威力1.5倍，但只能连续使用同一招式。",
    "choicespecs": "特殊招式威力1.5倍，但只能连续使用同一招式。",
    "choicescarf": "速度1.5倍，但只能连续使用同一招式。",
    "focussash": "满血时任何一击都保留1HP（一次性）。",
    "assaultvest": "特防1.5倍，但不能使用变化招式。",
    "heavydutyboots": "免疫隐形岩/撒菱/毒菱等入场伤害。",
    "rockyhelmet": "接触类攻击方损失1/6最大HP。",
    "boosterenergy": "特性为悖谬种时立即启动特性（一次性）。",
    "sitrusberry": "HP低于一半时回复25%最大HP（一次性）。",
    "airballoon": "免疫地面招式一次，被击中后气球消失。",
    "eviolite": "未完全进化的宝可梦防御和特防1.5倍。",
    "blackglasses": "恶属性招式威力1.2倍。",
    "charcoal": "火属性招式威力1.2倍。",
    "mysticwater": "水属性招式威力1.2倍。",
    "miracleseed": "草属性招式威力1.2倍。",
    "magnet": "电属性招式威力1.2倍。",
    "nevermeltice": "冰属性招式威力1.2倍。",
    "twistedspoon": "超能力属性招式威力1.2倍。",
    "silkscarf": "一般属性招式威力1.2倍。",
    "spelltag": "幽灵属性招式威力1.2倍。",
    "dragonsfang": "龙属性招式威力1.2倍。",
    "poisonbarb": "毒属性招式威力1.2倍。",
    "softsand": "地面属性招式威力1.2倍。",
    "sharpbeak": "飞行属性招式威力1.2倍。",
}


def _normalize_id(text: str) -> str:
    return "".join(c for c in text.lower() if c.isalnum())


def lookup_ability(species: str, item: str | None = None) -> dict[str, Any]:
    """查询一只宝可梦的可能特性（含隐藏特性），可选附带道具效果查询。"""
    data = get_pokemon(species)
    if not data:
        return {"ok": False, "error": f"未找到宝可梦：{species}"}

    slot_names = {"0": "常规1", "1": "常规2", "H": "隐藏特性", "S": "特殊"}
    abilities = []
    for slot, name in (data.get("abilities") or {}).items():
        aid = _normalize_id(name)
        zh = translate_ability(name) or name
        abilities.append(
            {
                "slot": slot_names.get(slot, slot),
                "ability": name,
                "zh_name": zh,
                "note": KNOWN_ABILITY_NOTES.get(aid, ""),
            }
        )

    result: dict[str, Any] = {
        "ok": True,
        "species": data.get("name"),
        "zh_name": translate_pokemon(str(data.get("name") or "")) or "",
        "types": data.get("types", []),
        "abilities": abilities,
    }

    if item:
        item_data = get_item(item)
        if item_data:
            iid = _normalize_id(item_data.get("name") or item)
            result["item"] = {
                "name": item_data.get("name"),
                "zh_name": translate_item(item_data.get("name") or "") or "",
                "note": KNOWN_ITEM_NOTES.get(iid, "（暂无说明，仅提供名称）"),
            }
        else:
            result["item"] = {"ok": False, "error": f"未知道具：{item}"}
    return result
