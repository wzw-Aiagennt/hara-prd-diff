"""FastAPI 应用入口 (开发模式: API 服务; 生产模式: 同时挂载前端静态文件)。"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import init_db
from .routers import analyze, report, review, upload

# 前端构建产物目录 (Docker 构建后拷贝到 backend/static/)
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if not settings.template_path.exists():
        print(f"[warn] Word 模板缺失: {settings.template_path} —— 请运行 scripts/make_template.py 生成后再导出报告。")
    print(f"[ startup ] {settings.app_name} | LLM provider = {settings.llm_provider}")
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(analyze.router)
app.include_router(review.router)
app.include_router(report.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "llm_provider": settings.llm_provider}


# ---------- 生产模式: 挂载前端静态文件 + SPA Fallback ----------
if STATIC_DIR.exists():
    # Vite 构建产出 assets/ 目录 (js/css chunks)
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="static_assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        """所有非 /api 路径: 先尝试静态文件, 否则回 index.html (SPA 单页路由)。"""
        file = STATIC_DIR / full_path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(STATIC_DIR / "index.html")
