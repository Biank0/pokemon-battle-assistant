# 数据层全库设计分析

> 本文回答两个问题：**为什么是四个库这样设计**，以及**每个库的字段如何支撑整体功能**。
> 字段级细节见各库专属文档：[dex_db_schema.md](dex_db_schema.md) / [teams_db_schema.md](teams_db_schema.md) / [battles_db_schema.md](battles_db_schema.md) / [analysis_db_schema.md](analysis_db_schema.md)

## 一、全库数据流：一条流水线，四道工序

整个系统的业务流是：**建队 → 对战 → 分析**。数据层把每道工序的产物各存一库， dex 作为知识底座服务全流程：

```
                    ┌────────────────────────────────────────────┐
                    │  dex.db（只读知识库）                        │
                    │  物种/招式/特性/道具/相克/可学招式             │
                    └──────┬──────────────┬──────────────┬───────┘
                    筛候选池│         校验合法性│         中文渲染│
                           │              │              │
                           ▼              │              │
   用户需求 ──► 模块一 AI建队 ──► teams.db（队伍活库）        │
                           │        │  结构化成员 + export_text │
                           │        │              │           │
                           │        ▼ 取队(零转换)   │           │
                           │   模块二 对战Lab ──► battles.db（对战记录库）
                           │        │              │           │
                           │        ▼ 读聚合/回合明细 │           │
                           │   模块三 分析Bot ──► analysis.db（分析索引库）
                           │                       │           │
                           ▼                       ▼           ▼
                      前端三个页面（建队/对战/分析）+ 文档文件（docs/*.md|json）
```

**外键链就是流水线的物理化**：

```
dex.species.id ──► team_members.species_id ──► teams.id ──► battle_sessions.team_a/b_id
                                                        └──► battles.session_id
                                                              └──► battle_turns.battle_id
                                                                      └──► analysis_highlights.battle_id
```

任何一个分析结论，都能顺着这条链一路回溯到"当时的用户需求是什么、用了哪个版本的 skill、当时队伍长什么样"。

## 二、为什么是四个库，而不是一个大库

**核心动机：一库一文件、一模块一写方。**

1. **消灭模块间代码耦合**。三个模块（建队/对战/分析）永不共享数据库连接对象，彼此只能通过"读对方的库"协作。上次重构的教训之一就是模块间直接调用导致 bug 连环传导；物理隔离后，模块一的 bug 物理上无法写坏对战记录。
2. **写锁不竞争**。SQLite 单写者模型下，四个文件 = 四个独立写锁。50 轮对战写 battles.db 时，用户同时在建队写 teams.db，互不阻塞。
3. **生命周期不同，重建策略不同**。dex 可整库重建（源数据在 JSON/引擎里）；teams/battles/analysis 是累积活库，删了就真没了。分库让"哪些数据能删、哪些不能"从纪律问题变成物理事实。
4. **备份与体积管理**。dex 4.7MB / teams 76KB / battles 会持续膨胀 / analysis 文档在磁盘。想备份"资产"只需拷 teams+battles+analysis，不用带上 4.7MB 的静态知识。

## 三、每个库的字段如何支撑功能

### dex.db：为"LLM 建队"优化的知识底座

模块一的流程是：**用户需求 → SQL 筛候选池 → 喂给 LLM → 校验产出**。字段设计逐条对应这个流程：

| 字段设计 | 支撑的功能 |
|---|---|
| 种族值六维拆成独立列 + 索引 | 候选池筛选是纯 SQL：`WHERE spe>=100 AND spa>=110` 秒出"高速特攻手"名单，不加载全图鉴 |
| `type1/type2` 拆两列 | "晴天队要火系"→ `WHERE type1='Fire' OR type2='Fire'`；单列 JSON 做不了这种查询 |
| `learnsets` 表（物种×招式 5 万行） | **合法性校验的唯一依据**：LLM 说"喷火龙学得会十万伏特"，一条 SQL 就能戳穿——这是防止 AI 幻觉落库的闸门 |
| `type_chart` 只存非 1 倍组合（120 行） | 查不到即 1 倍，表小加载快；建队 skill 算"打点覆盖"时全表读入内存也毫无压力 |
| 中文名内嵌各表（name_zh） | 展示零二次翻译：任何库 JOIN dex 即得中文，前端不需要翻译模块 |
| `formats` JSON、`abilities.rating` | 给 LLM 的候选池自带"这个形态能不能上 / 这个特性强不强"的先验，减少模型瞎选 |

**只读 + 整库重建**的特性意味着：引擎升级、翻译补全后，重跑一个脚本知识库即焕新，四个库中唯一可以"随手删"的。

### teams.db：双表示设计 = 结构化 × 可执行

队伍数据有两个完全不同的消费者，字段设计同时伺候：

| 消费者 | 需求 | 支撑字段 |
|---|---|---|
| 模块二（pokeenv） | 要 Showdown 导出串，直接开打 | `export_text`——零转换喂给引擎，拼串错误在建队时就消灭 |
| 前端/分析 | 要能按物种查、能渲染中文、能看配置 | `team_members` 结构化列，全部 slug 化，ATTACH dex 一次 JOIN 全中文 |

