const { reactive, computed, onMounted } = Vue
import { getTeam } from '../api.js'

export default {
  setup() {
    const route = VueRouter.useRoute()
    const state = reactive({ data: null })

    // 把中文摘要（team_zh）合并进原模板成员，PokemonCard 优先显示中文字段
    const members = computed(() => {
      if (!state.data || !state.data.team) return []
      const team = state.data.team.team || []
      const zh = state.data.team_zh || []
      return team.map((m, i) => ({ ...m, ...(zh[i] || {}) }))
    })

    onMounted(async () => {
      state.data = await getTeam(String(route.params.name))
    })

    return { state, members }
  },
  template: `
    <div>
      <el-card class="page-card">
        <div class="detail-head">
          <h1 class="page-title">{{ (state.data && state.data.display_name) || $route.params.name }}</h1>
          <div>
            <el-tag v-if="state.data && state.data.team && state.data.team.format" type="info">{{ state.data.team.format }}</el-tag>
            <el-button size="small" style="margin-left: 12px" @click="$router.back()">返回</el-button>
          </div>
        </div>
      </el-card>

      <el-row :gutter="16" v-if="members.length">
        <el-col :span="8" v-for="member in members" :key="member.species">
          <PokemonCard :member="member" />
        </el-col>
      </el-row>

      <el-card class="page-card" v-if="state.data && state.data.team">
        <template #header>原始 JSON（Showdown 模板）</template>
        <pre class="mono raw-json">{{ JSON.stringify(state.data.team, null, 2) }}</pre>
      </el-card>
    </div>
  `,
}
