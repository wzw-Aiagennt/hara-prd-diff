"""人工判断路由 (需求⑤)。

认可 -> review_status=approved (可导出)
不认可并打回 -> review_status=rejected, 且必须填写纠正理由 (强制), 理由进入最终报表。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AnalysisSession
from ..schemas import ReviewRequest

router = APIRouter(prefix="/api", tags=["review"])


@router.post("/sessions/{sid}/review")
def review(sid: str, body: ReviewRequest, db: Session = Depends(get_db)) -> dict:
    s = db.get(AnalysisSession, sid)
    if not s:
        raise HTTPException(404, "会话不存在")
    if not s.analyzed:
        raise HTTPException(400, "请先完成 AI 分析再进行人工判断")

    if not body.approve and not body.reason.strip():
        # 强制: 不认可必须给出纠正理由
        raise HTTPException(422, "打回时必须填写纠正理由 (例如: AI 未识别出底盘线束接口已更改)")

    s.review_status = "approved" if body.approve else "rejected"
    s.review_reason = body.reason.strip()
    s.reviewed_at = datetime.now()
    db.commit()
    return {"id": s.id, "review_status": s.review_status, "review_reason": s.review_reason}
