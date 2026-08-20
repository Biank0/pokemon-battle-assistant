"""FastAPI 应用：API 路由 + 前端静态托管。

路由结构（全部挂在 /api 下，其余路径由 frontend/ 静态服务）：
  GET  /api/teams            队伍列表
  GET  /api/teams/{name}     队伍详情（中文渲染，JOIN dex）
  POST /api/generate         发起 AI 建队（后台线程跑流水线）
  GET  /api/generate/{id}    轮询建队任务进度/结果
  POST /api/lab/start        发起对战跑量会话（后台线程）
  GET  /api/lab/sessions     历史会话列表
  GET  /api/lab/session/{id} 会话进度 + 逐场结果 + 聚合统计
  GET  /api/lab/battle/{id}  单场逐回合明细（中文渲染）
  POST /api/analyze          发起对战分析（后台线程）
  GET  /api/analyze/{id}     轮询分析任务进度/结果
  GET  /api/analyses         分析报告列表
  GET  /api/analyses/{id}    分析报告详情（结构化 + 高光跳转）
  GET  /api/settings         LLM 连接配置（key 打码）
  POST /api/settings         更新配置（写 .env，立即生效）
  POST /api/settings/test    连接测试（最小 LLM 调用）
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routes import analyze, generate, lab, settings, teams

ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIR = ROOT / "frontend"

app = FastAPI(title="宝可梦对战助手")
app.include_router(teams.router, prefix="/api")
app.include_router(generate.router, prefix="/api")
app.include_router(lab.router, prefix="/api")
app.include_router(analyze.router, prefix="/api")
app.include_router(settings.router, prefix="/api")


@app.middleware("http")
async def no_cache_html(request, call_next):
    """HTML 不缓存（JS 走 index.html 的版本参数控制），避免前端更新后浏览器拿旧页面。"""
    resp = await call_next(request)
    if "text/html" in resp.headers.get("content-type", ""):
        resp.headers["Cache-Control"] = "no-cache"
    return resp

# 前端静态托管（html=True：访问 / 返回 index.html）
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
