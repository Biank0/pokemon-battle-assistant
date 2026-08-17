# 热门规则建队指南

本目录提供 PBA 当前推荐优先支持的三个热门规则说明，帮助用户先理解规则，再创建队伍。

| 文档 | Showdown format id | 类型 | 适合用户 |
|---|---|---|---|
| [Gen 9 OU](gen9ou.md) | `gen9ou` | 6v6 单打 | 标准单打入门 |
| [Gen 9 Doubles OU](gen9doublesou.md) | `gen9doublesou` | 6v6 双打 | Smogon 双打入门 |
| [Gen 9 VGC 2026 Regulation I](gen9vgc2026regi.md) | `gen9vgc2026regi` | VGC 双打 | 官方赛事风格 / 带 6 选 4 |

## 使用方式

先选择规则，再创建和校验队伍：

```bash
pba team create
pba team validate my_team --format gen9ou
pba team validate my_team --format gen9doublesou
pba team validate my_team --format gen9vgc2026regi
```

真正开战前，PBA 也会自动校验队伍合法性：

```bash
pba battle my_team --format gen9ou
```

## 重要说明

- 文档用于建队入门，不替代 Showdown 合法性校验。
- 规则和 banlist 会随本地 `pokemon-showdown` 更新而变化。
- 最终是否合法，以 `pba team validate <队伍名> --format <规则>` 的结果为准。
