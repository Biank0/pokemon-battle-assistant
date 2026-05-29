# 对战环境结构

第一阶段只搭建对战环境，不开发助手、启发式策略或 RL 算法。

当前对战环境按三条轴线组织：

```text
Battle Kind      Team Source       Control Mode
单打 / 双打   ×  随机 / 模版   ×  随机基线 / 用户手动 / 未来外部 agent
```

## 1. Battle Kind：单打 / 双打

由 Showdown format 决定：

| 类型 | 示例 format | 说明 |
|---|---|---|
| 单打 | `gen9ou`, `gen9randombattle` | 单只 active Pokémon |
| 双打 | `gen9randomdoublesbattle`, `gen9doublesou` | 两只 active Pokémon，legal order 是组合动作 |

环境记录中会写入：

```json
{
  "game_type": "singles | doubles"
}
```

双打时：

```text
active_pokemon: [slot1, slot2]
available_moves: [[slot1 moves], [slot2 moves]]
legal_order_messages: ["/choose move ..., move ..."]
```

## 2. Team Source：随机 / 模版

| 来源 | 指令 | 说明 |
|---|---|---|
| 随机队伍 | `pba random-battle --format ...` | 队伍由 Showdown 随机生成 |
| 导入模版 | `pba battle <template> --opponent <template>` | 队伍来自 `data/trainers/*.json` |

示例：

```bash
pba random-battle --format gen9randombattle
pba random-battle --format gen9randomdoublesbattle
pba battle data/trainers/xiaobian.json --opponent data/trainers/example_team.json --format gen9ou
```

## 3. Control Mode：随机基线 / 用户手动 / 未来外部 agent

| 控制方式 | 当前状态 | 说明 |
|---|---|---|
| `random` | 已支持 | 环境基线，从 legal actions 中随机选 |
| `manual` | 已支持 | 终端列出 legal actions，由用户输入编号 |
| external agent / RL | 预留 | 后续接 action provider，不在第一阶段实现策略 |

示例：

```bash
# 用户手动操作玩家 1，玩家 2 随机
pba random-battle --format gen9randomdoublesbattle --manual

# 等价写法
pba random-battle --format gen9randomdoublesbattle --player1-control manual --player2-control random

# 模版队伍，用户手动操作玩家 1
pba battle data/trainers/xiaobian.json --opponent data/trainers/example_team.json --format gen9ou --manual
```

手动模式每个决策点会显示：

```text
# 手动操作决策点
player: player_1
battle_tag: ...
turn: ...
game_type: singles/doubles
我方在场: ...
对方在场: ...
合法动作:
   1. /choose move ...
   2. /choose switch ...
请选择 player_1 的动作编号:
```

## 当前 CLI 能力矩阵

| Battle Kind | Team Source | Control Mode | 示例 |
|---|---|---|---|
| 单打 | 随机 | 随机基线 | `pba random-battle --format gen9randombattle` |
| 双打 | 随机 | 随机基线 | `pba random-battle --format gen9randomdoublesbattle` |
| 单打 | 随机 | 用户手动 | `pba random-battle --format gen9randombattle --manual` |
| 双打 | 随机 | 用户手动 | `pba random-battle --format gen9randomdoublesbattle --manual` |
| 单打 | 模版 | 随机基线 | `pba battle team_a.json --opponent team_b.json --format gen9ou` |
| 单打 | 模版 | 用户手动 | `pba battle team_a.json --opponent team_b.json --format gen9ou --manual` |
| 双打 | 模版 | 随机/手动 | 结构已支持，前提是模版队伍满足对应 doubles format 的合法性 |

## 导出数据

每局输出：

```text
battle_outputs/<battle_tag>/
├── replay.html
├── record.json
├── report.md
└── steps.jsonl
```

`record.json` / `steps.jsonl` 中记录：

```text
observation
legal_actions
chosen_action
control_modes
battle_kind
team_source_kind
```

注意：当前 `BattleRunner` 是完整跑局并导出数据的 runner，不是交互式 `reset()/step()` RL 环境。


## 用户友好命令

环境检查：

```bash
pba env check
pba env check --json
```

队伍基础校验：

```bash
pba team validate xiaobian
pba team validate data/trainers/xiaobian.json
```

`team validate` 做本地基础检查，例如 JSON、宝可梦数量、招式数量、中文招式残留、EV/IV 范围等。Showdown 完整合法性仍以实际对战时的 server 校验为准。
