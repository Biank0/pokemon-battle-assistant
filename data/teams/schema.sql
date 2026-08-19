-- ============================================================
-- teams.db —— 队伍库（可写"活"库）
-- 唯一写方：模块一（AI 建队）。模块二从这里取队，模块三按队聚合分析
-- 表结构讲解：docs/teams_db_schema.md
-- 初始化/种子导入：scripts/build_teams_db.py
--
-- 与 dex.db（只读、整库重建）不同，本库是累积式活库：
--   种子脚本增量补种（按 name 去重），--rebuild 才删库重建
-- ============================================================

-- ------------------------------------------------------------
-- 1. teams —— 队伍主表（一行 = 一支队伍）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS teams (
    id                 TEXT PRIMARY KEY,  -- uuid4，内部主键（battle_sessions 外键指向它）
    name               TEXT NOT NULL UNIQUE, -- 人类可读英文标识（如 'xiaobian'），API 路径用
    display_name       TEXT NOT NULL,     -- 中文显示名，如 '小边的王牌'
    format             TEXT NOT NULL,     -- 赛制 ID（与 Showdown 一致：gen9ou / gen9bssregi / gen9vgc2026regi）
    source             TEXT NOT NULL CHECK (source IN ('preset', 'ai', 'manual')),
                                          -- preset=实验室预设 / ai=AI 生成 / manual=手工录入
    requirement_prompt TEXT,              -- AI 建队时的用户原始需求（追溯"这队为什么而生"；preset/manual 为 NULL）
    skill_version      TEXT,              -- 建队 skill 版本（对比不同版本 skill 的队伍质量）
    model              TEXT,              -- 生成模型名（如 deepseek-v4-flash）
    export_text        TEXT NOT NULL,     -- Showdown 文本导出串（模块二零转换直接喂 pokeenv）
    created_at         TEXT NOT NULL,     -- ISO8601 UTC
    updated_at         TEXT NOT NULL      -- ISO8601 UTC（队伍被迭代/编辑时更新）
);

CREATE INDEX IF NOT EXISTS idx_teams_format ON teams (format);
CREATE INDEX IF NOT EXISTS idx_teams_source ON teams (source);

-- ------------------------------------------------------------
-- 2. team_members —— 队伍成员表（一行 = 一个槽位的宝可梦）
-- 注意：species/ability/item/nature/moves 存 dex 官方 slug（逻辑外键 → dex.db，
--       SQLite 跨文件无法建硬外键，由写入方负责校验存在性）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS team_members (
    team_id    TEXT NOT NULL,             -- → teams.id
    slot       INTEGER NOT NULL CHECK (slot BETWEEN 1 AND 6),  -- 槽位 1~6
    species_id TEXT NOT NULL,             -- → dex.species.id，如 'ninetales'
    level      INTEGER NOT NULL DEFAULT 100,  -- 等级（BSS/VGC=50，OU=100）
    nature     TEXT,                      -- → dex.natures.id，如 'timid'
    ability    TEXT,                      -- → dex.abilities.id，如 'drought'
    item       TEXT,                      -- → dex.items.id，如 'heatrock'；NULL=不带道具
    tera_type  TEXT,                      -- 太晶属性（英文属性名，如 'Ghost'）；Gen9 专属
    moves      TEXT NOT NULL,             -- 招式 slug JSON 数组（1~4 个），如 '["weatherball","encore"]'
    evs        TEXT,                      -- 努力值 JSON：{"hp":12,"atk":0,...}（六维齐全）
    ivs        TEXT,                      -- 个体值 JSON：{"hp":31,...}（六维齐全）
    PRIMARY KEY (team_id, slot)
);

CREATE INDEX IF NOT EXISTS idx_members_species ON team_members (species_id);

-- ------------------------------------------------------------
-- 3. meta —— 元信息表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
