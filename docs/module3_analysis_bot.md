# 模块三 · 分析 bot（Battle Analyzer）设计说明

> 定位：吃 battles.db 的一次跑量会话，LLM 复盘分析师生成结构化分析报告，
> 反幻觉校验后落 analysis.db（+ 文档库 JSON/MD 双格式），前端结构化渲染，
> 高光回合一键跳回对战明细。复用模块一的 harness 与 skill 框架，零新依赖。

## 1. 架构与数据流

```
battles.db（session/battles/battle_turns，原始逐回合动作）
        │
        ▼
┌─ distiller 蒸馏 ─────────────────────────────────────────┐
│ session_meta     比分/胜率/回合分布（战绩解读的原料）      │
│ pokemon_profiles 每只出场宝可梦：出场率/换人/招式分布      │
│ matchup_matrix   攻→守攻击次数矩阵（对位分析原料）         │
│ sample_timelines 最长/最典型 3 场的逐回合动作采样          │
└──────────────┬───────────────────────────────────────────┘
               │ to_prompt_text ≈ 1 万字符（50 轮也压得住）
               ▼
   skill(battle_analysis/v1)：method.md 五层方法论
                             + report_contract.md 输出契约
               │
               ▼
   LLMHarness（模块一原样复用，temperature 0.4 + json_mode）
               │
               ▼
   validator 反幻觉闸门 ──未过──► repair_prompt 修复轮（≤2 次）
               │过
               ▼
┌─ repository 落盘落库 ────────────────────────────────────┐
│ data/analysis/docs/{id}.json  结构化报告（前端详情源）     │
│ data/analysis/docs/{id}.md    可读 Markdown（本地归档）    │
│ analysis.db analyses 行 + analysis_highlights 高光跳转行  │
└──────────────────────────────────────────────────────────┘
```

五个组件（`src/pokemon_battle_assistant/battle_analyzer/`）：

| 文件 | 职责 |
|---|---|
| `distiller.py` | 只读打开 battles.db，把 50 轮原始数据蒸馏成 ~1 万字符摘要（宝可梦/招式已中文渲染）；会话不存在抛 KeyError、无有效对战抛 ValueError |
| `validator.py` | 反幻觉闸门：名字/招式/阵营/高光回合定位必须真实存在于蒸馏数据；结构/枚举校验（rating S~D、priority 高中低、建议 ≥2 条） |
| `repository.py` | 先写文档文件、后写库行（失败回滚文档）；高光回合 round_no → battle_id 反查写 analysis_highlights 供前端跳转 |
| `pipeline.py` | distill → prompt → LLM → validate（≤2 轮修复）→ save；threading.local 日志钩子供 API 回传 |
| skill | `skills/battle_analysis/v1/`：method.md（五层分析法）+ report_contract.md（JSON 契约），加载器与 team_building 同构 |

## 2. 关键决策与理由

### 2.1 蒸馏而不是全量喂
50 轮 ≈ 400+ 回合原始动作全喂会爆 token 且淹没重点。蒸馏成四块
（战绩概览/个体档案/对位矩阵/采样时间线），6 轮实测 10976 字符 ≈ 6k tokens，
一次分析 8.7k tokens、18 秒。采样时间线只取 3 场代表性对局（最长/最短/典型），
足够支撑"关键回合"层的事实依据。

### 2.2 校验的是"事实性"而不是"合法性"
建队 validator 查赛制约束（clause/等级），分析没有合法性可查——
所有实体（宝可梦名、招式名、side 归属、高光 (round_no, turn, side) 三元组）
必须能在蒸馏数据里精确命中，否则判幻觉。高光校验通过后 repository 才敢
反查 battle_id 写跳转行，保证前端"查看明细"永不 404。

### 2.3 focus 通道
POST /api/analyze 可带 `focus`（如"重点看看快龙"），skill.prompt 把它作为
"用户特别关注"块拼进 user 消息。实测：focus 提到快龙地震，headline 直接
回应"快龙地震被空间队免疫成突破口"。

### 2.4 双格式产出，前端走 JSON
MD 是给人本地看/归档的；前端详情页读 JSON 结构化渲染（评分徽章、A/B 队
左右色边卡片、高光跳转链接），不引入 MD 渲染器。

## 3. API（与 /api/generate 同一套后台任务模式）

| 路由 | 说明 |
|---|---|
| `POST /api/analyze` | {session_id, focus?} → {job_id}；前置检查会话存在且有有效对战（404/400） |
| `GET /api/analyze/{job_id}` | 轮询：logs 逐条回传管线进度（前端 1.5s 轮询） |
| `GET /api/analyses` | 报告索引列表（只查 analysis.db，不读文件） |
| `GET /api/analyses/{id}` | 报告详情：report JSON + session_meta + highlight_links（含 battle_id） |

## 4. 前端

- **报告列表页 /#/analyses**：已完成会话下拉（比分/轮数/时间）+ 关注点输入 →
  发起分析 → 日志滚动 → 完成卡片（评分/结论/用量）→ 查看报告；
  下方历史报告表（标题/评分徽章/比分/胜率/模型/时间）
- **报告详情页 /#/analyses/:id**：头部（标题+评分+会话元信息）→ 战绩解读 →
  阵容表现网格（A 队绿边/B 队红边卡：角色/出场/招式分布/问题告警）→
  对位分析 + 威胁识别双栏 → 关键回合（点击跳 /#/lab/battle/:id）→
  改进建议（优先级徽章：高红/中橙/低灰）

## 5. 验收记录（2026-08-19，DeepSeek）

- 离线单测 `tests/test_analyzer.py` 9 个全过（validator 闸门 7 + 真实库蒸馏 1 + 仓储往返 1）
- CLI 冒烟 `tests/manual/smoke_analyze.py`：BSS 平衡轴 vs BSS 戏法空间（6 轮 2-4），
  1 次过校验，8749 tokens / 18.4s，评分 C，高光 3 条
- API 端到端 `tests/manual/e2e_analyze_check.py`：带 focus 的异步任务 24s 完成，
  列表/详情/高光跳转断言全过

## 6. 已知边界

- 会话级分析（scope_type 固定 'session'）；analysis.db schema 预留了
  team/format 级聚合分析，等跨会话数据积累后再做
- 采样时间线只取 3 场，validator 的高光校验也以此为界——LLM 引用未采样
  场次会被判幻觉（设计如此：报告只谈有据可查的回合）
