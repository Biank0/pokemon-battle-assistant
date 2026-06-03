# Pokemon Battle Assistant

**当前版本：v0.0.1**

宝可梦对战环境项目。v0.0.1 聚焦完整本地对战环境与 VGC 双打基础设施，支持自定义训练家队伍、本地模拟对战、VGC 6 选 4、结构化记录、中文报告，并为未来 agent / RL 接入预留接口。

## v0.0.1 版本定位

本版本是项目的第一个可用环境版本，目标不是直接提供最强对战 bot，而是先把后续 agent 需要依赖的工程底座打稳：

- 统一 CLI：`pba doctor`、`pba team ...`、`pba battle ...`、`pba random-battle ...`、`pba analyze ...`。
- VGC 双打主线：默认围绕 `gen9vgc2026regi`，支持 6 选 4 team preview，前两只为首发，后两只为后排。
- 本地 Showdown 对战环境：基于本地 `pokemon-showdown` + `poke-env` 跑完整对战。
- 数据导出：每局导出 replay、`record.json`、`steps.jsonl` 和中文报告。
- 用户友好：中文搜索、队伍合法性检查、手动选出界面、Showdown 错误中文解释。
- Agent 预研：新增环境层检查、宝可梦对战 AI 调研、VGC 学习框架设计文档，为后续 heuristic / LLM / imitation / RL agent 铺路。

## 外部依赖

本项目自身保存 PBA 代码、离线数据和队伍模版。真实本地对战依赖两个外部项目：

```text
/path/to/pokemon-showdown   # 本地规则裁判和对战服务器
/path/to/poke-env           # Python 侧 Showdown bot 客户端
```

建议把三个项目放在同一个工作目录下，例如：

```text
workspace/
├── pokemon-battle-assistant
├── pokemon-showdown
└── poke-env
```

如果你的 `pokemon-showdown` 不在 PBA 仓库同级目录，请设置：

```bash
export PBA_SHOWDOWN_PATH=/path/to/pokemon-showdown
```

`poke-env` 需要安装到本项目 `.venv` 中，见下方「环境准备」。

## 快速开始

### VGC 快速开始

当前项目后续主要围绕 **VGC 双打** 展开。推荐先用内置合法队伍跑通流程：

```bash
pba doctor
pba team list
pba team validate vgc_rain_balance --format gen9vgc2026regi
pba battle vgc_rain_balance --format gen9vgc2026regi --select manual
```

如果要两支内置队伍互打：

```bash
pba battle vgc_sun_koraidon \
  --opponent vgc_trick_room_calyrex \
  --format gen9vgc2026regi \
  --select manual \
  --opponent-select random
```

内置 VGC 示例队说明见：`docs/VGC_STARTER_TEAMS.md`。

真正对战前需要先启动本地 Showdown server：

```bash
cd /path/to/pokemon-showdown
node pokemon-showdown start --no-security
```


所有功能通过统一入口 `pba` 调用。首次使用需要设置 alias：

```bash
echo 'alias pba="/path/to/pokemon-battle-assistant/pba"' >> ~/.zshrc
source ~/.zshrc
```

### 环境检查

```bash
pba doctor                       # 新手推荐：一键检查环境（等同于 env check）
pba env check                    # 检查 Python、poke-env、Showdown server 和数据文件
pba env check --json             # JSON 格式输出
```

### 队伍管理

```bash
pba team list                    # 列出所有训练家模版
pba team create                  # 交互式创建队伍（支持中文搜索）
pba team show <名字>             # 查看队伍详情
pba team preview <名字>          # 输出 Showdown 格式（可粘贴到 Showdown）
pba team delete <名字>           # 删除队伍
pba team validate <名字>         # 检查队伍在当前规则下是否合法
pba team validate <名字> --format gen9ou   # 按指定规则检查
pba team validate <名字> --local-only      # 只做本地基础检查
```

队伍模版保存在 `data/trainers/*.json`，也可以直接编辑 JSON 文件。

当前项目后续主要围绕 **VGC 双打** 展开，因此 `pba team create` 默认推荐 `gen9vgc2026regi`，并会在创建时提示 VGC 常见注意点，例如 6 选 4、前两只首发、重复道具限制、Protect/速度控制/支援动作等。

`team validate` 会先做本地友好检查（JSON 结构、名称、EV/IV、特性等），再调用本地 Pokémon Showdown 的 TeamValidator 做权威规则校验。这个检查不需要 Showdown server 启动，但需要本地存在 `pokemon-showdown` 代码；如果路径不是 PBA 仓库同级的 `pokemon-showdown`，请设置环境变量 `PBA_SHOWDOWN_PATH`。

