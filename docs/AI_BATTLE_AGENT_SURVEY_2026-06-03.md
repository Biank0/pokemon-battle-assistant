# 宝可梦对战 AI 常见方案调研报告（2026-06-03 17:00）

> 目标：梳理 GitHub、论文/项目页、社区项目中常见的 Pokémon Showdown 对战 AI 路线，尤其关注 Metamon 系列，为我们的 agent 框架提供灵感。

## 1. 总体结论

当前 Pokémon Showdown 对战 AI 大致形成五类路线：

1. **poke-env 环境封装 + 启发式/随机 baseline**：最适合作为工程入口；优点是 Python 生态、可接本地 Showdown；缺点是高性能搜索/大规模训练需要额外补齐。
2. **传统 RL / Deep RL**：DQN、PPO、SARSA、Q-learning、policy network 等；通常需要强烈压缩状态/动作空间或大量 self-play，容易遇到稀疏奖励、部分可观测、非平稳对手问题。
3. **离线 RL / imitation learning + Transformer（Metamon）**：用人类 replay 与 self-play 轨迹训练序列模型，是目前最值得参考的数据工程路线。
4. **搜索 / Minimax / MCTS + world model**：用模拟器展开未来分支，结合启发式或 LLM 评估；适合高质量决策，但要求动作剪枝、对手模型和快速模拟。
5. **LLM agent / LLM + 工具**：用大语言模型做知识推理、解释和对手建模；单独使用容易慢且不稳定，更适合作为“建议层/评审层/解释层”嵌入 agent 框架。

对我们的项目而言，最优先的不是直接追求最强 bot，而是把**环境记录、动作空间、公开队表、选出、回合决策、评估指标**变成可训练、可解释、可替换的接口。

## 2. 重点项目梳理

### 2.1 poke-env：Python 环境与 bot 接口事实标准

- 定位：Python library，用于在 Pokémon Showdown 上构建 scripted agents、self-play experiments 和 RL workflows。
- 工程模式：子类化 `Player`，覆盖 `choose_move`；本地训练推荐启动本地 Showdown server，并使用 `--no-security` 降低限流/鉴权干扰。
- 对我们的启发：继续把当前 `BattleRunner` 建在 poke-env 上是合理的；但要在外层补齐稳定 schema、VGC 选出、数据集导出、agent 插拔接口。

### 2.2 Metamon：离线 RL + Transformer + 数据集平台

- 定位：Pokémon Showdown RL Agents and Datasets。
- 关键能力：
  - 5M+ 从真实人类战斗 replay 重建的轨迹；20M+ agent self-play 轨迹。
  - 提供 IL / RL policy 训练起点、标准化队伍集、40+ baseline policies。
  - 支持 Gen1-4 OU/NU/UU/Ubers 与 Gen9 OU；当前主线仍主要是 Singles。
  - 使用固定 `UniversalAction` 离散空间（常规移动、换人、Gen9 gimmick）。
  - 重点处理 replay 第三人称日志到第一人称轨迹重建、team prediction、team preview model、battle backend 版本化。
- 对我们的启发：
  1. **轨迹重建是核心资产**：我们的 `record.json` / `steps.jsonl` 应从一开始保证可回放、可训练、可版本化。
  2. **backend/schema 版本必须显式化**：Metamon 明确指出 message 到 RL observation 很难，输入特征修复会影响旧模型；我们也需要 `schema_version`、`backend_version`、`format_version`。
  3. **team preview 应单独建模**：Metamon 对 Gen9 team preview 有独立模型；VGC 6 选 4更应该拆成独立阶段。
  4. **动作空间先离散后结构化**：Metamon 先用固定 universal action；我们在 VGC 里可采用“合法 order 列表 + 结构化双槽动作”的混合表示。

### 2.3 PokéChamp：LLM + Minimax / Tree Search

- 定位：LLM 增强 minimax agent。
- 方法：LLM 替代/增强三个模块：己方动作采样、对手建模、价值评估；通过 world model 做多步展开，再选最高价值分支。
- 亮点：不需要额外 LLM 训练，强调 action proposal、opponent modeling、value function；能利用对战历史与人类知识缩小搜索空间。
- 对我们的启发：
  - 框架上应把 agent 拆为 `proposer -> simulator/evaluator -> judge -> executor`。
  - LLM 不一定直接输出最终 move，更适合生成候选、解释、对手意图、长程计划。

