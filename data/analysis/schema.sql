-- ============================================================
-- analysis.db —— 分析文档库（索引库 + 文档文件）
-- 唯一写方：模块三（分析 Bot）。前端只读
-- 表结构讲解：docs/analysis_db_schema.md
-- 初始化：scripts/build_analysis_db.py（建表 + 冒烟测试）
--
-- 核心设计：索引在库、本体在文件
--   analyses 表只存索引+摘要（列表页秒开，不碰大文档）
--   文档本体存磁盘文件：data/analysis/docs/{id}.json（结构化）+ {id}.md（渲染）
--   好处：文档结构随分析 skill 迭代，改 skill 不用改库表
-- ============================================================

-- ------------------------------------------------------------
-- 1. analyses —— 分析索引表（一行 = 一份分析文档）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analyses (
    id             TEXT PRIMARY KEY,  -- uuid4，同时是文档文件名主干
    scope_type     TEXT NOT NULL
                   CHECK (scope_type IN ('session','team','battle')),
                                        -- 分析对象粒度：跑量任务 / 队伍 / 单场
    scope_id       TEXT NOT NULL,     -- 对象 id（逻辑外键，见文档"scope 映射"）
    title          TEXT NOT NULL,     -- 文档标题（中文，如 '小边的王牌 vs BSS 平衡轴 · 50轮复盘')
    summary        TEXT NOT NULL,     -- 一句话摘要（列表页展示，不进大文档）
    rating         TEXT,              -- 整体评价档位：S/A/B/C/D（模型给出，可 NULL）
    win_rate       REAL,              -- scope 范围内胜率（0~1；列表页直接展示，免聚合查询）
    stats_json     TEXT NOT NULL,     -- 关键统计 JSON：{"battles":50,"avg_turns":24.3,...}
    model          TEXT NOT NULL,     -- 生成模型（如 deepseek-v4-flash）
    skill_version  TEXT NOT NULL,     -- 分析 skill 版本
    doc_json_path  TEXT NOT NULL,     -- 结构化文档路径（相对项目根，如 data/analysis/docs/{id}.json）
    doc_md_path    TEXT NOT NULL,     -- 渲染文档路径（同上 .md）
    created_at     TEXT NOT NULL      -- ISO8601 UTC
);

CREATE INDEX IF NOT EXISTS idx_analyses_scope ON analyses (scope_type, scope_id);
CREATE INDEX IF NOT EXISTS idx_analyses_created ON analyses (created_at DESC);

-- ------------------------------------------------------------
-- 2. analysis_highlights —— 高光回合引用表（一行 = 一个被点名的关键回合）
-- 文档 JSON 里也有这段内容；入表是为了能跨分析检索、直接跳转 battle_turns
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analysis_highlights (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id TEXT NOT NULL,       -- → analyses.id
    seq         INTEGER NOT NULL,    -- 文档内的展示顺序（1 起）
    battle_id   TEXT NOT NULL,       -- → battles.db battles.id（逻辑外键）
    round_no    INTEGER,             -- 第几轮（冗余自 battles.round_no，方便展示）
    turn        INTEGER,             -- 回合数
    side        TEXT CHECK (side IN ('a','b')),  -- 被点评方；全局时刻为 NULL
    description TEXT NOT NULL        -- 点评（中文一句话，如 '关键换人规避了对方先手招式'）
);

CREATE INDEX IF NOT EXISTS idx_highlights_analysis ON analysis_highlights (analysis_id);
CREATE INDEX IF NOT EXISTS idx_highlights_battle   ON analysis_highlights (battle_id);

-- ------------------------------------------------------------
-- 3. meta —— 元信息表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
