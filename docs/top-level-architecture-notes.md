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

---

# 补充：博弈论、玩家风格与心理博弈

## 背景

宝可梦对战不仅是规则模拟，也不是单纯的胜率预测问题。真实对战中存在大量心理博弈：读换、反读、50/50、保资源、强行翻盘、优势方求稳、劣势方冒险等。

因此，Game Theory Model 不应只做“搜索最优解”，还要考虑：

```text
- 不完全信息
- 同时行动
- 随机性
- 混合策略
- 玩家风险偏好
- 玩家抗压能力
- 玩家读换倾向
- 当前心理压力
- 对手风格剥削
```

长期目标应升级为：

> 在规则结算、隐藏信息、随机性、玩家风格和心理压力共同作用下，评估行动策略和长期胜率。

## 博弈论视角下的宝可梦对战

宝可梦对战可以被视为：

```text
不完全信息 + 随机性 + 同时行动 + 多阶段序贯博弈
```

对应关系：

```text
玩家 Player
- 双方训练家

行动 Action
- 出招、换人、太晶、守住、强化、Mega、Z 招式、极巨化等

收益 Payoff
- 胜率、血量收益、资源交换、位置优势、胜利条件推进程度

策略 Strategy
- 在不同局面下选择行动的规则

混合策略 Mixed Strategy
- 同一局面下按概率选择不同操作

不完全信息 Imperfect Information
- 不知道对方道具、努力值、招式、太晶属性、完整配置等

信念 Belief
- 对对方配置和行动倾向的概率判断

风险偏好 Risk Preference
- 稳健操作、高风险高收益、最坏情况规避等

纳什均衡 Nash Equilibrium
- 双方都无法单方面改进的行动分布

Exploit
- 针对对方风格和习惯进行剥削

Minimax / Maximin
- 假设对手最强，选择最坏情况最优解

Level-k Thinking
- 我想你想我想你会怎么操作
```

## Game Theory Model 需要新增的子模块

在原有博弈模型基础上，建议补充：

```text
game_theory/
├── payoff/           # 收益矩阵
├── equilibrium/      # 混合策略、均衡近似
├── player_model/     # 玩家风格模型
├── pressure/         # 心理压力状态
├── risk/             # 风险偏好与效用函数
├── exploit/          # 针对特定对手风格的剥削策略
└── level_k/          # 多层心理博弈推理
```

或合并成更简洁的结构：

```text
game_theory/
├── belief/
├── tree/
├── evaluation/
├── policy/
├── player_model/
├── risk_model/
└── explanation/
```

## 玩家风格模型 Player Model

### 目的

不同玩家在同一局面下会选择完全不同的行动。玩家风格会显著影响对局结果，因此需要显式建模。

例如同一局面下：

```text
A. 稳定攻击：收益中，风险低
B. 读换补盲：收益高，风险高
C. 换人保资源：收益低，风险低
```

不同玩家可能的选择分布：

```text
稳健型玩家：
A：60%
B：10%
C：30%

激进读换型玩家：
A：30%
B：55%
C：15%

劣势且抗压差玩家：
A：20%
B：65%
C：15%
```

### 建议结构

```python
PlayerProfile:
    risk_tolerance: float        # 风险承受度，0=极保守，1=极激进
    pressure_resistance: float   # 抗压能力，0=容易慌，1=很冷静
    prediction_tendency: float   # 读换倾向，0=少读，1=频繁读
    conservatism: float          # 保守程度，0=激进，1=保守
    bluff_frequency: float       # 虚张声势/钓招倾向
    switch_frequency: float      # 换人频率
    setup_preference: float      # 强化偏好
    preserve_wincon: float       # 保护胜利条件意识
    endgame_accuracy: float      # 残局稳定性
    tilt_sensitivity: float      # 受连续失误影响程度
    reasoning_depth: int         # 心理博弈层级，Level-k thinking
    overprediction_risk: float   # 过度读人的风险
```

### 初始风格模板

第一版不需要训练复杂模型，可以先手写风格模板：

