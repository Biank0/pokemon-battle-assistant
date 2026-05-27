# 顶层架构思考记录

本文档用于记录项目在正式开发前的顶层架构思路。当前内容不是最终设计，而是后续讨论、取舍和重构的基础。

## 项目长期定位

本项目不应只是一个简单的“宝可梦行动推荐 bot”，而应逐步发展为：

> 一个基于本地宝可梦对战规则引擎的智能对战分析系统。

底层负责复现不同世代、规则和特殊系统下的战斗结算；上层负责复盘、博弈树生成、行动推荐、配队建议和胜率估计。

可以概括为：

```text
Dex 数据库
  + 多规则战斗模拟器
  + Replay 时间轴
  + Belief State
  + Game Tree
  + Winrate Evaluator
  + Bot 解释层
```

## 总体两层结构

项目核心可分为两层。

```text
第一层：宝可梦对战模型 Battle Model
负责回答：在给定规则和状态下，对战会如何结算？

第二层：宝可梦对战博弈模型 Game Theory Model
负责回答：在不确定信息、多回合策略和对手行为下，应该如何选择？
```

两层之间的关系：

```text
静态数据 / 规则集
  ↓
Battle Model：合法性校验、回合结算、伤害、事件日志、胜负判定
  ↓
Game Theory Model：时间轴、复盘、局部博弈树、胜率估计、配队推荐
  ↓
Bot / API / UI：自然语言解释和交互
```

## 关键原则

1. **数据和规则分离**
   - 宝可梦种族值、招式威力、特性描述属于数据。
   - 伤害公式、速度顺序、异常结算、天气影响属于规则。

2. **对战模型和博弈模型分离**
   - 对战模型回答“会发生什么”。
   - 博弈模型回答“应该怎么选”。

3. **模拟和解释分离**
   - 模拟器输出结构化事件与状态变化。
   - 解释层负责转成人类可读建议。

4. **运行时优先本地数据**
   - 可以从开源数据源导入数据。
   - 但正式运行时应读取本地标准化数据，不应依赖在线 API 实时查询。

5. **版本和规则集必须显式化**
   - 不同世代、不同比赛格式、不同平台规则差异很大。
   - 任何分析都必须绑定明确规则集。

6. **随机结果必须可复现**
   - 随机数、伤害波动、命中、追加效果都应支持 seed。

7. **分析结果必须可追溯**
   - 每个推荐应能追溯到规则、数据、模拟分支或历史统计依据。

## 宝可梦信息收录方案

### 总体策略

建议采用：

```text
外部数据源
  ↓
导入 / 清洗 / 标准化脚本
  ↓
本地标准化数据快照
  ↓
对战模型读取
```

也就是说：

- 开发期可以参考或同步开源数据源。
- 运行期应使用本地数据。
- 每次数据升级都形成快照，保证结果可复现。

### 可能的数据来源

后续需要进一步调研和确认授权、格式与覆盖范围。

候选来源：

- Pokémon Showdown 数据与模拟逻辑
- PokéAPI 图鉴数据
- veekun / pokedex 数据
- 自己维护的规则差异和补丁数据
- 未来针对《宝可梦：冠军》的官方规则资料和实测数据

### 本地数据可能结构

```text
data/
├── raw/              # 原始导入数据，不直接供运行时使用
├── normalized/       # 标准化后的可读取数据
├── snapshots/        # 不同版本数据快照
└── patches/          # 项目自定义修正和规则补丁
```

代码层：

```text
src/pokemon_battle_assistant/
├── data_sources/
│   ├── showdown/
│   ├── pokeapi/
│   └── local/
└── battle_model/
    └── dex/
```

## 第一层：Battle Model 对战模型

Battle Model 是项目底座，本质上是一个规则引擎和战斗模拟器。

### 职责

