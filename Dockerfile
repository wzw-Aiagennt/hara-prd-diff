# ============================================================
# HARA / PRD 差异分析智能体 — 多阶段构建
# 前端 (Vue3+Vite) 构建静态文件 → 后端 (FastAPI) 挂载 → 单进程对外
# ============================================================

# ---------- Stage 1: 构建前端 ----------
FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --prefer-offline 2>/dev/null || npm install
COPY frontend/ .
RUN npm run build

# ---------- Stage 2: Python 后端 + 静态资源 ----------
FROM python:3.12-slim AS runtime

# 系统依赖 (pdfplumber 需要 libffi)
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 后端代码
COPY backend/ ./

# 前端构建产物 → backend/static/ (main.py 检测此目录自动挂载)
COPY --from=frontend-build /frontend/dist ./static

# 生成 Word 报告模板 (需 python-docx + docxtpl)
RUN cd /app && python scripts/make_template.py

# 数据持久化目录 (Render 持久磁盘挂载到此路径; 无磁盘则容器临时存储)
ENV STORAGE_DIR=/data
RUN mkdir -p /data

EXPOSE 8000

# Render 通过 PORT 环境变量注入端口; 本地默认 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
