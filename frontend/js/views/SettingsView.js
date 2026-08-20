/* 设置页：LLM 连接配置（OpenAI 兼容协议三件套：key / base_url / model） */
const SettingsView = {
  template: `
  <div>
    <h2 class="page-title">设置</h2>
    <p class="page-desc">LLM 连接配置（OpenAI 兼容协议：POST {base_url}/chat/completions + Bearer 鉴权），保存后立即对新任务生效</p>

    <div class="block" style="max-width: 640px">
      <div class="block-title">API 配置</div>
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="API Key">
          <div class="set-key-row">
            <el-input v-model="apiKey" type="password" show-password
                      :placeholder="hasKey ? '当前 ' + masked + '（留空则不修改）' : 'sk-…'"></el-input>
            <el-tag v-if="hasKey" type="success" size="small" class="set-key-tag">已配置</el-tag>
            <el-tag v-else type="danger" size="small" class="set-key-tag">未配置</el-tag>
          </div>
        </el-form-item>
        <el-form-item label="Base URL（OpenAI 兼容端点）">
          <el-input v-model="baseUrl" placeholder="https://api.deepseek.com/v1"></el-input>
        </el-form-item>
        <el-form-item label="模型名">
          <el-input v-model="model" placeholder="deepseek-chat"></el-input>
        </el-form-item>
        <div class="set-actions">
          <el-button type="primary" :loading="saving" @click="save">保存配置</el-button>
          <el-button :loading="testing" @click="test">测试连接</el-button>
        </div>
      </el-form>

      <el-alert v-if="saved" type="success" :closable="false" show-icon class="set-result"
                title="已保存并生效" :description="'当前 Key：' + masked + ' ｜ ' + baseUrl + ' ｜ ' + model"></el-alert>
      <el-alert v-if="testResult === 'ok'" type="success" :closable="false" show-icon class="set-result"
                :title="'连接正常（' + testInfo + '）'" description=""></el-alert>
      <el-alert v-if="testResult === 'fail'" type="error" :closable="false" show-icon class="set-result"
                title="连接失败" :description="testInfo"></el-alert>
    </div>

    <div class="block" style="max-width: 640px">
      <div class="block-title">常见服务商</div>
      <div class="muted set-help">
        任何 OpenAI 兼容服务商均可：DeepSeek（默认）、OpenAI、月之暗面 Kimi、智谱 GLM、
        本地 Ollama（http://127.0.0.1:11434/v1）等。改 Base URL + 模型名即可切换。
      </div>
    </div>
  </div>`,
  data() {
    return { apiKey: "", masked: "", hasKey: false, baseUrl: "", model: "",
             saving: false, testing: false, saved: false,
             testResult: "", testInfo: "" };
  },
  async mounted() {
    try {
      const d = await API.get("/api/settings");
      this.masked = d.api_key_masked;
      this.hasKey = d.has_key;
      this.baseUrl = d.base_url;
      this.model = d.model;
    } catch (e) {
      this.$message.error("读取配置失败：" + String(e.message || e));
    }
  },
  methods: {
    apply(d) {
      this.masked = d.api_key_masked;
      this.hasKey = d.has_key;
      if (d.base_url) this.baseUrl = d.base_url;
      if (d.model) this.model = d.model;
    },
    async save() {
      this.saving = true;
      this.saved = false;
      try {
        this.apply(await API.post("/api/settings", {
          api_key: this.apiKey, base_url: this.baseUrl, model: this.model,
        }));
        this.apiKey = "";
        this.saved = true;
        this.$message.success("配置已保存");
      } catch (e) {
        this.$message.error(String(e.message || e));
      } finally { this.saving = false; }
    },
    async test() {
      this.testing = true;
      this.testResult = "";
      try {
        const d = await API.post("/api/settings/test");
        this.testResult = "ok";
        this.testInfo = d.model + " 回复「" + d.reply + "」";
      } catch (e) {
        this.testResult = "fail";
        this.testInfo = String(e.message || e);
      } finally { this.testing = false; }
    },
  },
};
