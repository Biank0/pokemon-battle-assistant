# [Gen 9] BSS Regulation I 建队入门

Showdown format id：`gen9bssregi`

适合人群：想练官方 BSS（Battle Stadium Singles）风格单打、6 选 3、等级 50、道具不可重复、允许 2 只受限传说的用户。BSS 是项目当前的默认主线规则。

## 1. 规则定位

`gen9bssregi` 是本地 Pokémon Showdown 中的第九世代 BSS Regulation I format。它是**单打**规则，带 6 只实战选出 3 只，和 Smogon OU 的 6v6 单打完全不同，更接近游戏内排位（Ranked Battles）规则。

校验：

```bash
pba team validate my_team --format gen9bssregi
```

开战：

```bash
pba battle my_team --format gen9bssregi
```

固定 6 选 3：

```bash
pba battle my_team --format gen9bssregi --select 1,2,3
```

手动 6 选 3：

```bash
pba battle my_team --format gen9bssregi --select manual
```

## 2. 本地 Showdown 当前关键规则

以下规则来自本地 `pokemon-showdown` 的 format 定义，最终以 `pba team validate` 调用 Showdown 的结果为准。

- 对战类型：单打 `singles`
- 世代：Gen 9
- 规则集：`Flat Rules`
- 等级：`Adjust Level = 50`
- 最低来源世代：`Min Source Gen = 9`
- 计时：`VGC Timer`
- 限制规则：`Limit Two Restricted`
- restricted 分类：`Restricted Legendary`
- 队伍规模：6 只，team preview 选出 3 只（PBA fallback：`gen9bssregi: 3`）

通俗理解：队伍最多允许 2 只受限传说宝可梦（如 Koraidon、Miraidon、Calyrex-Shadow 等），全部自动调整到 50 级，道具体现官方 Item Clause（不能重复），同种宝可梦不能重复（Species Clause）。

## 3. BSS 和 OU / VGC 的核心区别

| 项目 | BSS Reg I | Gen 9 OU | VGC 2026 Reg I |
|---|---|---|---|
| 对战类型 | 单打 | 单打 | 双打 |
| 等级 | 自动 50 级 | 100 级 | 自动 50 级 |
| 出场 | 带 6 选 3 | 6 只都参与 | 带 6 选 4 |
| 道具 | 不能重复 | 可重复 | 不能重复 |
| 队表 | team preview 可见 6 只 | 无 team preview | Open Team Sheets |
| 受限传说 | 最多 2 只 | 按 Smogon 分级 | 最多 2 只 |

## 4. 选出（6 选 3）思路

- BSS 的 team preview 能看到对方 6 只，选出本身就是博弈：针对对方核心、避免被克制。
- 选出顺序有意义：第 1 只首发，通常选择对位好、能先手的宝可梦。
- 前排打线、后排补位：常见策略是「核心输出 + 起点掩护 + 针对位」。
- 常见反直觉点：不要只想着首发克制，BSS 换人惩罚较重，首发容错更重要。

## 5. 建队骨架建议

1. 确定核心：1 只受限传说或强力核心（如 Koraidon / Calyrex-Shadow / Gholdengo）。
2. 补速度线：至少 1 只能先手压制对方核心的快攻手。
3. 补耐久轴：1 只能扛住环境主流输出的盾（如 Ting-Lu / Amoonguss）。
4. 补控场：隐形岩、鬼火、催眠等状态手段在单打价值很高。
5. 太晶属性：进攻型（取反制属性）或保命型（消弱点），6 只尽量不重复思路。

## 6. 示例队伍

仓库内置三支通过 `gen9bssregi` 校验的示例队：

```text
data/trainers/bss_balance.json       # 平衡队：Gholdengo + Dragonite + Ting-Lu 等
data/trainers/bss_sun.json           # 晴天队：Koraidon + Torkoal + Walking Wake 等
data/trainers/bss_trick_room.json    # 戏法空间队：Calyrex-Shadow + Ursaluna + Hatterene 等
```

验证示例队：

```bash
pba team validate bss_balance --format gen9bssregi
pba team validate bss_sun --format gen9bssregi
pba team validate bss_trick_room --format gen9bssregi
```
