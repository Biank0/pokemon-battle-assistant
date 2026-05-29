# 项目进度记忆

更新时间：2026-05-29

## 当前状态

项目已收敛为简单可运行的 MVP，并在昨天新增了训练家模版、本地自定义队伍对战、统一 CLI、中文搜索等能力。

当前保留/已完成功能：

1. **统一命令入口 `pba`**
   - 文件：`pba`
   - 子命令：
     - `pba team ...`：训练家队伍管理
     - `pba battle ...`：本地 Showdown 模版对战
     - `pba analyze ...`：离线局面分析
   - README 已按统一入口重写。

2. **训练家队伍模版系统**
   - 脚本：`scripts/trainer_cli.py`
   - 数据目录：`data/trainers/*.json`
   - 示例：`data/trainers/example_team.json`
   - 支持：创建、列表、查看、预览 Showdown 文本、删除。
   - 创建时可配置：宝可梦、昵称、道具、特性、性格、太晶属性、等级、EVs、IVs、招式。

3. **Showdown 离线数据库查询**
   - 数据：`data/showdown_db.json`
   - 提取脚本：`scripts/extract_showdown_data.js`
   - 查询模块：`src/pokemon_battle_assistant/showdown_db.py`
   - 覆盖：Gen 9 宝可梦、招式、道具、特性、性格、learnsets。

4. **中文搜索与翻译**
   - 全量中文名表：`data/translations/zh_cn_names.json`
   - 翻译模块：`src/pokemon_battle_assistant/translation.py`
   - 支持在队伍创建时用中文搜索宝可梦、招式、道具。
   - 已补充部分 Showdown 特殊形态 ID 别名。

5. **本地模版对战**
   - 统一入口：`pba battle <template> [--opponent <template>] [--format <format>]`
   - 脚本入口：`scripts/run_battle_with_trainer.py`
   - 共享记录模块：`src/pokemon_battle_assistant/battle_recorder.py`
   - 当前对战双方仍是 `RecordingRandomPlayer`，但可使用自定义训练家队伍。
   - 输出目录：`battle_outputs/<battle_tag>/`
   - 导出：
     - `replay.html`
     - `record.json`
     - `report.md`

6. **随机对战烟雾测试**
   - 脚本：`scripts/poke_env_smoke_battle.py`
   - 依赖：本地 Pokémon Showdown server + poke-env
   - 用于验证 poke-env 与本地 Showdown 链路。

7. **离线局面分析器**
   - 输入：`examples/simple_battle.json`
   - 入口：`pba analyze examples/simple_battle.json --top 5`
   - 功能：基于属性克制、STAB、威力、HP 等启发式规则输出推荐操作和中文解释。

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

当前本机常见路径：

```text
~/Bian-workspace/pokemon-showdown
~/Bian-workspace/poke-env
~/Bian-workspace/pokemon-battle-assistant
```

## GitHub 状态

仓库：

```text
https://github.com/Biank0/pokemon-battle-assistant.git
```

当前分支状态：

```text
main 与 origin/main 对齐，工作区干净。
```

最新提交：

```text
fff249f Add contributors section to README
```

昨天重要提交：

```text
375d010 Add unified pba CLI, Chinese search support, and rewrite README
3377797 Add trainer template system and custom team battles
27d08f8 Add project progress note
38a368a Use generic local paths in docs
```

## 测试

当前测试：13 个，全部通过。

运行：

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

最近一次本地验证结果：

```text
Ran 13 tests in 0.002s
OK
```

安装后 CLI 入口验证：

```text
.venv/bin/pba --help
.venv/bin/pokemon-battle-assistant --help
```


最近一次真实本地 Showdown 对战验证：

```text
pba battle data/trainers/example_team.json --format gen9ou
battle_tag: battle-gen9ou-67
turns: 6
environment_steps: 14
record_json: battle_outputs/battle-gen9ou-67/record.json
steps_jsonl: battle_outputs/battle-gen9ou-67/steps.jsonl
step.done: null
step.info.episode_finished: true
```

最近一次随机双打真实本地 Showdown 验证：

```text
pba random-battle --format gen9randomdoublesbattle
battle_tag: battle-gen9randomdoublesbattle-82
turns: 20
environment_steps: 48
record_json: battle_outputs/battle-gen9randomdoublesbattle-82/record.json
steps_jsonl: battle_outputs/battle-gen9randomdoublesbattle-82/steps.jsonl
pre_battle_config.battle_kind: doubles
pre_battle_config.team_source_kind: random
pre_battle_config.control_modes: {player_1: random, player_2: random}
first observation game_type: doubles
```

## 本轮已完成

已按第一阶段目标完成第一版环境层抽象：

