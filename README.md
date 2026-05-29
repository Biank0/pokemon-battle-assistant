# Pokemon Battle Assistant

宝可梦对战环境项目。第一阶段聚焦完整本地对战环境，支持自定义训练家队伍、本地模拟对战、结构化记录、中文报告，并为未来 RL 接入预留接口。

## 快速开始

所有功能通过统一入口 `pba` 调用。首次使用需要设置 alias：

```bash
echo 'alias pba="~/Bian-workspace/pokemon-battle-assistant/pba"' >> ~/.zshrc
source ~/.zshrc
```

### 队伍管理

```bash
pba team list                    # 列出所有训练家模版
pba team create                  # 交互式创建队伍（支持中文搜索）
pba team show <名字>             # 查看队伍详情
pba team preview <名字>          # 输出 Showdown 格式（可粘贴到 Showdown）
pba team delete <名字>           # 删除队伍
```

队伍模版保存在 `data/trainers/*.json`，也可以直接编辑 JSON 文件。

### 本地对战

需要先启动本地 Pokemon Showdown（见下方「环境准备」）：

```bash
pba battle data/trainers/my_team.json                                       # 双方同队伍
pba battle data/trainers/team_a.json --opponent data/trainers/team_b.json   # 不同队伍对战
pba battle data/trainers/my_team.json --format gen9ou                       # 指定对战格式
pba random-battle --format gen9randomdoublesbattle                         # 双打随机对战
pba random-battle --format gen9randomdoublesbattle --manual                # 用户手动操作玩家 1
```

对战结束后在 `battle_outputs/<battle_tag>/` 下生成：
- `replay.html` — 可视化对战回放
- `record.json` — 完整对战数据，包含 environment steps、observation、legal actions、chosen action
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

## 功能概览

| 功能 | 说明 | 需要 Showdown |
|------|------|:---:|
| 队伍创建/管理 | 从 Showdown 数据库选择宝可梦，配置招式/道具/特性/性格/EVs/IVs/太晶属性 | 否 |
| 中文搜索 | 搜索宝可梦/招式/道具时支持中英文关键词 | 否 |
| 模版对战 | 用自定义队伍进行本地对战，导出回放、环境 step 记录和中文报告 | 是 |
| 随机对战 | 环境基线随机合法动作对战，支持单打/双打随机格式 | 是 |
| 局面分析 | 基于属性克制/STAB/威力等启发式规则的行动推荐 | 否 |

## 环境准备

### Python 环境

需要 Python 3.10+：

```bash
cd ~/Bian-workspace/pokemon-battle-assistant
python3.13 -m venv .venv
.venv/bin/python -m pip install -e ~/Bian-workspace/poke-env
```

### 本地 Pokemon Showdown（对战功能需要）

```bash
cd ~/Bian-workspace/pokemon-showdown
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
├── examples/simple_battle.json
└── tests/test_mvp.py
```

## 测试

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

## 第一阶段目标

第一阶段不开发任何对战助手或自动决策器。当前目标是搭建完整、稳定、可复现的对战环境，支持：

- 用户使用自定义队伍进行本地模拟对战
- 记录完整 battle state、动作、回放和中文报告
- 未来 RL agent 通过清晰接口接入环境
- 可批量运行、可复现实验、可导出训练数据

暂不做 `AssistantPlayer`、启发式 bot、复杂博弈树或 RL 算法本身。当前 `BattleRunner` 只负责完整跑局和导出数据，不是交互式 `reset()/step()` RL 环境。

## Contributors

- [Biank0](https://github.com/Biank0)
- Claude (Anthropic) — Claude Opus 4.6
- ChatGPT (OpenAI)