```text
ConservativePlayer 稳健型
- 风险低
- 少读换
- 优先保资源
- 优势时更稳
- 倾向最坏情况不亏

AggressivePlayer 激进型
- 风险高
- 喜欢读换
- 喜欢强化
- 劣势时更敢赌
- 倾向最大化上限

BalancedPlayer 平衡型
- 期望收益优先
- 风险和收益相对平衡
- 不过度读换

TiltPronePlayer 易波动型
- 连续不利后提高高风险操作概率
- 容易做出强行翻盘选择
- 在时间或淘汰压力下失误率升高

ElitePlayer 高水平冷静型
- 重视胜利条件
- 优势时避免无意义 50/50
- 劣势时能识别必要冒险
- 不轻易过度读人
```

## 心理压力模型 Pressure Model

玩家风格不是静态的。它会被当前对局压力调制。

建议引入：

```python
PressureState:
    score_disadvantage: float       # 当前劣势程度
    win_probability_gap: float      # 胜率落后程度
    remaining_timer_pressure: float # 时间压力
    recent_bad_events: int          # 最近不利事件数量
    match_importance: float         # 比赛重要程度
    elimination_risk: float         # 是否淘汰局
```

示例：

```text
- 平时稳健的玩家，在胜率低于 20% 时可能提高高风险操作概率。
- 优势方如果抗压差，可能过度保守，给对手白嫖强化机会。
- 连续被读换后，玩家可能降低读换倾向，回到直接操作。
- 时间压力较大时，玩家更可能选择熟悉、简单、直观的操作。
```

## 收益矩阵 Payoff Matrix

在具体回合中，可以构造双方行动收益矩阵。

示例：

```text
                  对方留场攻击   对方换钢鸟   对方强化
我方草本攻击          +30          -20        +10
我方 U-turn          +10          +25        -5
我方读换火招         -30          +50        +5
```

基于该矩阵可以分析：

```text
- 哪个操作最稳？
- 哪个操作期望最高？
- 哪个操作最坏情况最好？
- 哪个操作最好情况收益最高？
- 哪个操作专门惩罚对方换人？
- 如果对方知道我会这么想，会如何反制？
```

## 决策原则

不同风格和不同局势下可以采用不同决策原则。

```text
Expected Value 最大化
- 选择平均收益最高的行动
- 适合中性风险玩家或信息较充分的局面

Maximin / Minimax
- 选择最坏情况最不亏的行动
- 适合优势方、保守玩家、必须避免崩盘的局面

Maximax
- 选择最好情况收益最高的行动
- 适合劣势方、必须赌翻盘的局面

Regret Minimization
- 选择后悔值最小的行动
- 适合不确定对方风格时

Exploit
- 针对对方已知习惯选择最克制的行动
- 适合有对手历史样本时

Mixed Strategy
- 在多个行动间按概率混合，避免被对手稳定反制
- 适合高水平对局或反复对战场景
```

## 风险偏好与效用函数 Risk Utility

每个行动可以记录：

```text
expected_value   # 期望收益
worst_case_value # 最坏情况收益
best_case_value  # 最好情况收益
variance         # 收益波动 / 风险
exploit_value    # 针对某类玩家的剥削价值
```

玩家风格调整后的效用可以近似为：

```python
def style_adjusted_utility(action, profile):
    return (
        action.expected_value * profile.rationality
        + action.worst_case_value * profile.conservatism
        + action.best_case_value * profile.risk_tolerance
        - action.variance * profile.risk_aversion
        + action.exploit_value * profile.exploit_preference
    )
```

这意味着同一个客观局面，面对不同玩家、或由不同玩家操作时，推荐行动可以不同。

## Level-k Thinking 多层心理博弈

宝可梦读换中经常出现：

```text
Level 0：我点最强招。
Level 1：我猜你会换，所以我读换。
Level 2：我猜你知道我会读换，所以我点稳定招。
Level 3：我猜你会反读我不读，所以我再次读换。
```

可以通过：

```python
PlayerProfile.reasoning_depth
PlayerProfile.overprediction_risk
```

来建模。

注意：

```text
reasoning_depth 不是越高越好。
过度读人可能导致放弃简单最优解。
顶尖玩家通常不是无限套娃，而是在必要时读人，不必要时选择稳定胜利路线。
```

