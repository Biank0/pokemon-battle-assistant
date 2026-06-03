# VGC 双打学习框架设计：6 选 4 与回合决策（2026-06-03 17:30）

> 结合 17:00 调研报告。核心判断：VGC 不应把“6 选 4”和“每回合双槽动作”混成一个端到端黑盒；应拆成阶段化、可记录、可训练、可解释的 agent 框架。

## 1. VGC 任务拆解

VGC 一局至少有两个决策阶段：

```text
阶段 A：Team Preview / 6 选 4
输入：我方 6 只公开队表 + 对方 6 只公开队表 + 规则信息
输出：4 个 slot，顺序有含义：前 2 首发，后 2 后排

阶段 B：Turn Decision / 双打回合动作
输入：当前场面、双方在场 2 只、后排、HP/状态、天气/场地/空间/顺风、已揭示信息、legal orders
输出：一个完整 Showdown order，例如两个招式、招式+换人、双换、Protect 组合等
```

所以学习框架应是 **hierarchical policy**：

```text
VGCPolicy
  ├── TeamPreviewPolicy   # 6 -> 4；决定 lead pair + back pair
  └── TurnPolicy          # 每回合从 legal complete orders 中选择
```

不要一开始让一个模型直接从整局原始日志输出动作。Metamon 的经验说明 replay/状态重建、action space、team preview 模型都值得单独做版本化。

## 2. 6 选 4 应如何建模

### 2.1 输出不是集合，而是有序结构

VGC `/team 1234` 的语义是：

- 第 1、2 位：首发。
- 第 3、4 位：后排。
- 未选的 2 只：本局不上场，但仍作为公开信息影响对手心理与 matchup。

因此模型输出应是：

```json
{
  "lead_slots": [1, 2],
  "back_slots": [3, 4],
  "selected_slots": [1, 2, 3, 4],
  "confidence": 0.72,
  "reasons": ["..."],
  "risks": ["..."]
}
```

### 2.2 候选空间可控

6 选 4 有：

- 有序首发二只：`P(6,2)=30`。
- 有序后排二只：从剩余 4 只中 `P(4,2)=12`。
- 总有序方案：`360`。

如果后排顺序不重要，则是 `C(6,2)*C(4,2)=90` 种首发+后排组合。工程上可以先枚举 90 种，再把后排顺序固定为评分高者优先，最终生成 `/team abcd`。

### 2.3 第一版 TeamPreviewPolicy：启发式打分 + 可学习特征

先做可解释 heuristic baseline，再替换为 imitation / offline RL。

候选评分建议拆成：

```text
score(selection) =
  matchup_score
+ lead_pressure_score
+ speed_control_score
+ defensive_coverage_score
+ restricted_answer_score
+ support_synergy_score
- overlap_penalty
- vulnerability_penalty
```

特征示例：

1. **首发压制**：击掌奇袭、威吓、顺风、戏法空间、广域防守、看我嘛/愤怒粉、快速高压输出。
2. **速度控制**：Tailwind / Trick Room / Icy Wind / Electroweb / Thunder Wave，以及己方是否能利用。
3. **核心组合**：雨天手、晴天手、空间打手、精神场地 + 扩大力、Calyrex/Koraidon/Miraidon 等 restricted 核心。
4. **对方核心应对**：能否处理对方 restricted、天气、空间、红irection、Fake Out。
5. **防守覆盖**：选出的 4 只是否被同一属性/同一 spread move 打穿。
6. **后排价值**：是否有安全换入、残局清场、反转空间/天气的能力。

第一版可输出 top-k 选出建议，而不是只给一个答案，便于用户确认。

## 3. 回合动作学习框架

### 3.1 从 raw order 过渡到结构化双槽动作

当前环境层已经保存 `legal_order_messages`。下一步应把每个 order 解析为：

```json
{
  "command": "/choose move heatwave -1, move protect",
  "slots": [
    {"actor_slot": 1, "kind": "move", "move": "heatwave", "target": -1},
    {"actor_slot": 2, "kind": "move", "move": "protect", "target": null}
  ],
  "tags": ["spread", "protect"],
  "risks": []
}
```

这样 agent 可以学习“完整 order”，但 evaluator 能理解其中两个槽位。

### 3.2 TurnPolicy 第一版：合法动作排序器

不要让模型生成非法命令；输入合法 order 列表，输出排序：

```text
Observation + LegalOrders -> RankedActions[order, score, explanation]
```

候选特征：

- 即时收益：是否能击杀、是否能 Protect 挡关键攻击、是否能换入抗性。
- 位置收益：是否建立顺风/空间/天气/场地，是否让 restricted 安全输出。
- 风险：对方 Fake Out、Protect、换人、速度线不确定、命中率、双集火失败。
- 长期收益：保存关键宝可梦、消耗对方太晶/道具、逼出后排。

### 3.3 Reward 设计

