# Examples

示例数据索引（均可直接查看；同类结果可用对应命令重新生成）。

| 示例 | 内容 | 生成命令 |
|---|---|---|
| `simple_battle.json` | 离线局面分析 MVP 输入 | — |
| `agent_battle_demo/` | 一场完整 Agent 对战：`record.json`（含逐回合 observation / 合法动作 / Agent 决策与理由）、`replay.html` 回放、`report.md` 中文报告 | `pba agent-battle bss_balance --opponent bss_sun` |
| `analysis_demo/` | 上述对局的深度复盘：回放摘要、逐回合决策评估、对手画像、策略建议 | `pba analysis battle-gen9bssregi-1` |
| `team_build_demo.json` | 一次 AI 建队完整结果（含一轮迭代历史、工具调用记录、Showdown 校验） | `pba build-team "需求"` |

> `agent_battle_demo` 生成时未配置 LLM Key，Agent 决策为 fallback 策略（`fallback: true` 已在
> record 中标注）；`team_build_demo.json` 由 mock LLM 驱动真实建队管线生成。配置 `.env` 后
> 同类命令会产出真实 LLM 推理结果，数据结构完全一致。

离线局面分析 MVP：

```bash
python -m pokemon_battle_assistant.cli examples/simple_battle.json
```
