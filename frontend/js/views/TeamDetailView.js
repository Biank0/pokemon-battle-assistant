/* 队伍详情：信息头 + 六张宝可梦卡片 + Showdown 导出串 */
const TeamDetailView = {
  components: { PokemonCard },
  props: { name: { type: String, required: true } },
  template: `
  <div v-loading="loading">
    <el-page-header content="队伍详情" @back="$router.back()" class="back"></el-page-header>

    <template v-if="team">
      <div class="block head-block">
        <div class="head-row">
          <h2 class="head-name">{{ team.display_name }}</h2>
          <el-tag size="small" effect="plain">{{ team.format_zh }}</el-tag>
          <el-tag :type="team.source === 'ai' ? 'success' : 'info'" size="small" effect="plain">
            {{ team.source_zh }}
          </el-tag>
        </div>
        <div class="head-meta mono">{{ team.name }} ｜ 创建于 {{ fmt(team.created_at) }}
          <template v-if="team.skill_version"> ｜ skill {{ team.skill_version }} / {{ team.model }}</template>
        </div>
        <el-alert v-if="team.requirement_prompt" type="info" :closable="false" class="head-req"
                  :title="'建队需求'" :description="team.requirement_prompt" show-icon></el-alert>
      </div>

      <div class="pc-grid">
        <pokemon-card v-for="m in team.members" :key="m.slot" :member="m"></pokemon-card>
      </div>

      <div class="block" style="margin-top: 16px">
        <el-collapse>
          <el-collapse-item title="Showdown 导出串（可直接导入对战）">
            <pre class="export-pre">{{ team.export_text }}</pre>
          </el-collapse-item>
        </el-collapse>
      </div>
    </template>

    <el-empty v-else-if="!loading" description="队伍不存在"></el-empty>
  </div>`,
  data() { return { team: null, loading: false }; },
  async mounted() {
    this.loading = true;
    try { this.team = await API.get(`/api/teams/${encodeURIComponent(this.name)}`); }
    catch (e) { this.$message.error(String(e.message || e)); }
    finally { this.loading = false; }
  },
  methods: {
    fmt(iso) { return (iso || "").replace("T", " ").slice(0, 16); },
  },
};
