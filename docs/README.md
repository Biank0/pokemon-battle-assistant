# 项目说明

这个项目现在先保持最小可运行状态，避免过早搭太复杂的框架。

## 现在保留了什么

### 1. 简化对战分析 MVP

核心代码：

```text
src/pokemon_battle_assistant/models.py
src/pokemon_battle_assistant/type_chart.py
src/pokemon_battle_assistant/evaluator.py
src/pokemon_battle_assistant/explanation.py
src/pokemon_battle_assistant/cli.py
examples/simple_battle.json
tests/test_mvp.py
```

作用：读取一个手写 JSON 局面，基于属性克制、STAB、HP 等启发式规则，输出推荐操作和中文解释。

运行：

```bash
cd ~/Bian-workspace/pokemon-battle-assistant
PYTHONPATH=src python -m pokemon_battle_assistant.cli examples/simple_battle.json --top 5
```

### 2. poke-env 本地对战 smoke

脚本：

```text
scripts/poke_env_smoke_battle.py
```

作用：确认本地 Pokémon Showdown server + poke-env 能跑一场随机对战，并导出对战前配置、replay 和 JSON 对战记录。

先启动 Showdown：

```bash
cd ~/Bian-workspace/pokemon-showdown
node pokemon-showdown start --no-security
```

再运行脚本：

```bash
cd ~/Bian-workspace/pokemon-battle-assistant
.venv/bin/python scripts/poke_env_smoke_battle.py
```

## 暂时删掉了什么

为了降低复杂度，暂时删掉：

- `battle_model/`
- `game_theory/`
- `engines/`
- `adapters/`
- 大量未来规划文档
- 双打 joint action 骨架

这些东西以后需要时再加，不提前堆框架。

导出文件：

```text
battle_outputs/<battle_tag>/replay.html
battle_outputs/<battle_tag>/record.json
battle_outputs/<battle_tag>/report.md
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

## 下一步只做一件事

建议下一步只做：

> 写一个最简单的 `AssistantPlayer`，让它在 poke-env 对战中选择“当前威力最高/属性最好”的招式。

不要先做复杂博弈树、双打框架、Champions 支持。
