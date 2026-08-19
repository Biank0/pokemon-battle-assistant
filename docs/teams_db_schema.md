# teams.db 队伍库 · 字段说明文档

> 定位：**可写"活"库**，模块一（AI 建队）是唯一写方；模块二（对战 Lab）从这里取队上对战台，模块三（分析）按队伍聚合。
> 引擎：SQLite；表结构 DDL：[data/teams/schema.sql](../data/teams/schema.sql)；初始化/种子：[scripts/build_teams_db.py](../scripts/build_teams_db.py)
>
> 与 dex.db 的本质区别：dex 只读、可整库重建；**teams 是累积式活库**——种子脚本按 `name` 增量补种（已存在的队伍跳过），只有 `--rebuild` 才删库重建。AI 生成的队伍数据在本库中长期累积，不可随意重建。

## 全库总览

| 表 | 行数（当前种子） | 一句话职责 |
|---|---|---|
| `teams` | 10 | 一行一支队伍：标识、来源、需求溯源、导出串 |
| `team_members` | 57 | 一行一个槽位：宝可梦完整配置（结构化） |
| `meta` | 3 | schema 版本、关联的 dex 版本、种子时间 |

**通用约定**
- `id` 用 uuid4（内部主键，battles.db 的外键指向它）；`name` 是人类可读英文标识（UNIQUE）
- 成员相关字段（species/ability/item/nature/moves）一律存 **dex 官方 slug**，展示时跨库 JOIN dex.db 取中文名与种族值——**显示名只存在于 `export_text`**
- **逻辑外键**：SQLite 跨文件无法建硬外键约束，引用存在性由写入方（未来的数据访问层）负责校验
- JSON 字段存 `TEXT`；时间戳统一 ISO8601 UTC
- 跨库查询用 `ATTACH DATABASE ... AS dex` 后直接 JOIN（种子脚本里已演示）

---

## 1. teams 队伍主表

| 字段 | 类型 | 含义 | 示例 |
|---|---|---|---|
| `id` | TEXT PK | uuid4，内部主键 | `3f2a...` |
| `name` | TEXT UNIQUE | 人类可读英文标识（文件 ID 传统），API 路径与去重用 | `xiaobian` |
| `display_name` | TEXT | 中文显示名 | `小边的王牌` |
| `format` | TEXT | 赛制 ID，与 Showdown 格式一致 | `gen9bssregi` |
| `source` | TEXT CHECK | `preset`（实验室预设）/ `ai`（AI 生成）/ `manual`（手工） | `preset` |
| `requirement_prompt` | TEXT | AI 建队时的**用户原始需求**，回答"这队为什么而生"；preset/manual 为 NULL | `帮我建一支晴天队` |
| `skill_version` | TEXT | 建队 skill 版本号，用于对比不同版本 skill 的产出质量 | `1` |
| `model` | TEXT | 生成模型名 | `deepseek-v4-flash` |
| `export_text` | TEXT | Showdown 文本导出串（见下文格式），模块二**零转换**直接喂 pokeenv | 见下 |
| `created_at` / `updated_at` | TEXT | 创建/最后更新时间（种子导入时取源文件 mtime） | `2026-08-15T...` |

**索引**：`format`（按赛制筛队）、`source`（区分预设/AI 队）。

**设计取舍**
- **uuid 主键 + name 唯一标识并存**：uuid 保证永不怕冲突；name 保留可读性给 URL 和日志。写入契约：模块一发现 name 冲突时自动加后缀（如 `rain-team-2`）
- **export_text 冗余存储**：它与 team_members 表信息等价、格式不同。冗余它是因为模块二高频消费（pokeenv 接受 Showdown 导出格式），避免每次取队都现拼字符串出错。代价：写入方必须保证两处同步（见"写入契约"）

### export_text 格式（标准 Showdown 导出）

```
Ninetales @ Heat Rock
Ability: Drought
Level: 100
Tera Type: Ghost
EVs: 12 HP / 252 SpA / 252 Spe
Timid Nature
IVs: 0 Atk
- Weather Ball
- Encore
- Healing Wish
- Will-O-Wisp
```

生成规则：`等级≠100` 才写 Level 行；EVs 只写非 0 项；IVs 只写非 31 项；多个成员之间空一行分隔。

