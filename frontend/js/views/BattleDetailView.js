/* 单场对战明细：逐回合动作时间线（己方/对手 双色） */
const BattleDetailView = {
  template: `
  <div v-if="battle">
    <h2 class="page-title">对战明细 · 第 {{ battle.round_no }} 场</h2>
    <p class="page-desc">{{ battle.team_a }}（A） vs {{ battle.team_b }}（B） ｜
      <el-tag :type="battle.winner === 'a' ? 'success' : battle.winner === 'b' ? 'danger' : 'info'" size="small">
        {{ battle.winner === 'a' ? 'A 胜' : battle.winner === 'b' ? 'B 胜' : '平局' }}
      </el-tag> ｜ 共 {{ battle.end_turn }} 回合</p>

    <div class="block">
      <el-timeline>
        <el-timeline-item v-for="(t, i) in battle.turns" :key="i"
                          :type="t.side === 'a' ? 'primary' : 'warning'"
                          :hollow="t.side === 'b'"
                          :timestamp="'回合 ' + t.turn + (t.side === 'a' ? ' · A 队' : ' · B 队')"
                          placement="top">
          <span class="bd-actor">{{ t.actor_zh }}</span>
          <span v-if="t.action_type === 'move'" class="bd-move">使用 {{ t.move_zh }} → {{ t.target_zh }}</span>
          <span v-else-if="t.action_type === 'switch'" class="bd-switch">换上 {{ t.target_zh }}</span>
          <span v-else class="bd-order muted">选择出场顺序：{{ t.move_zh || t.actor_zh }}</span>
        </el-timeline-item>
      </el-timeline>
    </div>
    <el-button @click="$router.back()">返回</el-button>
  </div>
  <div v-else class="block muted">加载中…</div>`,
  data() { return { battle: null }; },
  async mounted() {
    this.battle = await API.get(`/api/lab/battle/${this.id}`);
  },
  props: { id: { type: String, required: true } },
};