1. 新增 `src/pokemon_battle_assistant/environment.py`
   - `BattleRunConfig`：统一描述一次 battle run 的格式、队伍、来源、server、输出目录、metadata。
   - `BattleRunResult`：统一返回 battle tag、导出路径和结构化 record。
   - `BattleRunner`：封装 poke-env player 创建、battle 执行、replay/record/report 导出。
   - `build_step_records()`：把双方 observation 规范化为 step 记录。

2. 新增 `src/pokemon_battle_assistant/action_space.py`
   - `LegalAction`：序列化 legal action。
   - `legal_actions_from_snapshot()`：从 battle snapshot 提取 legal actions。
   - `chosen_action_from_message()`：把 poke-env order message 规范化成 chosen action。

3. 扩展 `src/pokemon_battle_assistant/battle_recorder.py`
   - 每个决策快照新增 `legal_order_messages`。
   - 每个决策快照新增 `chosen_order_message`。

4. 改造入口复用环境层
   - `pba battle` 不再直接拼完整 poke-env 流程，而是构造 `BattleRunConfig` 后调用 `BattleRunner`。
   - `scripts/run_battle_with_trainer.py` 复用 `BattleRunner`。
   - `scripts/poke_env_smoke_battle.py` 复用 `BattleRunner`。

5. 新增测试
   - `tests/test_environment.py` 覆盖 action space、config 序列化和 step record 生成。

6. P1 工程化修正
   - 新增 `src/pokemon_battle_assistant/pba_cli.py`，统一 CLI 实现迁入 package。
   - 根目录 `pba` 改为 thin wrapper，避免仓库脚本和安装后命令走不同代码路径。
   - `pyproject.toml` 新增/修正 console scripts：`pba` 与 `pokemon-battle-assistant` 均指向 `pokemon_battle_assistant.pba_cli:main`。
   - 每局 battle 额外导出 `steps.jsonl`，每行一个 `BattleStepRecord`。
   - 文档中明确：当前 `BattleRunner` 是完整跑局/导出数据的 runner，不是交互式 `reset()/step()` RL 环境。

7. 对战结构三轴收敛
   - Battle Kind：支持单打/双打，由 Showdown format 决定。
   - Team Source：支持 Showdown 随机队伍和导入训练家模版。
   - Control Mode：支持随机基线 `random` 和用户手动 `manual`。
   - 新增 `docs/BATTLE_STRUCTURE.md` 说明矩阵。

8. 随机双打支持
   - 新增 `pba random-battle` 入口，默认运行 `gen9randombattle`。
   - 支持 `pba random-battle --format gen9randomdoublesbattle`。
   - `battle_recorder.py` 兼容双打的 active Pokémon、available moves/switches 和 valid order messages。
   - 中文报告兼容双打 nested available moves。

9. 用户手动操作对战
   - `pba battle` 与 `pba random-battle` 均支持 `--manual`。
   - 也支持显式参数 `--player1-control manual --player2-control random`。
   - 手动模式会在终端列出 legal order messages，由用户输入编号。

## 当前缺口

1. 当前 `BattleRunner` 仍是“一次 run 一局完整 battle”的 runner，不是可交互 `reset()/step()` 环境；该边界已在代码和文档中明确。
2. `reward` 目前预留为 `None`，未来需要定义训练/评估用 reward。
3. `done` 目前保守预留为 `None`，整局结束状态记录在 `info.episode_finished`；未来交互式 step 环境再逐步返回 terminal done。
4. `chosen_action` 已记录环境基线随机动作，但尚未支持外部用户/RL agent 主动传入 action。
5. 需要增强批量对战和实验管理，而不仅是单局运行。
6. 训练家模版创建已有中文搜索，但尚未做完整数据合法性校验/自动修正。
7. `pba` 是仓库根目录脚本，`pyproject.toml` 的 console script 仍指向旧的离线分析入口。

## 第一阶段目标

第一阶段不做任何对战助手、启发式 bot 或 RL 算法。

目标是搭建一个完整、可复现、可观测、可扩展的宝可梦对战环境，支持两类接入方：

1. **用户接入**
   - 用户可以创建/导入队伍。
   - 用户可以发起本地模拟对战。
   - 用户可以获得 replay、结构化记录和中文报告。

2. **未来 RL 接入**
   - 环境能提供标准化 observation。
   - 环境能提供 legal actions。
   - 外部 agent/RL 代码未来可以选择 action 并推进 step。
   - 环境能返回 reward/done/info，并导出训练数据。

## 下一步建议

下一步仍然不要实现 `AssistantPlayer`。

建议继续做环境能力：

> 在 `BattleRunner` 基础上增加批量运行与 run-level 汇总，为后续 RL dataset/agent 接入做准备。

推荐小目标：

- `pba battle --num-battles N` 或新增 `pba batch`。
- 批量运行目录输出 `summary.json` 和聚合 `all_steps.jsonl`。
- 记录 Showdown/poke-env 版本、队伍快照、运行配置。
- 设计但暂不实现外部 action provider 接口。