训练时不能只用 win/loss。建议多层 reward：

```text
terminal_reward = +1 / -1
shaping_reward =
  hp_delta
+ ko_delta
+ speed_control_delta
+ position_advantage_delta
+ preserve_restricted_bonus
+ successful_protect_or_switch_bonus
- illegal_or_invalid_penalty
- unnecessary_double_protect_penalty
```

但是线上决策不要过度依赖 shaping，避免学到刷 HP 的短视行为。

## 4. 结合 Metamon 的数据路线

Metamon 给出的启发是：先把轨迹做对，再谈模型。

我们的数据路线建议：

```text
Stage 0：本地自生成数据
  - 随机 vs 随机
  - heuristic vs random
  - heuristic vs heuristic
  - 用户手动对战记录

Stage 1：专家/半专家 imitation
  - 记录人类手动选出与回合选择
  - 记录用户修正 agent 建议的差异
  - 训练 TeamPreviewPolicy 和 TurnPolicy 的 supervised baseline

Stage 2：offline RL / sequence model
  - 使用 steps.jsonl + team_preview + reward
  - 学习状态-动作价值或 policy transformer
  - 先固定队伍池/固定 format，再扩展

Stage 3：self-play fine-tune
  - agent 间对战生成轨迹
  - 定期用规则校验和 human review 防止策略退化
```

## 5. 建议的代码模块演进

```text
src/pokemon_battle_assistant/
  vgc/
    __init__.py
    features.py              # 从公开队表/局面抽取 VGC 特征
    team_preview_policy.py   # 6选4 policy 接口与 heuristic baseline
    order_parser.py          # 将 legal order message 解析成双槽结构
    turn_policy.py           # 回合动作排序接口
    rewards.py               # VGC reward / metrics
    explanations.py          # VGC 中文解释
```

核心接口草案：

```python
class TeamPreviewPolicy:
    def rank(self, my_team, opponent_team, format_info) -> list[TeamPreviewDecision]: ...

class TurnPolicy:
    def rank(self, observation, legal_actions, battle_context) -> list[TurnDecision]: ...
```

## 6. 6 选 4 的第一阶段落地计划

### Step 1：结构化 `TeamPreviewDecision`

新增数据结构：

```python
@dataclass(frozen=True)
class TeamPreviewDecision:
    selected_slots: tuple[int, int, int, int]
    lead_slots: tuple[int, int]
    back_slots: tuple[int, int]
    score: float
    reasons: list[str]
    risks: list[str]
```

### Step 2：枚举候选

生成 90 个候选：

```text
for lead_pair in C(6, 2):
  for back_pair in C(remaining, 2):
    score candidate
```

若需要考虑首发顺序，可在生成 `/team` 前再比较 lead pair 的两个顺序。

### Step 3：启发式评分

先根据队伍 JSON 中的 species / item / ability / moves / tera_type 做粗打分：

- 有 `Fake Out` 的首发加分。
- 有 `Tailwind` / `Trick Room` 且有合适输出手加分。
- 有 `Protect` 的核心输出手加分。
- 对方明显天气/空间核心时，己方反制手进入 4 只加分。
- 4 只里功能重复但缺少输出/速度控制则扣分。

### Step 4：接入 CLI

新增命令：

```bash
pba vgc preview vgc_rain_balance --opponent vgc_sun_koraidon --format gen9vgc2026regi
```

输出：

```text
推荐选出：1,3,4,6
首发：1 Pelipper + 3 Calyrex-Ice
后排：4 Incineroar + 6 Amoonguss
理由：雨天压制火系；威吓+愤怒粉保护核心；保留空间反打。
风险：若对方 Miraidon 首发，速度线压力较大。
```

### Step 5：把选出决策写入 battle record

`record.json` 中增加：

```json
"agent_decisions": {
  "team_preview": {
    "policy": "HeuristicVGCPreviewPolicy.v1",
    "ranked_candidates": [...],
    "chosen": {...}
  }
}
```

## 7. 成功标准

第一阶段不要以天梯胜率作为唯一标准。建议先看：

1. 能否对 4 支示例 VGC 队给出合理、可解释、合法的 6 选 4。
2. 能否把每局 team preview 和每回合 order 以稳定 schema 记录。
3. 能否在相同队伍/相同对手下复现决策。
4. 用户是否能理解并手动覆盖 agent 建议。
5. 后续是否能用这些记录训练 imitation baseline。

## 8. 推荐下一步

1. 实现 `vgc/team_preview_policy.py` 的枚举 + heuristic baseline。
2. 实现 `vgc/order_parser.py`，把 VGC legal order 解析成双槽结构。
3. 新增 `pba vgc preview` 命令，只做选出建议，不启动对战。
4. 在 `record.json` 中追加 `agent_decisions` 字段，为学习闭环预留。
5. 用四支示例队做互相对阵的选出建议快照测试。
