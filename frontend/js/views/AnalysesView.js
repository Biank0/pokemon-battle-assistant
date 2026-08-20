/* 分析报告：选会话发起 AI 复盘（后台任务轮询）+ 报告索引列表 */
const AnalysesView = {
  template: `
  <div>
    <h2 class="page-title">分析报告</h2>
    <p class="page-desc">选择一次完成的跑量会话，AI 复盘分析师蒸馏对战数据后生成结构化复盘报告（约 10~20 秒）</p>

    <div class="block">
      <div class="block-title">发起分析</div>
      <el-form label-position="top" @submit.prevent>
        <div class="an-start-row">
          <el-form-item label="跑量会话" class="an-start-sess">
            <el-select v-model="sessionId" placeholder="选择已完成的会话" style="width: 100%"
                       :disabled="!!job">
              <el-option v-for="s in sessions" :key="s.id" :value="s.id"
                         :label="sessLabel(s)"></el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="特别关注（可选）" class="an-start-focus">
            <el-input v-model="focus" placeholder="如：重点看看九尾的表现，首发是不是有问题"
                      maxlength="100" :disabled="!!job"></el-input>
          </el-form-item>
          <el-form-item label=" " class="an-start-btn">
            <el-button type="primary" :loading="starting" :disabled="!sessionId || !!job"
                       @click="start">开始分析</el-button>
          </el-form-item>
        </div>
      </el-form>

      <template v-if="job">
        <div class="job-head">
          <span>分析进度</span>
          <el-tag v-if="job.status === 'running'" type="warning" size="small">进行中</el-tag>
          <el-tag v-else-if="job.status === 'done'" type="success" size="small">完成</el-tag>
          <el-tag v-else type="danger" size="small">失败</el-tag>
        </div>
        <div class="job-logs" v-if="job.logs.length">
          <div v-for="(l, i) in job.logs" :key="i">{{ l }}</div>
        </div>
        <el-alert v-if="job.status === 'failed'" type="error" :closable="false"
                  title="分析失败" :description="job.error" show-icon class="job-err"></el-alert>
        <div class="job-done" v-if="job.status === 'done' && job.result">
          <div class="done-name">{{ job.result.title }}</div>
          <div class="done-strategy">{{ job.result.headline }}</div>
          <div class="muted done-meta">
            评分 {{ job.result.rating }} ｜ {{ job.usage }} ｜ 校验轮次 {{ job.attempts }}
          </div>
          <div class="done-actions">
            <el-button type="primary" @click="openReport(job.result.analysis_id)">查看报告</el-button>
            <el-button @click="resetJob">再分析一次</el-button>
          </div>
        </div>
      </template>
    </div>

    <div class="block">
      <div class="block-title">历史报告</div>
      <el-empty v-if="!reports.length" description="还没有分析报告，先在对战实验室跑一轮"></el-empty>
      <el-table v-else :data="reports" size="small" @row-click="openReport"
                row-class-name="clickable">
        <el-table-column label="报告" min-width="220">
          <template #default="{ row }">
            <div class="an-title">{{ row.title }}</div>
            <div class="muted an-summary">{{ row.summary }}</div>
          </template>
        </el-table-column>
        <el-table-column label="评分" width="70" align="center">
          <template #default="{ row }">
            <span v-if="row.rating" class="rating-stamp sm" :class="'rating-' + row.rating">{{ row.rating }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="比分" width="90" align="center">
          <template #default="{ row }">{{ (row.stats || {}).score || '-' }}</template>
        </el-table-column>
        <el-table-column label="A 队胜率" width="90" align="center">
          <template #default="{ row }">
            {{ row.win_rate === null ? '-' : Math.round(row.win_rate * 100) + '%' }}
          </template>
        </el-table-column>
        <el-table-column prop="model" label="模型" width="120"></el-table-column>
        <el-table-column prop="created_at" label="生成时间" width="170"></el-table-column>
      </el-table>
    </div>
  </div>`,
  data() {
    return { sessions: [], sessionId: "", focus: "", starting: false, job: null, reports: [], timer: null };
  },
  async mounted() {
    await Promise.all([this.loadSessions(), this.loadReports()]);
  },
  beforeUnmount() { this.stopPoll(); },
  methods: {
    sessLabel(s) {
      const sum = s.summary;
      const vs = sum ? `${sum.team_a_display} vs ${sum.team_b_display}（${sum.team_a_wins}:${sum.team_b_wins}）`
                     : s.id.slice(0, 8);
      return `${vs} · ${s.rounds_total} 轮 · ${s.started_at}`;
    },
    async loadSessions() {
      try {
        const { sessions } = await API.get("/api/lab/sessions");
        this.sessions = sessions.filter((s) => s.status === "completed");
      } catch (e) { /* 忽略 */ }
    },
    async loadReports() {
      try {
        const { analyses } = await API.get("/api/analyses");
        this.reports = analyses;
      } catch (e) { /* 忽略 */ }
    },
    async start() {
      this.starting = true;
      try {
        const { job_id } = await API.post("/api/analyze", {
          session_id: this.sessionId, focus: this.focus,
        });
        this.job = { status: "running", logs: [], result: null, error: null, usage: "", attempts: 0 };
        this.poll(job_id);
      } catch (e) {
        this.$message.error(String(e.message || e));
      } finally { this.starting = false; }
    },
    async poll(jobId) {
      try {
        this.job = await API.get(`/api/analyze/${jobId}`);
        if (this.job.status === "running") {
          this.timer = setTimeout(() => this.poll(jobId), 1500);
        } else {
          this.stopPoll();
          if (this.job.status === "done") {
            this.loadReports();
            this.$message.success("分析完成");
          } else {
            this.$message.error("分析失败：" + (this.job.error || "未知错误"));
          }
        }
      } catch (e) {
        this.stopPoll();
        this.$message.error(String(e.message || e));
      }
    },
    stopPoll() { if (this.timer) { clearTimeout(this.timer); this.timer = null; } },
    resetJob() { this.job = null; this.focus = ""; },
    openReport(row) { this.$router.push(`/analyses/${row.id ?? row.analysis_id}`); },
  },
};
