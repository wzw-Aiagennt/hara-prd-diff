"""报告导出路由 (需求⑥): docxtpl 套版生成 Word 并下载。"""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AnalysisSession
from ..services import report_generator

router = APIRouter(prefix="/api", tags=["report"])


@router.get("/sessions/{sid}/report")
def export_report(sid: str, db: Session = Depends(get_db)) -> FileResponse:
    s = db.get(AnalysisSession, sid)
    if not s:
        raise HTTPException(404, "会话不存在")
    if not s.analyzed:
        raise HTTPException(400, "请先完成 AI 分析再导出报告")

    conclusion = json.loads(s.structured_json or "{}")
    out = Path(report_generator.generate(s, conclusion, s.review_status, s.review_reason))
    filename = f"HARA差异分析报告_{sid[:8]}.docx"
    return FileResponse(str(out), filename=filename,
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
