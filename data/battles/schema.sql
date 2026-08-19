-- ============================================================
-- battles.db —— 对战记录库（纯运行时活库）
-- 唯一写方：模块二（对战 Lab）。模块三（分析）只读
-- 表结构讲解：docs/battles_db_schema.md
-- 初始化：scripts/build_battles_db.py（建表 + 合成数据冒烟测试，事务回滚不留脏数据）
--
-- 本库无种子数据：内容全部由模块二在运行时写入
-- 三层结构：battle_sessions（跑量任务）→ battles（单场）→ battle_turns（逐回合动作）
-- ============================================================

-- ------------------------------------------------------------
-- 1. battle_sessions —— 跑量任务表（一行 = 一次"两队打 N 轮"任务）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS battle_sessions (
    id           TEXT PRIMARY KEY,  -- uuid4，任务标识
    team_a_id    TEXT NOT NULL,     -- → teams.db teams.id（己方/A 队）
    team_b_id    TEXT NOT NULL,     -- → teams.db teams.id（对手/B 队）
    format       TEXT NOT NULL,     -- 赛制 ID（gen9ou / gen9bssregi ...），冗余自两队共同赛制
    bot_config   TEXT NOT NULL,     -- 双方 bot 配置 JSON：{"a":{"type":"heuristic","version":1},"b":{...}}
    rounds_total INTEGER NOT NULL,  -- 计划轮数（如 50）
    rounds_done  INTEGER NOT NULL DEFAULT 0,  -- 已完成轮数（前端进度条轮询此字段）
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending','running','completed','failed','cancelled')),
                                      -- pending=已创建未开始 / running=进行中 / completed=全部完成
                                      -- failed=中途异常终止 / cancelled=用户手动取消
    error        TEXT,              -- failed 时的失败原因（异常堆栈摘要）
    started_at   TEXT,              -- 首场开始时间 ISO8601 UTC
    finished_at   TEXT,             -- 末场结束时间；未结束为 NULL
    stats_json   TEXT               -- completed 时的聚合统计 JSON（胜率/回合分布/招式热榜/宝可梦贡献）
);

CREATE INDEX IF NOT EXISTS idx_sessions_team_a ON battle_sessions (team_a_id);
CREATE INDEX IF NOT EXISTS idx_sessions_team_b ON battle_sessions (team_b_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON battle_sessions (status);

-- ------------------------------------------------------------
-- 2. battles —— 单场表（一行 = 一场完整对战）
-- 字段来源：poke-env AbstractBattle（battle_tag/turn/won/finished）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS battles (
    id          TEXT PRIMARY KEY,   -- uuid4
    session_id  TEXT NOT NULL,      -- → battle_sessions.id
    round_no    INTEGER NOT NULL,   -- 本任务内第几轮（1 起）
    battle_tag  TEXT,               -- Showdown 对战标识（如 'battle-gen9ou-1'），可追溯回放
    winner      TEXT NOT NULL
                CHECK (winner IN ('a','b','draw','error')),
                                     -- a=team_a 胜 / b=team_b 胜 / draw=平局(超时等) / error=本场异常
    end_turn    INTEGER,            -- 总回合数（battle.turn）
    record_json TEXT NOT NULL,      -- 引擎原始完整记录 JSON（保底层：含双方 observations/合法动作/选择）
    created_at  TEXT NOT NULL       -- 入库时间 ISO8601 UTC
);

CREATE INDEX IF NOT EXISTS idx_battles_session ON battles (session_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_battles_session_round ON battles (session_id, round_no);
CREATE INDEX IF NOT EXISTS idx_battles_winner ON battles (winner);

-- ------------------------------------------------------------
-- 3. battle_turns —— 逐回合动作明细表（一行 = 一次出招/换人/选队）
-- 从 record_json 的 steps 拆出的可查询层；HP 百分比快照已决策不记录
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS battle_turns (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增序号（同回合双方动作的稳定排序）
    battle_id      TEXT NOT NULL,   -- → battles.id
    turn          INTEGER,          -- 回合数；选队阶段（team preview）为 0
    side           TEXT NOT NULL CHECK (side IN ('a','b')),
                                      -- 动作方：a=team_a 侧 / b=team_b 侧
    action_type    TEXT NOT NULL CHECK (action_type IN ('move','switch','team_order')),
                                      -- move=出招 / switch=换人 / team_order=选出场顺序
    actor_species  TEXT,            -- 动作主体 slug（→ dex.species.id）；move=出手者 / switch=换下者
    move_id        TEXT,            -- 招式 slug（→ dex.moves.id）；仅 action_type='move' 有值
    target_species TEXT,            -- 目标 slug：switch=换上者 / move=在场对手（单打）；选队为 NULL
    raw_label      TEXT NOT NULL    -- 原始指令文本（引擎指令原文，保底与调试用）
);

CREATE INDEX IF NOT EXISTS idx_turns_battle  ON battle_turns (battle_id);
CREATE INDEX IF NOT EXISTS idx_turns_species ON battle_turns (actor_species);
CREATE INDEX IF NOT EXISTS idx_turns_move    ON battle_turns (move_id);

-- ------------------------------------------------------------
-- 4. meta —— 元信息表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