**溯源三件套**（`requirement_prompt` + `skill_version` + `model`）是这库最有价值的字段：它让每个队伍自带"出生证明"。三个月后看到一支怪队伍，能直接查出"这是用户当时要晴天队、用 v1 skill 和 deepseek 生成的"——对比不同 skill 版本的产出质量也靠它。

`name`（文件名 slug，稳定 ID）与 `display_name`（中文）分离：前者是 API 路径和外键锚点，永不变；后者随便改，不影响任何引用。

### battles.db：三层粒度对齐三种读取场景

| 读取场景 | 走的表 | 为什么快 |
|---|---|---|
| 前端进度条轮询 | `sessions.rounds_done` | 单行 UPDATE，不扫子表 |
| 列表页胜率 | `battles.winner` + 索引 | `SUM(winner='a')` 聚合，不碰大 blob |
| 前端回合时间线 / 分析取材 | `battle_turns` + `idx_turns_battle` | 结构化明细，毫秒级 |
| 深度分析兜底 / 回放追溯 | `battles.record_json` + `battle_tag` | 引擎原始输出全量保留 |

**双层存储（record_json + battle_turns）是这个库的灵魂**：明细层丢了可以随时从保底层重拆；反过来保底层太重没法做高频查询。两层各司其职，schema 演进永不丢数据——battle_turns 不记 HP 的决策之所以敢做，就是因为 record_json 里反正有。

`winner` 用 `'a'/'b'` 而非队名/队 id：语义锚定在"这场任务里的位置"而非"哪支队伍"，队改名、重赛都不影响历史统计的正确性。`error` 作为独立胜负态，保证掉线场既留档（可诊断）又被胜率统计排除（`WHERE winner!='error'`）。

### analysis.db：索引在库、本体在文件

分析文档有两个天然属性：**大**（几千字）且**结构会随 skill 迭代**。若存库，列表页就要搬动 blob，改文档结构就要改表。所以：

- **库内只放列表页需要的字段**：`title/summary/rating/win_rate/created_at`——一条 SELECT 零文件 IO 渲染整个分析列表页
- **`win_rate`/`stats_json` 是定版快照**：分析是"对当时数据的快照"，之后再跑新对战不污染旧结论。这是刻意的语义，不是数据冗余的坏味道
- **文档本体（json+md）在磁盘**：skill 想加"威胁矩阵"章节？改 skill 就行，库表不动。md 文件让前端零渲染逻辑直接展示
- **`analysis_highlights` 入表**：文档里也有高光，但入表才能反向检索（"这场对战被哪些分析点名过"）并 JOIN battle_turns 取回合上下文——文档 JSON 里的字段是给人读的，表里的字段是给 SQL 查的

## 四、横切设计原则（跨库一致性）

1. **slug 体系**：全数据层的存储键统一用 dex 官方 slug（`willowisp`），中文名只是 JOIN dex 之后的展示态。任何库里没有一处存中文主键——翻译更新后全系统自动换新皮肤。
2. **逻辑外键 + 写入契约**：SQLite 跨文件建不了硬外键，于是每个库的 schema 文档都有一节"写入契约"（谁校验、什么顺序、失败怎么办），把数据库约束做不到的事交给模块纪律，并写进文档可审计。
3. **双层存储**：teams（结构化列 + export_text）、battles（turns 明细 + record_json）、analysis（索引列 + 文档文件）——同一份数据，一个面向查询的形态 + 一个面向消费/保底的形态，贯穿始终。
4. **进度与状态内嵌**：`sessions.rounds_done/status` 让长任务（50 轮跑量）自带进度，前端轮询单字段即可，不需要额外的任务队列或心跳表。
5. **可重建性分级**：dex 整库可重建；teams 种子可重种但 AI 产物只增不减；battles/analysis 纯运行时累积。四个构建脚本（`scripts/build_*.py`）幂等/增量/回滚语义各自明确，全链路已验证可从零复原。

## 五、字段消费方速查表

| 消费方 | 读什么 | 写什么 |
|---|---|---|
| 模块一 AI 建队 | dex.species 拆列筛池、dex.learnsets 校验 | teams 全部 |
| 模块二 对战 Lab | teams.export_text | battles 全部 |
| 模块三 分析 Bot | battles 聚合 + battle_turns、teams 溯源字段 | analysis 索引 + 文档文件 |
| 前端·建队页 | teams 列表/详情（JOIN dex 中文） | 触发模块一 |
| 前端·对战页 | sessions 进度、battles 胜负、battle_turns 时间线 | 触发模块二 |
| 前端·分析页 | analyses 列表五字段、docs/*.md | 触发模块三 |
| 用户 | 全部中文展示（name_zh / display_name） | 需求 prompt |

这张表也反向定义了"哪些字段是必要的"：**每个字段都必须有至少一个明确的消费方，否则不进 schema**——这是四库设计过程中裁字段的实际标准。
