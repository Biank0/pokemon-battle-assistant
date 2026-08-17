# BSS Regulation I（`gen9bssregi`）规则详解

BSS（Battle Stadium Singles）是宝可梦官方排位赛的单打赛制。本项目主线规则为第九世代 Regulation I，本地 Showdown format id：`gen9bssregi`。建队入门向说明见 [formats/gen9bssregi.md](formats/gen9bssregi.md)。

## 1. 规则速览

| 条目 | 规则 |
|---|---|
| 对战类型 | 单打（singles） |
| 队伍规模 | 登记 6 只，team preview 选出 3 只 |
| 等级 | 自动调整到 50 级（Adjust Level = 50） |
| 规则集 | Flat Rules |
| 道具 | Item Clause：道具不可重复 |
| 宝可梦 | Species Clause：同种不可重复 |
| 受限传说 | 最多 2 只 Restricted Legendary（如 Koraidon、Calyrex-Shadow） |
| 来源世代 | Min Source Gen = 9（朱紫可获得） |
| 计时 | VGC Timer |
| 队表 | team preview 双方可见 6 只（选出隐藏） |

## 2. 与 OU / VGC 的核心区别

| 项目 | BSS Reg I | Gen 9 OU | VGC 2026 Reg I |
|---|---|---|---|
| 对战类型 | 单打 | 单打 | 双打 |
| 等级 | 自动 50 级 | 100 级 | 自动 50 级 |
| 出场 | 带 6 选 3 | 6 只都参与 | 带 6 选 4 |
| 道具 | 不能重复 | 可重复 | 不能重复 |
| 队表 | team preview 可见 6 只 | 无 team preview | Open Team Sheets |
| 受限传说 | 最多 2 只 | 按 Smogon 分级 | 最多 2 只 |

关键差异：BSS 是「选出博弈 + 单打对位」，6 选 3 意味着每局有明确的核心与针对位，且换人机会成本高。

## 3. 在 PBA 中的实现

- 默认 format 已切到 `gen9bssregi`（CLI / API / 各模块的 `format` 参数默认值）
- `team_selection.py`：选出数量默认 3，`/team` 指令在 team preview 阶段提交
- `showdown_formats.py`：`FALLBACK_PICKED_TEAM_SIZES` 含 `gen9bssregi: 3`
- 合法性校验：`pba team validate <team> --format gen9bssregi` 走本地 Showdown `TeamValidator`
- 内置示例队：`data/teams/lab/bss_balance.json` / `bss_sun.json` / `bss_trick_room.json`
- Agent 对战：`pba agent-battle <team> --format gen9bssregi`（team preview 由 `BattleAgent.decide_team_preview` 决策）

## 4. 选出策略（6 选 3）

- **选出即博弈**：preview 能看到对方 6 只，选出本身就是针对对方核心、规避克制的决策
- **顺序有意义**：第 1 只首发，优先对位好、容错高的宝可梦
- **常见结构**：核心输出 + 起点掩护 + 针对位；或双核心 + 灵活位
- **反直觉点**：不要只追求首发克制；BSS 换人惩罚重，首发容错比爆发更重要

## 5. 建队骨架

1. **确定核心**：1 只受限传说或强力核心（Koraidon / Calyrex-Shadow / Gholdengo 等）
2. **补速度线**：至少 1 只能先手压制对方核心的快攻手
3. **补耐久轴**：1 只能扛主流输出的盾（Ting-Lu / Amoonguss 等）
4. **补控场**：隐形岩、鬼火、催眠等状态手段在单打价值高
5. **太晶属性**：进攻型（取反制属性）或保命型（消弱点），6 只思路尽量不重复

## 6. 常见非法原因（校验报错排查）

- 道具重复（Item Clause）或同种宝可梦重复（Species Clause）
- 受限传说超过 2 只
- 招式 / 道具 / 特性在该宝可梦的 Min Source Gen = 9 下不可获得
- EV 总和超过 510 或单项超过 252；IV 超出 0-31
- 中文名误填（`species` / `moves` / `item` / `ability` 必须用 Showdown 英文名）

## 7. 相关命令

```bash
pba team validate bss_balance --format gen9bssregi   # 合法性校验
pba battle bss_balance --format gen9bssregi --select manual   # 手动 6 选 3
pba agent-battle bss_balance                          # Agent 自动对战
pba build-team "一支以 Gholdengo 为核心的平衡队"        # AI 建队
```

## 8. 参考

- 本地权威定义：`pokemon-showdown/config/formats.ts` 与 `custom-formats.js`
- 入门向说明：[formats/gen9bssregi.md](formats/gen9bssregi.md)
- 项目架构：[ARCHITECTURE.md](ARCHITECTURE.md)
