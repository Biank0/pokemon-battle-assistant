# dex.db 基础信息库 · 字段说明文档

> 定位：**只读**的宝可梦静态知识库，是 AI 建队（模块一）的数据地基。
> 引擎：SQLite；建库脚本读取 `data/dex/showdown_db.json` + `data/dex/translations/zh_cn_names.json`。
> 表结构 DDL：[data/dex/schema.sql](../data/dex/schema.sql)

## 全库总览

| 表 | 行数（约） | 一句话职责 |
|---|---|---|
| `species` | 1517 | 宝可梦图鉴主表，含全部形态 |
| `moves` | 718 | 招式表 |
| `abilities` | 310 | 特性表 |
| `items` | 249 | 道具表 |
| `learnsets` | 5 万+ | 谁能学哪招——建队合法性校验核心 |
| `natures` | 25 | 性格表 |
| `type_chart` | 324 | 18×18 属性相克矩阵 |
| `meta` | 少量 | 数据溯源信息 |

**通用约定**
- `id` 一律采用 Showdown 官方 slug（如 `charizard`、`flamethrower`），全库外键统一指向它——与对战引擎的对账零转换
- `name_en` 必填；`name_zh` 可空——中文缺失时前端/上层回退显示英文
- 属性值（`type`/`type1`/`type2`/`atk_type`/`def_type`）统一存**英文**（如 `Fire`），中文转换由展示层映射完成，库内不冗余
- JSON 字段存 `TEXT`，内容为 JSON 字符串（SQLite 无原生 JSON 列类型）

---

## 1. species 宝可梦表

| 字段 | 类型 | 含义 | 示例 |
|---|---|---|---|
| `id` | TEXT PK | 官方 slug，全球唯一 | `charizard` |
| `num` | INTEGER | 图鉴编号；**同一编号可有多个形态**（mega、地区形态等），不可作主键 | `6` |
| `name_en` | TEXT | 英文显示名 | `Charizard` |
| `name_zh` | TEXT | 中文名（可空） | `喷火龙` |
| `type1` | TEXT | 第一属性 | `Fire` |
| `type2` | TEXT | 第二属性，单属性为 NULL | `Flying` |
| `hp/atk/def/spa/spd/spe` | INTEGER | 种族值六维 | `78/84/78/109/85/100` |
| `bst` | INTEGER | 六维总和，导入时算好冗余存储，`ORDER BY bst` 直接排序 | `534` |
| `weight_kg` | REAL | 体重；草结绳/拍落等招式威力依赖体重 | `90.5` |
| `height_m` | REAL | 身高 | `1.7` |
| `abilities` | TEXT(JSON) | 特性字典：`"0"` 普特性、`"H"` 隐藏特性，多个普特性用 `"1"` | `{"0":"Blaze","H":"Solar Power"}` |
| `prevo` | TEXT | 进化前 slug，无进化为 NULL | `charmeleon` |
| `evos` | TEXT(JSON) | 进化后 slug 数组 | `["charizardmega","charizardmegax"]` |
| `gender_ratio` | TEXT(JSON) | 性别比例 | `{"M":0.875,"F":0.125}` |
| `base_species` | TEXT | 基础形态 slug（仅形态条目非 NULL，如 `landorustherian → landorus`）。**Showdown 的 learnsets 按基础形态存储**，形态宝可梦的可学招式必须回退到基础形态查——建队校验闸门4与候选池代表招均依赖此回退 | `landorus` |

**索引**：`type1/type2/spe/atk/spa/bst/num`——全部服务于建队高频筛选，如"特攻 ≥110 且带火属性"。

**设计取舍**：种族值拆独立列而非 JSON，让 `WHERE spe >= 100` 走索引；特性/进化链是"展示用"而非"筛选用"，保持 JSON。

## 2. moves 招式表

| 字段 | 类型 | 含义 | 示例 |
|---|---|---|---|
| `id` | TEXT PK | 官方 slug | `flamethrower` |
| `num` | INTEGER | 招式编号 | `126` |
| `name_en` / `name_zh` | TEXT | 名称 | `Flamethrower` / `喷射火焰` |
| `type` | TEXT | 属性 | `Fire` |
| `category` | TEXT | `Physical` 物理 / `Special` 特殊 / `Status` 变化 | `Special` |
| `base_power` | INTEGER | 威力；0 表示固定伤害/无直接伤害 | `90` |
| `accuracy` | INTEGER | 命中率百分比；**NULL 表示必中**（区别于 0） | `100` |
| `pp` | INTEGER | PP 上限 | `15` |
| `priority` | INTEGER | 先制度 -7～+5，速攻队/先手保护判定依赖 | `0` |
| `target` | TEXT | 目标类型（自身/单体/全场/我方场地等） | `normal` |
| `flags` | TEXT(JSON) | 细节标记（可被保护/可被弹反/接触类等） | `{"protect":1,"mirror":1}` |