- 宝可梦、招式、特性、道具、规则集的数据表示
- 队伍合法性校验
- 战斗状态表示
- 行动合法性校验
- 回合顺序判断
- 伤害计算
- 命中、随机数、追加效果模拟
- 天气、场地、异常、能力变化结算
- Mega / Z 招式 / 极巨化 / 太晶化等特殊系统支持
- 胜负判定
- 事件日志生成

### 建议模块

```text
battle_model/
├── dex/              # 静态图鉴数据
├── rulesets/         # 世代、比赛格式、禁用规则、特殊规则
├── mechanics/        # 伤害、命中、速度、异常、天气、场地等机制
├── state/            # 当前战斗状态
├── actions/          # 出招、换人、特殊系统行动
├── simulator/        # 回合模拟器
├── rng/              # 随机数模型
└── validation/       # 合法性校验
```

### Dex 数据范围

需要长期覆盖：

```text
Pokemon Species
- 编号
- 名称
- 属性
- 形态
- 种族值
- 可用世代
- 进化关系

Move
- 属性
- 威力
- 命中
- PP
- 物理 / 特殊 / 变化
- 优先度
- 目标范围
- 附加效果
- 世代差异

Ability
- 特性效果
- 触发时机
- 受哪些规则或效果影响

Item
- 道具效果
- 触发条件
- 消耗逻辑

Learnset
- 某宝可梦在某世代可学习招式
- 升级、机器、教学、蛋招式、活动招式等来源
```

### Ruleset 规则集

规则集需要显式建模，而不是写死在模拟器里。

可能规则集：

```text
gen1 - gen9
vgc
smogon
custom
champions
```

规则集应描述：

```text
- 世代
- 单打 / 双打 / 多打
- 队伍数量限制
- 选出数量限制
- 等级规则
- Species Clause
- Item Clause
- Sleep Clause
- 禁用宝可梦
- 禁用招式
- 禁用道具
- 允许的特殊系统
- 伤害公式版本
- 速度顺序规则
- 随机数规则
```

### 四大经典特殊系统

需要统一抽象为特殊机制，而不是散落在伤害公式或行动逻辑中。

```text
Mega Evolution
- 形态变化
- 种族值变化
- 特性变化
- 部分世代速度结算差异

Z-Move
- 招式转换
- Z 招式威力映射
- 变化招式 Z 效果
- 一场一次限制

Dynamax / Gigantamax
- HP 变化
- 极巨招式转换
- 极巨招式附加效果
- 持续回合限制
- 部分规则禁用

Terastal
- 属性变化
- 本系加成变化
- 太晶爆发变化
- 一场一次限制
```

建议以事件钩子方式接入：

```text
before_turn
before_action
before_move
modify_type
modify_base_power
modify_stat
modify_damage
after_damage
after_action
after_turn
```

### 《宝可梦：冠军》特殊规则

《宝可梦：冠军》应单独建规则集，不应强行塞入主系列规则。

建议：

```text
rulesets/champions/
├── stat_formula.py
├── legality.py
├── roster.py
├── battle_format.py
└── README.md
```

在官方资料完全稳定前，应标记为实验性规则：

```text
status: experimental
```

需要重点关注：

- 是否保留传统 IV / EV
- 是否引入新的 Stat Points 系统
- 招式、特性、道具和对战格式是否与主系列一致
- 是否存在特殊伤害公式或平衡调整

### 回合模拟器

理想接口：

```python
result = simulator.step(
    state=current_state,
    p1_action=Action.move("Flower Trick"),
    p2_action=Action.switch("Corviknight"),
    rng_seed=12345,
)
```

返回不应只是最终状态，而应该包括：

```text
- next_state
- event_log
- damage_rolls
- fainted_pokemon
- win_condition
- warnings / assumptions
```

一个回合的大致流程：

