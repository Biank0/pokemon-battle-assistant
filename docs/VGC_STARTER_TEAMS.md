# VGC 示例队伍说明

本项目内置 4 支已经通过 `gen9vgc2026regi` 合法性校验的 VGC 双打队伍，方便用户直接测试 6 选 4、手动选出、随机基线对战和后续助手功能。

校验全部使用：

```bash
pba team validate <队伍名> --format gen9vgc2026regi
```

VGC 对战前需要先启动本地 Pokémon Showdown：

```bash
cd ~/Bian-workspace/pokemon-showdown
node pokemon-showdown start --no-security
```

通用对战命令：

```bash
pba battle <队伍名> --format gen9vgc2026regi --select manual
```

固定选出时，编号顺序很重要：**前 2 只是首发，后 2 只是后排**。

---

## 1. `vgc_rain_balance`：雨天平衡队

文件：

```text
data/teams/lab/vgc_rain_balance.json
```

队伍成员：

```text
1. Miraidon
2. Pelipper
3. Archaludon
4. Rillaboom
5. Incineroar
6. Flutter Mane
```

核心思路：

- `Pelipper` 开雨、开顺风。
- `Archaludon` 在雨天下使用 `Electro Shot` 加速输出节奏。
- `Miraidon` 提供电场和强力特攻压制。
- `Rillaboom`、`Incineroar` 提供 Fake Out、场地、威吓和轮转。
- `Flutter Mane` 提供高速特攻和 `Icy Wind` 速度控制。

推荐选出：

```bash
pba battle vgc_rain_balance --format gen9vgc2026regi --select 1,2,3,5
```

含义：

```text
首发：Miraidon + Pelipper
后排：Archaludon + Incineroar
```

适合练习：

- 天气队基础节奏。
- Tailwind 下的高速压制。
- Fake Out + 轮转保护核心输出。

---

## 2. `vgc_trick_room_calyrex`：空间白马队

文件：

```text
data/teams/lab/vgc_trick_room_calyrex.json
```

队伍成员：

```text
1. Calyrex-Ice
2. Farigiraf
3. Amoonguss
4. Incineroar
5. Ursaluna-Bloodmoon
6. Rillaboom
```

核心思路：

- `Calyrex-Ice` 是空间下主输出，也能自己开 `Trick Room`。
- `Farigiraf` 用 `Armor Tail` 阻止对手先制干扰，并提供第二个空间点。
- `Amoonguss` 用 `Rage Powder`、`Spore`、`Pollen Puff` 保护和续航。
- `Ursaluna-Bloodmoon` 是空间下第二特攻输出点。
- `Incineroar`、`Rillaboom` 提供双 Fake Out、威吓、草场和轮转。

推荐选出：

```bash
pba battle vgc_trick_room_calyrex --format gen9vgc2026regi --select 2,1,3,5
```

含义：

```text
首发：Farigiraf + Calyrex-Ice
后排：Amoonguss + Ursaluna-Bloodmoon
```

适合练习：

- Trick Room 展开。
- 慢速核心的回合规划。
- Rage Powder / Fake Out 辅助开空间。

---

## 3. `vgc_sun_koraidon`：晴天故勒顿队

文件：

```text
data/teams/lab/vgc_sun_koraidon.json
```

队伍成员：

```text
1. Koraidon
2. Flutter Mane
3. Tornadus
4. Rillaboom
5. Incineroar
6. Amoonguss
```

核心思路：

- `Koraidon` 开晴天并作为物理压制核心。
- `Flutter Mane` 利用晴天触发 `Protosynthesis`。
- `Tornadus` 提供 Prankster `Tailwind`。
- `Rillaboom`、`Incineroar` 是标准双打支援轮转。
- `Amoonguss` 提供掩护、睡眠和反空间节奏。

推荐选出：

```bash
pba battle vgc_sun_koraidon --format gen9vgc2026regi --select 3,1,2,5
```

含义：

```text
首发：Tornadus + Koraidon
后排：Flutter Mane + Incineroar
```

适合练习：

- Tailwind + 高压 restricted 核心。
- 晴天和 Protosynthesis 配合。
- 进攻队如何用支援位保持节奏。

---

## 4. `vgc_psyspam_calyrex`：精神场黑马队

文件：

```text
data/teams/lab/vgc_psyspam_calyrex.json
```

队伍成员：

```text
1. Calyrex-Shadow
2. Indeedee-F
3. Miraidon
4. Whimsicott
5. Urshifu-Rapid-Strike
6. Incineroar
```

核心思路：

- `Indeedee-F` 开精神场并用 `Follow Me` 保护核心。
- `Calyrex-Shadow` 用 `Astral Barrage` 做高速范围压制。
- `Miraidon` 是第二 restricted 特攻核心。
- `Whimsicott` 提供 Prankster `Tailwind`。
- `Urshifu-Rapid-Strike` 处理需要物理水系突破的局面。
- `Incineroar` 提供威吓、Fake Out、Knock Off 和 Parting Shot。

推荐选出：

```bash
pba battle vgc_psyspam_calyrex --format gen9vgc2026regi --select 2,1,3,6
```

含义：

```text
首发：Indeedee-F + Calyrex-Shadow
后排：Miraidon + Incineroar
```

适合练习：

- 精神场保护高速核心。
- Follow Me + 范围输出。
- 双 restricted 特攻核心的选出判断。

---

## 两支队伍互打示例

```bash
pba battle vgc_sun_koraidon \
  --opponent vgc_trick_room_calyrex \
  --format gen9vgc2026regi \
  --select manual \
  --opponent-select random
```

也可以固定双方选出：

```bash
pba battle vgc_rain_balance \
  --opponent vgc_psyspam_calyrex \
  --format gen9vgc2026regi \
  --select 1,2,3,5 \
  --opponent-select 2,1,3,6
```

## 维护说明

这些队伍的目标是：

1. 保证合法，可直接用于 PBA 测试。
2. 覆盖不同 VGC archetype：雨天、空间、晴天、精神场。
3. 方便后续做选出推荐、对局分析、行动记录和助手功能。

它们不承诺是当前环境的最优天梯队。若 Showdown 规则更新导致非法，请先运行 `pba team validate` 查看原因，再修正对应 JSON。
