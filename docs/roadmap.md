# 开发路线

## Phase 0：项目初始化

- [x] 初始化仓库
- [x] 编写产品规划
- [x] 编写架构规划
- [x] 编写开发路线

## Phase 0.5：顶层架构确认

目标：在继续深入开发前，先确认项目的长期双层架构。

参考文档：[`top-level-architecture-notes.md`](top-level-architecture-notes.md)、[`ml-and-game-theory-knowledge-map.md`](ml-and-game-theory-knowledge-map.md)

任务：

- [ ] 明确 Battle Model 和 Game Theory Model 的边界
- [ ] 确认本地 Dex 数据策略
- [ ] 确认首个正式支持的规则集
- [ ] 确认项目长期重心是否明确为双打优先、冠军优先
- [ ] 确认 BattleState / Action / Target 是否从一开始按双打建模
- [ ] 确认 champions 规则集是否独立于 gen9 / gen10 规则族
- [ ] 确认 Replay / Timeline / Game Tree 的数据结构方向
- [ ] 确认玩家风格、风险偏好、心理压力和博弈论模块是否纳入第一版 Game Theory Model
- [ ] 决定 MVP 代码是否需要重构到长期目录结构


## Phase 1：最小可用原型 MVP

目标：实现一个命令行对战分析 demo。

任务：

- [ ] 创建 Python 包结构
- [ ] 定义 `PokemonSet`、`Team`、`BattleState`、`Action` 数据模型
- [ ] 支持手写 JSON 输入局面
- [ ] 实现基础属性克制表
- [ ] 实现简单行动评分器
- [ ] 输出推荐操作和解释

验收示例：

```bash
python -m pokemon_battle_assistant analyze examples/simple_battle.json
```

输出：

```text
推荐：使用草属性攻击
置信度：中
理由：属性优势，且对方当前 HP 进入击杀线。
风险：如果对方换入抗草宝可梦，收益下降。
备选：读换使用补盲招式。
```

## Phase 2：配队助手

目标：可以分析一支队伍的基础问题。

任务：

- [ ] 队伍导入格式
- [ ] 属性弱点统计
- [ ] 打点覆盖统计
- [ ] 速度线检查
- [ ] 角色分工识别：输出、盾牌、撒钉、清场、控速等
- [ ] 输出补盲和替换建议

## Phase 3：博弈树推理

目标：支持双方候选行动分支比较。

任务：

- [ ] 生成双方候选行动
- [ ] 简化伤害估算
- [ ] 评估行动后的局面分数
- [ ] 识别稳定解、激进解、读换解
- [ ] 解释最坏情况和最好情况

## Phase 4：知识库扩展

目标：提高事实准确性和环境适应性。

任务：

- [ ] 扩展宝可梦、招式、特性、道具数据
- [ ] 支持不同规则集
- [ ] 常见配置模板
- [ ] 常见威胁库
- [ ] 对局 replay 解析

## Phase 5：产品化

目标：变成可实际使用的 bot。

任务：

- [ ] Web API
- [ ] 前端页面
- [ ] 聊天机器人接入
- [ ] 用户队伍保存
- [ ] 对局历史和复盘管理
- [ ] 部署文档
