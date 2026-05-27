# Pokémon Battle Assistant

一个面向宝可梦对战玩家的智能助手项目，目标是帮助用户进行**模拟对战、协助配队、对战博弈推理与复盘分析**。

当前仓库处于初始规划阶段，本文档先定义产品方向、核心模块与后续开发路线。

## 项目愿景

构建一个可以像“对战教练”一样工作的 bot：

- 理解用户当前队伍、规则环境与对手信息
- 模拟可能的回合展开
- 给出配队建议、换人建议、出招建议与风险提示
- 解释每一步建议背后的博弈逻辑
- 支持赛前准备、实时辅助、赛后复盘三类场景

## 核心使用场景

### 1. 模拟宝可梦对战

用户输入己方队伍、对方队伍、当前场面与规则，bot 输出：

- 当前局面的优势 / 劣势判断
- 推荐行动：攻击、换人、强化、防守、读换等
- 多个候选行动的收益、风险与预期后果
- 接下来 1-3 回合的可能分支

### 2. 协助配队

用户输入想使用的核心宝可梦、规则环境或战术方向，bot 输出：

- 队伍构筑思路
- 队伍成员建议
- 属性、抗性、速度线、打点覆盖检查
- 常见威胁与补盲建议
- 努力值、性格、道具、招式配置草案

### 3. 对战博弈推理

bot 不只给结论，还要解释：

- 对方最可能的行动是什么
- 对方如果读我方操作，会产生什么反制
- 我方选择保守解 / 激进解的代价
- 哪些操作是“收益高但风险高”
- 哪些操作是“即使被读也不亏”的稳定解

### 4. 赛后复盘

用户提供 replay、日志或手动描述，bot 输出：

- 关键转折回合
- 可替代操作
- 配队暴露的问题
- 对局中读换、资源管理、胜利条件判断是否合理

## 初步功能模块

```text
pokemon-battle-assistant/
├── src/
│   └── pokemon_battle_assistant/
│       ├── battle/        # 对战状态、回合模拟、行动评估
│       ├── team_building/ # 配队分析、弱点检查、配置建议
│       ├── knowledge/     # 宝可梦、招式、特性、道具、规则环境知识
│       ├── reasoning/     # 博弈推理、分支搜索、风险收益解释
│       ├── bot/           # 对话入口：CLI / Web / Discord / 飞书等
│       └── utils/         # 通用工具
├── docs/
│   ├── architecture.md    # 技术架构规划
│   ├── roadmap.md         # 开发路线
│   └── product.md         # 产品需求草案
└── tests/                 # 单元测试与模拟对局测试
```

## MVP 目标

第一阶段先实现一个命令行原型：

1. 用户输入己方队伍、对方已知信息与当前场面
2. 系统解析成结构化 battle state
3. 给出 2-3 个候选操作
4. 对每个操作输出：预期收益、主要风险、推荐理由
5. 支持保存对局记录用于复盘

## 技术方向建议

- 语言：Python，适合快速实现推理、数据处理和 bot 原型
- 数据来源：先使用手写结构化数据，后续再接入完整宝可梦数据集或对战模拟器
- 推理方式：规则引擎 + 搜索树 + LLM 解释层
- 对战模拟：前期简化伤害和局面评估，后期可考虑对接成熟模拟器
- bot 入口：先 CLI，后续扩展 Web API / 聊天机器人

## 项目企划

面向教授和同学的项目介绍与招募企划：[`docs/project-proposal.md`](docs/project-proposal.md)。

## 顶层架构思考

补充方向：项目长期重心将优先考虑 **双打对战** 与 **《宝可梦：冠军》支持**，单打作为可支持模式之一，但后续 Battle Model / Game Theory Model 应以 doubles-ready、champions-ready 为核心约束。

项目已经记录了一份更长期的双层架构草案：[`docs/top-level-architecture-notes.md`](docs/top-level-architecture-notes.md)。另有一份机器学习与博弈论知识索引：[`docs/ml-and-game-theory-knowledge-map.md`](docs/ml-and-game-theory-knowledge-map.md)。该文档用于在正式深入开发前讨论 Battle Model、Game Theory Model、本地 Dex 数据、规则集、Replay 时间轴、博弈树、胜率估计和配队推荐等核心方向。

## 当前状态

- [x] 初始化 Git 仓库
- [x] 补充项目规划文档
- [ ] 创建 Python 项目骨架
- [ ] 实现基础数据模型
- [ ] 实现第一个局面分析 demo

## MVP 骨架运行方式

当前已经具备一个最小命令行分析器，可以读取 `examples/simple_battle.json`，对候选操作进行启发式评分并输出中文解释。

在仓库根目录运行：

```bash
PYTHONPATH=src python -m pokemon_battle_assistant.cli examples/simple_battle.json
```

可以通过 `--top` 控制展示几个候选操作：

```bash
PYTHONPATH=src python -m pokemon_battle_assistant.cli examples/simple_battle.json --top 5
```

当前 MVP 包含：

- `models.py`：局面、宝可梦、行动和评分结果数据模型
- `type_chart.py`：属性克制表和倍率计算
- `evaluator.py`：透明的启发式行动评分器
- `explanation.py`：将评分结果转成中文对战建议
- `cli.py`：命令行入口
- `examples/simple_battle.json`：示例局面

当前评分仍然是简化版本，不包含完整伤害公式、速度判断、特性、道具和随机数区间。下一步可以继续补：速度线、真实伤害估算、队伍分析和 1-2 回合博弈树。
