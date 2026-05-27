# Pokémon Showdown 源码导读笔记

本文档记录本地 fork 的 Pokémon Showdown 源码导读方向，帮助本项目学习其 Battle Model、Dex 数据、规则集、双打目标选择和 Champions 规则实现方式。

本地参考仓库位置：

```text
/Users/jyxc-dz-0101021/Bian-workspace/pokemon-showdown
```

远程仓库：

```text
origin   https://github.com/Biank0/pokemon-showdown.git
upstream https://github.com/smogon/pokemon-showdown.git
```

> 说明：Pokémon Showdown 是参考实现和学习对象，不建议直接把它的源码混入本项目。我们的项目目标是智能对战分析、博弈推理、复盘、配队推荐、RL/LLM 研究，因此应学习其规则和数据设计，再抽象出适合本项目的 Battle Model 与 Game Theory Model。

## 一、源码整体目录

重点目录：

```text
pokemon-showdown/
├── data/             # 主数据：宝可梦、招式、特性、道具、规则等
├── data/mods/        # 不同世代/特殊规则的 mod 数据
├── sim/              # 对战模拟器核心
├── config/           # ladder / format 配置
├── server/           # 在线服务、房间、用户、replay 等服务器逻辑
├── test/             # 大量规则和模拟器测试
├── tools/            # 工具脚本
└── translations/     # 多语言翻译
```

对本项目最重要的是：

```text
sim/
data/
data/mods/
config/formats.ts
test/sim/
```

其中 `server/` 对在线对战平台很重要，但不是我们第一阶段学习重点。

## 二、优先阅读顺序

建议不要试图一次性通读源码。推荐按以下顺序看：

```text
1. sim/README.md
2. sim/SIMULATOR.md
3. sim/SIM-PROTOCOL.md
4. sim/DEX.md
5. sim/battle.ts
6. sim/side.ts
7. sim/pokemon.ts
8. sim/battle-actions.ts
9. sim/battle-queue.ts
10. sim/field.ts
11. data/typechart.ts、data/moves.ts、data/pokedex.ts、data/abilities.ts、data/items.ts
12. config/formats.ts
13. data/mods/champions/
14. test/sim/
```

## 三、sim/：对战模拟器核心

### 1. `sim/index.ts`

这是 simulator 对外导出的入口。

关键导出：

```ts
export { Battle } from './battle';
export { BattleStream, getPlayerStreams } from './battle-stream';
export { Pokemon } from './pokemon';
export { PRNG } from './prng';
export { Side } from './side';
export { Dex, toID } from './dex';
export { Teams } from './teams';
export { TeamValidator } from './team-validator';
```

对本项目的启发：

```text
- Battle / Pokemon / Side / Field / Dex 分工非常清晰。
- 我们的 Battle Model 也应拆成类似层次。
- 对外 API 不应该暴露太多内部细节，应有稳定入口。
```

### 2. `sim/battle.ts`

`Battle` 是对战核心对象。

它大致负责：

```text
- 保存整场对战状态
- 管理双方 Side
- 管理 Field
- 处理事件系统
- 管理回合流程
- 输出 battle log
- 处理胜负
- 调用 action queue 和 battle actions
```

对本项目的启发：

```text
BattleState 不应该只是一个 dict，而应是多层对象组合：
Battle -> Side -> Pokemon -> Move / Ability / Item / Volatile / Status
```

我们可以学习其对象边界，但不一定照搬 TypeScript 实现。

### 3. `sim/side.ts`

`Side` 表示一方玩家。

重点关注：

```text
- side.pokemon：整支队伍
- side.active：当前场上宝可梦
- active 数量会随 gameType 变化
- chooseMove / chooseSwitch / chooseTeam 等选择解析
- activeRequest：向玩家发出的行动请求
```

重要观察：

```text
在 doubles 中，side.active 通常包含两个槽位。
Side 不是只支持单打，它的 active 设计本身就支持多槽位。
```

对本项目的启发：

```python
SideState:
    active_slots: list[ActivePokemon]
    bench: list[PokemonState]
    side_conditions: list[Effect]
```

我们的项目应从一开始设计 doubles-ready 的 `SideState`，不要先写死单打。

### 4. `sim/pokemon.ts`

`Pokemon` 表示一只宝可梦的战斗中状态。

它包含：

```text
- species
- baseSpecies
- ability / baseAbility
- item
- moves / baseMoves
- hp / maxhp
- status
- boosts
- volatiles
- position
- side
- tera / forme 相关状态
```

对本项目的启发：

```text
需要区分：
- 图鉴中的 Species 静态数据
- 队伍中的 PokemonSet 配置
- 战斗中的 PokemonState 动态状态
```

建议本项目保持三层：

