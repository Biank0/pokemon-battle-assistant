/* 对战实验室：选两队 → 跑量 → 进度 → 统计图表 + 逐场明细入口 */
const LabView = {
  template: `
  <div>
    <h2 class="page-title">对战实验室</h2>
    <p class="page-desc">选择两支队伍批量对战，本地启发式 bot 全自动操作，统计胜负与出招数据（每场约 5~15 秒）</p>

    <div class="block" v-if="!session">
      <el-form label-position="top">
        <div class="lab-vs">
          <el-form-item label="A 队（己方）" class="lab-vs-side">
            <el-select v-model="teamA" placeholder="选择队伍" style="width: 100%"
                       @change="syncFormat('a')">
              <el-option v-for="t in teams" :key="t.name"
                         :label="t.display_name + '（' + formatName(t.format) + '·' + sourceName(t.source) + '）'"
                         :value="t.name"></el-option>
            </el-select>
          </el-form-item>
          <div class="lab-vs-mid">VS</div>
          <el-form-item label="B 队（对手）" class="lab-vs-side">
            <el-select v-model="teamB" placeholder="选择队伍" style="width: 100%"
                       @change="syncFormat('b')">
              <el-option v-for="t in teams" :key="t.name"
                         :label="t.display_name + '（' + formatName(t.format) + '·' + sourceName(t.source) + '）'"
                         :value="t.name" :disabled="t.name === teamA"></el-option>
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="对战赛制">
          <el-radio-group v-model="format">
            <el-radio value="gen9bssregi">BSS（6选3单打 Lv50）</el-radio>
            <el-radio value="gen9vgc2026regi">VGC（6选4双打 Lv50）</el-radio>
            <el-radio value="gen9ou">OU（6v6 单打 Lv100）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="对战轮数">
          <el-slider v-model="rounds" :min="3" :max="50" :step="1" show-input
                     :marks="{3:'3', 10:'10', 50:'50'}" class="lab-rounds"></el-slider>
        </el-form-item>
        <el-button type="primary" :loading="starting" :disabled="!teamA || !teamB" @click="start">
          开始跑量
        </el-button>
      </el-form>
    </div>

    <div class="block" v-if="session">
      <div class="job-head">
        <span>对战进度</span>
        <el-tag v-if="session.status === 'running'" type="warning" size="small">进行中</el-tag>
        <el-tag v-else-if="session.status === 'completed'" type="success" size="small">完成</el-tag>
        <el-tag v-else type="danger" size="small">失败</el-tag>
      </div>
      <el-progress :percentage="progressPct" :stroke-width="14" class="lab-progress"></el-progress>
      <div class="muted lab-progress-text">{{ session.rounds_done }} / {{ session.rounds_total }} 场</div>

      <el-alert v-if="session.status === 'failed'" type="error" :closable="false"
                title="会话失败" :description="session.error" show-icon></el-alert>

      <template v-if="session.status === 'completed' && session.stats">
        <div class="lab-score">
          <div class="lab-score-side">
            <div class="lab-score-name">{{ session.stats.team_a_display }}</div>
            <div class="lab-score-num">{{ session.stats.team_a_wins }}</div>
          </div>
          <div class="lab-score-mid">
            <div class="lab-score-rate" v-if="session.stats.team_a_win_rate !== null">
              A 队胜率 {{ session.stats.team_a_win_rate }}%
            </div>
            <div class="muted">平均 {{ session.stats.avg_turns ?? '-' }} 回合/场</div>
          </div>
          <div class="lab-score-side">
            <div class="lab-score-name">{{ session.stats.team_b_display }}</div>
            <div class="lab-score-num">{{ session.stats.team_b_wins }}</div>
          </div>
        </div>

        <div class="lab-charts">
          <div class="lab-chart-card">
            <div class="lab-chart-title">逐场胜负序列</div>
            <div class="lab-win-seq">
              <div v-for="b in session.battles" :key="b.id" class="lab-win-dot"
                   :class="'w-' + b.winner" :title="'第' + b.round_no + '场 ' + winnerText(b.winner) + ' / ' + b.end_turn + '回合'"
                   @click="openBattle(b)"></div>
            </div>
            <div class="lab-legend muted">
              <span class="dot w-a"></span>A 胜　<span class="dot w-b"></span>B 胜　<span class="dot w-draw"></span>平局　（点击查看明细）
            </div>
          </div>
          <div class="lab-chart-card">
            <div class="lab-chart-title">招式热榜 TOP10</div>
            <div ref="movesChart" class="lab-chart"></div>
          </div>
        </div>
      </template>

      <el-table v-if="session.battles && session.battles.length" :data="session.battles"
                size="small" class="lab-table" @row-click="openBattle" row-class-name="clickable">
        <el-table-column prop="round_no" label="场次" width="70"></el-table-column>
        <el-table-column label="结果" width="90">
          <template #default="{ row }">
            <el-tag :type="row.winner === 'a' ? 'success' : row.winner === 'b' ? 'danger' : 'info'" size="small">
              {{ winnerText(row.winner) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="end_turn" label="回合数" width="90"></el-table-column>
        <el-table-column label="" width="120">
          <template #default="{ row }">
            <el-button link type="primary" size="small">查看明细</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="lab-actions">
        <el-button @click="reset">再跑一轮</el-button>
      </div>
    </div>

    <div class="block" v-if="!session && history.length">
      <div class="block-title">历史会话</div>
      <el-table :data="history" size="small" @row-click="openHistory" row-class-name="clickable">
        <el-table-column label="对阵" min-width="200">
          <template #default="{ row }">
            {{ row.summary ? row.summary.team_a_display + ' vs ' + row.summary.team_b_display : row.id.slice(0, 8) }}
          </template>
        </el-table-column>
        <el-table-column label="比分" width="90">
          <template #default="{ row }">
            {{ row.summary ? row.summary.team_a_wins + ' : ' + row.summary.team_b_wins : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="rounds_total" label="轮数" width="70"></el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="started_at" label="开始时间" width="170"></el-table-column>
      </el-table>
    </div>
  </div>`,
  data() {
    return {
      teams: [], teamA: "", teamB: "", format: "gen9bssregi", rounds: 10,
      starting: false, session: null, history: [], timer: null, chart: null,
    };
  },
  computed: {
    progressPct() {
      if (!this.session || !this.session.rounds_total) return 0;
      return Math.round(this.session.rounds_done / this.session.rounds_total * 100);
    },
  },
  async mounted() {
    try {
      this.teams = await API.get("/api/teams");  // 接口返回数组
      this.loadHistory();
    } catch (e) {
      this.$message.error("加载队伍列表失败：" + String(e.message || e));
    }
  },
  beforeUnmount() { this.stopPoll(); if (this.chart) this.chart.dispose(); },
  methods: {
    formatName(f) { return ({ gen9bssregi: "BSS", gen9vgc2026regi: "VGC", gen9ou: "OU" })[f] || f; },
    sourceName(s) { return ({ preset: "预设", ai: "AI 生成", manual: "手动" })[s] || s; },
    syncFormat(side) {
      const t = this.teams.find((x) => x.name === (side === "a" ? this.teamA : this.teamB));
      if (t) this.format = t.format;
    },
    async start() {
      this.starting = true;
      try {
        const { session_id } = await API.post("/api/lab/start", {
          team_a: this.teamA, team_b: this.teamB, format: this.format, rounds: this.rounds,
        });
        this.session = { id: session_id, status: "running", rounds_done: 0,
                         rounds_total: this.rounds, battles: [] };
        this.poll();
      } catch (e) {
        this.$message.error(String(e.message || e));
      } finally { this.starting = false; }
    },
    async poll() {
      try {
        this.session = await API.get(`/api/lab/session/${this.session.id}`);
        if (this.session.status === "running") {
          this.timer = setTimeout(() => this.poll(), 2000);
        } else {
          this.stopPoll();
          this.loadHistory();
          if (this.session.status === "completed") {
            this.$nextTick(() => this.renderChart());
            this.$message.success("跑量完成");
          } else {
            this.$message.error("会话失败：" + (this.session.error || "未知错误"));
          }
        }
      } catch (e) {
        this.stopPoll();
        this.$message.error(String(e.message || e));
      }
    },
    stopPoll() { if (this.timer) { clearTimeout(this.timer); this.timer = null; } },
    renderChart() {
      if (!this.$refs.movesChart || typeof echarts === "undefined") return;
      const top = (this.session.stats.top_moves || []).slice().reverse();
      this.chart = echarts.init(this.$refs.movesChart);
      this.chart.setOption({
        grid: { left: 8, right: 30, top: 8, bottom: 8, containLabel: true },
        xAxis: { type: "value", splitLine: { show: false } },
        yAxis: { type: "category", data: top.map((m) => m.move_zh) },
        series: [{ type: "bar", data: top.map((m) => m.count), barWidth: 14,
                   itemStyle: { color: "#409eff", borderRadius: [0, 4, 4, 0] }, label: { show: true, position: "right" } }],
        tooltip: { trigger: "axis" },
      });
    },
    winnerText(w) { return ({ a: "A 胜", b: "B 胜", draw: "平局", error: "异常" })[w] || w; },
    statusText(s) { return ({ running: "进行中", completed: "完成", failed: "失败", pending: "等待" })[s] || s; },
    statusType(s) { return ({ running: "warning", completed: "success", failed: "danger" })[s] || "info"; },
    openBattle(b) { this.$router.push(`/lab/battle/${b.id}`); },
    async openHistory(row) {
      this.session = await API.get(`/api/lab/session/${row.id}`);
      if (this.session.status === "running") this.poll();
      else if (this.session.status === "completed") this.$nextTick(() => this.renderChart());
    },
    async loadHistory() {
      try {
        const { sessions } = await API.get("/api/lab/sessions");
        this.history = sessions.filter((s) => s.id !== (this.session || {}).id);
        // 恢复观察：无当前会话且有进行中的会话时自动进入（页面刷新/外部发起场景）
        const running = this.history.find((s) => s.status === "running");
        if (!this.session && running) this.openHistory(running);
      } catch (e) { /* 忽略 */ }
    },
    async reset() {
      this.stopPoll();
      this.session = null;
      if (this.chart) { this.chart.dispose(); this.chart = null; }
      if (!this.teams.length) {  // 首屏加载失败兜底：回表单时重拉
        try { this.teams = await API.get("/api/teams"); } catch (e) { /* 忽略 */ }
      }
      this.loadHistory();
    },
  },
};
