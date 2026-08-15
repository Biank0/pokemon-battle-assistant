const { reactive, onMounted } = Vue
import { analyzeBattle, listAnalyses } from '../api.js'

export default {
  setup() {
    const route = VueRouter.useRoute()
    const state = reactive({
      battleTag: (route.query.tag || ''),
      depth: 'full',
      analyzing: false,
      analyses: [],
    })

    async function refresh() {
      state.analyses = await listAnalyses()
    }

    async function onAnalyze() {
      if (!state.battleTag.trim()) {
        ElementPlus.ElMessage.warning('请输入 battle_tag')
        return
      }
      state.analyzing = true
      try {
        const report = await analyzeBattle(state.battleTag.trim(), state.depth)
        ElementPlus.ElMessage.success('分析完成')
        await refresh()
        if (report.analysis_id) {
          VueRouter.useRouter().push('/analysis/' + report.analysis_id)
        }
      } finally {
        state.analyzing = false
      }
    }

    onMounted(refresh)
    return { state, onAnalyze }
  },
  template: `
    <div>
      <el-card class="page-card">
        <h1 class="page-title">分析报告</h1>
        <p class="page-desc">输入 battle_tag 对一局对战做深度复盘：回放时间线 + 逐回合评分 + 策略建议 + 对手画像。</p>
        <el-form inline>
          <el-form-item label="battle_tag">
            <el-input v-model="state.battleTag" placeholder="例如 battle-gen9bssregi-1" style="width: 320px" />
          </el-form-item>
          <el-form-item label="深度">
            <el-select v-model="state.depth" style="width: 130px">
              <el-option label="完整" value="full" />
              <el-option label="快速" value="quick" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="state.analyzing" @click="onAnalyze">开始分析</el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <el-card class="page-card">
        <template #header>已完成分析（本次服务会话内）</template>
        <el-table :data="state.analyses" border size="small">
          <el-table-column prop="created_at" label="时间" width="180" />
          <el-table-column prop="battle_tag" label="battle_tag" min-width="220" />
          <el-table-column prop="depth" label="深度" width="90" />
          <el-table-column label="操作" width="110" align="center">
            <template #default="{ row }">
              <el-button size="small" type="primary" link @click="$router.push('/analysis/' + row.analysis_id)">
                查看报告
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  `,
}