### 2.4 PokeLLMon：LLM 单体 agent 的早期代表

- 定位：LLM-embodied Pokémon battle agent。
- 关键策略：in-context reinforcement learning、knowledge-augmented generation、consistent action generation。
- 局限与启发：LLM 能做知识检索与解释，但需要动作合法性约束、重复切换抑制、一致性约束；这与我们的 CLI/环境层“只提交合法 order”的设计一致。

### 2.5 pkmn 生态：高速引擎、状态推断与 0 ERROR

- pkmn 生态关注高性能 battle engine、增强状态跟踪、反向伤害计算、usage stats 推断未知信息，以及 0 ERROR 这类基于搜索/评估的强 bot。
- 对我们的启发：
  - VGC 决策如果未来要搜索，需要比 poke-env 更快的 simulation engine 或缓存。
  - 信息集推断是中后期重点：对手道具/努力/招式未知时，要用 usage stats、公开队表、已揭示信息更新 belief state。

### 2.6 传统 RL / Deep RL 项目

- 典型项目：早期 `reinforcement-learning-pokemon-bot`、`poke_RL`、DQN/PPO/SARSA 类仓库。
- 共性：
  - 需要把状态压缩成向量；动作通常简化为“4 招式 + 若干换人”。
  - 常见实验会做 deterministic 改造、固定队伍、减少随机性，以便收敛。
  - 很适合验证 reward、state embedding、baseline，但距离完整 VGC 实战通常还远。
- 对我们的启发：先做 rule-based / imitation baseline，再上 RL；不要一开始端到端训练完整 VGC。

## 3. 对我们 Agent 框架的建议形态

建议拆成以下接口：

```text
BattleEnv / Recorder
  -> ObservationBuilder
  -> LegalActionBuilder
  -> PhaseRouter
       - TeamPreviewPolicy       # 6选4 / 首发后排
       - TurnPolicy              # 每回合双槽动作
  -> CandidateProposer           # 启发式 / LLM / learned policy
  -> Evaluator                   # damage、速度线、局势分、搜索/rollout
  -> OpponentModel               # 公开队表 + usage + 已揭示信息
  -> Judge / Ranker              # 排序与安全检查
  -> ExplanationBuilder          # 中文解释
  -> Executor                    # 只提交合法 Showdown order
```

### 最小可落地版本

1. **VGC team preview 独立模块**：输入双方公开队表，输出 4 个 slot（前 2 首发，后 2 后排）与理由。
2. **回合动作候选模块**：基于 legal order messages 生成候选，不让 agent 自己拼 Showdown 指令。
3. **局势评估器**：先手写特征：HP、击杀线、Protect、速度控制、威吓/击掌奇袭、空间/顺风/天气、位置安全。
4. **LLM 只做解释/候选补充**：先不要让 LLM 裸选最终动作；最终动作由合法动作 ranker 选出。
5. **数据闭环**：每局都存 `steps.jsonl` + `team_preview` + chosen action + reward outcome，后续可做 imitation / offline RL。

## 4. 与当前代码的差距

当前项目已经有：

- 本地 Showdown + poke-env 对战记录。
- `record.json` / `steps.jsonl`。
- VGC 6 选 4 team preview 提交。
- 手动/随机/固定选出。
- 合法动作导出。

下一步缺口：

1. 需要把 `team_preview` 拆成可单独调用的 policy 接口。
2. 需要为 VGC 双槽动作解析出结构化字段，而不仅是 raw order string。
3. 需要建立 opponent public team / revealed info / belief state。
4. 需要定义 reward 与 evaluation metrics，例如：win/loss、每回合 HP swing、position advantage、speed control、lead matchup score。
5. 需要一个最小 baseline：`HeuristicVGCPolicy`，先打通“选出 + 每回合动作 + 解释 + 记录”。

## 5. 来源线索

- UT-Austin-RPL/metamon: Pokémon Showdown RL Agents and Datasets
- arXiv: Human-Level Competitive Pokémon via Scalable Offline Reinforcement Learning with Transformers
- hsahovic/poke-env: Python Interface for Pokemon Showdown Bots
- PokéChamp project / arXiv: Expert-level Minimax Language Agent
- git-disl/PokeLLMon
- pkmn ecosystem: EPOké, 0 ERROR, pkmn/engine
- leolellisr/poke_RL
- hsahovic/reinforcement-learning-pokemon-bot
- PokéAgent Challenge leaderboard and competition pages
