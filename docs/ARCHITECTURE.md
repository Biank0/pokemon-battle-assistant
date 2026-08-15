# PBA 模块化架构与闭环设计

> 本文描述 Pokemon Battle Assistant v0.1 的功能模块化架构、共享环境层与闭环编排设计。

## 1. 设计目标

- **Agent 特性齐全**：LLM 调用、工具使用、记忆机制、规划能力（闭环编排）
- **模块自治**：5 个功能模块各自包含 Agent / 工具 / LLM 配置，可独立使用与测试
- **底层共享**：对战引擎连接、局面感知、记忆、LLM Client 只实现一次
- **决策可观测**：每回合的观察摘要、工具调用、决策理由、fallback 标记全部落盘
- **无 Key 可开发**：LLM 缺失时自动降级 mock，单测与 CI 不依赖真实 API

## 2. 全局架构

```text
┌───────────────────────────────────────────────────────────┐
│                 Vue 前端（frontend/，免构建）                │
└────────────────────────────┬──────────────────────────────┘
                             │ HTTP (fetch)
┌────────────────────────────▼──────────────────────────────┐
│           FastAPI（api/app.py + api/routes/，pba serve）    │
├──────────┬──────────┬─────────┬──────────┬────────────────┤
│  Team    │  Battle  │   Lab   │ Analysis │  Orchestrator  │
│  Builder │  Module  │  Module │  Module  │    Module      │
├──────────┴──────────┴─────────┴──────────┴────────────────┤
│               Environment Layer（共享底层）                  │
│  Pokemon Showdown + poke-env | perception/ | memory/       │
│  agent/llm_client.py | tools/ | environment.py             │
└───────────────────────────────────────────────────────────┘
```

## 3. Environment Layer（共享底层）

| 组件 | 位置 | 职责 |
|---|---|---|
| 对战引擎 | `environment.py` / `battle_recorder.py` | poke-env 封装，跑完整对战并导出 replay / record / steps / 报告 |
| 动作空间 | `action_space.py` | 合法动作序列化（move / switch / terastallize） |
| 感知层 | `perception/` | 从 `AbstractBattle` 提取结构化 `BattleObservation` |
| 记忆层 | `memory/` | 本局事件、跨局统计、对手建模 |
| LLM Client | `agent/llm_client.py` | OpenAI / Ollama 双后端，工具调用协议与 JSON 规范化 |
| 工具集 | `tools/` | 建队 4 件套 + 对战 5 件套，统一 `run_tool` 注册表 |

### 3.1 感知层（perception/）

| 文件 | 职责 |
|---|---|
| `observation.py` | `BattleObservation`：双方存活 / HP / 状态 / 太晶 / 已揭示信息 的结构化快照 |
| `tracker.py` | 跟踪对手已揭示的招式、道具、特性、太晶 |
| `classifier.py` | 局面阶段分类：opening / midgame / endgame / crisis |
| `summary.py` | 中文局面摘要，供 LLM prompt 使用 |

### 3.2 记忆层（memory/）

| 文件 | 职责 |
|---|---|
| `short_term.py` | 本局事件流（换人 / 击倒 / 状态 / 太晶） |
| `long_term.py` | 跨局统计与经验，持久化到 `data/memory/long_term.json` |
| `opponent.py` | 对手建模：行为预测、威胁评估 |
| `manager.py` | `MemoryManager` 统一入口：update / update_after_turn / record_action |
| `event_log.py` | 事件日志数据结构 |

### 3.3 LLM Client

- 统一接口 `LLMClient.chat(messages, tools=...)`，返回 `LLMResponse`
- 后端由 `.env` 的 `LLM_BACKEND` 决定（openai / ollama），兼容 `OPENAI_BASE_URL` 代理
- 模块级可覆盖：不同模块可指定不同 backend / model（如建队用云端、Lab 用本地）
- 无 Key 时抛出明确错误，由上层降级 mock（测试全部走 fake LLM）

## 4. 功能模块层（modules/）

