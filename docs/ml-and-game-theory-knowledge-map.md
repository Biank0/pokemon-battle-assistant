# 机器学习与博弈论知识地图

本文档记录本项目可能涉及的机器学习、强化学习、博弈论和决策理论知识点。它不是实现文档，而是后续学习、技术选型和模块设计的知识索引。

## 项目视角

本项目不是单纯训练一个模型，而是一个复合系统：

```text
对战规则模拟器
  + 对战数据集
  + 胜率预测模型
  + 行动策略模型
  + 不完全信息建模
  + 玩家风格建模
  + 博弈树搜索
  + 风险偏好决策
```

从机器学习视角，它需要：

```text
Replay 数据 → 监督学习 / 模仿学习 / 胜率预测 / 玩家风格建模
Battle Simulator → 强化学习环境 / 自我对弈 / Monte Carlo 模拟
Belief State → 概率推断 / 隐变量建模 / POMDP
```

从博弈论视角，它需要：

```text
单回合收益矩阵 → 混合策略 / 风险收益分析
多回合对局 → 扩展型博弈 / 博弈树搜索
隐藏配置 → 不完全信息博弈 / 贝叶斯博弈
玩家风格 → 对手建模 / exploit / 风险偏好
双打对战 → 联合动作 / 协同策略 / 目标选择博弈
```

## 机器学习知识点

### 1. 监督学习 Supervised Learning

监督学习是最容易开始的方向。可以从历史对战记录中构造训练样本。

#### Policy Model 行动策略模型

目标：

```text
给定当前局面，预测玩家会选择什么行动。
```

样本形式：

```text
输入 X：当前对战状态
标签 y：玩家实际选择的行动
```

模型输出：

```python
PolicyModel(state) -> action_probability
```

在双打中，输出不只是单个行动，而是联合行动：

```python
PolicyModel(state) -> joint_action_probability
```

例如：

```text
振翼发使用守住 + 铁包袱使用冰冻干燥：35%
振翼发使用月亮之力 + 铁包袱换人：20%
振翼发太晶输出 + 铁包袱守住：10%
```

#### Value Model 胜率模型

目标：

```text
给定当前局面，预测最终胜率。
```

样本形式：

```text
输入 X：第 t 回合局面
标签 y：最终是否获胜
```

模型输出：

```python
ValueModel(state) -> win_probability
```

这是后续搜索、复盘、配队胜率估计的核心组件。

### 2. 特征工程 Feature Engineering

宝可梦对战状态复杂，需要把局面转换为模型可处理的特征。

基础特征：

```text
- 宝可梦名称 / ID
- 属性
- 当前 HP
- 异常状态
- 能力变化
- 道具
- 特性
- 招式
- 速度线
- 天气
- 场地
- 剩余宝可梦
- 太晶 / Mega / Z / 极巨是否使用
```

双打特征：

```text
- 左右槽位
- 目标选择
- 集火可能性
- 范围招式收益
- 队友协同
- Protect 历史
- 控速状态
- 行动顺序
- 站位价值
```

会涉及：

```text
- 类别特征编码
- 数值特征标准化
- multi-hot encoding
- embedding 表示
- 序列特征
- 图结构特征
```

### 3. 表示学习 Representation Learning

后续可以让模型学习实体之间的关系。

可能的 embedding：

```text
- Pokemon embedding
- Move embedding
- Ability embedding
- Item embedding
- Team embedding
- Battle state embedding
- Player style embedding
- Ruleset embedding
```

目标是让模型学习：

```text
- 哪些宝可梦常承担控速、输出、辅助、联防等角色
- 哪些宝可梦常一起组成队伍核心
- 哪些招式在特定规则中价值更高
- 哪些队伍结构偏进攻、平衡或防守
```

### 4. 序列建模 Sequence Modeling

对战是时间序列，不是静态样本。

```text
turn 1 → turn 2 → turn 3 → ... → result
```

相关技术：

```text
- RNN / LSTM / GRU
- Transformer
- Temporal Convolution
- Sequence-to-sequence
- 事件序列建模
```

用途：

```text
- 根据前几回合行为预测对方下一回合行动
- 根据对战时间轴识别玩家风格
- 根据历史事件更新对方配置的概率
- 对 replay 进行关键回合识别
```

### 5. 事件建模 Event Modeling

Replay 可以表示为事件序列：

```text
Event 1: p1a used Protect
Event 2: p2a used Fake Out
Event 3: p1b took damage
Event 4: weather changed to Rain
...
```

模型可以学习：

```text
event sequence -> future state
event sequence -> player style
event sequence -> win probability
```

这与日志建模、行为建模、时序预测密切相关。

### 6. 概率建模 Probabilistic Modeling

宝可梦对战充满不确定性：

