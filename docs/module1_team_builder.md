# 模块一 · AI 建队 设计文档（harness + skill + pipeline）

> 定位：用户需求（自然语言）→ 合法对战队伍 → teams.db。
> 代码：`src/pokemon_battle_assistant/`（harness / skills / team_builder 三层）
> CLI 入口：`scripts/generate_team.py`
> 依赖：dex.db（只读知识）、teams.db（写入）、`.env`（DeepSeek 配置）

## 一、三层分离：harness 管调用，skill 管知识，pipeline 管编排

```
┌──────────────────────────────────────────────────┐
│ pipeline.py（业务编排层——唯一的业务逻辑所在）        │
│   需求 → 蓝图 → 候选池 → 队伍 → 校验 → 入库        │
└──────┬────────────────────────┬──────────────────┘
       │ 调 LLM                  │ 加载知识
       ▼                        ▼
┌──────────────┐        ┌─────────────────────────┐
│ harness/llm  │        │ skills/team_building/v1 │
│ 零业务知识    │        │ 赛制条款+方法论+输出契约  │
│ 模块三直接复用│        │ 版本化，落库可追溯        │
└──────────────┘        └─────────────────────────┘
```

**为什么这样分**：
- harness 不 import 项目内任何模块 → 模块三（分析 bot）原样复用，换模型只改 `.env`
- skill 是"知识包"不是代码 → 迭代建队方法论只改文件、升版本号，teams.skill_version 记录每支队伍是哪个版本产出
- 业务逻辑集中在 pipeline → 出 bug 只看一个文件

## 二、两阶段 LLM 流水线（核心设计讲解）

### 为什么是两次调用而不是一次

矛盾点：dex 有 1480 只宝可梦，全塞进 prompt 不现实（token 爆炸且模型注意力涣散）；但用户需求是自然语言（"帮我建支晴天队"），直接写 SQL 又翻译不了。

解法：**让 LLM 做它擅长的（理解需求、规划阵容），让 SQL 做它擅长的（在 49401 行 learnsets 里精确筛选）**。拆成"规划"和"构建"两次调用：

```
用户需求："帮我建一支晴天队，打法激进一点"
   │
   ▼ 阶段1 planner（LLM 第1次调用）
队伍蓝图 JSON：
   { strategy: "晴天下高速特攻压制",
     slots: [
       { role_zh: "日照启动手", types: ["Fire"], stat_min: {spe: 90} },
       { role_zh: "晴天子核心", types: ["Fire","Grass"], stat_min: {spa: 100} },
       ... 共 6 个角色位 ]
   }
   │
   ▼ 阶段2 pool（纯 SQL，零 LLM）
每个角色位查 dex.db（种族值拆列 + 属性列，索引直查）：
   → 每池 15~25 只候选，带中文名/种族值/特性/高威力代表招
   │
   ▼ 阶段3 builder（LLM 第2次调用）
蓝图 + 候选池 + skill（规则/方法论/输出契约）
   → 完整队伍 JSON：6 只的招式/道具/特性/性格/EVs/太晶（全 slug）
   │
   ▼ 阶段4 validator（纯本地，零 LLM）
四道闸门 → 失败则错误清单回喂 builder 修复（≤3 轮）
   │
   ▼ 阶段5 repository（零 LLM）
按 teams.db 写入契约入库
```

### 各阶段输入输出契约

| 阶段 | 输入 | 输出 | 谁干活 |
|---|---|---|---|
| planner | 需求文本 + 赛制 ID + skill 的蓝图 schema | 蓝图 JSON（≤6 角色位） | LLM |
| pool | 蓝图每个角色位 | 每位 15~25 只候选池文本 | SQL |
| builder | 蓝图 + 池 + skill 全文 | 队伍 JSON | LLM |
| validator | 队伍 JSON + dex.db + rules 约束 | 错误清单（空=通过） | 本地 |
| repository | 合法队伍 JSON | teams.id | 本地 |

## 三、harness 设计（`harness/llm.py`）

- httpx 直连 DeepSeek 的 OpenAI 兼容端点（`/v1/chat/completions`）——**不装 openai 包**，httpx 已在 venv
- `chat(messages, *, json_mode=False, temperature=0.7) → str`
- 指数退避重试：429/5xx/超时共 3 次；单次超时 60s
- 每次调用累计 token 用量与耗时（pipeline 结束时打印成本）
- 配置从 `.env`：`OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL`（现配 deepseek-chat，换 V4 Flash 只改这一行）

## 四、skill 设计（`skills/team_building/`）

```
skills/team_building/
  skill.py            # 加载器：拼装 prompt 片段
  v1/
    rules.json        # 机器可校验的赛制约束（validator 共用）
    method.md         # 建队方法论（喂 LLM 的常识文本）
    contract.md       # 输出 JSON 契约（schema + slug 规则）
```

