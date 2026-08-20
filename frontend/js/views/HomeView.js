/* 首页：数据看板（四统计卡 + 最近动态）+ 模块入口 */
const HomeView = {
  components: { PokeSprite },
  template: `
  <div>
    <h2 class="page-title">宝可梦对战助手</h2>
    <p class="page-desc">AI 建队 · 对战实验室 · 分析报告 —— 全流程自动化数据平台</p>

    <div class="stat-grid">
      <div class="stat-card c-red">
        <div class="stat-label">队伍</div>
        <div class="stat-value">{{ ov.teams ? ov.teams.total : '—' }}</div>
        <div class="stat-foot">预设 + AI 生成</div>
      </div>
      <div class="stat-card c-blue">
        <div class="stat-label">对战场次</div>
        <div class="stat-value">{{ ov.battles ? ov.battles.total : '—' }}</div>
        <div class="stat-foot">Showdown 引擎真实对战</div>
      </div>
      <div class="stat-card c-orange">
        <div class="stat-label">分析报告</div>
        <div class="stat-value">{{ ov.analyses ? ov.analyses.total : '—' }}</div>
        <div class="stat-foot">AI 结构化复盘</div>
      </div>
      <div class="stat-card c-green">
        <div class="stat-label">图鉴物种</div>
        <div class="stat-value">{{ ov.dex_species || '—' }}</div>
        <div class="stat-foot">建队候选池（含形态）</div>
      </div>
    </div>

    <div class="home-latest" v-if="ov.teams">
      <div class="home-mini clickable" @click="ov.teams.latest && $router.push('/teams/' + ov.teams.latest.name)">
        <div class="home-mini-title">◆ 最近 AI 建队</div>
        <div class="home-mini-main">{{ ov.teams.latest ? ov.teams.latest.display_name : '暂无' }}</div>
        <div class="home-mini-sub">{{ ov.teams.latest ? fmt(ov.teams.latest.created_at) : '去建一支 →' }}</div>
      </div>
      <div class="home-mini clickable" @click="$router.push('/lab')">
        <div class="home-mini-title">◆ 最近跑量</div>
        <div class="home-mini-main">
          {{ latestSess ? latestSess.team_a + ' vs ' + latestSess.team_b : '暂无' }}
        </div>
        <div class="home-mini-sub" v-if="latestSess">
          比分 {{ latestSess.score }} · A 队胜率 {{ latestSess.team_a_win_rate }}%
        </div>
        <div class="home-mini-sub" v-else>去实验室开跑 →</div>
      </div>
      <div class="home-mini clickable"
           @click="ov.analyses.latest && $router.push('/analyses/' + ov.analyses.latest.id)">
        <div class="home-mini-title">◆ 最近分析报告</div>
        <div class="home-mini-main">{{ ov.analyses.latest ? ov.analyses.latest.title : '暂无' }}</div>
        <div class="home-mini-sub" v-if="ov.analyses.latest">评分 {{ ov.analyses.latest.rating }}</div>
        <div class="home-mini-sub" v-else>跑一轮后生成 →</div>
      </div>
    </div>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="8">
        <el-card shadow="never">
          <div class="card-title">AI 建队</div>
          <div class="card-body">一句话需求，LLM 从图鉴数据库构筑合法对战队伍，自动校验入库</div>
          <el-button type="primary" plain @click="$router.push('/generate')">开始建队</el-button>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never">
          <div class="card-title">对战实验室</div>
          <div class="card-body">选两支队伍自动跑量，Showdown 引擎真实对战，统计胜率与出招数据</div>
          <el-button type="primary" plain @click="$router.push('/lab')">开始对战</el-button>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never">
          <div class="card-title">分析报告</div>
          <div class="card-body">对战数据蒸馏后 LLM 复盘，产出评分 / 阵容表现 / 威胁 / 改进建议</div>
          <el-button plain @click="$router.push('/analyses')">查看报告</el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>`,
  data() { return { ov: {} }; },
  computed: {
    latestSess() { return this.ov.battles ? this.ov.battles.latest_session : null; },
  },
  async mounted() {
    try { this.ov = await API.get("/api/overview"); } catch (e) { /* 首页容错 */ }
  },
  methods: {
    fmt(iso) { return (iso || "").replace("T", " ").slice(0, 16); },
  },
};
