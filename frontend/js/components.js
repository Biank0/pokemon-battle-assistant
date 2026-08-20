/* 全局公共组件：TypeBadge / PokeSprite / PokemonCard */

const TypeColors = {
  Normal: "#A8A77A", Fire: "#EE8130", Water: "#6390F0", Electric: "#F7D02C",
  Grass: "#7AC74C", Ice: "#96D9D6", Fighting: "#C22E28", Poison: "#A33EA1",
  Ground: "#E2BF65", Flying: "#A98FF3", Psychic: "#F95587", Bug: "#A6B91A",
  Rock: "#B6A136", Ghost: "#735797", Dragon: "#6F35FC", Dark: "#705746",
  Steel: "#B7B7CE", Fairy: "#D685AD",
};

const TypeBadge = {
  props: { type: { type: Object, required: true } },
  computed: { color() { return TypeColors[this.type.en] || "#909399"; } },
  template: `<span class="type-badge" :style="{ background: color }">{{ type.zh }}</span>`,
};

/* 官方像素精灵图：/sprites/{slug}.png（本地 vendor，下载管线见 scripts/download_sprites.py）。
   缺图时隐藏元素（入场包已覆盖全部队伍/对战物种；新建队伍物种由增量下载补齐）。 */
const PokeSprite = {
  props: {
    slug: { type: String, required: true },
    size: { type: String, default: "md" },          // sm(32) / md(56) / lg(96)
  },
  computed: {
    src() { return "/sprites/" + this.slug + ".png"; },
    cls() { return "sprite sprite-" + this.size; },
  },
  template: `<img :src="src" :class="cls" :alt="slug" loading="lazy"
                 @error="$event.target.style.visibility='hidden'">`,
};

const PokemonCard = {
  components: { TypeBadge, PokeSprite },
  props: { member: { type: Object, required: true } },
  computed: {
    /* 种族值条：>120 绿 / >90 蓝 / >60 橙 / 其余红（经典宝可梦梯度） */
    statRows() {
      const st = this.member.stats || {};
      const defs = [["hp", "HP"], ["atk", "攻"], ["def", "防"],
                    ["spa", "特攻"], ["spd", "特防"], ["spe", "速"]];
      return defs.map(([k, label]) => {
        const v = st[k] ?? 0;
        return {
          k, label, v,
          pct: Math.min(100, Math.round(v / 180 * 100)),
          color: v >= 120 ? "#67C23A" : v >= 90 ? "#409EFF"
               : v >= 60 ? "#E6A23C" : "#F56C6C",
        };
      });
    },
  },
  template: `
  <el-card class="pc" shadow="never">
    <div class="pc-head">
      <span class="pc-name">{{ member.name_zh }}</span>
      <span class="pc-en">{{ member.name_en }}</span>
      <span class="pc-lv">Lv{{ member.level }}</span>
    </div>
    <div class="pc-sprite-box">
      <poke-sprite :slug="member.species" size="lg"></poke-sprite>
    </div>
    <div class="pc-types">
      <type-badge v-for="t in member.types" :key="t.en" :type="t"></type-badge>
    </div>
    <div class="pc-stats" v-if="member.stats">
      <div class="pc-stat-row" v-for="s in statRows" :key="s.k">
        <span class="pc-stat-label">{{ s.label }}</span>
        <span class="pc-stat-val">{{ s.v }}</span>
        <span class="pc-stat-bar"><i :style="{ width: s.pct + '%', background: s.color }"></i></span>
      </div>
      <div class="pc-stat-bst">总和 {{ member.stats.bst }}</div>
    </div>
    <div class="pc-stat-reason" v-if="member.stat_reason">“{{ member.stat_reason }}”</div>
    <el-descriptions class="pc-desc" :column="1" size="small" border>
      <el-descriptions-item label="特性">{{ member.ability_zh }}</el-descriptions-item>
      <el-descriptions-item label="道具">{{ member.item_zh || '无道具' }}</el-descriptions-item>
      <el-descriptions-item label="性格">{{ member.nature_zh }}</el-descriptions-item>
      <el-descriptions-item label="太晶">{{ member.tera_zh || '-' }}</el-descriptions-item>
    </el-descriptions>
    <div class="pc-moves">
      <el-tag v-for="m in member.moves" :key="m.slug" size="small" effect="plain" class="pc-move">
        {{ m.zh }}
      </el-tag>
    </div>
  </el-card>`,
};
