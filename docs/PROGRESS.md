# 项目进度记忆

更新时间：2026-05-28

## 当前状态

项目已收敛为简单可运行的 MVP，不再保留复杂未来框架。

当前保留功能：

1. **离线局面分析器**
   - 输入：`examples/simple_battle.json`
   - 入口：`src/pokemon_battle_assistant/cli.py`
   - 功能：基于属性克制、STAB、HP 等启发式规则输出推荐操作和中文解释。

2. **本地对战记录脚本**
   - 脚本：`scripts/poke_env_smoke_battle.py`
   - 依赖：本地 Pokémon Showdown server + poke-env
   - 功能：运行 `RandomPlayer vs RandomPlayer`，导出：
     - `replay.html`
     - `record.json`
     - `report.md`

3. **中文名翻译**
   - 全量中文名表：`data/translations/zh_cn_names.json`
   - 翻译模块：`src/pokemon_battle_assistant/translation.py`
   - 生成脚本：`scripts/build_zh_translation_file.py`
   - 覆盖：宝可梦、招式、道具、特性。
   - 已补充部分 Showdown 特殊形态 ID 别名。

## 外部依赖

真实本地对战依赖两个外部项目，路径在 README 中用通用示例表示：

```text
~/path/to/pokemon-showdown
~/path/to/poke-env
```

本地对战链路：

```text
本项目脚本 -> poke-env -> 本地 Pokémon Showdown server -> 本地结算对战
```

## GitHub 状态

已推送到 GitHub：

```text
https://github.com/Biank0/pokemon-battle-assistant.git
```

最新提交：

```text
38a368a Use generic local paths in docs
```

重要提交：

```text
ee71490 Simplify MVP and add Chinese battle reports
a88b029 Document poke-env and Showdown dependencies
38a368a Use generic local paths in docs
```

## 测试

当前测试：6 个，全部通过。

运行：

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

## 下次建议做什么

下一步只做一个小目标：

> 实现最简单的 `AssistantPlayer`，让它在 poke-env 对战中根据简单规则选择行动。

不要先恢复复杂框架。先从：

```text
RandomPlayer vs RandomPlayer
```

升级到：

```text
AssistantPlayer vs RandomPlayer
```

第一版 AssistantPlayer 只需要：

- 有可用招式时，选择威力最高或属性收益最高的招式。
- 没有可用招式时，随机换人。
- 继续导出中文 `report.md`。
