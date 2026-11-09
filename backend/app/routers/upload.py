"""上传 / 会话管理路由 (需求①)。"""
import json
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import AnalysisSession
from ..schemas import SessionDetail, SessionMeta
from ..services.demo_data import HARA as DEMO_HARA
from ..services.demo_data import NEW_PRD, OLD_PRD
from ..services.parsers import dispatch

router = APIRouter(prefix="/api", tags=["upload"])

_ALLOWED_PRD = {".docx", ".pdf"}
_ALLOWED_HARA = {".xlsx", ".xlsm", ".xls"}


def _save_upload(upload: UploadFile, dest_dir: Path, allowed: set[str]) -> Path:
    name = upload.filename or "unnamed"
    ext = Path(name).suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, f"文件 {name} 类型不支持, 允许: {sorted(allowed)}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{uuid.uuid4().hex[:6]}_{name}"
    with path.open("wb") as fh:
        shutil.copyfileobj(upload.file, fh)
    return path


def _to_meta(s: AnalysisSession) -> dict:
    return {
        "id": s.id,
        "old_prd_name": s.old_prd_name,
        "new_prd_name": s.new_prd_name,
        "hara_name": s.hara_name,
        "created_at": s.created_at,
        "review_status": s.review_status,
        "analyzed": bool(s.analyzed),
    }


@router.post("/sessions", response_model=SessionMeta)
async def create_session(
    old_prd: UploadFile = File(...),
    new_prd: UploadFile = File(...),
    hara: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> SessionMeta:
    """接收 2 份 PRD + 1 份 HARA, 解析后建立分析会话。"""
    sid = uuid.uuid4().hex
    updir = settings.uploads_dir / sid
    try:
        p_old = _save_upload(old_prd, updir, _ALLOWED_PRD)
        p_new = _save_upload(new_prd, updir, _ALLOWED_PRD)
        p_hara = _save_upload(hara, updir, _ALLOWED_HARA)

        old_text = dispatch.extract_document(p_old)
        new_text = dispatch.extract_document(p_new)
        hara_obj = dispatch.extract_hara(p_hara)
    except HTTPException:
        raise
    except Exception as exc:  # 解析失败
        raise HTTPException(422, f"文件解析失败: {exc}") from exc

    sess = AnalysisSession(
        id=sid,
        old_prd_name=old_prd.filename or "",
        new_prd_name=new_prd.filename or "",
        hara_name=hara.filename or "",
        old_prd_text=old_text,
        new_prd_text=new_text,
        hara_json=json.dumps(hara_obj, ensure_ascii=False),
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return SessionMeta.model_validate(_to_meta(sess))


@router.post("/sessions/demo", response_model=SessionMeta)
def create_demo_session(db: Session = Depends(get_db)) -> SessionMeta:
    """无需上传文件, 直接载入内置示例 (含车速/ODD/删除/文案 4 类改动)。"""
    sess = AnalysisSession(
        old_prd_name="示例_旧PRD_ACC.docx",
        new_prd_name="示例_新PRD_ACC.docx",
        hara_name="示例_旧HARA_ACC.xlsx",
        old_prd_text=OLD_PRD,
        new_prd_text=NEW_PRD,
        hara_json=json.dumps(DEMO_HARA, ensure_ascii=False),
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return SessionMeta.model_validate(_to_meta(sess))


@router.get("/sessions", response_model=list[SessionMeta])
def list_sessions(db: Session = Depends(get_db)) -> list[SessionMeta]:
    rows = db.query(AnalysisSession).order_by(AnalysisSession.created_at.desc()).all()
    return [SessionMeta.model_validate(_to_meta(r)) for r in rows]


@router.get("/sessions/{sid}", response_model=SessionDetail)
def get_session(sid: str, db: Session = Depends(get_db)) -> SessionDetail:
    s = db.get(AnalysisSession, sid)
    if not s:
        raise HTTPException(404, "会话不存在")
    hara_obj = json.loads(s.hara_json or "{}")
    detail = SessionDetail(
        **_to_meta(s),
        diff_items=json.loads(s.diff_json or "[]"),
        conclusion=json.loads(s.structured_json) if s.structured_json and s.structured_json != "{}" else None,
        ai_conclusion_text=s.ai_conclusion or "",
        review_reason=s.review_reason or "",
        hara_columns=hara_obj.get("columns", []),
        hara_record_count=hara_obj.get("record_count", 0),
        analysis_round=s.analysis_round or 0,
    )
    return detail
