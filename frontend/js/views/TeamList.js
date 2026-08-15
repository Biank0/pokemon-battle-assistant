const { reactive, onMounted } = Vue
import { listTeams, deleteTeam, validateTeam } from '../api.js'

export default {
  setup() {
    const state = reactive({
      teams: [],
      loading: false,
      validateVisible: false,
      validateName: '',
      validation: null,
    })

    async function refresh() {
      state.loading = true
      try {
        state.teams = await listTeams()
      } finally {
        state.loading = false
      }
    }

    async function onValidate(name) {
      state.validateName = name
      state.validation = await validateTeam(name)
      state.validateVisible = true
    }

    async function onDelete(name) {
      try {
        await ElementPlus.ElMessageBox.confirm(
          '确定删除队伍「' + name + '」？该操作不可恢复。',
          '删除确认',
          { type: 'warning' },
        )
      } catch {
        return
      }
      await deleteTeam(name)
      ElementPlus.ElMessage.success('已删除：' + name)
      await refresh()
    }

    onMounted(refresh)
    return { state, onValidate, onDelete }
  },
  template: `
    <div>
      <el-card class="page-card">
        <h1 class="page-title">队伍管理</h1>
        <p class="page-desc">已保存的训练家队伍模板（data/trainers），可校验合法性后用于对战 / 实验。</p>
      </el-card>

      <el-table :data="state.teams" v-loading="state.loading" border stripe>
        <el-table-column prop="name" label="队伍名" min-width="140">
          <template #default="{ row }">
            <el-link type="primary" @click="$router.push('/team/' + row.name)">{{ row.name }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="format" label="格式" width="170" />
        <el-table-column prop="pokemon_count" label="宝可梦数量" width="110" align="center" />
        <el-table-column label="操作" width="240" align="center">
          <template #default="{ row }">
            <el-button size="small" @click="onValidate(row.name)">校验</el-button>
            <el-button size="small" type="primary" @click="$router.push('/battle?team=' + row.name)">去对战</el-button>
            <el-button size="small" type="danger" @click="onDelete(row.name)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-dialog v-model="state.validateVisible" :title="'校验结果：' + state.validateName" width="520px">
        <div v-if="state.validation">
          <el-tag :type="state.validation.ok ? 'success' : 'danger'" size="large">
            {{ state.validation.ok ? '本地校验通过' : '存在错误' }}
          </el-tag>
          <div v-if="state.validation.errors.length" class="validate-block">
            <div v-for="e in state.validation.errors" :key="e" class="validate-error">❌ {{ e }}</div>
          </div>
          <div v-if="state.validation.warnings.length" class="validate-block">
            <div v-for="w in state.validation.warnings" :key="w" class="validate-warn">⚠️ {{ w }}</div>
          </div>
        </div>
      </el-dialog>
    </div>
  `,
}
