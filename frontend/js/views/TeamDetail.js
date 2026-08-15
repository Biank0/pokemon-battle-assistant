const { reactive, onMounted } = Vue
import { getTeam } from '../api.js'

export default {
  setup() {
    const route = VueRouter.useRoute()
    const state = reactive({ template: null })

    onMounted(async () => {
      state.template = await getTeam(String(route.params.name))
    })

    return { state }
  },
  template: `
    <div>
      <el-card class="page-card">
        <div class="detail-head">
          <h1 class="page-title">{{ $route.params.name }}</h1>
          <div>
            <el-tag v-if="state.template && state.template.format" type="info">{{ state.template.format }}</el-tag>
            <el-button size="small" style="margin-left: 12px" @click="$router.back()">返回</el-button>
          </div>
        </div>
      </el-card>

      <el-row :gutter="16" v-if="state.template">
        <el-col :span="8" v-for="member in state.template.team" :key="member.species">
          <PokemonCard :member="member" />
        </el-col>
      </el-row>

      <el-card class="page-card" v-if="state.template">
        <template #header>原始 JSON（Showdown 模板）</template>
        <pre class="mono raw-json">{{ JSON.stringify(state.template, null, 2) }}</pre>
      </el-card>
    </div>
  `,
}