| 模块 | 目录 | 核心 | 工具 | 输出 |
|---|---|---|---|---|
| Team Builder | `team_builder/` | `TeamBuilderAgent`：需求解析 → 工具检索 → 生成 → 校验修正 → 保存；`iterate_team` 基于分析报告迭代 | 环境热门 / 属性互补 / 打击面 / 规则校验 | `data/trainers/` + 建队结果（含迭代链 `parent_team_hash`） |
| Battle | `battle/` | `BattleAgent`（team preview 选出 + 逐回合决策）+ `BattleSession` + `RecordingAgentPlayer` | 伤害计算 / 属性查询 / 速度比较 / 威胁评估 / 特性查询 + 记忆层 | `battle_outputs/`（record.json 含决策日志） |
| Lab | `lab/` | `LabRunner` 批量对战 + `stats` 统计 + `reporter` 报告；简化决策换吞吐 | 无（heuristic 简化决策） | `lab_outputs/`（每局 + 汇总报告） |
| Analysis | `analysis/` | `replayer` 回放重建 + `reviewer` 逐回合评估 + `profiler` 对手画像 + `advisor` 策略建议 | 复用对战工具 + replay 数据 | `analysis_outputs/` |
| Orchestrator | `orchestrator/` | 闭环状态机编排，串联上面四个模块 | 调用各模块 | `orchestrator_outputs/<run_id>/` |

## 5. 接口层

### 5.1 CLI（`pba`）

统一入口 `pba_cli.py`：`doctor` / `team` / `battle` / `random-battle` / `analyze` / `build-team` / `agent-battle` / `lab run` / `analysis` / `closed-loop` / `serve`。

### 5.2 FastAPI（`api/`）

- `app.py`：应用工厂 + 依赖注入 + 前端静态托管（SPA 回退）
- `routes/`：`teams` / `team_builder` / `battle` / `lab` / `analysis` / `orchestrator` 六组 RESTful 路由
- `jobs.py`：长任务（对战 / 实验 / 闭环）异步执行与状态查询

### 5.3 Vue 前端（`frontend/`）

免构建方案：CDN/vendor 本地化的 Vue 3 + Vue Router + Element Plus，原生 ES module 组织 9 个页面（首页 / 队伍列表 / 队伍详情 / AI 建队 / 对战面板 / 实验室 / 分析列表 / 分析详情 / 闭环流程），由 FastAPI 直接静态托管。

## 6. 闭环设计（Orchestrator）

### 6.1 状态机

```text
building ──▶ battling ──▶ analyzing ──▶ iterating ──┐
   ▲                                             │
   └─────────（未达 stop-win-rate 且轮数未耗尽）───┘
                               │ 达标 / 轮数耗尽 / 手动停止
                               ▼
                          done / stopped
```

- **building**：`TeamBuilderAgent.generate_team`（首轮）/ `iterate_team`（后续轮）
- **battling**：`LabRunner` vs 每个对手 × `--battles` 局，可并发
- **analyzing**：`AnalysisEngine` 汇总胜率、逐回合评估、弱点与改进建议
- **iterating**：默认人工确认（CLI 提示 / Web「确认迭代」按钮），`--auto` 自动继续
- **终止条件**：达到 `--stop-win-rate`、完成 `--iterations` 轮、手动停止

### 6.2 Run 记录

`orchestrator_outputs/<run_id>/` 保存每轮：队伍快照、胜率对比、分析报告、迭代链（`parent_team_hash`），闭环结束后可完整回放整个优化历史。

## 7. 关键设计决策

1. **模块自包含 LLM 配置**：建队 / 对战 / 复盘可用不同 backend + model，LLMClient 统一抽象
2. **校验闭环**：AI 生成队伍必须过 Showdown `TeamValidator`，非法时把错误信息回喂 LLM 修正（上限 N 次）
3. **决策可观测**：每回合记录 observation 摘要 / 工具调用链 / 决策理由 / fallback 标记，复盘与调试共用同一份数据
4. **mock 优先**：所有单测用 fake LLM，CI 不需要真实 Key；真实 LLM 仅在 `.env` 就绪时少量验证
5. **免构建前端**：vendor 本地化 CDN 依赖，避免离线 / 沙箱环境 npm build

## 8. 目录结构（src）

```text
src/pokemon_battle_assistant/
├── agent/            # LLM Client、决策日志（llm_client.py）
├── api/              # FastAPI：app.py / routes/ / jobs.py
├── memory/           # 记忆层：short/long/opponent/manager
├── modules/
│   ├── team_builder/ # parser / generator / agent / result
│   ├── battle/       # agent_player / session / exporter
│   ├── lab/          # config / runner / stats / reporter
│   ├── analysis/     # replayer / reviewer / advisor / profiler / engine
│   └── orchestrator/ # orchestrator / record
├── perception/       # observation / tracker / classifier / summary
├── tools/            # 建队 + 对战工具，统一注册表
├── environment.py    # BattleRunner / BattleRunConfig
└── pba_cli.py        # 统一 CLI
```
