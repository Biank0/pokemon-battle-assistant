/* 全局公共组件：TypeBadge / PokemonCard */

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

const PokemonCard = {
  components: { TypeBadge },
  props: { member: { type: Object, required: true } },
  template: `
  <el-card class="pc" shadow="never">
    <div class="pc-head">
      <span class="pc-name">{{ member.name_zh }}</span>
      <span class="pc-en">{{ member.name_en }}</span>
      <span class="pc-lv">Lv{{ member.level }}</span>
    </div>
    <div class="pc-types">
      <type-badge v-for="t in member.types" :key="t.en" :type="t"></type-badge>
    </div>
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
