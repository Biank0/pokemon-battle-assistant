# Pokemon Battle Assistant (PBA)

**v0.1 · BSS 单打 AI 对战助手**

基于 LLM Agent 的宝可梦对战助手：自然语言建队、Agent 自动对战、批量实验、深度复盘，并通过闭环编排自动迭代优化队伍。主线规则为 BSS Regulation I（`gen9bssregi`，6 选 3 单打）。

## 架构总览

```text
┌───────────────────────────────────────────────────────────┐
│                 Vue 前端（frontend/，免构建）                │
│  首页 · 队伍管理 · AI 建队 · 对战面板 · 实验室 · 分析 · 闭环  │
└────────────────────────────┬──────────────────────────────┘
                             │ HTTP
┌────────────────────────────▼──────────────────────────────┐
│              FastAPI 后端（pba serve，:8000）                │
├──────────┬──────────┬─────────┬──────────┬────────────────┤
│  Team    │  Battle  │   Lab   │ Analysis │  Orchestrator  │
│  Builder │  Module  │  Module │  Module  │    闭环编排     │
│  AI 建队 │ 单局对战  │ 批量模拟 │ 深度复盘  │ 建队→跑量→     │
│          │          │         │          │ 复盘→迭代       │
├──────────┴──────────┴─────────┴──────────┴────────────────┤
│               Environment Layer（共享底层）                  │
│    Pokemon Showdown + poke-env · 感知层 · 记忆层 · 工具集   │
│    LLM Client（OpenAI / Ollama 双后端）                     │
└───────────────────────────────────────────────────────────┘
```

5 个功能模块自包含各自的 Agent、工具与 LLM 配置，共享底层的环境连接、局面感知与记忆。详见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 闭环流程

Orchestrator 把各模块串成自我改进的闭环：

```text
自然语言需求 ──▶ Team Builder（AI 建队 + Showdown 合法性校验修正）
                        │
                        ▼
              Lab Module（vs 多对手 × N 局批量跑量）
                        │
                        ▼
              Analysis Module（胜率统计 + 逐回合复盘 + 改进建议）
                        │
                        ▼  迭代（默认手动确认，--auto 全自动）
              Team Builder（基于分析报告迭代队伍）… 循环
```

每轮的队伍版本、胜率对比与优化建议都落盘到 `orchestrator_outputs/<run_id>/`，可随时回看对比。

## 快速开始

### 1. 环境准备

```bash
python -m pip install -e .          # Python 3.10+

cd /path/to/pokemon-showdown        # 本地对战引擎（对战功能需要）
node pokemon-showdown start --no-security
```

LLM 配置：项目根 `.env`（没有 Key 时 Agent 自动走 mock，测试与开发不受影响）

```text
LLM_BACKEND=openai                       # 或 ollama
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=...                      # 可选，兼容代理
OLLAMA_BASE_URL=http://localhost:11434   # ollama 后端时使用
```

### 2. CLI 核心命令

| 命令 | 说明 |
|---|---|
| `pba doctor` | 一键环境检查 |
| `pba team list / validate / create ...` | 队伍管理与合法性校验 |
| `pba build-team "需求"` | AI 建队：需求解析 → 工具检索 → 生成 → 校验修正 |
| `pba agent-battle <team>` | Agent 自动对战，导出决策日志 |
| `pba lab run <team> --opponents a,b` | 批量模拟 + 胜率统计报告 |
| `pba analysis <battle_tag>` | 深度复盘：回放 + 逐回合评估 + 对手画像 |
| `pba closed-loop "需求" --opponents a,b` | 闭环：建队 → 跑量 → 复盘 → 迭代 |
| `pba serve` | 启动 FastAPI 后端 + Web 前端 |

### 3. Web 界面

```bash
pba serve        # 打开 http://127.0.0.1:8000
```

免构建 Vue 3 + Element Plus 前端（CDN 依赖 + 原生 ES module，无需 npm），覆盖 AI 建队、对战面板、实验室控制台、分析报告与闭环流程。

## BSS 规则与示例队

主线规则 `gen9bssregi`：单打、带 6 选 3、自动 50 级、Item Clause、至多 2 只受限传说。完整说明见 [docs/BSS_RULES.md](docs/BSS_RULES.md) 与 [docs/formats/gen9bssregi.md](docs/formats/gen9bssregi.md)。

内置示例队（均已过合法性校验）：`bss_balance`（平衡）、`bss_sun`（晴天）、`bss_trick_room`（戏法空间），位于 `data/trainers/`。

## 数据与输出

| 目录 | 内容 |
|---|---|
| `data/trainers/` | 队伍 JSON（含 AI 生成队伍） |
| `battle_outputs/<battle_tag>/` | 单局 replay / record.json / steps.jsonl / 中文报告 |
| `lab_outputs/` | 批量实验报告与统计 |
| `analysis_outputs/` | 深度复盘报告 |
| `orchestrator_outputs/<run_id>/` | 闭环每轮记录（迭代链 + 胜率对比） |
| `examples/` | 示例数据：Agent 对战 record、分析报告、AI 建队结果（见 `examples/README.md`） |

## 测试与质量

```bash
python -m unittest discover -s tests   # 全量单测（LLM 全 mock，无需 Key）
python -m ruff check .                 # 代码风格
python -m mypy src                     # 类型检查
```

## 更多文档

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 模块化架构与闭环设计
- [docs/BSS_RULES.md](docs/BSS_RULES.md) — BSS Regulation I 规则详解
- [docs/PROGRESS.md](docs/PROGRESS.md) — 项目进度记录
- [docs/BATTLE_STRUCTURE.md](docs/BATTLE_STRUCTURE.md) — 对战结构说明

## Contributors

- [Biank0](https://github.com/Biank0)
- Claude (Anthropic)
- ChatGPT (OpenAI)