## 2. team_members 队伍成员表

| 字段 | 类型 | 含义 | 示例 |
|---|---|---|---|
| `team_id` | TEXT | → teams.id（联合主键之一） | |
| `slot` | INTEGER CHECK | 槽位 1~6（联合主键之一） | `1` |
| `species_id` | TEXT | → dex.species.id（slug） | `ninetales` |
| `level` | INTEGER | 等级，默认 100；BSS/VGC 队为 50 | `100` |
| `nature` | TEXT | → dex.natures.id；NULL=未指定 | `timid` |
| `ability` | TEXT | → dex.abilities.id | `drought` |
| `item` | TEXT | → dex.items.id；**NULL=不带道具** | `heatrock` |
| `tera_type` | TEXT | 太晶属性（英文属性名，与 dex 属性存储一致）；Gen9 专属，旧赛制 NULL | `Ghost` |
| `moves` | TEXT(JSON) | 招式 slug 数组，1~4 个 | `["weatherball","encore","healingwish","willowisp"]` |
| `evs` | TEXT(JSON) | 努力值六维（0~252，总和≤510） | `{"hp":12,"atk":0,"def":0,"spa":244,"spd":0,"spe":252}` |
| `ivs` | TEXT(JSON) | 个体值六维（0~31） | `{"hp":31,"atk":0,"def":31,...}` |

**索引**：`species_id`——支撑反向查询"哪些队伍带了土地云"（分析模块高频用）。

**设计取舍**
- **slug 而非显示名**：结构化列的意义就是能 JOIN dex.db（中文、种族值、属性一次拿全）；显示名（`Ninetales`）只在 export_text 里保留
- **evs/ivs 用 JSON 而非拆 12 列**：与 dex 的"拆列原则"（筛选项拆列）相反——努力值/个体值是纯构建细节，没有任何筛选场景，JSON 保持表干净
- **moves 数组上限 4**：schema 不强制，写入方校验（1~4 个且都存在于 dex.moves）

**slug 转换规则**（显示名 → dex id）：小写 + 去掉所有非字母数字字符。`Will-O-Wisp → willowisp`、`Lilligant-Hisui → lilliganthisui`、`Heavy-Duty Boots → heavydutyboots`。

## 3. meta 元信息表

| key | 含义 |
|---|---|
| `schema_version` | 本库表结构版本 |
| `dex_schema_version` | 种子导入时关联的 dex.db 版本（数据对账用） |
| `seeded_at` | 最近一次种子导入时间 |

---

## 写入契约（模块一 / 未来的数据访问层必须遵守）

1. `id` 用 uuid4 生成
2. `name` 唯一：冲突时自动加后缀重试，不能覆盖已有队伍
3. 成员所有 slug（species/ability/item/nature/moves）与 tera_type **先过 dex.db 校验**再落库
4. `export_text` 与 team_members 同一次事务内写入，保证一致
5. AI 队伍必须落 `source='ai'` + `requirement_prompt` + `skill_version` + `model`（可追溯）

## 种子导入行为（scripts/build_teams_db.py）

- `data/teams/lab/*.json` → `source='preset'`；`data/teams/generated/*.json` → `source='ai'`
- **`name` 取文件名 slug**（如 `bss_balance`）：源 JSON 内的 `name` 字段是英文显示名（如 `BSS Balance`，含空格），不作标识用；`display_name` 取 JSON 的 `display_name`，缺省回退 JSON `name`
- 增量补种：`name` 已存在的队伍整个跳过（不动库内数据）；`--rebuild` 参数才删库重种
- 源 JSON 里的显示名（`Ninetales` 等）转 slug 后逐一与 dex.db 比对，**解析失败记警告不阻断**（如遇到 mega 特殊命名）
- `created_at` 取源文件修改时间

## 与其他库的关系

- **dex.db**：成员表全部字段的逻辑引用源；跨库 JOIN（ATTACH）即得全中文渲染
- **battles.db**（下一步）：`battle_sessions.team_a_id / team_b_id` → `teams.id`——对战记录永远能回溯到具体队伍版本
- **analysis.db**：按 `scope_type='team'` + `scope_id`（= teams.id）挂分析文档
