/* 首页：模块入口 + 概览 */
const HomeView = {
  template: `
  <div>
    <h2 class="page-title">宝可梦对战助手</h2>
    <p class="page-desc">AI 建队 · 对战实验室 · 分析报告 —— 全流程自动化</p>

    <el-row :gutter="16">
      <el-col :span="8">
        <el-card shadow="never">
          <div class="card-title">AI 建队</div>
          <div class="card-body">一句话需求，DeepSeek 从图鉴数据库构筑合法对战队伍，自动校验入库</div>
          <el-button type="primary" plain @click="$router.push('/generate')">开始建队</el-button>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never">
          <div class="card-title">队伍库</div>
          <div class="card-body">当前共 {{ teamsCount }} 支队伍（预设 / AI 生成），点击查看完整配置</div>
          <el-button plain @click="$router.push('/teams')">浏览队伍</el-button>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never">
          <div class="card-title">对战实验室</div>
          <div class="card-body">选两支队伍自动跑量，Showdown 引擎真实对战，统计胜率与出招数据</div>
          <el-button type="primary" plain @click="$router.push('/lab')">开始对战</el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>`,
  data() { return { teamsCount: 0 }; },
  async mounted() {
    try { this.teamsCount = (await API.get("/api/teams")).length; } catch (e) { /* 首页容错 */ }
  },
};