```text
SpeciesData  # 静态图鉴
PokemonSet   # 队伍配置
PokemonState # 战斗中状态
```

### 5. `sim/field.ts`

`Field` 表示全场效果。

关注内容：

```text
- weather
- terrain
- pseudoWeather
- side conditions 的区别
```

对本项目的启发：

```text
天气、场地、空间、顺风、墙、钉子等不应混在 PokemonState 中；
应分别放在 FieldState / SideCondition / SlotCondition 中。
```

### 6. `sim/battle-actions.ts`

这是招式执行、目标处理和伤害结算等关键逻辑所在。

重点搜索：

```text
chooseMove
useMove
getTarget
ModifyMove
ModifyType
ModifyDamage
AfterMove
```

对本项目的启发：

```text
招式不是简单的“扣血函数”。
它会触发一系列事件：BeforeMove、ModifyMove、命中、伤害、附加效果、AfterMove 等。
```

这支持我们之前设想的事件钩子系统：

```text
before_turn
before_action
before_move
modify_type
modify_base_power
modify_damage
after_damage
after_action
after_turn
```

### 7. `sim/battle-queue.ts`

行动队列和行动顺序核心。

源码注释显示行动排序大致考虑：

```text
order
priority
speed
subOrder
```

对本项目的启发：

```text
速度顺序不是简单比较速度。
双打中要同时考虑：
- 换人
- Mega / 特殊系统
- 优先度
- 速度
- Trick Room
- 先制失败条件
- 行动插队效果
```

本项目可以先做简化版 ActionQueue，再逐步补齐。

### 8. `sim/battle-stream.ts`

`BattleStream` 提供流式 API。

`sim/SIMULATOR.md` 中的核心思想：

```text
向 stream 写入玩家选择
从 stream 读取 battle protocol 输出
```

示例输入：

```text
>start {"formatid":"gen7randombattle"}
>player p1 {"name":"Alice"}
>player p2 {"name":"Bob"}
>p1 move 1
>p2 switch 3
```

对本项目的启发：

```text
未来可以用 Showdown 作为对照模拟器：
- 用相同 seed 和队伍输入运行 Showdown
- 用我们的 Battle Model 运行同样局面
- 对比 event log / damage / faint / winner
```

## 四、data/：Dex 静态数据

重点文件：

```text
data/pokedex.ts        # 宝可梦 species 数据
data/moves.ts          # 招式数据
data/abilities.ts      # 特性数据
data/items.ts          # 道具数据
data/learnsets.ts      # 可学习招式
data/typechart.ts      # 属性克制表
data/conditions.ts     # 状态 / 条件
data/rulesets.ts       # 通用规则集
data/formats-data.ts   # 分级 / 可用性等格式数据
data/scripts.ts        # 当前世代脚本入口
```

对本项目的启发：

```text
数据层需要显式区分：
- species
- moves
- abilities
- items
- learnsets
- rulesets
- format metadata
```

我们的 Dex 设计可以参考：

```text
battle_model/dex/species.py
battle_model/dex/moves.py
battle_model/dex/abilities.py
battle_model/dex/items.py
battle_model/dex/learnsets.py
battle_model/rulesets/
```

## 五、data/mods/：世代与特殊规则差异

`data/mods/` 是非常值得学习的目录。

它用于表示不同世代或特殊环境相对于主数据的差异。

例如：

```text
data/mods/gen1/
data/mods/gen2/
...
data/mods/gen9/
data/mods/champions/
```

常见文件：

```text
pokedex.ts
moves.ts
abilities.ts
items.ts
learnsets.ts
rulesets.ts
scripts.ts
conditions.ts
formats-data.ts
```

重要设计：

```text
很多 mod 文件使用 inherit: true 表示继承基础数据，只覆盖差异。
```

对本项目的启发：

```text
我们也应采用“基础数据 + 规则差异补丁”的模式：
Base Dex
  ↓
Gen-specific Patch
  ↓
Champions Patch
  ↓
Season Patch
```

这对《宝可梦：冠军》和未来 Gen10 规则非常重要。

## 六、Champions mod：与本项目高度相关

本地 fork 中已经存在：

```text
data/mods/champions/
├── abilities.ts
├── conditions.ts
├── formats-data.ts
├── items.ts
├── learnsets.ts
├── moves.ts
├── rulesets.ts
└── scripts.ts
```

这与本项目“冠军优先”的方向高度相关。

### 1. `data/mods/champions/scripts.ts`

观察到 Champions mod 覆盖了若干关键机制。

例如：

```ts
init() {
    for (const i in this.data.Moves) {
        if (this.data.Moves[i].pp > 20) {
            this.modData('Moves', i).pp = 20;
        }
    }
}
```

说明：

