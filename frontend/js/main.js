const { createApp, reactive, computed } = Vue
const { createRouter, createWebHistory } = VueRouter

const TypeColors = {
  Normal: '#a8a77a', Fire: '#ee8130', Water: '#6390f0', Electric: '#f7d02c',
  Grass: '#7ac74c', Ice: '#96d9d6', Fighting: '#c22e28', Poison: '#a33ea1',
  Ground: '#e2bf65', Flying: '#a98ff3', Psychic: '#f95587', Bug: '#a6b91a',
  Rock: '#b6a136', Ghost: '#735797', Dragon: '#6f35fc', Dark: '#705746',
  Steel: '#b7b7ce', Fairy: '#d685ad',
}

const TypeBadge = {
  props: { type: String },
  computed: {
    color() {
      return TypeColors[this.type] || '#68a090'
    },
  },
  template: '<span class="type-badge" :style="{ background: color }">{{ type }}</span>',
}

const PokemonCard = {
  components: { TypeBadge },
  props: { member: Object },
  template: `
    <el-card class="page-card" shadow="hover">
      <template #header>
        <div class="pkm-head">
          <span class="pkm-name">{{ member.species }}</span>
          <span v-if="member.level" class="pkm-level">Lv.{{ member.level }}</span>
        </div>
      </template>
      <div class="pkm-types">
        <TypeBadge v-for="t in member.types || []" :key="t" :type="t" />
      </div>
      <div class="pkm-line" v-if="member.item"><b>道具：</b>{{ member.item }}</div>
      <div class="pkm-line" v-if="member.ability"><b>特性：</b>{{ member.ability }}</div>
      <div class="pkm-line" v-if="member.nature"><b>性格：</b>{{ member.nature }}</div>
      <div class="pkm-moves" v-if="member.moves && member.moves.length">
        <el-tag v-for="m in member.moves" :key="m" size="small" effect="plain" class="move-tag">{{ m }}</el-tag>
      </div>
      <slot />
    </el-card>
  `,
}

const App = {
  computed: {
    activeMenu() {
      const path = this.$route.path
      if (path.startsWith('/team-builder')) return '/team-builder'
      if (path.startsWith('/team/')) return '/team'
      if (path.startsWith('/battle')) return '/battle'
      if (path.startsWith('/lab')) return '/lab'
      if (path.startsWith('/analysis')) return '/analysis'
      if (path.startsWith('/orchestrator')) return '/orchestrator'
      return path
    },
  },
  template: `
    <el-container class="layout">
      <el-aside width="220px" class="sidebar">
        <div class="brand">
          <span class="brand-title">宝可梦对战助手</span>
          <span class="brand-sub">Pokemon Battle Assistant</span>
        </div>
        <el-menu
          :default-active="activeMenu"
          router
          class="side-menu"
          background-color="#1d2b36"
          text-color="#c7d3dc"
          active-text-color="#ffd04b"
        >
          <el-menu-item index="/"><el-icon><HomeFilled /></el-icon><span>首页</span></el-menu-item>
          <el-menu-item index="/team"><el-icon><Collection /></el-icon><span>队伍管理</span></el-menu-item>
          <el-menu-item index="/team-builder"><el-icon><MagicStick /></el-icon><span>AI 建队</span></el-menu-item>
          <el-menu-item index="/battle"><el-icon><Sword /></el-icon><span>对战面板</span></el-menu-item>
          <el-menu-item index="/lab"><el-icon><Odometer /></el-icon><span>实验室</span></el-menu-item>
          <el-menu-item index="/analysis"><el-icon><DataAnalysis /></el-icon><span>分析报告</span></el-menu-item>
          <el-menu-item index="/orchestrator"><el-icon><Refresh /></el-icon><span>闭环流程</span></el-menu-item>
        </el-menu>
      </el-aside>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  `,
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('./views/HomeView.js') },
    { path: '/team', name: 'team-list', component: () => import('./views/TeamList.js') },
    { path: '/team/:name', name: 'team-detail', component: () => import('./views/TeamDetail.js') },
    { path: '/team-builder', name: 'team-builder', component: () => import('./views/AITeamBuilder.js') },
    { path: '/battle', name: 'battle', component: () => import('./views/BattlePanel.js') },
    { path: '/lab', name: 'lab', component: () => import('./views/LabConsole.js') },
    { path: '/analysis', name: 'analysis', component: () => import('./views/AnalysisList.js') },
    { path: '/analysis/:id', name: 'analysis-detail', component: () => import('./views/AnalysisDetail.js') },
    { path: '/orchestrator', name: 'orchestrator', component: () => import('./views/ClosedLoopView.js') },
  ],
})

const app = createApp(App)
app.use(router)
app.use(ElementPlus, { locale: ElementPlus.lang && ElementPlus.lang.zh ? ElementPlus.lang.zh : undefined })
for (const [name, comp] of Object.entries(ElementPlusIconsVue)) {
  app.component(name, comp)
}
app.component('TypeBadge', TypeBadge)
app.component('PokemonCard', PokemonCard)
app.mount('#app')