**rules.json 一份两用**（防"讲的和查的不一致"）：

```json
{"formats": {
  "gen9bssregi":  {"level": 50, "team_size": 6, "allow_dup_items": false,
                   "allow_dup_species": false},
  "gen9vgc2026regi": {...同 BSS...},
  "gen9ou":       {"level": 100, "team_size": 6, "allow_dup_items": true,
                   "allow_dup_species": false}
}}
```

- **喂 LLM 时**：skill.py 把机器字段渲染成中文条款 + 并入 `data/rules/formats.json` 的人类规则文本（BSS 6选3、VGC 双打 6选4 等）
- **校验时**：validator 直接读同一份 JSON 的字段
- 规则文本权威源是 `data/rules/formats.json`；skill 只补充机器字段，不复制叙述

**method.md 内容要点**：角色分工常识（扫荡手/受盾/辅助/天气轴心）、属性联防互补、道具与性格搭配原则、EV 分配直觉、太晶属性策略。这是产出质量的上限所在。

**contract.md 内容要点**：输出必须是纯 JSON（无 markdown 包裹）；成员字段全用 dex slug（小写无符号）；species 必须从候选池中选；moves 1~4 招且必须真实可学；`name_en`（英文标识）+ `display_name`（中文队名）+ `strategy_notes`（战术说明）。

## 五、候选池设计（`team_builder/pool.py`）

每个角色位的 SQL 策略：

```sql
SELECT s.id, s.name_zh, s.type1, s.type2, s.hp..s.spe, s.abilities
FROM species s
WHERE (s.type1 IN (:types) OR s.type2 IN (:types))   -- 属性偏好
  AND s.spe >= :spe_min AND s.spa >= :spa_min          -- 数值门槛（拆列直查）
  AND s.bst >= :bst_min                                -- 保底强度
ORDER BY 相关数值 DESC LIMIT 25
```

- 池内每只附**高威力代表招**（JOIN learnsets + moves 取威力 TOP6）——给 LLM 配招线索
- 蓝图筛选过松导致池超 25 → 收紧（提高门槛）；过空（<5）→ 放宽（降门槛/去属性限制），由 pool.py 自动调节两轮
- 属性/数值全无约束的角色位（"自由位"）→ 按 bst + 双打/单打适应性取 TOP25

## 六、校验闸门（`team_builder/validator.py`）

| 闸门 | 检查内容 | 数据源 |
|---|---|---|
| 1 结构 | 字段齐全、恰好 team_size 只、每人 1~4 招、EV 总和≤510 单项≤252 | rules.json |
| 2 存在性 | species/ability/item/nature/move 的 slug 全在 dex | dex.db 四表 |
| 3 归属 | ability ∈ 该物种的特性列表 | species.abilities JSON |
| 4 可学习 | 每一招都在该物种的 learnsets 里（反幻觉核心） | learnsets 表 |
| 5 赛制 | 等级、道具不重复（BSS/VGC）、物种不重复 | rules.json |

- 错误消息全中文、带槽位号，格式如 `槽位2：喷火龙学不会"十万伏特"`
- **修复循环**：错误清单回喂 builder 重生成，最多 3 轮；仍失败 → 整单报错退出，**绝不写库**（宁可不生成，不生成假队）
- 受限传说数量（BSS/VGC ≤2）暂不机器校验（dex 无结构化受限名单），由 method.md 约束，留待后续

## 七、入库（`team_builder/repository.py`，落实 teams.db 写入契约）

1. `id` = uuid4
2. `name` = LLM 给的 `name_en` slug 化；冲突自动加 `-2/-3` 后缀
3. 成员 slug 已过闸门 → 同一事务写 `teams` + `team_members`
4. `export_text` 由结构化数据现拼（与 build_teams_db.py 同规则：等级≠100 才写 Level 行、EVs 只写非 0、IVs 只写非 31）
5. 溯源字段齐全：`source='ai'`、`requirement_prompt`、`skill_version='v1'`、`model`（harness 读到的实际模型名）

## 八、测试策略

- **离线**（不花 token）：FakeHarness 返回固定 JSON → 测 validator 五闸门（含每类非法用例）、repository 写入契约、pool 筛选正确性、skill 三文件加载、pipeline 修复循环（第一轮故意非法、第二轮合法）
- **在线冒烟**：真实 DeepSeek 跑 1~2 个需求，人工审队伍合理性 + 校验零错误 + teams.db 可查

## 九、本期不做

- FastAPI / 前端页面（三模块核心打通后统一建）
- 队伍迭代优化（"基于这份分析改进队伍"是模块三之后的需求）
- 受限传说机器校验、按 tier 的池过滤（dex 数据补齐后再加）
