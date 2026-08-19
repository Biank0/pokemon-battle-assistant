/* 队伍库：列表 + 筛选 */
const TeamsView = {
  template: `
  <div>
    <h2 class="page-title">队伍库</h2>
    <p class="page-desc">共 {{ filtered.length }} 支队伍</p>

    <div class="block">
      <el-input v-model="kw" placeholder="按中文名 / 文件 ID / 需求筛选" clearable
                style="max-width: 320px; margin-bottom: 14px"></el-input>
      <el-table :data="filtered" v-loading="loading" @row-click="open"
                class="teams-table" :header-cell-style="{ background: '#fafafa' }">
        <el-table-column prop="display_name" label="队伍" min-width="160">
          <template #default="{ row }">
            <span class="team-name">{{ row.display_name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="文件 ID" min-width="140">
          <template #default="{ row }"><span class="mono">{{ row.name }}</span></template>
        </el-table-column>
        <el-table-column prop="format_zh" label="赛制" min-width="130"></el-table-column>
        <el-table-column label="来源" width="90">
          <template #default="{ row }">
            <el-tag :type="row.source === 'ai' ? 'success' : 'info'" size="small" effect="plain">
              {{ row.source_zh }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="requirement_prompt" label="建队需求" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.requirement_prompt || '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }"><span class="mono">{{ fmt(row.created_at) }}</span></template>
        </el-table-column>
      </el-table>
    </div>
  </div>`,
  data() { return { teams: [], loading: false, kw: "" }; },
  computed: {
    filtered() {
      const k = this.kw.trim().toLowerCase();
      if (!k) return this.teams;
      return this.teams.filter(t =>
        [t.display_name, t.name, t.requirement_prompt || ""]
          .some(v => String(v).toLowerCase().includes(k)));
    },
  },
  async mounted() {
    this.loading = true;
    try { this.teams = await API.get("/api/teams"); }
    catch (e) { this.$message.error(String(e.message || e)); }
    finally { this.loading = false; }
  },
  methods: {
    open(row) { this.$router.push(`/teams/${row.name}`); },
    fmt(iso) { return (iso || "").replace("T", " ").slice(0, 16); },
  },
};
