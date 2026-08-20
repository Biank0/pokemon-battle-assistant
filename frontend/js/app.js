/* 应用入口：路由 + 布局挂载 */
const { createApp, computed } = Vue;
const { createRouter, createWebHashHistory, useRoute } = VueRouter;

const routes = [
  { path: "/", component: HomeView },
  { path: "/generate", component: GenerateView },
  { path: "/teams", component: TeamsView },
  { path: "/teams/:name", component: TeamDetailView, props: true },
  { path: "/lab", component: LabView },
  { path: "/lab/battle/:id", component: BattleDetailView, props: true },
  { path: "/analyses", component: AnalysesView },
  { path: "/analyses/:id", component: AnalysisDetailView, props: true },
  { path: "/settings", component: SettingsView },
];

const router = createRouter({ history: createWebHashHistory(), routes });

const app = createApp({
  setup() {
    const route = useRoute();
    const active = computed(() => {
      if (route.path.startsWith("/teams")) return "/teams";
      if (route.path.startsWith("/lab")) return "/lab";
      if (route.path.startsWith("/analyses")) return "/analyses";
      if (route.path.startsWith("/settings")) return "/settings";
      return route.path;
    });
    return { active };
  },
});

app.use(router);
app.use(ElementPlus, { locale: ElementPlusLocaleZhCn });
app.component("type-badge", TypeBadge);
app.component("pokemon-card", PokemonCard);
app.mount("#app");
