# [Gen 9] VGC 2026 Regulation I 建队入门

Showdown format id：`gen9vgc2026regi`

适合人群：想练官方 VGC 风格双打、想学习带 6 选 4、等级 50、道具不可重复、公开队表和限制神规则的用户。

## 1. 规则定位

`gen9vgc2026regi` 是本地 Pokémon Showdown 中的第九世代 VGC 2026 Regulation I format。它是双打规则，但和 Smogon Doubles OU 不同：VGC 更接近官方赛事和游戏内排位规则。

校验：

```bash
pba team validate my_team --format gen9vgc2026regi
```

开战：

```bash
pba battle my_team --format gen9vgc2026regi
```

固定 6 选 4：

```bash
pba battle my_team --format gen9vgc2026regi --select 1,2,3,4
```

手动 6 选 4：

```bash
pba battle my_team --format gen9vgc2026regi --select manual
```

## 2. 本地 Showdown 当前关键规则

以下规则来自本地 `pokemon-showdown` 的 format 定义，最终以 `pba team validate` 调用 Showdown 的结果为准。

- 对战类型：双打 `doubles`
- 世代：Gen 9
- 规则集：`Flat Rules`
- 等级：`Adjust Level = 50`
- 最低来源世代：`Min Source Gen = 9`
- 计时：`VGC Timer`
- 队表：`Open Team Sheets`
- 限制规则：`Limit Two Restricted`
- restricted 分类：`Restricted Legendary`

通俗理解：队伍可以围绕最多 2 只限制级传说宝可梦构建，但仍有幻之宝可梦、特殊形态、重复道具等官方风格限制。具体名单和细节不要手动背，直接用 Showdown 校验。

## 3. VGC 和 Doubles OU 的核心区别

| 项目 | VGC Regulation I | Doubles OU |
|---|---|---|
| 对战类型 | 双打 | 双打 |
| 等级 | 自动 50 级 | 通常 100 级 |
| 出场 | 常见为带 6 选 4 | 6 只都参与 |
| 道具 | 通常不能重复 | 依 Showdown 规则 |
| 队表 | Open Team Sheets | 通常不是核心规则 |
| 限制级传说 | Regulation I 允许最多 2 只 | 按 DOU/DUber 体系限制 |

PBA 当前的环境主要负责连接 Showdown 和记录对战；具体选出 4 只、规则细节和合法性由 Showdown 处理。

## 4. 建队核心思路

VGC Reg I 的队伍通常围绕“核心 + 支援 + 反制”构建：

1. **先决定限制级核心**
   - 最多 2 只 Restricted Legendary。
   - 两只核心最好互补，而不是都被同一种对策压制。

2. **给核心配支援**
   - 击掌奇袭、威吓、看我嘛、愤怒粉、顺风、戏法空间、广域防守都很常见。
   - 支援位的目标是帮核心安全行动。

3. **准备速度方案**
   - 顺风队要考虑顺风过后怎么办。
   - 空间队要考虑如何稳定开空间，以及空间结束后怎么办。
   - 中速平衡队要准备多种局面下的速度控制。

4. **准备保护和换位节奏**
   - VGC 中 Protect 非常重要。
   - 不带 Protect 的宝可梦要有明确理由，例如突击背心、讲究道具或强功能定位。

5. **重视 4 只选出逻辑**
   - 队伍不是每局 6 只都上。
   - 建队时要想清楚常见对局中选哪 4 只，首发哪 2 只。

## 5. 一个通用队伍骨架

```text
1. Restricted 核心 A
2. Restricted 核心 B 或非限制级主输出
3. 速度控制手：顺风 / 戏法空间 / 降速
4. 辅助手：击掌奇袭 / 威吓 / 看我嘛 / 愤怒粉
5. 防守补强 / 属性联防
6. 针对位：反空间、广域防守、天气控制、反制热门核心
```

如果你是新手，建议先用一个明确的主计划：

```text
首发支援 + 核心，后排第二输出 + 反制位
```

而不是每只都想单独打伤害。

## 6. 常见建队错误

- 只放强力 Restricted，不给它们速度控制和支援。
- 重复道具导致官方/VGC 风格规则不合法。
- 6 只看起来都强，但不知道每局选哪 4 只。
- 全队太依赖天气、空间或顺风，被反制后没有备用计划。
- 忘记公开队表环境下，对手能看到你的招式、道具、太晶等信息。

## 7. PBA 模版建议

VGC 推荐先做合法性检查：

```bash
pba team validate my_team --format gen9vgc2026regi
```

再预览队伍文本：

```bash
pba team preview my_team
```

VGC 的队伍选出由 Showdown team preview 阶段处理。PBA 会提交类似：

```text
/team 1234
```

不是简单把 6 只裁剪成 4 只。编号顺序很重要：前 2 只是双打首发，后 2 只是后排。

如果你当前本地 Showdown 不支持这个 format，先更新本地 `pokemon-showdown`，或者用当前本地支持的 VGC format id。

## 8. 参考来源

- 本地 Pokémon Showdown format：`gen9vgc2026regi`
- Pokémon Scarlet/Violet Regulation I 官方规则页
- Pokémon VGC Tournament Handbook / Video Game Rules 文档

## 9. 使用 PBA 创建 VGC 队伍

现在项目后续主要围绕 VGC 双打展开，因此：

```bash
pba team create
```

默认会推荐 `gen9vgc2026regi`，并在创建过程中提醒：

- VGC 是双打 6 选 4。
- 前 2 只是首发，后 2 只是后排。
- 道具通常不能重复。
- 很多宝可梦需要考虑 `Protect`。
- 队伍最好有速度控制，例如顺风、戏法空间、降速或先制节奏。
- 队伍最好有支援动作，例如击掌奇袭、威吓、看我嘛、愤怒粉、广域防守等。

建完以后建议立刻运行：

```bash
pba team validate my_team --format gen9vgc2026regi
```

然后用手动选出体验真实 VGC 节奏：

```bash
pba battle my_team --format gen9vgc2026regi --select manual
```
