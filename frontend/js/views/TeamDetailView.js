/* 队伍详情：信息头（含管理操作）+ 六张宝可梦卡片 + Showdown 导出串 */
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
          <span class="head-actions">
            <el-button size="small" @click="openEdit">调整队伍</el-button>
            <el-popconfirm title="确定删除这支队伍？历史对战记录会保留，但队伍配置不可恢复"
                           confirm-button-text="删除" confirm-button-type="danger"
                           cancel-button-text="取消" width="260"
                           @confirm="remove">
              <template #reference>
                <el-button size="small" type="danger" plain>删除队伍</el-button>
              </template>
            </el-popconfirm>
          </span>
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

    <el-dialog v-model="editDlg" title="调整队伍" width="640px" :close-on-click-modal="false">
      <el-form label-position="top">
        <el-form-item label="队伍名">
          <el-input v-model="editForm.display_name" maxlength="30" show-word-limit></el-input>
        </el-form-item>
        <el-form-item label="Showdown 导出串（整体替换 6 名成员，保存前会重新校验；赛制不变）">
          <el-input v-model="editForm.export_text" type="textarea" :rows="14" class="mono-area"></el-input>
        </el-form-item>
        <el-alert v-if="editErr" type="error" :closable="false" :title="editErr"
                  show-icon class="pre-line"></el-alert>
      </el-form>
      <template #footer>
        <el-button @click="editDlg = false">取消</el-button>
        <el-button type="primary" :loading="saving"
                   :disabled="!editForm.display_name.trim() || !editForm.export_text.trim()"
                   @click="saveEdit">校验并保存</el-button>
      </template>
    </el-dialog>
  </div>`,
  data() {
    return {
      team: null, loading: false,
      editDlg: false, saving: false, editErr: "",
      editForm: { display_name: "", export_text: "" },
    };
  },
  async mounted() {
    await this.load();
  },
  methods: {
    fmt(iso) { return (iso || "").replace("T", " ").slice(0, 16); },
    async load() {
      this.loading = true;
      try { this.team = await API.get(`/api/teams/${encodeURIComponent(this.name)}`); }
      catch (e) { this.$message.error(String(e.message || e)); }
      finally { this.loading = false; }
    },
    openEdit() {
      this.editErr = "";
      this.editForm = {
        display_name: this.team.display_name,
        export_text: this.team.export_text,
      };
      this.editDlg = true;
    },
    async saveEdit() {
      this.saving = true;
      this.editErr = "";
      try {
        await API.put(`/api/teams/${encodeURIComponent(this.name)}`, this.editForm);
        this.editDlg = false;
        this.$message.success("已保存");
        await this.load();
      } catch (e) {
        this.editErr = String(e.message || e);
      } finally {
        this.saving = false;
      }
    },
    async remove() {
      try {
        await API.del(`/api/teams/${encodeURIComponent(this.name)}`);
        this.$message.success("队伍已删除");
        this.$router.replace("/teams");
      } catch (e) {
        this.$message.error(String(e.message || e));
      }
    },
  },
};
