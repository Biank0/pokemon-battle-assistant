# 项目进度记忆

更新时间：2026-08-15（夜间接力模式）

> **注意：本文件以下（分隔线之后）的旧内容写于 2026-06-01，方向已过时
>（旧方向是 VGC 双打）。当前主线是 BSS Regulation I 单打 + AI 助手，
> 以本章节和 `改进prompt.md` 为准。**

## 当前状态（2026-08-16 夜间接力更新）

- Phase 1 ✅ BSS 规则适配 + 感知层 + 记忆层 + LLM Client（commit 89dc5b5）
- Phase 2 ✅ Team Builder Module：工具四件套 + TeamBuilderAgent + `pba build-team`（commit c90eb80）
- Phase 3 ✅ Battle Module：对战工具 5 件套（39f5da4）+ BattleAgent（0e46efe）+ RecordingAgentPlayer + `pba agent-battle`（54b54d1）
- Phase 4 ✅ Lab Module `pba lab run`（93aafd5）+ Analysis Module `pba analysis`（27dd4aa）
- Phase 5 ✅ Orchestrator 闭环 `pba closed-loop`（e5ece97）+ FastAPI `pba serve`（efa7d18）
- Phase 6 ✅ 免构建 Vue 前端 9 页面 + 截图（3ef9bd2）
- Phase 7 🔄 文档收尾：README 已精简（<150 行），新增 `docs/ARCHITECTURE.md`、`docs/BSS_RULES.md`；剩余 7.2 示例数据（Agent 对战 record / 建队结果 / 分析报告示例）

环境要点：
- 项目在 `E:\workspace\pokemon-battle-assistant`，系统 Python 3.13 直接可用（已 editable 安装）
- 本地 Showdown 在 `E:\workspace\pokemon-showdown`
- LLM 配置：项目根 `.env`（OPENAI_API_KEY / LLM_BACKEND / OPENAI_BASE_URL / OLLAMA_BASE_URL），
  LLMClient 启动时自动加载；没有 key 时只做 mock 测试，不要卡在等 key
- 验证命令：`python -m unittest discover -s tests` + `python -m ruff check .` + `python -m mypy src`

## 夜间接力执行规则（自动化会话必读）

1. 先 `git -C E:\workspace\pokemon-battle-assistant log --oneline -8` 和 `git status`，再读本文件，确认进度和下一个任务
2. 任务清单在根目录 `改进prompt.md` 第七章（按 Phase 顺序），对照上面的当前状态找下一个未完成项
3. 沙箱限制：Write/Edit 工具不能直接写 E 盘，用 python 脚本写文件（写到工作目录再执行）
4. 每完成一个任务：全量测试 + ruff + mypy 全绿后 git 本地提交；**绝不 push 远程**
5. 完成或收尾时更新本文件的「当前状态」章节
6. 遇到阻塞（缺 API key、环境问题、设计存疑）：跳过该任务并在本文件记录原因，继续下一个不被阻塞的任务
7. 真实 LLM 实测仅当 `.env` 已配置时执行；用少量对局验证即可，不要大量消耗
8. 若 git status 显示有未提交改动（可能是上次会话中断），先理解并补完测试再提交

---


## 当前方向

项目后续主要围绕 **VGC 双打本地环境与建队助手** 展开。当前优先支持本地 Pokémon Showdown 的：

```text
gen9vgc2026regi
```

也就是 VGC 双打 6 选 4、50 级、公开队表、最多 2 只 Restricted Legendary 的规则环境。

不再继续推进 BSS / 6 选 3 单打方向；已有通用 team preview 机制可以复用，但产品主线聚焦 VGC 双打。

## 当前核心能力

### 1. 统一 CLI：`pba`

主要命令：

```bash
pba doctor
pba team list
pba team create
pba team show <team>
pba team preview <team>
pba team validate <team> --format gen9vgc2026regi
pba battle <team> --format gen9vgc2026regi --select manual
pba random-battle --format gen9randomdoublesbattle
pba analyze examples/simple_battle.json --top 5
```

`python -m pokemon_battle_assistant ...` 已修正为同样走统一 `pba_cli` 入口。

### 2. VGC 队伍创建引导

`pba team create` 现在默认推荐：

```text
gen9vgc2026regi
```

创建时会提示：

- VGC 是双打 6 选 4。
- 前 2 只是首发，后 2 只是后排。
- Item Clause：道具通常不能重复。
- 多数宝可梦需要考虑 `Protect`。
- 队伍应考虑速度控制、支援动作和选出逻辑。

### 3. 队伍合法性判断

`pba team validate` 现在有两层：

