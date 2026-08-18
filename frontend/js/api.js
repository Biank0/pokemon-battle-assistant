// Thin fetch wrapper around the FastAPI backend.
const { ElMessage } = ElementPlus

async function request(method, url, body) {
  let resp
  try {
    resp = await fetch(url, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch (err) {
    ElMessage.error('网络错误：无法连接后端服务（pba serve）')
    throw err
  }
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`
    try {
      const data = await resp.json()
      detail = data.detail || detail
    } catch {
      /* ignore parse error */
    }
    ElMessage.error(String(detail))
    throw new Error(String(detail))
  }
  return resp.json()
}

export const get = (url) => request('GET', url)
export const post = (url, body) => request('POST', url, body)
export const del = (url) => request('DELETE', url)

// ---- teams ----
export async function listTeams() {
  const data = await get('/api/teams')
  return data.teams
}
export async function getTeam(name) {
  // 返回完整 payload：{ name, display_name, team, team_zh }
  return get(`/api/teams/${name}`)
}
export async function deleteTeam(name) {
  return del(`/api/teams/${name}`)
}
export async function validateTeam(name, format) {
  return post(`/api/teams/${name}/validate`, { format: format || null })
}

// ---- team builder ----
export async function generateTeam(requirement, format) {
  return post('/api/team-builder/generate', { requirement, format })
}
export async function iterateTeam(team, report, format) {
  return post('/api/team-builder/iterate', { team, report, format })
}
export async function getBuilderHistory() {
  const data = await get('/api/team-builder/history')
  return data.history
}

// ---- battle ----
export async function startBattle(payload) {
  return post('/api/battle/start', payload)
}
export function getBattleStatus(jobId) {
  return get(`/api/battle/${jobId}/status`)
}
export function getBattleResult(jobId) {
  return get(`/api/battle/${jobId}/result`)
}

// ---- lab ----
export async function startLab(payload) {
  return post('/api/lab/start', payload)
}
export function getLabStatus(jobId) {
  return get(`/api/lab/${jobId}/status`)
}
export function getLabReport(jobId) {
  return get(`/api/lab/${jobId}/report`)
}

// ---- analysis ----
export function analyzeBattle(battleTag, depth) {
  return post(`/api/analysis/battle/${battleTag}`, { depth: depth || 'full', record: null })
}
export async function listAnalyses() {
  const data = await get('/api/analysis/list')
  return data.analyses
}
export function getAnalysis(analysisId) {
  return get(`/api/analysis/${analysisId}`)
}

// ---- orchestrator ----
export async function startLoop(payload) {
  return post('/api/orchestrator/start', payload)
}
export function getLoopStatus(runId) {
  return get(`/api/orchestrator/${runId}/status`)
}
export async function getLoopHistory(runId) {
  const data = await get(`/api/orchestrator/${runId}/history`)
  return data.iterations
}
export function confirmIteration(runId) {
  return post(`/api/orchestrator/${runId}/confirm`, {})
}

// ---- meta ----
export async function getFormats() {
  const data = await get('/api/formats')
  return data.formats
}
export function getHealth() {
  return get('/api/health')
}
