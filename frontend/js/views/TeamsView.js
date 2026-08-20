/* 队伍库：列表 + 筛选 + 新建（Showdown 串导入） */
const TeamsView = {
  components: { PokeSprite },
  template: `
  <div>
    <h2 class="page-title">队伍库</h2>
    <p class="page-desc">共 {{ filtered.length }} 支队伍</p>

    <div class="block">
      <div class="teams-toolbar">
        <el-input v-model="kw" placeholder="按中文名 / 文件 ID / 需求筛选" clearable
                  style="max-width: 320px"></el-input>
        <el-button type="primary" @click="openCreate">＋ 新建队伍</el-button>
      </div>
      <el-table :data="filtered" v-loading="loading" @row-click="open"
                class="teams-table" :header-cell-style="{ background: '#fafafa' }">
        <el-table-column prop="display_name" label="队伍" min-width="160">
          <template #default="{ row }">
            <poke-sprite v-if="row.ace_sprite" :slug="row.ace_sprite" size="sm" class="cell-sprite"></poke-sprite>
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

    <el-dialog v-model="createDlg" title="新建队伍（粘贴 Showdown 导出串）" width="640px"
               :close-on-click-modal="false">
      <el-form label-position="top">
        <el-form-item label="队伍名">
          <el-input v-model="createForm.display_name" maxlength="30" show-word-limit
                    placeholder="例：小边的雨天队"></el-input>
        </el-form-item>
        <el-form-item label="赛制">
          <el-radio-group v-model="createForm.format">
            <el-radio value="gen9bssregi">BSS（6选3单打 Lv50）</el-radio>
            <el-radio value="gen9ou">OU（6v6 单打 Lv100）</el-radio>
            <el-radio value="gen9vgc2026regi">VGC（6选4双打 Lv50）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="Showdown 导出串（恰好 6 只，空行分隔；招式/特性/道具会做法务校验）">
          <el-input v-model="createForm.export_text" type="textarea" :rows="12" class="mono-area"
                    placeholder="Urshifu-Rapid-Strike @ Choice Scarf&#10;Ability: Unseen Fist&#10;Level: 50&#10;Tera Type: Water&#10;EVs: 252 Atk / 4 SpD / 252 Spe&#10;Jolly Nature&#10;- Surging Strikes&#10;- Aqua Jet&#10;- Close Combat&#10;- U-turn&#10;&#10;（空行隔开后继续第二只…）"></el-input>
        </el-form-item>
        <el-alert v-if="createErr" type="error" :closable="false" :title="createErr"
                  show-icon class="pre-line"></el-alert>
      </el-form>
      <template #footer>
        <el-button @click="createDlg = false">取消</el-button>
        <el-button type="primary" :loading="creating"
                   :disabled="!createForm.display_name.trim() || !createForm.export_text.trim()"
                   @click="submitCreate">校验并入库</el-button>
      </template>
    </el-dialog>
  </div>`,
  data() {
    return {
      teams: [], loading: false, kw: "",
      createDlg: false, creating: false, createErr: "",
      createForm: { display_name: "", format: "gen9bssregi", export_text: "" },
    };
  },
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
    await this.load();
  },
  methods: {
    open(row) { this.$router.push(`/teams/${row.name}`); },
    fmt(iso) { return (iso || "").replace("T", " ").slice(0, 16); },
    async load() {
      this.loading = true;
      try { this.teams = await API.get("/api/teams"); }
      catch (e) { this.$message.error(String(e.message || e)); }
      finally { this.loading = false; }
    },
    openCreate() {
      this.createErr = "";
      this.createForm = { display_name: "", format: "gen9bssregi", export_text: "" };
      this.createDlg = true;
    },
    async submitCreate() {
      this.creating = true;
      this.createErr = "";
      try {
        const saved = await API.post("/api/teams", this.createForm);
        this.createDlg = false;
        this.$message.success(`队伍「${saved.display_name}」已入库`);
        this.$router.push(`/teams/${saved.name}`);
      } catch (e) {
        this.createErr = String(e.message || e);
      } finally {
        this.creating = false;
      }
    },
  },
};