```text
- 对方道具
- 对方努力值
- 对方招式
- 对方太晶属性
- 对方是否会 Protect
- 对方玩家是否会读换
- 命中、伤害随机数、急所、追加效果
```

相关知识：

```text
- 条件概率
- 贝叶斯推断
- 后验更新
- 隐变量模型
- 概率图模型
- 蒙特卡洛采样
```

示例：

```text
对方先手了
→ 更新其可能是围巾、加速性格或高速努力值的概率

对方没有吃剩饭回复
→ 降低剩饭道具概率

对方第一回合 Protect
→ 更新其双打风格或侦查倾向
```

### 7. Belief State 建模

由于宝可梦是不完全信息游戏，系统不能只维护一个确定状态，而要维护对隐藏信息的概率信念。

示例：

```text
对方振翼发可能配置：
- Booster Energy 速度型：45%
- 讲究眼镜：25%
- 讲究围巾：15%
- 气势披带：10%
- 其他：5%
```

相关知识：

```text
- belief update
- Bayesian filtering
- particle filter
- hidden state inference
```

项目模块对应：

```text
game_theory/belief/
```

### 8. 强化学习 Reinforcement Learning

如果后续让 bot 自己对战，就会涉及强化学习。

基本元素：

```text
State：当前对战局面
Action：本回合行动或双打联合行动
Reward：胜利 +1，失败 -1，中间奖励可选
Policy：从状态到动作概率
Value：状态胜率
Environment：Battle Simulator
```

项目对应：

```text
Battle Simulator = RL Environment
Bot = RL Agent
```

### 9. MDP / POMDP

普通强化学习常用 MDP：

```text
Markov Decision Process
状态完全可见，动作影响下一个状态，目标最大化累计奖励。
```

宝可梦更接近 POMDP：

```text
Partially Observable Markov Decision Process
真实状态不完全可见，只能看到 observation，并根据历史维护 belief state。
```

因此，宝可梦对战模型应区分：

```text
true_state       # 完整真实状态，仅模拟器知道
observation      # 玩家可见状态
belief_state     # 玩家基于 observation 和历史推断出的概率状态
```

### 10. 自我对弈 Self-play

借鉴 AlphaGo / AlphaZero，可以通过自我对弈产生数据。

```text
Bot A vs Bot B
新模型 vs 旧模型
不同风格模型之间对战
不同队伍之间批量模拟
```

产出：

```text
- 新训练数据
- 胜率标签
- 策略改进样本
- 队伍 matchup 数据
```

前提：

```text
需要足够准确、足够快的 Battle Simulator。
```

### 11. 模仿学习 Imitation Learning

利用人类 replay 学习高手操作。

```text
state -> human action
```

优点：

```text
- 比强化学习容易起步
- 不需要一开始就有自我对弈系统
- 可以快速获得类人策略
```

缺点：

```text
- 人类操作未必最优
- 低水平 replay 会带来噪声
- 不同玩家风格混在一起会让模型混乱
```

改进方式：

```text
- 按玩家水平过滤
- 按规则环境过滤
- 按风格聚类
- 按最终胜负加权
```

### 12. 离线强化学习 Offline RL

从历史 replay 中学习行动长期价值。

```text
在这个局面做这个行动，长期结果如何？
```

相关知识：

```text
- Q-learning
- behavior policy
- off-policy evaluation
- distribution shift
- conservative Q-learning
```

难点：

```text
历史数据覆盖不足时，模型容易高估未见过行动。
```

### 13. 多智能体强化学习 Multi-Agent RL

宝可梦是双方对抗，不是单智能体固定环境。

相关知识：

```text
- Multi-Agent Reinforcement Learning
- non-stationarity
- self-play instability
- policy population
- league training
- meta-game
```

如果后续做多风格 bot、队伍生态模拟或环境演化，这块会很重要。

### 14. 模型评估 Evaluation

需要评估模型是否真的有用。

策略模型指标：

```text
- Policy accuracy
- Top-k accuracy
- Cross entropy
- Log loss
```

胜率模型指标：

```text
- Value calibration
- Brier score
- Log loss
- AUC
```

实战指标：

```text
- Win rate
- Elo / Glicko
- 对固定 bot 胜率
- 对不同风格 bot 胜率
- exploitability
```

辅助系统指标：

```text
- 解释是否合理
- 建议是否符合规则
- 是否过度冒险
- 是否能识别胜利条件
- 是否能适应玩家风格
```

## 博弈论知识点

### 1. 标准型博弈 Normal-form Game

单个回合可以抽象成收益矩阵。

示例：

```text
                  对方攻击   对方换人   对方守住
我方攻击            +10       -5       0
我方读换            -20      +30       -5
我方强化            -10      +20      +15
```

可分析：

```text
- 期望收益
- 风险
- 支配策略
- 混合策略
- 最坏情况收益
```

### 2. 扩展型博弈 Extensive-form Game

