# [Gen 9] Doubles OU 建队入门

Showdown format id：`gen9doublesou`

适合人群：想学习 6v6 双打、想体验围绕双目标攻击、保护、速度控制和站位配合展开的对战。

## 1. 规则定位

`gen9doublesou` 是第九世代 Smogon 双打 OU 规则。每边带 6 只宝可梦，场上同时有 2 只宝可梦。它和 VGC 都是双打，但不是同一个规则：Doubles OU 默认是 6v6、等级 100；VGC 通常是带 6 选 4、等级 50。

校验：

```bash
pba team validate my_team --format gen9doublesou
```

开战：

```bash
pba battle my_team --format gen9doublesou
```

## 2. 本地 Showdown 当前关键规则

以下规则来自本地 `pokemon-showdown` 的 format 定义，最终以 `pba team validate` 调用 Showdown 的结果为准。

- 对战类型：双打 `doubles`
- 世代：Gen 9
- 规则集：`Standard Doubles`
- 额外规则：`Evasion Abilities Clause`
- 当前本地 banlist 包含：
  - `DUber`
  - `Shadow Tag`
  - `Commander`

注意：Doubles OU 的 tier 限制和单打 OU 不一样。单打里属于 OU/UU/RU 等分级，并不直接决定它在 Doubles OU 里是否合法。

## 3. 双打和单打最大的区别

双打不是“两个单打同时进行”。建队时要优先考虑：

1. **保护 Protect 的价值很高**
   - 保护可以拖顺风、空间、天气回合。
   - 保护可以让队友安全输出或换位。
   - 很多双打宝可梦都会带 Protect。

2. **速度控制更重要**
   - 顺风、戏法空间、电磁波、冰冻之风、凍風类降速、先制招式都很关键。
   - 队伍最好至少有一种主要速度控制方案。

3. **AOE 招式价值更高**
   - 热风、地震、魔法闪耀、浊流等可以同时压两只。
   - 注意队友是否免疫或抵抗你的 AOE。

4. **站位配合比单体强度更重要**
   - 威吓、击掌奇袭、看我嘛、愤怒粉、广域防守、帮助等辅助很关键。
   - 队伍需要能制造安全输出回合。

5. **联防不只看属性，还看双场压制**
   - 对手一回合有两个行动，你要考虑“双集火”风险。

## 4. 一个通用队伍骨架

新手可以先按这个结构建：

```text
1. 主要输出核心
2. 第二输出点 / AOE 输出
3. 速度控制手：顺风 / 戏法空间 / 降速
4. 辅助手：击掌奇袭 / 看我嘛 / 愤怒粉 / 威吓
5. 防守轮转 / 抗性补充
6. 反制位：反空间、广域防守、清天气或针对热门威胁
```

如果队伍偏进攻，至少确保有 Protect 和速度控制；如果队伍偏空间，确保有可靠开空间手和低速输出手。

## 5. 常见建队错误

- 从单打队伍直接搬 6 只过来，没有 Protect 和速度控制。
- 全队都需要队友保护才能输出，主动权不足。
- AOE 招式误伤队友，自己限制自己。
- 没有应对击掌奇袭、顺风、戏法空间等双打常见节奏。
- 忽视双打专属限制，例如 `Commander`、`Shadow Tag` 等。

## 6. PBA 模版建议

双打 legal action 是组合动作，手动模式会看到类似：

```text
/choose move heatwave -1, move protect
```

建议先校验：

```bash
pba team validate my_team --format gen9doublesou
```

然后用随机基线或手动模式测试：

```bash
pba battle my_team --format gen9doublesou
pba battle my_team --format gen9doublesou --manual
```

## 7. 参考来源

- 本地 Pokémon Showdown format：`gen9doublesou`
- Smogon SV Doubles OU 规则页