```text
Champions mod 会统一调整招式 PP 上限。
```

`statModify` 被重写：

```ts
if (statName === 'hp') {
    return stat + evs + 75;
}
stat = stat + evs + 20;
```

说明：

```text
Champions mod 有不同于传统主系列的能力值计算方式。
这与我们之前认为 Champions 需要独立规则族的判断一致。
```

此外还看到：

```ts
canTerastallize(pokemon) {
    return null;
}
```

说明：

```text
Champions mod 中太晶可能被禁用或至少不按 Gen9 标准处理。
```

还看到：

```text
canMegaEvo
modifyDamage
```

说明：

```text
Champions mod 对 Mega、伤害修正、双打范围招式、STAB 等机制有定制逻辑。
```

这对本项目的启发非常大：

```text
Champions 不应建成 gen9 的一个小 flag，应该是独立 RuleSet family。
```

### 2. `data/mods/champions/rulesets.ts`

观察到 Champions 自定义了：

```text
standardag
standard
standarddraft
flatrules
teampreview
```

例如 flat rules 描述包括：

```text
Adjust Level = 50
Species Clause
Item Clause = 1
Picked Team Size = Auto
Min Team Size = 6
Cancel Mod
```

对本项目的启发：

```text
Champions RuleSet 应至少表达：
- level rule
- team size
- picked team size
- item clause
- species clause
- banlist
- open team sheet
- battle mode
```

### 3. `config/formats.ts` 中的 Champions formats

本地 fork 中已经有 Champions section，例如：

```text
[Gen 9 Champions] OU
[Gen 9 Champions] UU
[Gen 9 Champions] BSS Reg M-A
[Gen 9 Champions] VGC 2026 Reg M-A
[Gen 9 Champions] VGC 2026 Reg M-A (Bo3)
[Gen 9 Champions] Custom Game
```

其中 VGC Champions format 使用：

```text
mod: 'champions'
gameType: 'doubles'
ruleset: ['Flat Rules', 'VGC Timer', 'Open Team Sheets']
```

这正好对应本项目重点：

```text
双打 + Champions + Open Team Sheets + 赛季化规则
```

## 七、config/formats.ts：规则格式入口

`config/formats.ts` 定义了大量可选格式。

重点关注：

```text
name
mod
gameType
ruleset
banlist
restricted
team
bestOfDefault
searchShow
```

示例：

```ts
{
    name: "[Gen 9] VGC 2026 Reg I",
    mod: 'gen9',
    gameType: 'doubles',
    bestOfDefault: true,
    ruleset: ['Flat Rules', '!! Adjust Level = 50', 'Min Source Gen = 9', 'VGC Timer', 'Open Team Sheets', 'Limit Two Restricted'],
    restricted: ['Restricted Legendary'],
}
```

对本项目的启发：

```python
RuleSet:
    id: str
    name: str
    family: str
    battle_mode: singles | doubles
    rules: list[str]
    banlist: list[str]
    restricted: list[str]
    open_team_sheets: bool
    best_of: int | None
    data_mod: str
```

## 八、test/sim/：规则测试库

`test/sim/` 是非常值得学习的目录。

它包含大量针对特性、招式、道具、规则的测试：

```text
test/sim/abilities/
test/sim/moves/
test/sim/items/
test/sim/misc/
```

对本项目的启发：

```text
宝可梦规则太复杂，必须测试驱动。
不能只靠手动试。
```

本项目未来也应设计测试结构：

```text
tests/battle_model/mechanics/
tests/battle_model/doubles/
tests/battle_model/champions/
tests/game_theory/tree/
tests/game_theory/player_model/
```

建议优先建立测试用例：

```text
- 属性倍率
- STAB
- 双打范围招式伤害修正
- Protect
- Fake Out
- Tailwind
- Trick Room
- Intimidate
- switch order
- Champions stat formula
- Champions PP rule
```

## 九、对本项目最值得借鉴的设计

### 1. Dex + Mod 差异覆盖

Showdown 的 `data/mods/` 很适合参考。

本项目建议：

```text
base data
  ↓
gen9 patch
  ↓
champions patch
  ↓
season patch
```

这样才能支持未来 Gen10 和 Champions 赛季化变化。

### 2. Battle / Side / Pokemon / Field 分层

建议本项目采用类似分层：

```text
BattleState
├── RuleSet
├── FieldState
├── SideState p1
│   ├── active_slots
│   ├── bench
│   └── side_conditions
└── SideState p2
    ├── active_slots
    ├── bench
    └── side_conditions
```

### 3. ActionQueue

双打必须有明确行动队列。

建议本项目建立：

```text
Action
JointAction
ActionQueue
TurnResolution
EventLog
```

### 4. Event system

