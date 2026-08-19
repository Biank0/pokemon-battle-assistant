/* 分析报告详情：结构化渲染 JSON 报告 + 高光回合跳转到对战明细 */
const AnalysisDetailView = {
  template: `
  <div v-if="doc">
    <el-button link class="back" @click="$router.push('/analyses')">← 返回报告列表</el-button>

    <div class="block an-head">
      <div class="head-row">
        <h2 class="head-name">{{ report.title }}</h2>
        <el-tag :type="ratingType(report.rating)" effect="dark">{{ report.rating }}</el-tag>
      </div>
      <div class="an-headline">{{ report.headline }}</div>
      <div class="muted head-meta">
        {{ sm.team_a }} vs {{ sm.team_b }} ｜ 比分 {{ sm.score }}（A 队胜率 {{ sm.team_a_win_rate }}%）
        ｜ {{ sm.rounds }} 轮 · 平均 {{ sm.avg_turns }} 回合 ｜ {{ sm.format }}
        ｜ 生成于 {{ doc.generated_at }}
      </div>
    </div>

    <div class="block">
      <div class="block-title">战绩解读</div>
      <p class="an-text">{{ report.win_loss_read }}</p>
    </div>

    <div class="block">
      <div class="block-title">阵容表现</div>
      <div class="an-perf-grid">
        <div v-for="(p, i) in report.pokemon_performance" :key="i" class="an-perf"
             :class="'side-' + p.side">
          <div class="an-perf-head">
            <span class="an-perf-name">{{ p.species_zh }}</span>
            <el-tag size="small" :type="p.side === 'a' ? 'success' : 'danger'">
              {{ p.side === 'a' ? 'A 队' : 'B 队' }}
            </el-tag>
            <span class="muted an-perf-role">{{ p.role }} · 出场 {{ p.appearance }} 次</span>
          </div>
          <div class="an-perf-moves">
            <el-tag v-for="(m, j) in p.moves_used" :key="j" size="small" type="info" class="an-move">
              {{ m.move_zh }}×{{ m.count }}
            </el-tag>
          </div>
          <p class="an-text">{{ p.verdict }}</p>
          <el-alert v-for="(iss, j) in p.issues" :key="'i' + j" type="warning" :closable="false"
                    :title="iss" show-icon class="an-issue"></el-alert>
        </div>
      </div>
    </div>

    <div class="an-two-col">
      <div class="block" v-if="report.matchups && report.matchups.length">
        <div class="block-title">对位分析</div>
        <div v-for="(m, i) in report.matchups" :key="i" class="an-line">
          <span class="an-pair">{{ m.attacker_zh }} → {{ m.defender_zh }}</span>
          <span class="muted">{{ m.read }}</span>
        </div>
      </div>
      <div class="block" v-if="report.threats && report.threats.length">
        <div class="block-title">威胁识别</div>
        <div v-for="(t, i) in report.threats" :key="i" class="an-line">
          <span class="an-pair">{{ t.from_zh }}</span>
          <span class="muted">{{ t.why }} → 应对：{{ t.counter }}</span>
        </div>
      </div>
    </div>

    <div class="block" v-if="doc.highlight_links && doc.highlight_links.length">
      <div class="block-title">关键回合（点击回看对战明细）</div>
      <div v-for="h in doc.highlight_links" :key="h.seq" class="an-hl clickable"
           @click="$router.push('/lab/battle/' + h.battle_id)">
        <el-tag size="small" type="warning">第 {{ h.round_no }} 场</el-tag>
        <span class="an-hl-turn">回合 {{ h.turn }}</span>
        <span class="an-hl-side" :class="'side-' + h.side + '-text'">
          {{ h.side === 'a' ? 'A 队' : 'B 队' }}
        </span>
        <span class="an-hl-what">{{ h.description }}</span>
        <span class="muted">→ 查看明细</span>
      </div>
    </div>

    <div class="block">
      <div class="block-title">改进建议</div>
      <div v-for="(r, i) in report.recommendations" :key="i" class="an-rec">
        <el-tag size="small" :type="prioType(r.priority)" effect="dark">{{ r.priority }}</el-tag>
        <span class="an-rec-target">{{ r.target }}</span>
        <span class="an-rec-change">{{ r.change }}</span>
        <span class="muted">（{{ r.reason }}）</span>
      </div>
    </div>
  </div>

  <div v-else-if="error">
    <el-button link class="back" @click="$router.push('/analyses')">← 返回报告列表</el-button>
    <el-alert type="error" :title="'报告加载失败'" :description="error" show-icon :closable="false"></el-alert>
  </div>

  <div v-else class="block"><el-skeleton :rows="6" animated></el-skeleton></div>`,
  props: { id: String },
  data() {
    return { doc: null, error: "" };
  },
  computed: {
    report() { return (this.doc || {}).report || {}; },
    sm() { return (this.doc || {}).session_meta || {}; },
  },
  async mounted() {
    try {
      this.doc = await API.get(`/api/analyses/${this.id}`);
    } catch (e) {
      this.error = String(e.message || e);
    }
  },
  methods: {
    ratingType(r) {
      return ({ S: "danger", A: "success", B: "primary", C: "warning", D: "info" })[r] || "info";
    },
    prioType(p) {
      return ({ 高: "danger", 中: "warning", 低: "info" })[p] || "info";
    },
  },
};
