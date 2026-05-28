# Pokémon Battle Assistant

一个宝可梦对战助手原型。现在先保持简单：

1. 一个能跑的命令行局面分析器。
2. 一个能验证 poke-env 本地对战的 smoke 脚本。

复杂框架先不保留，后面真正需要时再加。

## 当前保留的功能

### 1. 命令行局面分析

输入：`examples/simple_battle.json`  
输出：推荐操作、评分、理由、风险。

运行：

```bash
cd ~/Bian-workspace/pokemon-battle-assistant
PYTHONPATH=src python -m pokemon_battle_assistant.cli examples/simple_battle.json --top 5
```

### 2. poke-env 本地对战验证

先启动本地 Pokémon Showdown：

```bash
cd ~/Bian-workspace/pokemon-showdown
node pokemon-showdown start --no-security
```

再运行：

```bash
cd ~/Bian-workspace/pokemon-battle-assistant
.venv/bin/python scripts/poke_env_smoke_battle.py
```

这个脚本会让两个随机 bot 在本地打一场，并在 `battle_outputs/<battle_tag>/` 下导出：

- `replay.html`：可打开查看的完整 replay
- `record.json`：JSON 格式的对战配置、双方队伍、每回合观察快照和原始 replay events
- `report.md`：中文 Markdown 报告，适合直接打开阅读

## 当前项目结构

```text
pokemon-battle-assistant/
├── docs/
│   └── README.md
├── examples/
│   └── simple_battle.json
├── scripts/
│   └── poke_env_smoke_battle.py
├── src/pokemon_battle_assistant/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── evaluator.py
│   ├── explanation.py
│   ├── models.py
│   └── type_chart.py
└── tests/
    └── test_mvp.py
```

## 测试

```bash
cd ~/Bian-workspace/pokemon-battle-assistant
PYTHONPATH=src python -m unittest discover -s tests
```

如果用 `.venv`：

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
```


## 中文名翻译

项目现在有一份本地全量中文名文件：

```text
data/translations/zh_cn_names.json
```

来源是 PokéAPI，当前大小约 139 KB，包含：

- 宝可梦：1025 条
- 招式：915 条
- 道具：1996 条
- 特性：276 条

运行报告时不会联网，只读取这个本地文件。需要重新生成时运行：

```bash
.venv/bin/python scripts/build_zh_translation_file.py
```

## 下一步

只做一个小目标：

> 实现最简单的 `AssistantPlayer`，让它能在 poke-env 对战中根据简单规则选择行动。

等这个跑通后，再考虑博弈、双打、解释层等复杂功能。
