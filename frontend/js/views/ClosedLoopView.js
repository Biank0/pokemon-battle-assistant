const { reactive, computed, onMounted, onBeforeUnmount } = Vue
import { listTeams, getFormats, startLoop, getLoopStatus, getLoopHistory, confirmIteration } from '../api.js'

export default {
  setup() {
    const state = reactive({
      teams: [],
      formats: [],
      form: {
        requirement: '构筑一支能稳定对抗天气队的平衡队伍，速度线不低于 100',
        opponents: [],
        iterations: 3,
        battles: 3,
        auto: true,
        format: 'gen9bssregi',
        backend: '',
      },
      stopWinRatePct: 70,
      starting: false,
      confirming: false,
      runId: '',
      status: null,
      iterations: [],
      teamVisible: null,
    })
    let timer = undefined

    const teamDialogVisible = computed({
      get: () => state.teamVisible != null,
      set: (v) => {
        if (!v) state.teamVisible = null
      },
    })

    function progressColor(rate) {
      if (rate >= 0.6) return '#67c23a'
      if (rate >= 0.4) return '#e6a23c'
      return '#f56c6c'
    }

    function stateTagType(s) {
      if (s === 'completed') return 'success'
      if (s === 'running') return 'warning'
      if (s === 'error') return 'danger'
      return 'info'
    }

    function stateLabel(s) {
      const map = { running: '运行中', waiting_confirm: '等待确认', completed: '已完成', error: '出错' }
      return map[s] || s
    }

    function iterationDesc(i) {
      const record = state.iterations.find((it) => it.iteration === i)
      if (!record) {
        return i <= (state.status ? state.status.current_iteration : 0) ? '进行中' : '待开始'
      }
      if (record.win_rate != null) return '胜率 ' + Math.round(record.win_rate * 100) + '%'
      return record.error ? '失败' : '已完成'
    }

    const stepsActive = computed(() => {
      if (!state.status) return 0
      if (state.status.state === 'completed') return state.status.max_iterations
      return state.status.current_iteration
    })

    async function refreshStatus() {
      if (!state.runId) return
      try {
        state.status = await getLoopStatus(state.runId)
        state.iterations = await getLoopHistory(state.runId)
        if (state.status.state === 'completed') ElementPlus.ElMessage.success('闭环流程已完成')
      } catch {
        /* ignore poll errors */
      }
    }

    function schedulePoll() {
      timer = window.setTimeout(async () => {
        await refreshStatus()
        const s = state.status ? state.status.state : ''
        if (s === 'running' || s === 'waiting_confirm') schedulePoll()
      }, 5000)
    }

    async function onStart() {
      if (!state.form.requirement.trim()) {
        ElementPlus.ElMessage.warning('请输入需求描述')
        return
      }
      state.starting = true
      try {
        const resp = await startLoop({
          requirement: state.form.requirement,
          opponents: state.form.opponents,
          iterations: state.form.iterations,
          auto: state.form.auto,
          battles: state.form.battles,
          format: state.form.format,
          concurrency: 2,
          backend: state.form.backend || null,
          stop_win_rate: state.stopWinRatePct > 0 ? state.stopWinRatePct / 100 : null,
        })
        state.runId = resp.run_id
        state.status = null
        state.iterations = []
        ElementPlus.ElMessage.success('闭环已启动：' + resp.run_id)
        await refreshStatus()
        schedulePoll()
      } finally {
        state.starting = false
      }
    }

    async function onConfirm() {
      if (!state.runId) return
      state.confirming = true
      try {
        state.status = await confirmIteration(state.runId)
        ElementPlus.ElMessage.success('已确认，继续下一轮')
        schedulePoll()
      } finally {
        state.confirming = false
      }
    }

    onMounted(async () => {
      state.teams = await listTeams()
      state.formats = await getFormats()
    })
    onBeforeUnmount(() => {
      if (timer) window.clearTimeout(timer)
    })

    return {
      state, teamDialogVisible, stepsActive,
      progressColor, stateTagType, stateLabel, iterationDesc, onStart, onConfirm,
    }
  },
  template: `
    <div>
      <el-card class="page-card">
        <h1 class="page-title">闭环流程</h1>
        <p class="page-desc">一条龙：AI 建队 → 批量跑量 → 深度复盘 → 迭代优化。自动迭代或每轮确认后继续，追求目标胜率。</p>
        <el-form label-width="110px">
          <el-form-item label="需求描述">
            <el-input
              v-model="state.form.requirement"
              type="textarea"
              :rows="2"
              placeholder="例如：构筑一支能稳定对抗雨天队的平衡队，速度线不低于 100"
            />
          </el-form-item>
          <el-row :gutter="24">
            <el-col :span="10">
              <el-form-item label="对手列表">
                <el-select v-model="state.form.opponents" multiple filterable>
                  <el-option v-for="t in state.teams" :key="t.name" :label="t.display_name || t.name" :value="t.name" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="4">
              <el-form-item label="迭代轮数">
                <el-input-number v-model="state.form.iterations" :min="1" :max="6" />
              </el-form-item>
            </el-col>
            <el-col :span="5">
              <el-form-item label="每对手局数">
                <el-input-number v-model="state.form.battles" :min="1" :max="10" />
              </el-form-item>
            </el-col>
            <el-col :span="5">
              <el-form-item label="自动迭代">
                <el-switch v-model="state.form.auto" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="24">
            <el-col :span="6">
              <el-form-item label="对战格式">
                <el-select v-model="state.form.format">
                  <el-option v-for="f in state.formats" :key="f.id" :label="f.name" :value="f.id" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="LLM 后端">
                <el-select v-model="state.form.backend" clearable placeholder="默认（.env 配置）">
                  <el-option label="OpenAI" value="openai" />
                  <el-option label="Ollama（本地）" value="ollama" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="目标胜率(%)">
                <el-input-number v-model="state.stopWinRatePct" :min="0" :max="100" :step="5" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label=" ">
                <el-button type="primary" :loading="state.starting" @click="onStart">启动闭环</el-button>
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </el-card>

      <el-card class="page-card" v-if="state.status">
        <template #header>
          <div class="status-head">
            <span>运行状态：{{ state.status.run_id }}</span>
            <span>
              <el-tag :type="stateTagType(state.status.state)">{{ stateLabel(state.status.state) }}</el-tag>
              <el-button
                v-if="state.status.state === 'waiting_confirm'"
                type="primary"
                size="small"
                style="margin-left: 10px"
                :loading="state.confirming"
                @click="onConfirm"
              >
                确认进入下一轮
              </el-button>
            </span>
          </div>
        </template>
        <el-steps :active="stepsActive" align-center class="page-card" finish-status="success">
          <el-step
            v-for="i in state.status.max_iterations"
            :key="i"
            :title="'第 ' + i + ' 轮'"
            :description="iterationDesc(i)"
          />
        </el-steps>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="需求">{{ state.status.requirement }}</el-descriptions-item>
          <el-descriptions-item label="最佳轮次">{{ state.status.best_iteration || '-' }}</el-descriptions-item>
          <el-descriptions-item label="最佳胜率">
            {{ state.status.best_win_rate != null ? Math.round(state.status.best_win_rate * 100) + '%' : '-' }}
          </el-descriptions-item>
        </el-descriptions>
        <el-alert v-if="state.status.message" :closable="false" class="page-card">{{ state.status.message }}</el-alert>
      </el-card>

      <el-card class="page-card" v-if="state.iterations.length">
        <template #header>迭代历史</template>
        <el-table :data="state.iterations" border>
          <el-table-column prop="iteration" label="轮次" width="70" align="center" />
          <el-table-column label="胜率" width="160">
            <template #default="{ row }">
              <el-progress
                v-if="row.win_rate != null"
                :percentage="Math.round(row.win_rate * 100)"
                :stroke-width="14"
                :color="progressColor(row.win_rate)"
              />
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="战绩" width="110" align="center">
            <template #default="{ row }">{{ row.wins }}W / {{ row.total_battles }}局</template>
          </el-table-column>
          <el-table-column label="合法" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="row.valid ? 'success' : 'danger'" size="small">{{ row.valid ? '是' : '否' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="advice_summary" label="复盘总评" min-width="240" show-overflow-tooltip />
          <el-table-column label="建队反馈" min-width="240">
            <template #default="{ row }">
              <div v-for="(fb, i) in row.team_builder_feedback || []" :key="i">· {{ fb }}</div>
            </template>
          </el-table-column>
          <el-table-column label="队伍" width="90" align="center">
            <template #default="{ row }">
              <el-button size="small" link type="primary" @click="state.teamVisible = row">查看</el-button>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="时间" width="170" />
        </el-table>
      </el-card>

      <el-dialog v-model="teamDialogVisible" :title="'第 ' + (state.teamVisible ? state.teamVisible.iteration : '') + ' 轮队伍'" width="900px">
        <el-row v-if="state.teamVisible" :gutter="12">
          <el-col :span="8" v-for="member in (state.teamVisible.team && state.teamVisible.team.team) || []" :key="member.species">
            <PokemonCard :member="member" />
          </el-col>
        </el-row>
      </el-dialog>
    </div>
  `,
}
