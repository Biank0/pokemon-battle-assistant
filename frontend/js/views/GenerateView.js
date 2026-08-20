/* AI 建队页：需求表单 → 任务进度 → 结果 */
const GenerateView = {
  template: `
  <div>
    <h2 class="page-title">AI 建队</h2>
    <p class="page-desc">描述你的战术需求，AI 从 1480 只图鉴中构筑一支通过合法性校验的队伍（约 20~40 秒）</p>

    <div class="block" v-if="!job">
      <el-form label-position="top">
        <el-form-item label="建队需求">
          <el-input v-model="requirement" type="textarea" :rows="3" maxlength="200" show-word-limit
                    placeholder="例：帮我建一支雨天队，打法激进一点 / 围绕戏法空间的慢速爆发队"></el-input>
        </el-form-item>
        <el-form-item label="赛制">
          <el-radio-group v-model="format">
            <el-radio value="gen9bssregi">BSS（6选3单打 Lv50）</el-radio>
            <el-radio value="gen9vgc2026regi">VGC（6选4双打 Lv50）
              <span class="muted" style="font-size:12px">（暂不能进实验室）</span>
            </el-radio>
            <el-radio value="gen9ou">OU（6v6 单打 Lv100）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-button type="primary" :loading="submitting" :disabled="!requirement.trim()" @click="submit">
          开始构筑
        </el-button>
      </el-form>
    </div>

    <div class="block" v-if="job">
      <div class="job-head">
        <span>任务 {{ job.id }}</span>
        <el-tag v-if="job.status === 'running'" type="warning" size="small">进行中</el-tag>
        <el-tag v-else-if="job.status === 'done'" type="success" size="small">完成</el-tag>
        <el-tag v-else type="danger" size="small">失败</el-tag>
      </div>

      <div class="job-logs mono">
        <div v-for="(l, i) in job.logs" :key="i" class="job-log-line">{{ l }}</div>
        <div v-if="job.status === 'running'" class="job-log-line muted">…</div>
      </div>

      <el-alert v-if="job.status === 'failed'" type="error" :closable="false"
                :title="'建队失败'" :description="job.error" show-icon class="job-err"></el-alert>

      <div v-if="job.status === 'done'" class="job-done">
        <div class="done-name">{{ job.team.display_name }}</div>
        <div class="done-strategy">{{ job.team.strategy }}</div>
        <div class="done-meta muted">校验轮次 {{ job.attempts }} ｜ {{ job.usage }}</div>
        <div class="done-actions">
          <el-button type="primary" @click="viewTeam">查看队伍详情</el-button>
          <el-button @click="reset">再建一支</el-button>
        </div>
      </div>
    </div>
  </div>`,
  data() {
    return {
      requirement: "",
      format: "gen9bssregi",
      submitting: false,
      job: null,
      timer: null,
    };
  },
  methods: {
    async submit() {
      this.submitting = true;
      try {
        const { job_id } = await API.post("/api/generate", {
          requirement: this.requirement, format: this.format,
        });
        this.job = { id: job_id, status: "running", logs: [] };
        this.poll();
      } catch (e) {
        this.$message.error(String(e.message || e));
      } finally {
        this.submitting = false;
      }
    },
    async poll() {
      try {
        this.job = await API.get(`/api/generate/${this.job.id}`);
      } catch (e) {
        this.job.status = "failed";
        this.job.error = String(e.message || e);
        return;
      }
      if (this.job.status === "running") {
        this.timer = setTimeout(() => this.poll(), 1500);
      }
    },
    viewTeam() {
      this.$router.push(`/teams/${this.job.team.name}`);
    },
    reset() {
      clearTimeout(this.timer);
      this.job = null;
    },
  },
  unmounted() { clearTimeout(this.timer); },
};
