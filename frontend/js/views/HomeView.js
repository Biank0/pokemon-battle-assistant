/* 首页：GBA 标题画面 Hero（随机遭遇）+ 数据看板（count-up）+ 最近动态 + 模块入口 */
const HomeView = {
  components: { PokeSprite },
  template: `
  <div>
    <!-- GBA 标题画面 -->
    <div class="hero">
      <div class="hero-left">
        <div class="hero-title">宝可梦对战助手</div>
        <div class="hero-sub">AI 建队 · 对战实验室 · 分析报告 —— 全流程自动化数据平台</div>
        <div class="hero-start" @click="$router.push('/generate')">▼ 开始新任务</div>
      </div>
      <div class="hero-wild" v-if="ov.featured">
        <div class="hero-wild-stage">
          <poke-sprite :slug="ov.featured.slug" size="lg" class="hero-wild-sprite"></poke-sprite>
        </div>
        <div class="hero-wild-text">野生的 <b>{{ ov.featured.name_zh }}</b> 出现了！</div>
      </div>
    </div>

    <!-- 数据看板（count-up） -->
    <div class="stat-grid">
      <div class="stat-card c-red">
        <div class="stat-label">队伍</div>
        <div class="stat-value">{{ loaded ? disp.teams : '—' }}</div>
        <div class="stat-foot">预设 + AI 生成</div>
      </div>
      <div class="stat-card c-blue">
        <div class="stat-label">对战场次</div>
        <div class="stat-value">{{ loaded ? disp.battles : '—' }}</div>
        <div class="stat-foot">Showdown 引擎真实对战</div>
      </div>
      <div class="stat-card c-orange">
        <div class="stat-label">分析报告</div>
        <div class="stat-value">{{ loaded ? disp.analyses : '—' }}</div>
        <div class="stat-foot">AI 结构化复盘</div>
      </div>
      <div class="stat-card c-green">
        <div class="stat-label">图鉴物种</div>
        <div class="stat-value">{{ loaded ? disp.dex : '—' }}</div>
        <div class="stat-foot">建队候选池（含形态）</div>
      </div>
    </div>

    <!-- 最近动态 -->
    <div class="home-latest" v-if="ov.teams">
      <div class="home-mini clickable" @click="ov.teams.latest && $router.push('/teams/' + ov.teams.latest.name)">
        <div class="home-mini-title">◆ 最近 AI 建队</div>
        <div class="home-mini-main">{{ ov.teams.latest ? ov.teams.latest.display_name : '暂无' }}</div>
        <div class="home-mini-sub">{{ ov.teams.latest ? fmt(ov.teams.latest.created_at) : '去建一支 →' }}</div>
      </div>
      <div class="home-mini clickable" @click="$router.push('/lab')">
        <div class="home-mini-title">◆ 最近跑量</div>
        <template v-if="latestSess">
          <div class="mini-vs">
            <poke-sprite v-if="latestSess.team_a_sprite" :slug="latestSess.team_a_sprite" size="sm"></poke-sprite>
            <span class="mini-vs-score">{{ latestSess.score }}</span>
            <poke-sprite v-if="latestSess.team_b_sprite" :slug="latestSess.team_b_sprite" size="sm"></poke-sprite>
          </div>
          <div class="home-mini-main">{{ latestSess.team_a }} vs {{ latestSess.team_b }}</div>
          <div class="home-mini-sub">A 队胜率 {{ latestSess.team_a_win_rate }}%</div>
        </template>
        <template v-else>
          <div class="home-mini-main">暂无</div>
          <div class="home-mini-sub">去实验室开跑 →</div>
        </template>
      </div>
      <div class="home-mini clickable"
           @click="ov.analyses.latest && $router.push('/analyses/' + ov.analyses.latest.id)">
        <div class="home-mini-title">◆ 最近分析报告</div>
        <div class="home-mini-main">{{ ov.analyses.latest ? ov.analyses.latest.title : '暂无' }}</div>
        <div class="home-mini-sub" v-if="ov.analyses.latest">
          <span v-if="ov.analyses.latest.rating" class="rating-stamp sm"
                :class="'rating-' + ov.analyses.latest.rating">{{ ov.analyses.latest.rating }}</span>
          {{ fmt(ov.analyses.latest.created_at) }}
        </div>
        <div class="home-mini-sub" v-else>跑一轮后生成 →</div>
      </div>
    </div>

    <!-- 模块入口 -->
    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="8">
        <el-card shadow="never" class="entry-card">
          <div class="card-title">AI 建队</div>
          <div class="card-body">一句话需求，LLM 从图鉴数据库构筑合法对战队伍，自动校验入库</div>
          <el-button type="primary" plain @click="$router.push('/generate')">开始建队</el-button>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="entry-card">
          <div class="card-title">对战实验室</div>
          <div class="card-body">选两支队伍自动跑量，Showdown 引擎真实对战，统计胜率与出招数据</div>
          <el-button type="primary" plain @click="$router.push('/lab')">开始对战</el-button>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="entry-card">
          <div class="card-title">分析报告</div>
          <div class="card-body">对战数据蒸馏后 LLM 复盘，产出评分 / 阵容表现 / 威胁 / 改进建议</div>
          <el-button plain @click="$router.push('/analyses')">查看报告</el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>`,
  data() {
    return {
      ov: {}, loaded: false,
      disp: { teams: 0, battles: 0, analyses: 0, dex: 0 },
    };
  },
  computed: {
    latestSess() { return this.ov.battles ? this.ov.battles.latest_session : null; },
  },
  async mounted() {
    try {
      this.ov = await API.get("/api/overview");
      this.loaded = true;
      this.countUp();
    } catch (e) { /* 首页容错 */ }
  },
  methods: {
    fmt(iso) { return (iso || "").replace("T", " ").slice(0, 16); },
    /* 统计数字滚动登场（~700ms ease-out；reduced-motion 直接落定） */
    countUp() {
      const t = {
        teams: (this.ov.teams || {}).total || 0,
        battles: (this.ov.battles || {}).total || 0,
        analyses: (this.ov.analyses || {}).total || 0,
        dex: this.ov.dex_species || 0,
      };
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        this.disp = t;
        return;
      }
      const t0 = performance.now(), dur = 700;
      const step = (now) => {
        const k = Math.min(1, (now - t0) / dur);
        const e = 1 - Math.pow(1 - k, 3);
        for (const key of Object.keys(t)) this.disp[key] = Math.round(t[key] * e);
        if (k < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    },
  },
};