整场对战是多回合序列，可以表示为博弈树。

```text
当前局面
├── 行动组合 A
│   ├── 下一回合分支
│   └── ...
├── 行动组合 B
└── 行动组合 C
```

项目对应：

```text
game_theory/tree/
```

### 3. 不完全信息博弈 Incomplete Information Game

对方完整配置不可见，因此需要建模类型空间。

```text
对方可能是围巾型，也可能是命玉型。
不同类型导致不同行动概率和威胁程度。
```

相关知识：

```text
- Bayesian game
- type space
- belief
- posterior update
```

### 4. 混合策略 Mixed Strategy

在高水平对局中，固定操作容易被读。

示例：

```text
稳定攻击：70%
U-turn：20%
读换补盲：10%
```

用途：

```text
- 避免被稳定反制
- 处理 50/50 局面
- 在长期反复对战中降低可剥削性
```

### 5. 纳什均衡 Nash Equilibrium

在小型局部收益矩阵中，可以求近似均衡。

```text
双方都没有动力单方面改变策略。
```

完整宝可梦对战过于复杂，不适合全局精确求解。更现实的目标是：

```text
在局部行动矩阵中求近似混合策略。
```

### 6. Minimax / Maximin

对抗游戏常用思想。

```text
Minimax：假设对方会最优反制我。
Maximin：选择最坏情况收益最高的行动。
```

宝可梦应用：

```text
优势局：适合 maximin，避免被翻盘。
劣势局：可能需要 maximax，寻找翻盘线。
```

### 7. Regret Minimization 后悔最小化

当不知道对方如何选择时，可以考虑：

```text
如果我选错了，最多会后悔多少？
```

选择后悔值最小的行动。

适合：

```text
- 对手风格未知
- 多个行动收益接近
- 读换失败代价较高
```

### 8. Exploitability 可剥削性

策略如果过于固定，会被针对。

示例：

```text
如果我每次都在残血时点先制招式，
对方就可以更稳定地 Protect、换免疫位或强化。
```

系统应评估：

```text
- 当前推荐是否过于固定
- 对手是否能稳定反制
- 是否需要混合策略
```

### 9. 对手建模 Opponent Modeling

对手建模是本项目非常重要的方向。

关注：

```text
- 风险偏好
- 是否爱读换
- 是否爱守住
- 是否容易 tilt
- 是否优势时过保守
- 是否劣势时强行赌
- 是否偏好集火
- 是否重视控速
```

可以从 replay 中学习，也可以先使用手写模板。

### 10. Level-k Thinking

心理博弈中的多层推理。

```text
Level 0：我点最明显的最强招。
Level 1：我猜你会换，所以我读换。
Level 2：我猜你知道我会读，所以我不读。
Level 3：我猜你知道我不读，所以我再读。
```

注意：

```text
推理层级不是越高越好。过度读人会导致放弃简单最优解。
```

### 11. 风险偏好与效用理论 Utility Theory

同一个收益矩阵，不同玩家可能选择不同操作。

需要区分：

```text
客观收益 payoff
主观效用 utility
```

例子：

```text
行动 A：稳定 +10
行动 B：50% +40，50% -30
```

风险中性玩家可能选 B，保守玩家可能选 A。

相关知识：

```text
- expected utility
- risk aversion
- risk seeking
- variance penalty
- prospect theory
```

### 12. 信号与信息 Signal / Information

每个行动都会暴露信息。

示例：

```text
对方先手了 → 暗示速度配置
对方没有吃剩饭 → 可能不是剩饭
对方伤害很高 → 暗示攻击努力值或道具
对方第一回合 Protect → 暗示双打风格或侦查意图
```

相关知识：

```text
- signaling game
- information reveal
- belief update
```

### 13. 元博弈 Meta-game

配队推荐会涉及环境博弈。

示例：

```text
当前环境很多雨天队
→ 草抗、水抗、电抗价值上升
→ 反雨组件使用率上升
→ 雨天队又调整配置
```

相关知识：

```text
- meta-game
- population game
- rock-paper-scissors dynamics
- usage statistics
```

## 双打对战额外知识点

由于项目重心放在双打与《宝可梦：冠军》上，双打带来额外复杂度。

### 1. 联合动作 Joint Action

双打一方一回合有两个行动。

```text
我方行动 = A 宝可梦动作 × B 宝可梦动作
对方行动 = C 宝可梦动作 × D 宝可梦动作
```

如果每只宝可梦有 5 个可选行动：

```text
我方 joint action = 5 × 5 = 25
对方 joint action = 5 × 5 = 25
一回合行动组合 = 625
```

需要：

```text
- action pruning
- candidate generation
- policy prior
- beam search
- MCTS
```

### 2. 协同策略 Coordination

双打不是两个单打相加。

典型协同：