Showdown 的事件系统很复杂，但思想值得借鉴：

```text
效果不是写死在一个大函数里，而是通过事件钩子触发。
```

本项目可简化为：

```text
before_turn
before_action
before_move
modify_move
modify_damage
after_damage
after_move
after_turn
```

### 5. Battle protocol / event log

Showdown 会输出 battle protocol。

本项目也应保证每次模拟输出结构化事件日志：

```json
{
  "turn": 3,
  "events": [
    {"type": "move", "actor": "p1a", "move": "Protect"},
    {"type": "move", "actor": "p2a", "move": "Fake Out", "target": "p1a"},
    {"type": "block", "reason": "Protect"}
  ]
}
```

这对 Replay、RL、LLM 复盘都很重要。

## 十、不建议直接照搬的地方

### 1. 不要把本项目变成另一个 Showdown server

Showdown 的目标是在线对战平台。

本项目目标是：

```text
分析、推理、复盘、配队、胜率、玩家风格、RL/LLM
```

所以 `server/` 大量逻辑不是当前重点。

### 2. 不要一开始完整复刻全部规则

Showdown 已经积累多年规则细节。本项目如果一开始追求全量复刻，容易失控。

建议：

```text
先做 Champions 双打最小子集
再逐步补全机制
用 Showdown 作为参考和对照测试
```

### 3. 不要让 Game Theory Model 依赖 Showdown 内部对象

我们的博弈模型、玩家风格模型、RL 状态表示需要自己的稳定抽象。

可用 Showdown 对照规则，但不要让上层直接绑定 `Pokemon` / `Battle` 内部结构。

建议适配层：

```text
Showdown Battle Log / Request
  ↓
Adapter
  ↓
Our BattleState / EventLog / AnalysisState
```

## 十一、可以围绕这些问题继续阅读源码

### Battle Model 问题

```text
1. Showdown 如何表示 Battle / Side / Pokemon / Field？
2. 双打中 active slots 如何表示？
3. action choice 如何从文本解析为内部 Action？
4. targetLoc 如何处理？
5. move target 类型如何定义？
6. turn order 如何排序？
7. Trick Room 如何影响速度？
8. weather / terrain / side conditions 如何区分？
9. faint / switch / request 流程如何衔接？
10. battle log 如何生成？
```

### Dex / RuleSet 问题

```text
1. Dex.mod 如何合并 base data 和 mod data？
2. inherit: true 如何覆盖差异？
3. ruleset 如何影响 team validation 和 battle behavior？
4. format 中 ruleset / banlist / restricted 如何组合？
5. Open Team Sheets 如何表达？
```

### Champions 问题

```text
1. Champions statModify 与传统公式差异是什么？
2. PP 上限如何调整？
3. 太晶是否禁用？
4. Mega 是否可用，如何可用？
5. damage formula 是否完整不同？
6. champions roster 如何由 formats-data / learnsets 控制？
7. Champions VGC format 与普通 VGC format 有何差异？
```

### 本项目架构问题

```text
1. 哪些 Showdown 抽象应学习？
2. 哪些抽象不适合 Python/RL/LLM 项目？
3. 是否需要写 Showdown importer？
4. 是否需要写 Showdown battle log parser？
5. 如何用 Showdown 作为 oracle 测试我们的 Battle Model？
```

## 十二、建议下一步任务

### 任务 1：写 Showdown 目录地图

为 `sim/`、`data/`、`data/mods/champions/` 各写更详细的子导读。

### 任务 2：抽象我们的 doubles-ready BattleState

参考 Showdown 的 `Battle / Side / Pokemon / Field`，设计本项目 Python 数据模型。

### 任务 3：写 Champions 规则差异表

从 `data/mods/champions/` 提取：

```text
- stat formula
- PP rule
- disabled mechanics
- enabled gimmicks
- move changes
- ability changes
- item legality
- format rules
```

### 任务 4：写 Showdown 对照运行 demo

运行一个最小 Showdown doubles battle，保存 battle protocol，作为本项目未来测试用例。

### 任务 5：设计 adapter

设计：

```text
Showdown protocol -> Our EventLog
Showdown request -> Our LegalActions
Showdown dex data -> Our Dex Snapshot
```

## 十三、结论

Pokémon Showdown 对本项目最重要的价值是：

```text
- 成熟的对战规则参考实现
- 完整的 Dex 和 mod 数据组织方式
- 双打 action / target / queue 设计参考
- Champions mod 的早期规则实现参考
- 大量可学习的测试用例
```

但本项目不应成为 Showdown 的复制品。我们的核心差异是：

```text
Showdown：在线对战模拟器
本项目：双打与 Champions 优先的智能对战分析、博弈推理、复盘、配队、RL/LLM 平台
```