```text
1. 接收双方行动
2. 校验行动是否合法
3. 判断优先级和速度顺序
4. 处理换人
5. 处理特殊系统激活
6. 处理招式命中
7. 计算伤害
8. 处理附加效果
9. 处理濒死
10. 处理天气、场地、异常、回合末效果
11. 判断胜负
12. 生成事件日志
```

## 第二层：Game Theory Model 博弈模型

Game Theory Model 建立在 Battle Model 之上，不直接处理底层规则结算。

### 职责

- 对战记录收录
- 按时间轴访问每个回合
- 对局复盘
- 对方未知信息推断
- 博弈树生成
- 行动策略评估
- 胜率估计
- 配队推荐
- 自然语言解释

### 建议模块

```text
game_theory/
├── replay/           # 对战记录解析与存储
├── timeline/         # 按回合重建状态
├── belief/           # 未知信息和概率分布
├── tree/             # 局部博弈树生成
├── evaluation/       # 局面评分
├── policy/           # 行动策略模型
├── monte_carlo/      # 随机模拟和胜率估算
├── team_builder/     # 配队推荐
└── explanation/      # 博弈推理解释
```

## 对战记录和时间轴

建议使用事件溯源思想保存对局。

```text
BattleRecord
├── metadata
├── initial_state
├── turn_1_events
├── turn_2_events
├── ...
└── final_result
```

应支持：

```python
record.state_at(turn=7)
record.events_at(turn=7)
record.diff_between(turn=6, turn=7)
```

这样可以支持：

- 赛后复盘
- 回合级分析
- 关键转折点识别
- 胜率曲线
- 博弈树重建
- 训练样本生成

## 博弈树生成

真实完整博弈树会迅速爆炸，因此应生成“局部候选博弈树”。

初期限制：

```text
我方候选行动 Top 3
对方候选行动 Top 3
向后搜索 1-3 回合
```

节点设计：

```python
GameTreeNode:
    state: BattleState
    p1_action: Action | None
    p2_action: Action | None
    probability: float
    evaluation_score: float
    win_probability: float
    children: list[GameTreeNode]
```

边设计：

```python
GameTreeEdge:
    action_pair: tuple[Action, Action]
    probability: float
    expected_value: float
    risk: float
    explanation: str
```

## Belief State 不确定信息模型

宝可梦对战不是完全信息游戏。系统需要表达未知信息。

常见未知项：

```text
- 对方具体努力值
- 对方具体道具
- 对方剩余招式
- 对方太晶属性
- 对方伤害随机数
- 对方玩家风格和行动倾向
```

建议结构：

```python
BeliefState:
    possible_sets: dict[Pokemon, list[PokemonSetHypothesis]]
    item_probabilities: dict[str, float]
    move_probabilities: dict[str, float]
    tera_type_probabilities: dict[str, float]
    opponent_policy_model: OpponentPolicy
```

博弈模型真正评估的是：

```text
在多个可能世界下，这个操作的期望收益和风险是多少？
```

## 胜率计算

胜率计算可以分阶段实现。

### 阶段一：启发式胜率

基于局面特征打分：

```text
- 剩余宝可梦数量
- 总 HP 资源
- 速度线优势
- 属性对位优势
- 场地资源
- 钉子 / 墙 / 天气等资源
- 关键宝可梦存活情况
- 胜利条件达成度
```

### 阶段二：Monte Carlo 模拟

对未知信息和随机因素采样：

```text
- 对方可能配置
- 对方可能行动
- 伤害随机数
- 命中 / 急所 / 追加效果
- 后续几回合行动
```

输出示例：

```text
选择 A：胜率 62%
选择 B：胜率 55%
选择 C：胜率 41%
```

### 阶段三：学习型模型

当积累足够对战记录后，再考虑训练：

```text
局面 → 胜率
局面 + 行动 → 行动价值
局面 → 对方行动概率
队伍 → matchup 胜率
```

可选模型：

- 逻辑回归 / XGBoost
- 神经网络
- replay transformer
- 强化学习 policy model