```text
- A 使用 Fake Out，B 强化
- A 使用 Follow Me，B 输出
- A 使用 Tailwind，B 保护
- A 换入威吓，B 守住
- A 集火，B 补刀
```

相关知识：

```text
- coordination game
- team policy
- joint optimization
```

### 3. 目标选择 Targeting

双打中不仅要选招式，还要选目标。

问题：

```text
- 冰冻干燥打谁？
- 击掌奇袭打谁？
- 是否双集火？
- 是否打 Protect 概率低的目标？
- 是否用范围招式绕过目标选择？
```

这会显著增加行动空间和心理博弈复杂度。

### 4. Protect 博弈

Protect 是双打核心心理博弈之一。

需要建模：

```text
- 对方是否会 Protect
- 我方是否读 Protect 转火队友
- 是否双集火可能 Protect 的目标
- 连续 Protect 成功率
- Protect 是否拖天气、顺风、戏法空间回合
```

这是典型混合策略博弈。

### 5. 控速与未来回合价值

双打中当前回合伤害最大化不一定最优。控速可能决定未来数回合。

例子：

```text
Tailwind 本回合没有伤害，但未来数回合改变速度优势。
Trick Room 可能反转速度线。
Icy Wind 同时压低对面双目标速度。
```

相关知识：

```text
- long-term value
- delayed reward
- temporal credit assignment
```

## 项目模块与知识点对应

```text
Battle Model
- 规则建模
- 状态空间
- 随机过程
- MDP / POMDP 环境

Replay / Timeline
- 数据工程
- 序列建模
- 监督学习数据集构造

Belief State
- 贝叶斯推断
- 隐变量模型
- 粒子滤波

Policy Model
- 行动分类
- 模仿学习
- 强化学习策略

Value Model
- 胜率预测
- 回归 / 校准
- 自我对弈标签

Game Tree
- Minimax
- Expectimax
- MCTS
- 双打 joint action pruning

Player Style Model
- 对手建模
- 风险偏好
- 心理压力
- 风格聚类

Team Builder
- 组合优化
- 元博弈
- 胜率估计
- 搜索 / 进化算法
```

## 推荐学习顺序

### 阶段一：基础决策与规则

```text
- 概率论基础
- 期望值
- 方差
- 条件概率
- 启发式评分
- 状态建模
```

项目对应：

```text
行动评分器、伤害估算、局面评分
```

### 阶段二：监督学习

```text
- 分类模型
- 回归模型
- 交叉熵
- 概率校准
- 特征工程
- 训练 / 验证 / 测试集
```

项目对应：

```text
Policy Model、Value Model、Replay 数据训练
```

### 阶段三：博弈树搜索

```text
- Minimax
- Expectimax
- MCTS
- UCT
- Alpha-beta pruning
- Beam search
```

项目对应：

```text
局部博弈树、双打 joint action 搜索
```

### 阶段四：不完全信息

```text
- 贝叶斯推断
- POMDP
- Belief State
- Particle Filter
- Opponent Modeling
```

项目对应：

```text
对方配置推断、玩家风格建模、隐藏信息更新
```

### 阶段五：强化学习

```text
- MDP / POMDP
- Q-learning
- Policy Gradient
- Actor-Critic
- Self-play
- Offline RL
- Multi-Agent RL
```

项目对应：

```text
bot 自我对弈、胜率模型迭代、策略优化
```

## 优先级清单

### P0 必学

```text
- 概率论：期望、方差、条件概率、贝叶斯更新
- 基础监督学习：分类、回归、交叉熵、校准
- 博弈树：Minimax、Expectimax、MCTS
- 不完全信息：Belief State
- 决策理论：风险偏好、效用函数
```

### P1 重要

```text
- Replay 数据处理
- 特征工程
- 序列建模
- 对手建模
- 混合策略
- Regret Minimization
- 双打联合动作搜索
```

### P2 进阶

```text
- 强化学习
- Self-play
- Offline RL
- Multi-Agent RL
- 纳什均衡近似
- 元博弈 / 环境建模
```

### P3 长期研究

```text
- 深度强化学习
- League Training
- Population-based Training
- 风格条件化模型
- 大规模自动配队搜索
```

## 总结

本项目涉及的核心知识可以概括为：

```text
监督学习：从 replay 学人类操作和胜率
强化学习：通过自我对弈优化策略
概率建模：处理隐藏配置、随机数和不确定性
POMDP：把宝可梦看成不完全信息决策过程
博弈论：处理双方策略、混合策略、读换和反读
决策理论：根据风险偏好选择不同操作
搜索算法：用博弈树和 MCTS 推演未来回合
对手建模：根据玩家风格调整行动预测
```

最关键的前置基础仍然是：

```text
1. 准确的 Battle Model
2. 可复盘的 Replay / Timeline 数据结构
3. 能表达不确定信息和玩家风格的 Game Theory Model
```