**索引**：`type/category/base_power/priority`——支撑"找火系特殊招""找先制招"类查询。

## 3. abilities 特性表

| 字段 | 类型 | 含义 | 示例 |
|---|---|---|---|
| `id` | TEXT PK | 官方 slug | `intimidate` |
| `num` | INTEGER | 特性编号 | `22` |
| `name_en` / `name_zh` | TEXT | 名称 | `Intimidate` / `威吓` |
| `rating` | INTEGER | Showdown 官方强度评分 1~5，建队选特性时的重要参考 | `4` |

> 注意：数据源只有名字没有中文/英文效果描述。如后续需要描述文本，需另接 Showdown `text/` 目录的描述数据，届时加列即可（只读库重建零成本）。

## 4. items 道具表

| 字段 | 类型 | 含义 | 示例 |
|---|---|---|---|
| `id` | TEXT PK | 官方 slug | `leftovers` |
| `num` | INTEGER | 道具编号 | `234` |
| `name_en` / `name_zh` | TEXT | 名称 | `Leftovers` / `吃剩的东西` |
| `gen` | INTEGER | 首次登场世代 | `2` |
| `fling_power` | INTEGER | 投掷招式威力，无投掷效果为 NULL | `10` |

> 与特性同理，暂无效果描述文本。

## 5. learnsets 可学招式表（建队校验核心）

| 字段 | 类型 | 含义 | 示例 |
|---|---|---|---|
| `species_id` | TEXT | 宝可梦 slug（联合主键之一） | `charizard` |
| `move_id` | TEXT | 招式 slug（联合主键之一） | `flamethrower` |
| `methods` | TEXT(JSON) | 习得方式数组：世代+方式编码（M=招式机，L=升级，E=蛋招，T=导师） | `["9M","8M","7M"]` |

**用法**：建队合法性校验"喷火龙学没学过大地之力"→ `SELECT 1 FROM learnsets WHERE species_id='charizard' AND move_id='earthpower'`。

**索引**：`(species_id, move_id)` 主键覆盖正向查询；`idx_learnsets_move` 支撑反向查询"谁会这招"（设计找 counter 时用）。

> 数据源 `learnsets` 仅覆盖 903 只（常用对战形态），非全图鉴——校验逻辑需容忍"查无此行"。

## 6. natures 性格表

| 字段 | 类型 | 含义 | 示例 |
|---|---|---|---|
| `id` | TEXT PK | 官方 slug | `adamant` |
| `name_en` / `name_zh` | TEXT | 名称 | `Adamant` / `固执` |
| `plus_stat` | TEXT | +10% 的能力；**NULL = 中性性格**（如认真/勤奋，无增减） | `atk` |
| `minus_stat` | TEXT | −10% 的能力；NULL = 中性性格 | `spa` |

**中文名来自固定映射**（翻译数据源无性格条目），映射表在建库脚本 `scripts/build_dex_db.py` 内维护。

## 7. type_chart 属性相克表

| 字段 | 类型 | 含义 | 示例 |
|---|---|---|---|
| `atk_type` | TEXT | 攻击方属性 | `Fire` |
| `def_type` | TEXT | 防御方属性 | `Grass` |
| `multiplier` | REAL | 2 克制 / 0.5 抵抗 / 0 免疫；**未记录的组合 = 1 倍**（表只存非 1 倍关系） | `2.0` |

18×18 全组合 324 行中只约 120 行非 1 倍，故全量写入 324 行含 1 倍也可——**当前设计只写非 1 倍组合**，查询逻辑：查不到即 1 倍。双属性防御方 = 两行 multiplier 相乘（漏斗查询两个 def_type）。

## 8. meta 元信息表

| 字段 | 类型 | 含义 |
|---|---|---|
| `key` | TEXT PK | 元信息键 |
| `value` | TEXT | 值 |

约定写入的键：

| key | 含义 |
|---|---|
| `schema_version` | 表结构版本（如 `1`），升级重建时判断用 |
| `source_db_generated_at` | 源数据 showdown_db.json 的生成时间 |
| `translation_source` | 中文翻译数据来源标识 |
| `imported_at` | 本次建库时间 |

---

## 附：与后续三库的关系

- **teams.db（队伍库）**：`team_members.species_id / move_id / item / ability / nature` 全部引用本库的 `id`——队伍库不冗余存宝可梦信息，展示时 JOIN 本库取中文与种族值
- **battles.db（对战记录库）**：已确定**不记录 HP 百分比快照**，回合明细只存动作序列
- **分析文档库**：分析 skill 引用本库的 `type_chart` 做属性覆盖计算

## 附：重建方式

只读库的演进方式是"改 schema.sql → 重跑导入脚本整库重建"，不做 `ALTER TABLE` 迁移。`meta.schema_version` 用于运行期校验库版本是否与代码预期一致。