## 风格条件化博弈树

博弈树生成时应支持玩家风格输入。

```python
tree = build_game_tree(
    state=current_state,
    opponent_profile=aggressive_reader,
    my_profile=balanced_player,
)
```

同一局面面对不同风格的对手，行动概率和推荐操作应不同。

```text
面对保守玩家：
- 对方留场或安全换人的概率更高
- 对方高风险读换概率更低
- 我方可考虑更主动地压迫或白嫖节奏

面对激进玩家：
- 对方读换、强化、反打概率更高
- 我方需要减少可被惩罚的贪心操作
- 稳定攻击或保持主动的操作可能更好

面对劣势且抗压差玩家：
- 对方可能提高高风险操作频率
- 我方需要防止被单点翻盘
- 优势方应避免无意义 50/50
```

## 与 AlphaGo 式思路的区别

AlphaGo-like 系统主要是：

```text
Policy Model + Value Model + MCTS
```

宝可梦对战需要扩展为：

```text
Battle Model
  ↓
Belief State
  ↓
Player Style Model
  ↓
Payoff Matrix
  ↓
Risk Utility
  ↓
Game Tree Search
  ↓
Policy / Value Model
  ↓
Explanation
```

原因：

```text
- 宝可梦是不完全信息游戏
- 双方同回合同时行动
- 有伤害、命中、追加效果等随机性
- 玩家风格和心理状态会显著改变行动分布
- 配队和对局操作都带有风格倾向
```

## 对配队推荐的影响

玩家风格不只影响回合操作，也影响配队。

```text
激进玩家适合：
- 高速攻队
- 强化清场
- 高压对攻结构
- 高收益读换招式

稳健玩家适合：
- 平衡队
- 可靠轮转
- 多个 defensive pivot
- 容错率高的胜利条件

抗压较差玩家适合：
- 操作路径明确的队伍
- 低随机依赖
- 不需要频繁 50/50 的队伍
- 稳定收割手

高水平冷静玩家适合：
- 有多条胜利路线的队伍
- 能根据 matchup 改变节奏的队伍
- 可以利用对手风格缺陷的结构
```

因此配队推荐可以增加输入：

```json
{
  "player_style": {
    "risk_tolerance": 0.7,
    "prediction_tendency": 0.6,
    "pressure_resistance": 0.4
  }
}
```

输出示例：

```text
你倾向激进但抗压一般，因此不建议使用过度依赖连续读换的队伍。
推荐选择有明确清场路线、但保留一个稳定轮转核心的平衡攻队。
```

## 未来输出形式示例

理想情况下，系统不只输出单一推荐，而是输出风格条件化建议。

```text
当前局面：
我方魔幻假面喵 vs 对方水主，双方都可能换人。

基础推荐：
Flower Trick 是最高即时收益操作。

博弈分析：
- 如果对方是保守型玩家，对方大概率留场或换安全位，U-turn 的期望收益更高。
- 如果对方是激进读换型玩家，对方可能预判我方 U-turn 或换人，此时直接 Flower Trick 更稳。
- 如果对方当前处于劣势且抗压能力低，需要警惕其选择高风险强化或太晶反打。

推荐：
- 默认解：Flower Trick
- 稳健解：U-turn
- 针对激进玩家：直接攻击
- 针对保守玩家：轮转保持主动
- 高风险读换：补盲招式，仅建议在确认对方习惯换人时使用。
```

## 阶段性落地建议

第一版不需要复杂机器学习，可以先实现手写模板：

```text
1. 定义 PlayerProfile 数据结构
2. 定义 Conservative / Aggressive / Balanced / TiltProne / Elite 模板
3. 为每个行动计算 expected / worst / best / variance
4. 根据不同玩家风格调整行动概率和效用
5. 在局部博弈树中使用 opponent_profile 修正对手行动概率
6. 在解释层输出“面对不同风格对手时”的推荐差异
```

暂缓实现：

```text
- 纳什均衡精确求解
- 大规模玩家风格聚类
- 基于真实玩家历史的自动画像
- 深度强化学习中的风格条件化 policy
- 多玩家长期元博弈模型
```
