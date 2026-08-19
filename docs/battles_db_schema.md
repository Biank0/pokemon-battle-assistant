# battles.db 对战记录库 · 字段说明文档

> 定位：**纯运行时活库**，模块二（对战 Lab）是唯一写方，模块三（分析 Bot）只读。
> 引擎：SQLite；表结构 DDL：[data/battles/schema.sql](../data/battles/schema.sql)；初始化脚本：[scripts/build_battles_db.py](../scripts/build_battles_db.py)
>
> 与前两库的区别：**无种子数据**——内容全部由模块二跑对战时写入。初始化脚本只建表 + 用合成数据做冒烟测试（事务回滚，测完不留脏数据）。

## 全库总览

| 表 | 粒度 | 一句话职责 |
|---|---|---|
| `battle_sessions` | 一次跑量任务 | "A 队 vs B 队打 50 轮"的任务登记与进度 |
| `battles` | 一场对战 | 单场结果：胜负、回合数、原始记录 blob |
| `battle_turns` | 一次动作 | 逐回合出招明细（可查询层，分析 bot 与前端时间线直接 SQL） |

三层结构：`battle_sessions 1 → N battles 1 → N battle_turns`。

**通用约定**
- 时间戳 ISO8601 UTC；JSON 存 TEXT
- 宝可梦/招式一律存 dex slug，展示时 ATTACH dex.db JOIN 取中文
- **不记录 HP 百分比快照**（已决策）：回合明细只存动作序列，血量信息需要时从 `battles.record_json` 保底层取
- 每场对战约 20~40 回合 → 50 轮任务约产生 50 行 battles + 2000~4000 行 battle_turns

---

## 1. battle_sessions 跑量任务表

| 字段 | 类型 | 含义 | 示例 |
|---|---|---|---|
| `id` | TEXT PK | uuid4 任务标识 | |
| `team_a_id` | TEXT | → teams.db `teams.id`（A 队，通常是用户/被考核方） | |
| `team_b_id` | TEXT | → teams.db `teams.id`（B 队，对手/陪练方） | |
| `format` | TEXT | 赛制 ID，冗余存储（省得每次 JOIN 两队才知道赛制） | `gen9bssregi` |
| `bot_config` | TEXT(JSON) | 双方 bot 配置 | `{"a":{"type":"heuristic","v":1},"b":{"type":"heuristic","v":1}}` |
| `rounds_total` | INTEGER | 计划轮数 | `50` |
| `rounds_done` | INTEGER | 已完成轮数——**前端进度条轮询这个字段** | `37` |
| `status` | TEXT CHECK | `pending`→`running`→`completed`；异常 `failed`、手动 `cancelled` | `running` |
| `error` | TEXT | failed 时的失败原因摘要 | `Showdown 连接超时` |
| `started_at` | TEXT | 首场开始时间 | |
| `finished_at` | TEXT | 末场结束时间（未结束 NULL） | |

**索引**：`team_a_id`/`team_b_id`（"这支队伍参加过哪些任务"）、`status`（进度轮询按状态过滤活跃任务）。

**设计取舍**
- 进度不用单独表：`rounds_done` 由模块二每场打完原子 `+1`（`UPDATE ... SET rounds_done=rounds_done+1`），SQLite 写锁天然保证并发安全
- `status` 五态够用：不引入暂停/恢复（cancelled 之后重新开任务即可，历史不篡改）

## 2. battles 单场表

| 字段 | 类型 | 含义 | 示例 |
|---|---|---|---|
| `id` | TEXT PK | uuid4 | |
| `session_id` | TEXT | → battle_sessions.id | |
| `round_no` | INTEGER | 任务内第几轮（1 起）；**联合唯一**（session_id+round_no）保证不重不漏 | `37` |
| `battle_tag` | TEXT | Showdown 对战标识，可追溯回放 | `battle-gen9ou-8321` |
| `winner` | TEXT CHECK | `a` / `b` / `draw`（超时等平局）/ `error`（本场异常，如掉线） | `a` |
| `end_turn` | INTEGER | 总回合数（poke-env `battle.turn`）；error 场可能为 NULL | `23` |
| `record_json` | TEXT | **引擎原始完整记录**（保底层）：双方 observations、合法动作列表、实际选择、队伍配置——模块三深度分析的兜底数据源 | |
| `created_at` | TEXT | 入库时间 | |

