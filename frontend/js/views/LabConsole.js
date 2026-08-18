const { reactive, computed, onMounted, onBeforeUnmount } = Vue
import { listTeams, getFormats, startLab, getLabStatus, getLabReport } from '../api.js'

export default {
  setup() {
    const route = VueRouter.useRoute()
    const state = reactive({
      teams: [],
      formats: [],
      form: {
        team: (route.query.team || ''),
        battles_per_opponent: 3,
        format: 'gen9bssregi',
        concurrency: 2,
        backend: '',
      },
      starting: false,
      jobId: '',
      jobStatus: '',
      jobError: null,
      report: null,
    })
    let timer = undefined

    const stats = computed(() => (state.report && state.report.stats) || {})
    const results = computed(() => (state.report && state.report.results) || [])

    // 预设对手 = lab 目录全部队伍（排除己方），与后端缺省逻辑一致
    const presetOpponentCount = computed(() =>
      state.teams.filter(t => t.source === 'lab' && t.name !== state.form.team).length
    )

    function displayName(name) {
      const team = state.teams.find(t => t.name === name)
      return (team && team.display_name) || name
    }

    function progressColor(rate) {
      if (rate >= 0.6) return '#67c23a'
      if (rate >= 0.4) return '#e6a23c'
      return '#f56c6c'
    }

    async function onStart() {
      if (!state.form.team) {
        ElementPlus.ElMessage.warning('请选择己方队伍')
        return
      }
      if (presetOpponentCount.value < 1) {
        ElementPlus.ElMessage.warning('没有可用的预设对手队伍')
        return
      }
      state.starting = true
      state.report = null
      state.jobError = null
      try {
        const job = await startLab({
          team: state.form.team,
          opponents: null,
          battles_per_opponent: state.form.battles_per_opponent,
          format: state.form.format,
          concurrency: state.form.concurrency,
          backend: state.form.backend || null,
        })
        state.jobId = job.job_id
        state.jobStatus = job.status
        poll()
      } finally {
        state.starting = false
      }
    }

    function poll() {
      timer = window.setTimeout(async () => {
        try {
          const job = await getLabStatus(state.jobId)
          state.jobStatus = job.status
          state.jobError = job.error
          if (job.status === 'done') {
            state.report = await getLabReport(state.jobId)
            ElementPlus.ElMessage.success('实验完成')
            return
          }
          if (job.status === 'error') return
        } catch {
          return
        }
        poll()
      }, 4000)
    }

    onMounted(async () => {
      state.teams = await listTeams()
      state.formats = await getFormats()
      if (!state.form.team && state.teams.length) {
        state.form.team = state.teams[0].name
      }
    })
    onBeforeUnmount(() => {
      if (timer) window.clearTimeout(timer)
    })

    return { state, stats, results, presetOpponentCount, displayName, progressColor, onStart }
  },
  template: `
    <div>
      <el-card class="page-card">
        <h1 class="page-title">实验室控制台</h1>
        <p class="page-desc">
          自动与全部预设队伍（{{ presetOpponentCount }} 支）批量对战，统计胜率，不逐场检查细节。
          自建队伍放入 data/teams/lab/ 即可参与。
        </p>
        <el-form label-width="110px">
          <el-row :gutter="24">
            <el-col :span="8">
              <el-form-item label="己方队伍">
                <el-select v-model="state.form.team" filterable>
                  <el-option v-for="t in state.teams" :key="t.name" :label="t.display_name || t.name" :value="t.name" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="每对手局数">
                <el-input-number v-model="state.form.battles_per_opponent" :min="1" :max="20" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="对战格式">
                <el-select v-model="state.form.format">
                  <el-option v-for="f in state.formats" :key="f.id" :label="f.name" :value="f.id" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="24">
            <el-col :span="8">
              <el-form-item label="并发数">
                <el-input-number v-model="state.form.concurrency" :min="1" :max="8" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="LLM 后端">
                <el-select v-model="state.form.backend" clearable placeholder="默认（.env 配置）">
                  <el-option label="OpenAI" value="openai" />
                  <el-option label="Ollama（本地）" value="ollama" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label=" ">
                <el-button type="primary" :loading="state.starting" @click="onStart">开始批量实验</el-button>
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </el-card>

      <el-card class="page-card" v-if="state.jobId">
        <template #header>实验任务 {{ state.jobId }}</template>
        <el-descriptions :column="4" border>
          <el-descriptions-item label="状态">
            <el-tag :type="state.jobStatus === 'done' ? 'success' : state.jobStatus === 'error' ? 'danger' : 'warning'">
              {{ state.jobStatus }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ state.report ? (state.report.started_at || '-') : '-' }}</el-descriptions-item>
          <el-descriptions-item label="结束时间">{{ state.report ? (state.report.finished_at || '-') : '-' }}</el-descriptions-item>
          <el-descriptions-item label="总局数">{{ stats.total_battles != null ? stats.total_battles : '-' }}</el-descriptions-item>
        </el-descriptions>
        <el-alert v-if="state.jobError" type="error" :closable="false" class="page-card">{{ state.jobError }}</el-alert>
      </el-card>

      <el-card class="page-card" v-if="stats && stats.total_battles">
        <template #header>胜率统计</template>
        <el-row :gutter="16" class="page-card">
          <el-col :span="12">
            <div class="stat-label">
              总胜率（{{ stats.wins }}W / {{ stats.losses }}L / {{ stats.errors }}E）
            </div>
            <el-progress
              :percentage="Math.round((stats.win_rate || 0) * 100)"
              :stroke-width="22"
              :color="progressColor(stats.win_rate || 0)"
              text-inside
            />
            <div class="stat-sub">平均回合数：{{ stats.avg_turns != null ? stats.avg_turns : '-' }}</div>
          </el-col>
          <el-col :span="12">
            <div class="stat-label">分对手胜率</div>
            <div v-for="(data, opp) in stats.by_opponent" :key="opp" class="opp-row">
              <span class="opp-name">{{ displayName(opp) }}</span>
              <el-progress
                :percentage="Math.round((data.win_rate || 0) * 100)"
                :stroke-width="16"
                :color="progressColor(data.win_rate || 0)"
                class="opp-progress"
              />
              <span class="opp-record">{{ data.wins }}/{{ data.total }}</span>
            </div>
          </el-col>
        </el-row>

        <el-table :data="results" size="small">
          <el-table-column label="对手" min-width="140">
            <template #default="{ row }">{{ displayName(row.opponent) }}</template>
          </el-table-column>
          <el-table-column label="结果" width="90" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.error" type="info" size="small">错误</el-tag>
              <el-tag v-else :type="row.won ? 'success' : 'danger'" size="small">
                {{ row.won ? '胜' : '负' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="turns" label="回合数" width="90" align="center" />
        </el-table>
      </el-card>
    </div>
  `,
}