## 配队推荐

配队推荐最终不应只是属性弱点统计，而应和博弈模型、胜率模型联动。

长期目标：

```text
输入核心宝可梦
  ↓
生成候选队友
  ↓
检查合法性
  ↓
检查属性、打点、速度线、队伍职能
  ↓
模拟主流 matchup
  ↓
评估胜率
  ↓
输出推荐队伍与修改建议
```

需要数据：

```text
- 当前规则环境
- 主流宝可梦使用率
- 常见配置
- 常见队伍结构
- 环境威胁列表
- 历史对战记录
```

## 建议的长期目录结构

当前 MVP 目录可以保留，但长期建议逐渐重构为：

```text
src/pokemon_battle_assistant/
├── battle_model/
│   ├── dex/
│   ├── rulesets/
│   ├── mechanics/
│   ├── state/
│   ├── actions/
│   ├── simulator/
│   ├── rng/
│   └── validation/
├── game_theory/
│   ├── replay/
│   ├── timeline/
│   ├── belief/
│   ├── tree/
│   ├── evaluation/
│   ├── policy/
│   ├── monte_carlo/
│   ├── team_builder/
│   └── explanation/
├── data_sources/
│   ├── showdown/
│   ├── pokeapi/
│   └── local/
├── bot/
│   ├── cli.py
│   └── formatter.py
└── app/
    └── api.py
```

## 建议开发阶段

### Phase 1：顶层架构确认

- [ ] 确认两层架构边界
- [ ] 确认本地数据策略
- [ ] 确认首个规则集范围
- [ ] 确认是否以 Pokémon Showdown 作为优先参考源

### Phase 2：本地 Dex 标准

- [ ] 定义 Species / Move / Ability / Item / Learnset 数据模型
- [ ] 定义数据快照格式
- [ ] 写一个最小数据导入样例

### Phase 3：简化 Battle Model

- [ ] 属性倍率
- [ ] 基础伤害区间
- [ ] 本系修正
- [ ] 命中与随机数 seed
- [ ] 单回合事件日志

### Phase 4：Replay / Timeline

- [ ] BattleRecord 数据结构
- [ ] state_at(turn)
- [ ] events_at(turn)
- [ ] diff_between(turn_a, turn_b)

### Phase 5：局部博弈树

- [ ] 候选行动生成
- [ ] 双方行动组合展开
- [ ] 1-2 回合搜索
- [ ] 稳定解 / 激进解 / 风险解释

### Phase 6：配队推荐与胜率估计

- [ ] 队伍合法性检查
- [ ] 队伍职能检查
- [ ] matchup 评估
- [ ] Monte Carlo 胜率估算

## 暂不立即开发的内容

为了避免过早复杂化，以下内容可以先记录，暂缓实现：

- 全世代完整规则复刻
- 完整 Pokémon Showdown 兼容
- 所有特性和招式的特殊效果
- 完整 replay parser
- 大规模机器学习胜率模型
- Web 前端和部署
- 《宝可梦：冠军》正式规则实现

## 下一步需要思考的问题

1. 第一版正式 Battle Model 应选择哪个规则集？
   - Gen 9 Singles?
   - Gen 9 VGC?
   - Pokémon Champions experimental?
   - 自定义简化规则？

2. 数据源优先级如何确定？
   - 是否优先使用 Pokémon Showdown 数据结构？
   - 是否额外接 PokéAPI？
   - 是否需要自己的中文名称映射？

3. 模拟器目标是什么？
   - 追求和 Pokémon Showdown 完全一致？
   - 还是先追求可解释、可扩展和可控？

4. 博弈模型第一版做多深？
   - 单回合行动排序？
   - 1 回合双方组合？
   - 2-3 回合局部博弈树？

5. 配队推荐第一版基于什么？
   - 属性弱点？
   - 角色分工？
   - 环境威胁？
   - 模拟胜率？