**索引**：`session_id`、`(session_id, round_no)` 唯一、`winner`（胜率聚合）。

**设计取舍**
- **双层存储**：`record_json` 保原始（可能几百 KB，永不丢信息），`battle_turns` 拆明细（分析高频查询走索引不碰 blob）
- `winner` 用 a/b 而非队名：队名可改、uuid 冗长；"A 队赢率" = `winner='a'` 占比，语义稳定
- `error` 算独立胜负态而非 status：一场掉线不影响任务继续，但统计胜率时必须排除

## 3. battle_turns 逐回合动作明细表

| 字段 | 类型 | 含义 | 示例 |
|---|---|---|---|
| `id` | INTEGER PK 自增 | 稳定排序键（同回合双方动作的先后） | |
| `battle_id` | TEXT | → battles.id | |
| `turn` | INTEGER | 回合数；**选队阶段（team preview）为 0** | `12` |
| `side` | TEXT CHECK | 动作方：`a` / `b` | `a` |
| `action_type` | TEXT CHECK | `move` 出招 / `switch` 换人 / `team_order` 选出场顺序 | `move` |
| `actor_species` | TEXT | 动作主体 slug；move=出手者、switch=**换下者** | `charizard` |
| `move_id` | TEXT | 招式 slug；仅 move 有值 | `flamethrower` |
| `target_species` | TEXT | switch=**换上者**、move=在场对手（单打）；选队 NULL | `ninetales` |
| `raw_label` | TEXT | 引擎指令原文（保底：结构化解析失败时仍可读） | `move flamethrower` |

**索引**：`battle_id`（按场取时间线）、`actor_species`（"这只宝可梦最爱用什么招"）、`move_id`（"这招在整个对局里出现频率"）。

**设计取舍**
- **不记 HP 快照**（用户已决策）：写入量减半，分析需要血量时读 record_json
- `actor/target` 语义按动作类型区分（switch 的 actor=旧、target=新），文档即契约
- 双打时同一方一回合可有多个动作（两只想各一条）——`id` 自增保证顺序稳定

---

## 分析模块常用查询（写进文档备查）

```sql
-- A 队对 B 队战绩（胜/负/平/异常）
SELECT winner, COUNT(*) FROM battles WHERE session_id=? GROUP BY winner;

-- 某队伍全部任务的总体胜率（跨库 ATTACH teams 后按 name 查）
SELECT SUM(winner='a')*1.0/COUNT(*) FROM battles b
JOIN battle_sessions s ON b.session_id=s.id WHERE s.team_a_id=? AND winner!='error';

-- 高频招式 TOP10（全库招式使用统计）
SELECT t.move_id, m.name_zh, COUNT(*) c FROM battle_turns t
JOIN dex.moves m ON m.id=t.move_id WHERE t.action_type='move'
GROUP BY t.move_id ORDER BY c DESC LIMIT 10;

-- 单场逐回合时间线（前端时间线数据源）
SELECT turn, side, action_type, actor_species, move_id, target_species
FROM battle_turns WHERE battle_id=? ORDER BY id;
```

## 写入契约（模块二必须遵守）

1. 先 INSERT session（status='running'），每场打完**同事务**写入 battle + battle_turns 并 `rounds_done+1`
2. 全部完成 → status='completed'；异常 → status='failed' + error 摘要；二者必居其一（cancelled 由用户触发）
3. `winner='error'` 的场次也要写（保留回合明细供诊断），但胜率统计必须排除
4. battle_turns 按引擎 steps 顺序插入，不自造 turn 编号
5. record_json 原样存引擎输出，不做删改（保底原则）

## 与其他库的关系

- **teams.db**：`team_a_id/team_b_id` → teams.id；分析时 ATTACH 即得队伍中文名与配置
- **dex.db**：turns 表的 species/move slug → 中文渲染
- **analysis.db**（下一步）：`scope_type='session'` 的分析挂 `battle_sessions.id`；`scope_type='battle'` 挂 `battles.id`
