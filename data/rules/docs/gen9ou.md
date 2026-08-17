# [Gen 9] OU 建队入门

Showdown format id：`gen9ou`

适合人群：想打最常见的 6v6 单打、想从标准单打环境开始学习轮转、撒钉、破盾和终盘清场的用户。

## 1. 规则定位

`gen9ou` 是第九世代 Smogon 单打 OU 规则。每边带 6 只宝可梦，场上一次只能有 1 只宝可梦。PBA 中可以这样校验：

```bash
pba team validate my_team --format gen9ou
```

这样开战：

```bash
pba battle my_team --format gen9ou
```

## 2. 本地 Showdown 当前关键规则

以下规则来自本地 `pokemon-showdown` 的 format 定义，最终以 `pba team validate` 调用 Showdown 的结果为准。

- 对战类型：单打 `singles`
- 世代：Gen 9
- 规则集：`Standard`
- 额外规则：`Evasion Abilities Clause`
- 睡眠规则：`Sleep Moves Clause`，并取消传统 `Sleep Clause Mod`
- 当前本地 banlist 包含：
  - `Uber`
  - `AG`
  - `Arena Trap`
  - `Moody`
  - `Shadow Tag`
  - `King's Rock`
  - `Razor Fang`
  - `Baton Pass`
  - `Last Respects`
  - `Shed Tail`
  - `Tera Blast`

注意：banlist 会随 Showdown 更新而变化，不建议手动记忆完整列表。建队后直接运行：

```bash
pba team validate my_team --format gen9ou
```

## 3. 建队核心思路

一个新手友好的 OU 队伍通常先保证这几件事：

1. **有稳定的物理/特殊输出**
   - 不要 6 只全是物攻或全是特攻。
   - 至少准备 1 个能快速压血线的输出点。

2. **有防守轮转点**
   - 队伍需要能安全切入常见攻击属性。
   - 不要让全队同时怕同一个属性，例如全队都怕地面或冰。

3. **有速度控制或高速点**
   - 高速宝可梦、围巾手、先制招式、强化后提速都可以。
   - 没有速度控制的队伍容易被对方终盘清场。

4. **有场地资源处理**
   - OU 很重视隐形岩、撒菱、毒菱等 entry hazards。
   - 队伍最好有撒钉手，也最好有清场地手，例如高速旋转或清除浓雾。

5. **有终盘计划**
   - 建队时先想清楚：最后靠谁收比赛？
   - 例如强化清场、围巾收割、优先度收割，或者靠持续消耗赢。

## 4. 一个通用队伍骨架

可以先按这个结构建 6 只：

```text
1. 主输出 / 破盾手
2. 高速点 / 围巾手 / 清场手
3. 物理防守轮转
4. 特殊防守轮转
5. 撒钉手
6. 清场地手 / 功能手
```

这不是唯一答案，但适合新手避免队伍结构失衡。

## 5. 常见建队错误

- 只堆高种族值，没有抗性轮转。
- 忘记处理隐形岩和撒菱。
- 队伍太慢，无法阻止对方强化后清场。
- 过度依赖一个宝可梦破盾，一旦被针对就无法推进。
- 使用当前 OU 禁止的宝可梦、招式、特性或道具。

## 6. PBA 模版建议

创建队伍：

```bash
pba team create
```

检查合法性：

```bash
pba team validate my_team --format gen9ou
```

查看 Showdown 文本：

```bash
pba team preview my_team
```

如果校验报错，先修正本地错误；如果本地通过但 Showdown 拒绝，以 Showdown 原因为准。

## 7. 参考来源

- 本地 Pokémon Showdown format：`gen9ou`
- Smogon SV OU / Pokémon Showdown 规则页
- Smogon 关于 SV OU Sleep Moves Clause 的公告