### 本地对战

需要先启动本地 Pokemon Showdown（见下方「环境准备」）：

```bash
pba battle my_team                                                          # 直接用队伍名，双方同队伍
pba battle team_a --opponent team_b                                         # 不同队伍对战
pba battle my_team --format gen9ou                                          # 指定对战格式
pba battle vgc_team --format gen9vgc2026regi --select 1,2,3,4              # VGC：玩家 1 固定 6 选 4
pba battle vgc_team --format gen9vgc2026regi --select manual               # VGC：玩家 1 手动选出
pba battle my_team --skip-validation                                        # 高级用法：跳过开战前合法性检查
pba battle my_team --output-root runs/exp001                                # 指定对战记录输出目录
pba random-battle --format gen9randomdoublesbattle                         # 双打随机对战
pba random-battle --format gen9randomdoublesbattle --manual                # 用户手动操作玩家 1
```

对于 `gen9vgc2026regi` 这类带 6 选 4 的规则，PBA 会在 Showdown team preview 阶段提交 `/team` 指令，不是简单裁剪队伍。`--select` 支持：

- `auto`：默认，选择前 N 只
- `random`：随机选出 N 只
- `manual`：终端交互选择
- `1,2,3,4`：按编号固定选出，VGC 中前两只是首发

手动选出界面会展示队伍编号、中文名/种族、属性、道具、特性和招式摘要，方便根据公开队表做更接近实战的 VGC 选出。

对战结束后默认在 `battle_outputs/<battle_tag>/` 下生成；也可以用 `--output-root` 指定输出根目录：
- `replay.html` — 可视化对战回放
- `record.json` — 完整对战数据，包含 environment steps、observation、legal actions、chosen action；VGC 双打复合动作会作为完整 order 保存
- `steps.jsonl` — 逐 step JSONL 数据，便于后续批量分析/RL 数据管线读取
- `report.md` — 中文对战报告

### 随机对战

不需要自定义队伍，队伍由 Showdown 随机生成：

```bash
pba random-battle                                # 默认 gen9randombattle
pba random-battle --format gen9randomdoublesbattle  # 双打随机
pba random-battle --format gen9randomdoublesbattle --manual  # 用户手动操作玩家 1
```

### 离线局面分析

不需要 Showdown，纯本地运行：

```bash
pba analyze examples/simple_battle.json --top 5
```

输入一个对战局面 JSON，输出推荐操作、评分、理由和风险。

## 对战结构

当前对战环境按三条轴线组织：

```text
单打/双打 × 随机队伍/导入模版 × 随机基线/用户手动
```

详见 `docs/BATTLE_STRUCTURE.md`。

## 热门规则建队指南

为了方便先理解规则再建队，项目提供了三个常用 format 的中文说明：

| 规则 | format id | 文档 |
|---|---|---|
| Gen 9 OU | `gen9ou` | `docs/formats/gen9ou.md` |
| Gen 9 Doubles OU | `gen9doublesou` | `docs/formats/gen9doublesou.md` |
| Gen 9 VGC 2026 Regulation I | `gen9vgc2026regi` | `docs/formats/gen9vgc2026regi.md` |

入口见：`docs/formats/README.md`。

## v0.0.1 设计与调研文档

本版本新增三份面向后续 agent 开发的文档：

- `docs/ENVIRONMENT_LAYER_REVIEW_2026-06-03.md`：环境层架构检查、已完成改进和后续接口打磨清单。
- `docs/AI_BATTLE_AGENT_SURVEY_2026-06-03.md`：宝可梦对战 AI 常见方案调研，覆盖 poke-env、Metamon、PokéChamp、PokeLLMon、pkmn 生态和传统 RL 项目。
- `docs/VGC_LEARNING_FRAMEWORK_2026-06-03.md`：VGC 双打学习框架设计，重点拆解 6 选 4 team preview 和每回合双槽 order 决策。

## 功能概览

| 功能 | 说明 | 需要 Showdown |
|------|------|:---:|
| 环境检查 | 检查 Python、依赖、本地 Showdown server 和数据文件 | 否 |
| 队伍创建/管理 | 从 Showdown 数据库选择宝可梦，配置招式/道具/特性/性格/EVs/IVs/太晶属性，并支持本地基础校验 | 否 |
| 中文搜索 | 搜索宝可梦/招式/道具时支持中英文关键词 | 否 |
| 模版对战 | 用自定义队伍进行本地对战，导出回放、环境 step 记录和中文报告 | 是 |
| 随机对战 | 环境基线随机合法动作对战，支持单打/双打随机格式 | 是 |
| 局面分析 | 基于属性克制/STAB/威力等启发式规则的行动推荐 | 否 |

