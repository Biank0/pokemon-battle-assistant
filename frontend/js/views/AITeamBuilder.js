const { reactive, onMounted } = Vue
import { generateTeam, iterateTeam, getBuilderHistory, getFormats } from '../api.js'

export default {
  setup() {
    const state = reactive({
      requirement: '快攻队：先手压制，高速高攻，配优先度招式',
      format: 'gen9bssregi',
      formats: [],
      generating: false,
      result: null,
      history: [],
    })

    async function refreshHistory() {
      state.history = await getBuilderHistory()
    }

    async function onGenerate() {
      if (!state.requirement.trim()) {
        ElementPlus.ElMessage.warning('请先输入需求描述')
        return
      }
      state.generating = true
      try {
        state.result = await generateTeam(state.requirement, state.format)
        await refreshHistory()
        if (state.result.valid) ElementPlus.ElMessage.success('队伍已生成且通过校验')
      } finally {
        state.generating = false
      }
    }

    async function onIterate() {
      if (!state.result || !state.result.team) return
      state.generating = true
      try {
        state.result = await iterateTeam(
          state.result.team,
          { feedback: '上一轮队伍在实战中暴露的问题：请优化属性覆盖与速度线' },
          state.format,
        )
        await refreshHistory()
        ElementPlus.ElMessage.success('迭代完成（第 ' + state.result.iteration + ' 轮）')
      } finally {
        state.generating = false
      }
    }

    function goLab() {
      const name = state.result && state.result.team ? state.result.team.name : ''
      if (name) this.$router.push('/lab?team=' + encodeURIComponent(name))
    }

    onMounted(async () => {
      state.formats = await getFormats()
      await refreshHistory()
    })

    return { state, onGenerate, onIterate, goLab }
  },
  template: `
    <div>
      <el-card class="page-card">
        <h1 class="page-title">AI 建队</h1>
        <p class="page-desc">描述你的战术需求（风格 / 核心宝可梦 / 克制目标），LLM 生成一支规则合法的队伍并给出建队理由。</p>
        <el-form label-width="90px">
          <el-form-item label="对战格式">
            <el-select v-model="state.format" style="width: 320px">
              <el-option v-for="f in state.formats" :key="f.id" :label="f.name" :value="f.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="需求描述">
            <el-input
              v-model="state.requirement"
              type="textarea"
              :rows="3"
              maxlength="500"
              show-word-limit
              placeholder="示例：以喷火龙为核心构筑 Balanced 队伍，能对抗雨天队和鞭炮队，需要一只 Stealth Rock 铺钉手"
            />
          </el-form-item>
          <el-form-item label="快捷风格">
            <el-radio-group v-model="state.requirement" @change="onGenerate">
              <el-radio-button value="快攻队：先手压制，高速高攻，配优先度招式">快攻</el-radio-button>
              <el-radio-button value="平衡队：攻防兼备，有回复和换挡能力">平衡</el-radio-button>
              <el-radio-button value="受队：高耐久消耗，剧毒+护盾+回复">耐久</el-radio-button>
              <el-radio-button value="天气队：围绕晴天/雨天核心构筑">天气</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="state.generating" @click="onGenerate">
              {{ state.generating ? '生成中…' : '生成队伍' }}
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <el-card class="page-card" v-if="state.result">
        <template #header>
          <div class="result-head">
            <span>生成结果（第 {{ state.result.iteration }} 轮）</span>
            <span>
              <el-tag :type="state.result.valid ? 'success' : 'danger'">
                {{ state.result.valid ? '校验通过' : '校验未通过' }}
              </el-tag>
              <el-button size="small" style="margin-left: 10px" @click="onIterate" :loading="state.generating">
                基于反馈迭代
              </el-button>
              <el-button size="small" type="primary" :disabled="!(state.result.team && state.result.team.name)" @click="goLab">
                送实验室跑量
              </el-button>
            </span>
          </div>
        </template>

        <el-alert
          v-if="!state.result.valid && state.result.validation_errors.length"
          type="error"
          :closable="false"
          class="page-card"
        >
          <div v-for="e in state.result.validation_errors" :key="e">❌ {{ e }}</div>
        </el-alert>

        <el-row :gutter="16">
          <el-col :span="8" v-for="member in (state.result.team && state.result.team.team) || []" :key="member.species">
            <PokemonCard :member="member" />
          </el-col>
        </el-row>

        <el-collapse>
          <el-collapse-item title="建队理由（LLM Reasoning）">
            <div class="reasoning">{{ state.result.reasoning || '（无）' }}</div>
          </el-collapse-item>
        </el-collapse>
      </el-card>

      <el-card class="page-card">
        <template #header>建队历史</template>
        <el-table :data="state.history" border size="small">
          <el-table-column prop="created_at" label="时间" width="170" />
          <el-table-column prop="action" label="动作" width="90" />
          <el-table-column prop="requirement" label="需求" min-width="220" show-overflow-tooltip />
          <el-table-column prop="format" label="格式" width="150" />
          <el-table-column label="合法" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="row.valid ? 'success' : 'danger'" size="small">{{ row.valid ? '是' : '否' }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  `,
}