1. 本地友好检查：JSON、名称、EV/IV、性格、特性、太晶属性、重复招式、中文名误填等。
2. Showdown 权威检查：调用本地 Pokémon Showdown `validate-team`，按指定 format 判断是否合法。

示例：

```bash
pba team validate vgc_rain_balance --format gen9vgc2026regi
```

### 4. VGC 6 选 4 team preview

`pba battle` 支持真正的 Showdown team preview，不是裁剪队伍。

```bash
pba battle vgc_rain_balance --format gen9vgc2026regi --select 1,2,3,4
pba battle vgc_rain_balance --format gen9vgc2026regi --select manual
pba battle vgc_rain_balance --format gen9vgc2026regi --select random
```

`--select` 支持：

- `auto`：默认选择前 N 只。
- `manual`：终端交互选出。
- `random`：随机选出。
- `1,2,3,4`：固定编号选出。

VGC 中前 2 只是首发，后 2 只是后排。

对手也支持：

```bash
--opponent-select random
--opponent-select 1,2,3,4
```

### 5. 对战记录导出

每局对战导出：

```text
battle_outputs/<battle_tag>/
├── replay.html
├── record.json
├── report.md
└── steps.jsonl
```

`record.json` 现在包含：

- `pre_battle_config`
- `battle`
- `player_1_observations`
- `player_2_observations`
- `steps`
- `team_preview`

其中 `team_preview` 会记录：

```json
{
  "selected_slots": [1, 2, 3, 4],
  "command": "/team 1234",
  "required_count": 4,
  "mode": "fixed"
}
```

### 6. 四支合法 VGC 示例队

已新增并通过 `gen9vgc2026regi` 合法性校验：

```text
data/trainers/vgc_rain_balance.json
data/trainers/vgc_trick_room_calyrex.json
data/trainers/vgc_sun_koraidon.json
data/trainers/vgc_psyspam_calyrex.json
```

说明文档：

```text
docs/VGC_STARTER_TEAMS.md
```

### 7. 热门规则文档

```text
docs/formats/README.md
docs/formats/gen9ou.md
docs/formats/gen9doublesou.md
docs/formats/gen9vgc2026regi.md
```

虽然项目主线转向 VGC，OU / Doubles OU 文档仍保留作参考。

## 当前重要模块

```text
src/pokemon_battle_assistant/pba_cli.py             # 统一 CLI
src/pokemon_battle_assistant/environment.py         # BattleRunner / BattleRunConfig
src/pokemon_battle_assistant/battle_recorder.py     # poke-env player 记录、team preview、报告生成
src/pokemon_battle_assistant/team_selection.py      # 6选4/选出配置与校验
src/pokemon_battle_assistant/showdown_validator.py  # Showdown TeamValidator 桥接
src/pokemon_battle_assistant/showdown_formats.py    # 读取 format pickedTeamSize 等信息
src/pokemon_battle_assistant/validators.py          # 本地友好队伍校验
src/pokemon_battle_assistant/showdown_db.py         # 本地 Showdown 数据库查询
scripts/trainer_cli.py                              # 队伍创建/管理交互逻辑，当前仍由 pba team 动态调用
```

## 外部依赖

本地对战依赖：

```text
~/Bian-workspace/pokemon-showdown
~/Bian-workspace/poke-env
```

合法性校验不需要启动 Showdown server，但需要本地 `pokemon-showdown` 代码。

真正对战需要先启动 server：

```bash
cd ~/Bian-workspace/pokemon-showdown
node pokemon-showdown start --no-security
```

## 最近验证

测试：

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

最近结果：

```text
Ran 22 tests
OK
```

四支 VGC 示例队均通过：

```bash
pba team validate <team> --format gen9vgc2026regi
```

## 已知不完善点

1. Showdown 原始错误的中文解释仍较粗糙，尤其是事件配布、IV、Item Clause、Restricted 限制等。
2. `scripts/run_battle_with_trainer.py` 和 `scripts/poke_env_smoke_battle.py` 是旧调试入口，主入口应优先使用 `pba`。
3. 旧的离线 `pba analyze` 仍是单打启发式 MVP，和 VGC 双打主线尚未整合。
4. VGC 手动选出界面还可以显示更多信息，例如道具、特性、太晶、主要招式和对方公开队表。
5. `showdown_formats.py` 当前通过 Node 子进程读取 format 元数据，后续可加缓存或做 `pba format show`。
6. 若未来要 pip 发布，需要把 `data/` 配成 package data；当前主要面向本地仓库运行。

## 推荐下一步

1. 优化 Showdown 错误中文解释。
2. 给 VGC 选出界面增加更完整的队伍信息展示。
3. 为四支示例队增加 smoke battle 脚本或 CI 可选校验。
4. 开始做 VGC 选出建议/首发推荐模块。
