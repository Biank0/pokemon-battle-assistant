const { reactive, computed, onMounted, onBeforeUnmount } = Vue
import { listTeams, getFormats, startBattle, getBattleStatus, getBattleResult } from '../api.js'

export default {
  setup() {
    const route = VueRouter.useRoute()
    const state = reactive({
      teams: [],
      formats: [],
      form: {
        template: (route.query.team || ''),
        opponent: '',
        format: 'gen9bssregi',
        opponent_control: 'random',
        backend: '',
      },
      starting: false,
      jobId: '',
      jobStatus: '',
      jobError: null,
      polling: false,
      battleResult: null,
    })
    let timer = undefined

    const stepActive = computed(() => {
      if (state.jobStatus === 'done') return 3
      if (state.jobStatus === 'running') return 2
      return 1
    })
    const statusTagType = computed(() => {
      if (state.jobStatus === 'done') return 'success'
      if (state.jobStatus === 'error') return 'danger'
      return 'warning'
    })

    async function onStart() {
      if (!state.form.template) {
        ElementPlus.ElMessage.warning('请选择己方队伍')
        return
      }
      state.starting = true
      state.battleResult = null
      state.jobError = null
      try {
        const job = await startBattle({
          template: state.form.template,
          opponent: state.form.opponent || null,
          format: state.form.format,
          opponent_control: state.form.opponent_control,
          backend: state.form.backend || null,
        })
        state.jobId = job.job_id
        state.jobStatus = job.status
        state.polling = true
        poll()
      } finally {
        state.starting = false
      }
    }

    function poll() {
      timer = window.setTimeout(async () => {
        try {
          const job = await getBattleStatus(state.jobId)
          state.jobStatus = job.status
          state.jobError = job.error
          if (job.status === 'done') {
            state.polling = false
            state.battleResult = await getBattleResult(state.jobId)
            ElementPlus.ElMessage.success('对战完成')
            return
          }
          if (job.status === 'error') {
            state.polling = false
            return
          }
        } catch {
          state.polling = false
          return
        }
        poll()
      }, 2500)
    }

    function goAnalysis(tag) {
      VueRouter.useRouter().push('/analysis?tag=' + encodeURIComponent(tag))
    }

    function teamLabel(team) {
      return team.display_name || team.name
    }

    onMounted(async () => {
      state.teams = await listTeams()
      state.formats = await getFormats()
      if (!state.form.template && state.teams.length) {
        state.form.template = state.teams[0].name
      }
    })
    onBeforeUnmount(() => {
      if (timer) window.clearTimeout(timer)
    })

    return { state, stepActive, statusTagType, onStart, goAnalysis, teamLabel }
  },
  template: `
    <div>
      <el-card class="page-card">
        <h1 class="page-title">对战面板</h1>
        <p class="page-desc">选择己方队伍与对手，后台运行一局 Agent 对战（Showdown），完成后展示结果与记录文件。</p>
        <el-form label-width="100px">
          <el-row :gutter="24">
            <el-col :span="8">
              <el-form-item label="己方队伍">
                <el-select v-model="state.form.template" filterable placeholder="选择队伍">
                  <el-option v-for="t in state.teams" :key="t.name" :label="teamLabel(t)" :value="t.name" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="对手队伍">
                <el-select v-model="state.form.opponent" filterable clearable placeholder="留空=镜像对战">
                  <el-option v-for="t in state.teams" :key="t.name" :label="teamLabel(t)" :value="t.name" />
                </el-select>
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
              <el-form-item label="对手控制">
                <el-select v-model="state.form.opponent_control">
                  <el-option label="随机出招" value="random" />
                  <el-option label="最强出招" value="strongest" />
                </el-select>
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
                <el-button type="primary" :loading="state.starting" @click="onStart">开始对战</el-button>
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </el-card>

      <el-card class="page-card" v-if="state.jobId">
        <template #header>对战任务</template>
        <el-steps :active="stepActive" align-center finish-status="success" class="page-card">
          <el-step title="已提交" />
          <el-step title="对战中" />
          <el-step :title="state.jobStatus === 'error' ? '失败' : '完成'" />
        </el-steps>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="Job ID">{{ state.jobId }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagType">{{ state.jobStatus }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="轮询">{{ state.polling ? '进行中' : '已停止' }}</el-descriptions-item>
        </el-descriptions>
        <el-alert v-if="state.jobError" type="error" :closable="false" class="page-card">{{ state.jobError }}</el-alert>
      </el-card>

      <el-card class="page-card" v-if="state.battleResult">
        <template #header>对战结果</template>
        <el-result
          :icon="state.battleResult.won ? 'success' : 'error'"
          :title="state.battleResult.won ? '胜利！' : '惜败'"
          :sub-title="'battle_tag: ' + (state.battleResult.battle_tag || '-') + ' ｜ 回合数: ' + (state.battleResult.turns != null ? state.battleResult.turns : '-')"
        />
        <div class="turn-actions">
          <el-button v-if="state.battleResult.battle_tag" type="primary" @click="goAnalysis(state.battleResult.battle_tag)">
            深度复盘这场对战
          </el-button>
        </div>
      </el-card>

      <el-card class="page-card" v-if="state.battleResult && state.battleResult.turn_log && state.battleResult.turn_log.length">
        <template #header>逐回合出招明细</template>
        <div class="turn-log">
          <el-timeline>
            <el-timeline-item
              v-for="(item, i) in state.battleResult.turn_log"
              :key="i"
              :timestamp="'回合 ' + (item.turn != null ? item.turn : '-')"
              :type="item.side === '己方' ? 'primary' : 'warning'"
              :hollow="item.side !== '己方'"
            >
              <span class="turn-side">{{ item.side }}</span>
              <span class="turn-kind">{{ item.kind_zh }}</span>
              <span class="turn-label">{{ item.label_zh }}</span>
              <span
                v-if="item.active_zh || item.opponent_active_zh"
                class="turn-active"
              >出场：{{ item.active_zh || '-' }} vs {{ item.opponent_active_zh || '-' }}</span>
            </el-timeline-item>
          </el-timeline>
        </div>
      </el-card>

      <el-card class="page-card" v-if="state.battleResult">
        <template #header>记录文件</template>
        <el-descriptions :column="1" border>
          <el-descriptions-item v-for="(path, key) in state.battleResult.files" :key="key" :label="String(key)">
            <span class="mono">{{ path }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
    </div>
  `,
}
