const { reactive, onMounted } = Vue
import { getHealth } from '../api.js'

export default {
  setup() {
    const state = reactive({
      healthy: false,
      health: {},
      cards: [
        { path: '/team-builder', icon: 'MagicStick', title: 'AI 建队', desc: '输入需求，生成合法 BSS 队伍与建队理由' },
        { path: '/battle', icon: 'Sword', title: '对战面板', desc: '配置队伍与对手，Agent 自动打一局' },
        { path: '/team', icon: 'Collection', title: '队伍管理', desc: '查看 / 校验 / 删除已保存队伍' },
        { path: '/lab', icon: 'Odometer', title: '实验室', desc: '多对手批量模拟，统计胜率报告' },
        { path: '/analysis', icon: 'DataAnalysis', title: '分析报告', desc: '对战复盘与逐回合决策评估' },
        { path: '/orchestrator', icon: 'Refresh', title: '闭环流程', desc: '建队 → 跑量 → 复盘 → 迭代一条龙' },
      ],
    })

    onMounted(async () => {
      try {
        state.health = await getHealth()
        state.healthy = state.health.status === 'ok'
      } catch {
        state.healthy = false
      }
    })

    return { state }
  },
  template: `
    <div>
      <el-card class="page-card">
        <h1 class="page-title">宝可梦对战助手</h1>
        <p class="page-desc">
          环境层（Showdown + 感知 + 记忆）之上构建的 LLM Agent 系统：
          AI 建队 → 批量对战 → 深度复盘 → 迭代优化 的完整闭环。
        </p>
        <el-steps :active="4" align-center class="loop-steps">
          <el-step title="AI 建队" description="需求 → 合法队伍" />
          <el-step title="批量跑量" description="Lab 多对手模拟" />
          <el-step title="深度复盘" description="逐回合决策评估" />
          <el-step title="迭代优化" description="复盘 → 改进队伍" />
        </el-steps>
      </el-card>

      <el-row :gutter="16">
        <el-col :span="8" v-for="card in state.cards" :key="card.path">
          <el-card class="entry-card" shadow="hover" @click="$router.push(card.path)">
            <div class="entry-icon"><el-icon :size="30"><component :is="card.icon" /></el-icon></div>
            <div class="entry-title">{{ card.title }}</div>
            <div class="entry-desc">{{ card.desc }}</div>
          </el-card>
        </el-col>
      </el-row>

      <el-card class="page-card">
        <template #header>服务状态</template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="API 服务">
            <el-tag :type="state.healthy ? 'success' : 'danger'">{{ state.healthy ? '在线' : '离线' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="服务">{{ state.health.service || '-' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>
    </div>
  `,
}
