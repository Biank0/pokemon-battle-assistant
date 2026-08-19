# analysis.db 分析文档库 · 字段说明文档

> 定位：模块三（分析 Bot）的唯一写库；前端分析页只读。
> 引擎：SQLite；表结构 DDL：[data/analysis/schema.sql](../data/analysis/schema.sql)；初始化脚本：[scripts/build_analysis_db.py](../scripts/build_analysis_db.py)
>
> **核心设计：索引在库、本体在文件。** `analyses` 表只存索引与摘要（列表页秒开）；文档本体存磁盘文件（结构化 JSON + 渲染 MD）。分析 skill 迭代文档结构时不用动库表。

## 全库总览

| 存储 | 粒度 | 职责 |
|---|---|---|
| `analyses` 表 | 一份分析 | 索引：标题/摘要/评分/胜率/统计快照/文档路径 |
| `analysis_highlights` 表 | 一个高光回合 | 文档中被点名的关键回合，可跳转 battle_turns |
| `data/analysis/docs/{id}.json` | 文档本体 | 结构化全文（章节、威胁分析、建议等，结构由 skill 定义） |
| `data/analysis/docs/{id}.md` | 文档本体 | 渲染好的 Markdown（前端直接展示，零前端渲染逻辑） |

## 1. analyses 分析索引表

| 字段 | 类型 | 含义 | 示例 |
|---|---|---|---|
| `id` | TEXT PK | uuid4；同时是文档文件名主干 | |
| `scope_type` | TEXT CHECK | 分析对象粒度：`session`（跑量任务）/ `team`（队伍）/ `battle`（单场） | `session` |
| `scope_id` | TEXT | 对象 id（逻辑外键，见下"scope 映射"） | |
| `title` | TEXT | 中文标题 | `小边的王牌 vs BSS 平衡轴 · 50轮复盘` |
| `summary` | TEXT | 一句话摘要——**列表页只查此列，不读文档文件** | `晴天轴运转顺畅但怕钢联防，建议补位` |
| `rating` | TEXT | 模型给的档位 S/A/B/C/D；可 NULL（模型未给） | `B+` |
| `win_rate` | REAL | scope 范围内胜率（0~1）冗余存储——列表页直接展示，免去每次聚合 battles 表 | `0.62` |
| `stats_json` | TEXT(JSON) | 关键统计快照：`{"battles":50,"avg_turns":24.3,"top_move":"earthquake"}` | |
| `model` | TEXT | 生成模型 | `deepseek-v4-flash` |
| `skill_version` | TEXT | 分析 skill 版本（追溯"这份分析是哪个版本产出的"） | `1` |
| `doc_json_path` | TEXT | 结构化文档路径（相对项目根） | `data/analysis/docs/{id}.json` |
| `doc_md_path` | TEXT | 渲染文档路径 | `data/analysis/docs/{id}.md` |
| `created_at` | TEXT | 创建时间 | |

**索引**：`(scope_type, scope_id)`（"这场任务的分析在哪"）、`created_at DESC`（列表按时间倒序）。

### scope 映射（scope_type → scope_id 指向）

| scope_type | scope_id 指向 | 典型问题 |
|---|---|---|
| `session` | battles.db `battle_sessions.id` | "这次 50 轮跑量打得怎么样？" |
| `team` | teams.db `teams.id` | "这支队伍整体强不强？"（可跨多个 session 聚合） |
| `battle` | battles.db `battles.id` | "这一场关键回合怎么输的？" |

均为**逻辑外键**（跨库无法建硬约束），写入方负责存在性校验。

**设计取舍**
- `win_rate`/`stats_json` 是**冗余快照**：分析时刻的数据定版。之后再跑新对战不改变旧分析的结论——这是"分析是对当时数据的快照"语义，不是 bug
- `summary` 与 `rating` 让列表页一次查询全部呈现：`SELECT id,title,summary,rating,win_rate,created_at FROM analyses ORDER BY created_at DESC`，零文件 IO

## 2. analysis_highlights 高光回合引用表

| 字段 | 类型 | 含义 | 示例 |
|---|---|---|---|
| `id` | INTEGER PK 自增 | 稳定排序 | |
| `analysis_id` | TEXT | → analyses.id | |
| `seq` | INTEGER | 文档内展示顺序（1 起） | `1` |
| `battle_id` | TEXT | → battles.db battles.id（逻辑外键） | |
| `round_no` | INTEGER | 任务内第几轮（冗余自 battles.round_no） | `37` |
| `turn` | INTEGER | 回合数 | `12` |
| `side` | TEXT CHECK | 被点评方 a/b；全局时刻（如天气持续伤害）NULL | `a` |
| `description` | TEXT | 中文点评一句话 | `关键换人规避了烈咬陆鲨的地震` |

**设计取舍**：高光内容文档 JSON 里本身有，入表是为了两点——① 跨分析检索"所有被点名的回合"（`WHERE battle_id=?` 反查哪些分析提过这场）；② 前端时间线页直接 JOIN battle_turns 取上下文，不用解析文档。

## 3. meta 元信息表

| key | 含义 |
|---|---|
| `schema_version` | 本库表结构版本 |
| `battles_schema_version` | 关联 battles.db 版本 |
| `teams_schema_version` | 关联 teams.db 版本 |

## 文档文件结构约定（对 skill 的要求）

**{id}.json**（结构化，供前端交互/二次分析）：

```json
{
  "id": "…", "scope_type": "session", "scope_id": "…",
  "title": "…", "summary": "…", "rating": "B+",
  "sections": [
    {"heading": "整体战绩", "body": "…"},
    {"heading": "核心威胁", "body": "…"},
    {"heading": "改进建议", "body": "…"}
  ],
  "highlights": [
    {"seq": 1, "battle_id": "…", "round_no": 37, "turn": 12, "side": "a", "description": "…"}
  ]
}
```

`sections` 结构由分析 skill 自由定义（这是"本体在文件"的意义）；`highlights` 与库表内容一致（skill 产出后由数据访问层同步入表）。

**{id}.md**（渲染版，前端直接展示）：由 skill 或访问层从 JSON 渲染，含全部 sections 与高光列表。

## 写入契约（模块三必须遵守）

1. 先写两个文档文件，成功后再写库（索引行 + highlights 行同事务）——**避免库里有索引、文件不存在**
2. scope 存在性校验：session/battle 查 battles.db，team 查 teams.db
3. `win_rate`/`stats_json` 按分析时刻数据定版写入
4. id 用 uuid4，文件名 = `{id}.json` / `{id}.md`
5. 分析失败不写半成品：文件写入失败即中止，不留孤儿文件

## 与其他库的关系

- **battles.db**：主要数据源（session/battle 粒度分析读其聚合与 turns）；highlights.battle_id 可回跳具体回合
- **teams.db**：team 粒度分析的对象；title 渲染需要队伍中文名
- **dex.db**：分析中提到的宝可梦/招式中文名
- 四库数据流到此闭环：dex（知识）→ teams（建队产物）→ battles（对战产物）→ analysis（分析产物）

## 初始化脚本行为（scripts/build_analysis_db.py）

- 建表（幂等）+ 写 meta
- 冒烟测试：合成一份 session 分析（索引 + 高光 + 临时文档文件），验证列表查询/高光 JOIN battle_turns/孤儿文件清理，然后回滚并删除临时文件——库与文档目录保持干净待用
