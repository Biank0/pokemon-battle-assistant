-- ============================================================
-- dex.db —— 基础信息库（只读）
-- 数据源：data/dex/showdown_db.json + translations/zh_cn_names.json
-- 引擎：SQLite（Python 标准库自带，零依赖）
-- 说明：本库由导入脚本一次性构建，运行期只读不写
-- ============================================================

PRAGMA journal_mode = WAL;

-- ------------------------------------------------------------
-- 1. species —— 宝可梦图鉴主表（1517 条，含全部形态）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS species (
    id          TEXT PRIMARY KEY,   -- 官方 slug，如 'charizard'（全球唯一 ID，全库外键指向它）
    num         INTEGER NOT NULL,   -- 图鉴编号，如 6；同编号不同形态（mega 等）会重复
    name_en     TEXT NOT NULL,      -- 英文显示名，如 'Charizard'
    name_zh     TEXT,               -- 中文名，如 '喷火龙'（无翻译时为 NULL，前端回退英文）
    type1       TEXT NOT NULL,      -- 第一属性（英文，如 'Fire'）
    type2       TEXT,               -- 第二属性，单属性为 NULL
    hp          INTEGER NOT NULL,   -- 种族值：HP
    atk         INTEGER NOT NULL,   -- 种族值：攻击
    def         INTEGER NOT NULL,   -- 种族值：防御
    spa         INTEGER NOT NULL,   -- 种族值：特攻
    spd         INTEGER NOT NULL,   -- 种族值：特防
    spe         INTEGER NOT NULL,   -- 种族值：速度
    bst         INTEGER NOT NULL,   -- 六维总和（导入时计算冗余存列，便于直接排序）
    weight_kg   REAL,               -- 体重 kg（部分招式如 草结绳 依赖）
    height_m    REAL,               -- 身高 m
    abilities   TEXT NOT NULL,      -- 特性 JSON：{"0":"Blaze","H":"Solar Power"}（0=普特性,H=隐藏特性）
    prevo       TEXT,               -- 进化前 slug（无进化为 NULL）
    evos        TEXT,               -- 进化后 slug 列表 JSON（如 '["Ivysaur"]'）
    gender_ratio TEXT,              -- 性别比例 JSON：{"M":0.875,"F":0.125}
    base_species TEXT               -- 基础形态 slug（形态条目非 NULL；learnsets 按基础形态存，校验回退键）
);

-- 建队常用筛选的覆盖索引
CREATE INDEX IF NOT EXISTS idx_species_type1     ON species (type1);
CREATE INDEX IF NOT EXISTS idx_species_type2     ON species (type2);
CREATE INDEX IF NOT EXISTS idx_species_spe       ON species (spe);
CREATE INDEX IF NOT EXISTS idx_species_atk       ON species (atk);
CREATE INDEX IF NOT EXISTS idx_species_spa       ON species (spa);
CREATE INDEX IF NOT EXISTS idx_species_bst       ON species (bst);
CREATE INDEX IF NOT EXISTS idx_species_num       ON species (num);

-- ------------------------------------------------------------
-- 2. moves —— 招式表（718 条）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS moves (
    id           TEXT PRIMARY KEY,  -- 官方 slug，如 'flamethrower'
    num          INTEGER NOT NULL,  -- 招式编号
    name_en      TEXT NOT NULL,     -- 英文名，如 'Flamethrower'
    name_zh      TEXT,              -- 中文名，如 '喷射火焰'
    type         TEXT NOT NULL,     -- 属性（英文，如 'Fire'）
    category     TEXT NOT NULL,     -- 分类：Physical / Special / Status（物理/特殊/变化）
    base_power   INTEGER NOT NULL,  -- 威力（0 = 固定伤害或无伤害类）
    accuracy     INTEGER,           -- 命中率百分比；NULL = 必中（如 波导弹）
    pp           INTEGER,           -- PP 上限
    priority     INTEGER NOT NULL,  -- 先制度（-7 ~ +5，如 子弹拳 +1）
    target       TEXT,              -- 目标类型（normal / self / adjacentAlly ...）
    flags        TEXT               -- 标记 JSON（protect/mirror/contact 等，判定细节用）
);

CREATE INDEX IF NOT EXISTS idx_moves_type    ON moves (type);
CREATE INDEX IF NOT EXISTS idx_moves_cat     ON moves (category);
CREATE INDEX IF NOT EXISTS idx_moves_power  ON moves (base_power);
CREATE INDEX IF NOT EXISTS idx_moves_prio   ON moves (priority);

-- ------------------------------------------------------------
-- 3. abilities —— 特性表（310 条）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS abilities (
    id       TEXT PRIMARY KEY,      -- 官方 slug，如 'intimidate'
    num      INTEGER NOT NULL,      -- 特性编号
    name_en  TEXT NOT NULL,         -- 英文名，如 'Intimidate'
    name_zh  TEXT,                  -- 中文名，如 '威吓'
    rating   INTEGER                -- Showdown 评分 1-5（衡量特性强度，建队参考）
);

-- ------------------------------------------------------------
-- 4. items —— 道具表（249 条）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS items (
    id           TEXT PRIMARY KEY,  -- 官方 slug，如 'leftovers'
    num          INTEGER NOT NULL,  -- 道具编号
    name_en      TEXT NOT NULL,     -- 英文名，如 'Leftovers'
    name_zh      TEXT,              -- 中文名，如 '吃剩的东西'
    gen          INTEGER,           -- 登场世代
    fling_power  INTEGER            -- 投掷招式威力（无投掷效果为 NULL）
);

-- ------------------------------------------------------------
-- 5. learnsets —— 可学招式表（建队合法性校验的核心）
-- 用途：校验"某宝可梦能否学会某招式"
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS learnsets (
    species_id  TEXT NOT NULL,      -- 宝可梦 slug（逻辑外键 → species.id）
    move_id     TEXT NOT NULL,      -- 招式 slug（逻辑外键 → moves.id）
    methods     TEXT NOT NULL,      -- 习得方式 JSON 数组，如 '["9M","8L50"]'（9M=九代机器学习）
    PRIMARY KEY (species_id, move_id)
);

CREATE INDEX IF NOT EXISTS idx_learnsets_move ON learnsets (move_id);

-- ------------------------------------------------------------
-- 6. natures —— 性格表（25 条）
-- 中文名来源：固定映射表（翻译文件中无性格）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS natures (
    id          TEXT PRIMARY KEY,   -- 官方 slug，如 'adamant'
    name_en     TEXT NOT NULL,      -- 英文名，如 'Adamant'
    name_zh     TEXT NOT NULL,      -- 中文名，如 '固执'
    plus_stat   TEXT,               -- 提升的能力（atk/def/spa/spd/spe）；NULL = 中性性格
    minus_stat  TEXT                -- 降低的能力；NULL = 中性性格
);

-- ------------------------------------------------------------
-- 7. type_chart —— 属性相克表（18×18 = 324 行）
-- multiplier：2=克制 0.5=抵抗 0=免疫；未出现的组合即 1 倍
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS type_chart (
    atk_type   TEXT NOT NULL,       -- 攻击方属性（英文）
    def_type   TEXT NOT NULL,       -- 防御方属性（英文）
    multiplier REAL NOT NULL,       -- 倍率 2 / 0.5 / 0
    PRIMARY KEY (atk_type, def_type)
);

-- ------------------------------------------------------------
-- 8. meta —— 元信息表（数据溯源）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,         -- 键：schema_version / source_db / generated_at ...
    value TEXT NOT NULL             -- 值
);
