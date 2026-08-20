# 模块二 · 对战实验室（Battle Lab）设计说明

> 定位：把 teams.db 里的任意两支队伍放上对战台，本地规则型 bot 全自动操作，
> 跑 N 轮（默认 10，可到 50）产出结构化对战数据写入 battles.db，前端可视化展示。

## 1. 架构与数据流

```
teams.db 取队(export_text)
        │
        ▼
┌─ Showdown 服务器(8000, 自动拉起/复用) ──────────────────┐
│        ▲                    ▲                          │
│   CollectorBot(A)     CollectorBot(B)   ← poke-env     │
│   （继承库自带 SimpleHeuristicsPlayer，               │
│     决策零改动，外层包逐回合数据采集）                  │
└────────────┬───────────────────────────┬───────────────┘
             │ battle_against() ×N 轮    │
             ▼                           ▼
   battles.db 三层写入         session 聚合统计(胜率/回合/招式热榜)
        battle_sessions ← rounds_done 进度（前端 2s 轮询）
        battles         ← winner/end_turn/record_json
        battle_turns    ← 逐回合动作明细
```

四个组件（`src/pokemon_battle_assistant/lab/`）：

| 文件 | 职责 |
|---|---|
| `server.py` | Showdown 生命周期：探活 8000 → 自动 spawn `node pokemon-showdown start --no-security`（日志 `data/lab/showdown.log`），会话结束不杀、下次复用。用户零手工安装/启动 |
| `bot.py` | `CollectorBot`：继承 poke-env 自带 `SimpleHeuristicsPlayer`（分层启发式：伤害估算选招/威胁评估换人），`choose_move()` 里 super() 决策后记录一条动作（回合/双方在场/招式或换人）。采集失败静默跳过，绝不影响对战 |
| `runner.py` | 单场执行：两队 → 两个 bot → `battle_against(n_battles=1)` → 从 `battle.won/.lost` 判胜负 → battles + battle_turns 同事务写库 |
| `session.py` | N 轮编排（后台线程跑 asyncio）+ 每轮更新 rounds_done + 完成时聚合统计存 stats_json |

## 2. 关键决策与理由

### 2.1 bot 用规则型而不是 LLM
50 轮 × 约 8 回合 × 双方 ≈ 800 次决策。LLM 每次几秒、几万 tokens，跑量又慢又贵；
跑量的目的是**统计两队强弱**，bot 只要决策合理且**双方一视同仁**，胜负差异就反映队伍质量。
直接继承 poke-env 的 `SimpleHeuristicsPlayer`：决策质量有库保证、零维护成本。
将来要做"LLM 操作员 vs 启发式"的对照实验，只需换 bot 类（bot_config 已留配置位）。

### 2.2 双方都是自己的 bot → 双视角采集
poke-env 每次决策回调给完整局面（双方在场/HP/招式）。A、B 两侧都是 CollectorBot，
两边视角的动作都进 battle_turns（side='a'/'b'）——比解析引擎原始协议干净，
且 schema 与 battles_db_schema.md 完全对齐。

### 2.3 胜负判定用 `battle.won/.lost`
这版 poke-env（0.15.0）的 `AbstractBattle` 没有 `winner` 属性（老文档有，坑），
`won`/`lost` 是布尔值，A 视角 won 即 a 胜。首轮冒烟正是靠这个修正了"全 draw"的 bug。

### 2.4 赛制一致性前置校验
BSS 队伍（Lv50）拿去打 OU（Lv100）会被服务器拒队、bot 挂死等待。
`POST /api/lab/start` 先比对两队 format 与请求赛制，不一致直接 400，错误信息中文可读。
（开发中实测：xiaobian 标错 gen9ou 导致拒队，顺手修正了 teams.db 的 format 字段。）

### 2.5 第一期仅支持单打（BSS / OU）
VGC 双打路径未适配，实测会卡死：
- poke-env 的 `DoubleBattle.active_pokemon` 返回**列表**（两只在场），
  CollectorBot 的单打采集假设会抛 AttributeError 被 `except: pass` 吞掉 → 明细/热榜/分析全空
