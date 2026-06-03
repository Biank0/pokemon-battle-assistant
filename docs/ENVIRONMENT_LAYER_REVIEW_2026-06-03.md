# 环境层架构检查与改进清单（2026-06-03 16:30）

## 检查范围

- `BattleRunner` / `BattleRunConfig`：本地 Showdown 对战运行、记录导出。
- `battle_recorder.py`：poke-env player 封装、team preview、局面快照、报告生成。
- `action_space.py`：从快照生成合法动作与已选动作记录。
- `team_selection.py`：VGC / bring-6-pick-N 队伍选出策略。
- `pba_cli.py`：用户入口、对战前检查、输出文件提示。
- `tests/test_environment.py`：环境层与 CLI 友好能力的单元测试。

## 当前架构判断

整体分层已经合理：

1. **运行层**：`BattleRunner` 只负责运行完整对战并导出记录，没有把策略/助手逻辑混进环境。
2. **记录层**：`RecordingRandomPlayer` / `RecordingManualPlayer` 收集 poke-env 快照，保留 Showdown 原始 order message，适合后续 RL/Agent 复用。
3. **动作层**：`legal_actions_from_snapshot` 将合法动作转成稳定 JSON，已兼容单打、双打复合 order。
4. **选出层**：`TeamSelectionConfig` / `TeamSelectionRecord` 把 VGC 6 选 4 从对战逻辑中抽出，方向正确。
5. **用户入口**：`pba battle` / `pba random-battle` 是统一 CLI，已经比旧脚本入口更清晰。

## 发现的问题 / 可打磨点

1. **VGC 双打复合动作语义不够准确**  
   之前 `chosen_action_from_message("/choose move heatwave -1, move protect")` 会被识别成单个 `move`，这对 VGC/RL 数据不友好；双打每回合往往是两个位置的组合动作，应该当作原子 `order` 保存。

2. **手动 6 选 4界面信息不足**  
   之前 team preview 只显示宝可梦名，用户很难根据公开队表做真实选出；VGC 需要至少看到属性、道具、特性、招式摘要。

3. **输出目录不够可配置**  
   CLI 只能写到默认 `battle_outputs`，批量实验、不同规则/不同 agent 实验时不方便归档。

## 已完成改进

1. **修正双打复合已选动作记录**
   - 文件：`src/pokemon_battle_assistant/action_space.py`
   - 改动：如果 chosen order 是带逗号的复合指令，或是 `/team ...` 指令，则记录为 `kind="order"`。
   - 价值：后续 VGC 学习框架不会把一个双打组合动作误标成单个招式。

2. **增强手动 team preview 显示**
   - 文件：`src/pokemon_battle_assistant/battle_recorder.py`
   - 新增：`teampreview_option_line()`。
   - 改动：手动选出时显示：编号、中文名/种族、属性、道具、特性、招式。
   - 价值：用户可以在终端直接做更接近实战的 VGC 选出判断。

3. **增加 CLI 输出目录参数**
   - 文件：`src/pokemon_battle_assistant/pba_cli.py`
   - 新增：`pba battle --output-root <dir>` 与 `pba random-battle --output-root <dir>`。
   - 价值：实验数据可以按 agent / 规则 / 日期分目录保存，接口更友好。

4. **补充回归测试**
   - 文件：`tests/test_environment.py`
   - 新增：`test_chosen_double_order_stays_atomic_order`。
   - 验证：`PYTHONPATH=src python3 -m unittest discover -s tests`，23 tests OK。

## 仍建议后续继续打磨

1. 给 `record.json` 增加更明确的 schema 文档，例如 `docs/ENVIRONMENT_SCHEMA.md`。
2. 为 `legal_actions` 增加面向 agent 的结构化字段：双打槽位、目标、是否 Protect、是否 switch、是否 Tera。
3. 提供 `pba format show gen9vgc2026regi`，把 pickedTeamSize、gameType、规则摘要输出给用户。
4. 给 VGC team preview 做一个“选出建议接口”：输入双方公开队表，输出首发二只+后排二只+理由。
5. 批量对战建议增加 `pba battle --n-battles` 或单独 `pba batch`，并在输出目录记录 experiment metadata。
