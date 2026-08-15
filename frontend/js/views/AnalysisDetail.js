const { reactive, computed, onMounted } = Vue
import { getAnalysis } from '../api.js'

export default {
  setup() {
    const route = VueRouter.useRoute()
    const state = reactive({ report: null })

    const replay = computed(() => (state.report && state.report.replay) || {})
    const advice = computed(() => (state.report && state.report.strategy_advice) || {})
    const profile = computed(() => (state.report && state.report.opponent_profile) || {})
    const decisionReview = computed(() => (state.report && state.report.decision_review) || [])

    function ratingType(rating) {
      if (rating === 'good') return 'success'
      if (rating === 'questionable') return 'warning'
      if (rating === 'mistake') return 'danger'
      return 'info'
    }

    onMounted(async () => {
      state.report = await getAnalysis(String(route.params.id))
    })

    return { state, replay, advice, profile, decisionReview, ratingType }
  },
  template: `
    <div v-if="state.report">
      <el-card class="page-card">
        <div class="detail-head">
          <h1 class="page-title">分析报告：{{ state.report.battle_tag }}</h1>
          <el-button size="small" @click="$router.push('/analysis')">返回列表</el-button>
        </div>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="分析 ID">{{ state.report.analysis_id }}</el-descriptions-item>
          <el-descriptions-item label="时间">{{ state.report.created_at }}</el-descriptions-item>
          <el-descriptions-item label="深度">{{ state.report.depth }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card class="page-card">
        <template #header>对局摘要</template>
        <div class="summary-text">{{ replay.summary || '（无）' }}</div>
        <div v-if="replay.key_turns && replay.key_turns.length" style="margin-top: 8px">
          <el-tag v-for="t in replay.key_turns" :key="t" type="warning" style="margin-right: 6px">回合 {{ t }}</el-tag>
        </div>
      </el-card>

      <el-card class="page-card">
        <template #header>策略建议</template>
        <div class="advice-block">
          <div class="advice-title">总评</div>
          <div>{{ advice.summary || '（无）' }}</div>
        </div>
        <div class="advice-block">
          <div class="advice-title">选出评估</div>
          <div>{{ advice.team_selection_assessment || '（无）' }}</div>
        </div>
        <div class="advice-block">
          <div class="advice-title">首发分析</div>
          <div>{{ advice.lead_analysis || '（无）' }}</div>
        </div>
        <div class="advice-block">
          <div class="advice-title">关键回合替代方案</div>
          <ul>
            <li v-for="(item, i) in advice.key_turn_alternatives || []" :key="i">{{ item }}</li>
          </ul>
        </div>
        <div class="advice-block">
          <div class="advice-title">下局针对建议</div>
          <ul>
            <li v-for="(item, i) in advice.opponent_adjustments || []" :key="i">{{ item }}</li>
          </ul>
        </div>
        <div class="advice-block" v-if="advice.team_builder_feedback">
          <div class="advice-title">建队反馈</div>
          <div>{{ advice.team_builder_feedback }}</div>
        </div>
      </el-card>

      <el-card class="page-card">
        <template #header>逐回合决策评估</template>
        <el-table :data="decisionReview" border size="small">
          <el-table-column prop="turn" label="回合" width="70" align="center" />
          <el-table-column prop="order_message" label="决策" min-width="170" show-overflow-tooltip />
          <el-table-column label="评分" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="ratingType(row.rating)" size="small">{{ row.rating_zh || row.rating }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="comment" label="点评" min-width="220" show-overflow-tooltip />
          <el-table-column prop="alternative" label="更优选择" min-width="180" show-overflow-tooltip />
          <el-table-column prop="source" label="来源" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="row.source === 'llm' ? 'success' : 'info'" size="small" effect="plain">
                {{ row.source === 'llm' ? 'LLM' : '规则' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card class="page-card">
        <template #header>对手画像</template>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="风格">{{ profile.style || '-' }}</el-descriptions-item>
          <el-descriptions-item label="换人率">{{ profile.switch_rate != null ? profile.switch_rate : '-' }}</el-descriptions-item>
          <el-descriptions-item label="太晶使用">{{ profile.tera_used ? '是' : '否' }}</el-descriptions-item>
          <el-descriptions-item label="我方击倒数">{{ profile.our_kos != null ? profile.our_kos : '-' }}</el-descriptions-item>
          <el-descriptions-item label="对手击倒数">{{ profile.opponent_kos != null ? profile.opponent_kos : '-' }}</el-descriptions-item>
          <el-descriptions-item label="暴露宝可梦">
            {{ (profile.revealed_pokemon || []).join('、') || '-' }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card class="page-card">
        <template #header>回放时间线</template>
        <el-timeline>
          <el-timeline-item
            v-for="(event, i) in replay.events || []"
            :key="i"
            :type="event.kind === 'ko' ? 'danger' : 'primary'"
            :timestamp="'回合 ' + event.turn"
          >
            <b>{{ event.player }}</b> · {{ event.kind }} — {{ event.detail }}
          </el-timeline-item>
        </el-timeline>
      </el-card>
    </div>
  `,
}