## 环境准备

### Python 环境

需要 Python 3.10+：

```bash
cd /path/to/pokemon-battle-assistant
python3.13 -m venv .venv
.venv/bin/python -m pip install -e /path/to/poke-env
```

### 本地 Pokemon Showdown（对战功能需要）

```bash
cd /path/to/pokemon-showdown
npm install
cp config/config-example.js config/config.js
node pokemon-showdown start --no-security
```

看到 `Worker 1 now listening on 0.0.0.0:8000` 即启动成功。

注意：`--no-security` 只适合本地开发，不要暴露到公网。

## 训练家模版格式

队伍以 JSON 文件存储在 `data/trainers/`，完整字段如下：

```json
{
  "name": "队伍名称",
  "format": "gen9ou",
  "team": [
    {
      "species": "Dragapult",
      "nickname": "",
      "item": "Choice Specs",
      "ability": "Infiltrator",
      "nature": "Timid",
      "tera_type": "Dragon",
      "level": 100,
      "evs": {"hp": 0, "atk": 0, "def": 0, "spa": 252, "spd": 4, "spe": 252},
      "ivs": {"hp": 31, "atk": 0, "def": 31, "spa": 31, "spd": 31, "spe": 31},
      "moves": ["Shadow Ball", "Draco Meteor", "Flamethrower", "U-turn"]
    }
  ]
}
```

- `team` 包含 1-6 只宝可梦
- `evs` 每项 0-252，总和不超过 510
- `ivs` 每项 0-31，省略默认 31
- `species`/`item`/`ability`/`moves` 使用 Showdown 英文名称

## 数据来源

- **宝可梦数据库** (`data/showdown_db.json`)：从本地 Pokemon Showdown 提取的 Gen 9 数据，包含 1517 宝可梦、718 招式、249 道具、310 特性、25 种性格。重新生成：`node scripts/extract_showdown_data.js`
- **中文名翻译** (`data/translations/zh_cn_names.json`)：来自 PokeAPI，覆盖宝可梦/招式/道具/特性。重新生成：`.venv/bin/python scripts/build_zh_translation_file.py`

## 项目结构

```
pokemon-battle-assistant/
├── pba                              # 统一 CLI 入口
├── data/
│   ├── showdown_db.json             # Showdown Gen9 离线数据库
│   ├── trainers/                    # 训练家队伍模版
│   └── translations/zh_cn_names.json
├── scripts/
│   ├── extract_showdown_data.js     # Showdown 数据提取脚本
│   ├── trainer_cli.py               # 队伍管理 CLI
│   ├── run_battle_with_trainer.py   # 模版对战脚本
│   ├── poke_env_smoke_battle.py     # 随机对战烟雾测试
│   └── build_zh_translation_file.py # 中文翻译表生成
├── src/pokemon_battle_assistant/
│   ├── environment.py               # 对战环境/runner 封装
│   ├── action_space.py              # legal actions 序列化
│   ├── pba_cli.py                   # 统一 CLI 实现
│   ├── battle_recorder.py           # 对战记录共享模块
│   ├── showdown_db.py               # 数据库查询模块
│   ├── team_converter.py            # 模版 → Showdown 格式转换
│   ├── translation.py               # 中文翻译
│   ├── evaluator.py                 # 启发式行动评分
│   ├── explanation.py               # 中文解释生成
│   ├── models.py                    # 数据模型
│   ├── type_chart.py                # 属性克制表
│   └── cli.py                       # 局面分析入口
├── docs/                            # 使用说明、规则说明、调研和设计文档
├── examples/simple_battle.json
└── tests/                           # 单元测试
```

## 测试

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

## v0.0.1 范围与下一步

v0.0.1 不承诺提供完整自动对战助手或强策略 bot。当前目标是搭建完整、稳定、可复现的对战环境，支持：

- 用户使用自定义队伍进行本地模拟对战
- 记录完整 battle state、动作、回放和中文报告
- 未来 RL agent 通过清晰接口接入环境
- 可批量运行、可复现实验、可导出训练数据

当前暂不把 `AssistantPlayer`、复杂博弈树或 RL 算法本身作为稳定功能发布。`BattleRunner` 只负责完整跑局和导出数据，不是交互式 `reset()/step()` RL 环境。下一步建议从 `HeuristicVGCPreviewPolicy`、VGC 双槽 order parser、`pba vgc preview` 和 agent decision 记录开始。

## Contributors

- [Biank0](https://github.com/Biank0)
- Claude (Anthropic) — Claude Opus 4.6
- ChatGPT (OpenAI)
