# 分析报告输出契约

返回**纯 JSON**（无 markdown 代码块包裹），结构如下：

```json
{
  "title": "标题，如：小边的王牌 vs BSS 平衡轴 · 3轮复盘",
  "headline": "一句话核心结论（30字内，直击要害）",
  "rating": "A",
  "win_loss_read": "战绩解读段落（150~300字）",
  "pokemon_performance": [
    {
      "species_zh": "九尾",
      "side": "a",
      "role": "晴天启动手",
      "appearance": 3,
      "moves_used": [{"move_zh": "气象球", "count": 5}],
      "verdict": "表现评价（80~150字）",
      "issues": ["问题1（没有则空数组）"]
    }
  ],
  "matchups": [
    {
      "attacker_zh": "波荡水", "defender_zh": "快龙",
      "read": "对位解读（攻方压制/吃亏/互有往来 + 依据）"
    }
  ],
  "threats": [
    {"from_zh": "快龙", "why": "为何构成威胁（数据依据）", "counter": "建议应对手段"}
  ],
  "highlights": [
    {"round_no": 2, "turn": 5, "side": "a", "what": "该回合发生了什么、为什么关键"}
  ],
  "recommendations": [
    {"priority": "高", "target": "九尾", "change": "具体改动", "reason": "数据依据"}
  ]
}
```

## 字段规则

- **rating**：综合评价档位，五档 `"S"|"A"|"B"|"C"|"D"`。胜率≥70% 且建议少 → S/A 区间；
  30%~70% → B/C；≤30% 或结构性缺陷明显 → C/D。主观但要有依据
- **pokemon_performance**：蒸馏数据 `pokemon_profiles` 里每只**出场过的**宝可梦都要一条；
  `side` 为该宝可梦所属方（"a"/"b"）；`appearance` 直接用数据里的出场数
- **moves_used**：按使用次数降序，只列实际用过的招式
- **matchups**：2~5 条，选对位矩阵里最有信息量的组合（高频或压制关系明确的）；
  attacker=进攻方视角
- **threats**：站在**双方各自视角**都值得指出（A 队的威胁、B 队的威胁都可以列），0~4 条
- **highlights**：0~4 个关键回合；`round_no`/`turn`/`side` 必须精确对应蒸馏数据
  `sample_timelines` 中存在的场次与回合（这是跳转链接的定位键，编错即失效）
- **recommendations**：2~5 条；`target` 是改动的落点（宝可梦中文名或"首发策略"等）；
  `priority` 只能是 `"高"|"中"|"低"`；建议主要面向**败方或低评价方**，胜方给保持性建议
- 所有 `*_zh` 字段必须原样使用蒸馏数据提供的中文名（校验会比对）