- 双打是 6 选 4 + 双指令组合（`DoubleBattleOrder`）+ 保护/目标选择，采集与决策都要单写

处理：`POST /api/lab/start` 白名单（`SUPPORTED_FORMATS = {gen9bssregi, gen9ou}`），
前端赛制只留单打两项、双打队伍下拉禁用并标注"暂不支持"；AI 建队仍可建 VGC 队
（标注"暂不能进实验室"），二期适配双打采集后再放开。

## 3. 产出数据（battles.db 三层）

- **battle_sessions**：一任务一行，`rounds_done` 供轮询，`stats_json` 存聚合
  （比分/胜率/平均回合/招式热榜 TOP10，招式中文名 JOIN dex 渲染好）
- **battles**：一场一行，winner(a/b/draw)、end_turn、battle_tag（Showdown 回放标识）、
  record_json（双方动作全记录保底层）
- **battle_turns**：一次动作一行（turn/side/action_type/actor/move/target），
  是"对战详情页时间线"和"模块三分析"的直接数据源。HP 快照不记（已决策，record_json 兜底）

## 4. API

| 路由 | 说明 |
|---|---|
| `POST /api/lab/start` | {team_a, team_b, format, rounds} → {session_id}，后台线程立即返回 |
| `GET /api/lab/sessions` | 历史会话列表（含比分摘要） |
| `GET /api/lab/session/{id}` | 进度 + 逐场结果 + 聚合统计（前端 2s 轮询） |
| `GET /api/lab/battle/{id}` | 单场逐回合明细，宝可梦/招式已中文渲染 |

## 5. 前端（Vue3 + Element Plus + ECharts，全部 vendor 本地化）

- **实验室页 /#/lab**：A/B 队下拉（中文名+赛制+来源）→ 轮数滑块 → 开跑 →
  进度条 → 比分卡片 / 逐场胜负序列色块（可点进明细）/ 招式热榜柱状图 / 场次表。
  刷新页面自动恢复观察进行中的会话（跑 50 轮时可以切走再回来）
- **明细页 /#/lab/battle/:id**：el-timeline 逐回合时间线，己方实心蓝/对手空心橙，
  招式/换人中文显示
- ECharts 从 CDN 下载进 `frontend/vendor/`（1MB），与 Element Plus 同策略零外网依赖

## 6. 验证记录（2026-08-19）

| 层 | 方式 | 结果 |
|---|---|---|
| 离线单测 | `python -m unittest discover -s tests`（29 个，含模块一 21） | 全过 |
| 引擎冒烟 | tests/manual/smoke_battle.py：真实 2 场（xiaobian vs bss_balance） | winner 判定/44 条回合明细语义正确 |
| API 冒烟 | tests/manual/smoke_lab_api.py：3 轮会话全链路 | 比分 1-2、热榜中文、明细时间线 ✓ |
| 浏览器 E2E | 自动化浏览器全流程 | 表单 13 队下拉/跑量/图表/明细/历史 全 PASS |

开发中修掉的真 bug：winner 属性不存在（全 draw）→ won/lost；Move 导入路径错（明细空）
→ battle.move；stats_json 列未建（schema --rebuild 未实现）→ 补 rebuild；
xiaobian 赛制标错 gen9ou → 修数据；前端 el-select filterable+插槽组合渲染异常 → 朴素写法。

## 7. 已知边界（v1）

- **顺序执行**：一轮一场串行（50 轮约 8~15 分钟），并发留待后续
- **双打（VGC）支持**：bot 用 singles 决策路径，双打时 poke-env 会走默认兜底，
  VGC 对战质量有限（能打完、数据完整，但决策不针对双打优化）
- **error 场次**：引擎异常记 winner='error' 不进胜率，record_json 保留现场
- Showdown 服务器由首个会话拉起后常驻；`data/lab/showdown.log` 可排查引擎问题
