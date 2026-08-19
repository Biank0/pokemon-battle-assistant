# 队伍输出契约（builder 阶段）

你将收到：队伍蓝图（角色位说明）+ 每个角色位的候选宝可梦池 + 赛制规则 + 建队方法论。

你的任务：从候选池中为每个角色位选定一只宝可梦，给出完整配置，组成一支可直接对战队伍。

## 输出格式（纯 JSON，无 markdown 包裹）

```json
{
  "name_en": "english_team_id",
  "display_name": "中文队名",
  "strategy_notes": "2~4 句中文战术说明：怎么打、怕什么、换人思路",
  "members": [
    {
      "slot_role": "对应蓝图的 role_zh",
      "species": "species_slug",
      "ability": "ability_slug",
      "item": "item_slug 或 null",
      "nature": "nature_slug",
      "tera_type": "Fire",
      "level": 50,
      "moves": ["move_slug1", "move_slug2", "move_slug3", "move_slug4"],
      "evs": {"hp": 0, "atk": 252, "def": 0, "spa": 0, "spd": 4, "spe": 252},
      "ivs": {"hp": 31, "atk": 31, "def": 31, "spa": 31, "spd": 31, "spe": 31}
    }
  ]
}
```

## 字段规则（硬性，违反会被校验拒收）

- **所有 slug 必须原样使用候选池/数据给出的写法**（小写、无空格无符号）；species 必须从候选池中选，不得使用池外宝可梦；
- `ability` 必须是该物种候选池列出的特性之一；
- `moves`：恰好 4 招，优先从候选池的"代表招"里选；自己补充的招必须真实存在且该宝可梦学得会；
- `item`：全队不可重复（BSS/VGC）；确实不带写 null；
- `nature`：25 性格之一（如 timid / adamant / bold）；
- `tera_type`：18 属性之一（英文首字母大写，如 "Ghost"）；
- `level`：按赛制（BSS/VGC=50，OU=100）；
- `evs`：六维齐全、单项 0~252、总和 ≤510；`ivs` 六维齐全、0~31（不投的物理项可写 0）；
- `members` 恰好 6 只，slot_role 覆盖蓝图各角色位；
- `name_en`：小写英文+下划线（如 sun_hyper_offense），是队伍的文件标识；
- `display_name`：中文队名（如"晴之疾风·特攻压制队"）。

## 修复约定

如果收到"校验错误清单"，你必须输出**修正后的完整队伍 JSON**（同样格式），只修错误项，其余保持不变。
