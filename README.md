# Pokémon Battle Assistant

一个宝可梦对战助手原型。现在先保持简单：

1. 一个能跑的命令行局面分析器。
2. 一个能验证 poke-env 本地对战的 smoke 脚本。

复杂框架先不保留，后面真正需要时再加。


## 外部依赖与本地运行环境

本项目当前有两类运行方式，依赖不同。

### 1. 离线命令行分析器

只依赖本项目 Python 代码，不需要启动 Pokémon Showdown，也不需要联网。

运行：

```bash
PYTHONPATH=src python -m pokemon_battle_assistant.cli examples/simple_battle.json --top 5
```

### 2. 本地真实对战模拟

这个功能依赖两个外部项目：

```text
~/path/to/pokemon-showdown   # 本地 Pokémon Showdown server，负责真实对战结算
~/path/to/poke-env           # Python 客户端，负责让 bot 连接 Showdown
```

上面的 `~/path/to/...` 是示例路径，请替换成你自己 clone 仓库的位置。

当前对战链路是：

```text
本项目脚本
  -> poke-env
  -> 本地 Pokémon Showdown server
  -> 本地完成对战结算
```

也就是说，对战运行时不连接官方服务器；只要依赖已经安装好，就可以离线在本机跑。

### 首次准备 Pokémon Showdown

```bash
cd ~/path/to/pokemon-showdown
npm install
cp config/config-example.js config/config.js
```

启动本地 Showdown：

```bash
cd ~/path/to/pokemon-showdown
node pokemon-showdown start --no-security
```

看到类似下面的输出就说明启动成功：

```text
Worker 1 now listening on 0.0.0.0:8000
Test your server at http://localhost:8000
```

注意：`--no-security` 只适合本地开发，不要暴露到公网。

### 首次准备 poke-env

本机系统 Python 可能是 3.9，而 poke-env 需要 Python 3.10+。当前使用 Anaconda Python 3.13 创建虚拟环境：

```bash
cd ~/path/to/pokemon-battle-assistant
python3.13 -m venv .venv
.venv/bin/python -m pip install -e ~/path/to/poke-env
```

然后运行本地对战脚本：

```bash
cd ~/path/to/pokemon-battle-assistant
.venv/bin/python scripts/poke_env_smoke_battle.py
```

## 当前保留的功能

### 1. 命令行局面分析

输入：`examples/simple_battle.json`  
输出：推荐操作、评分、理由、风险。

运行：

```bash
cd ~/path/to/pokemon-battle-assistant
PYTHONPATH=src python -m pokemon_battle_assistant.cli examples/simple_battle.json --top 5
```

### 2. poke-env 本地对战验证

先启动本地 Pokémon Showdown：

```bash
cd ~/path/to/pokemon-showdown
node pokemon-showdown start --no-security
```

再运行：

```bash
cd ~/path/to/pokemon-battle-assistant
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
cd ~/path/to/pokemon-battle-assistant
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
