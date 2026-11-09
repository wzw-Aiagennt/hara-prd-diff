"""Pydantic 请求/响应模型。"""
from datetime import datetime

from pydantic import BaseModel, Field


class SecRating(BaseModel):
    """GB/T 34590 S/E/C/ASIL 评估建议。"""

    S: str | None = None
    E: str | None = None
    C: str | None = None
    ASIL: str | None = None
    rationale: str | None = None


class HazardItem(BaseModel):
    """拟新增危害事件 (追加需求①)。"""

    event_id: str
    hazard_event: str
    scenario: str = ""
    S: str | None = None
    E: str | None = None
    C: str | None = None
    ASIL: str | None = None
    rationale: str | None = None


class Finding(BaseModel):
    change_id: str
    category: str = Field(..., description="reuse | new | removed")
    category_label: str = Field(..., description="完全复用 | 新增分析 | 删减分析")
    before: str = ""
    after: str = ""
    impact: str = ""
    risk_level: str = "low"  # high | medium | low
    hara_ref: str | None = None
    hara_action: str | None = Field(None, description="无需变更 | 新增HARA条目 | 修改现有HARA | 删除/归档 | 需人工定位")
    sec: SecRating | None = None
    proposed_hazards: list[HazardItem] | None = None
    recheck_note: str | None = None
    feedback_adopted: bool | None = Field(None, description="追加③: 本条是否为核实并采纳工程师打回理由后的更新")
    recommendation: str = ""
    gbt_ref: str | None = None


class StructuredConclusion(BaseModel):
    summary: str = ""
    findings: list[Finding] = []
    round_note: str = ""
    analysis_round: int = 1


class DiffItem(BaseModel):
    change_id: str
    type: str  # replace | insert | delete
    before: str = ""
    after: str = ""


class ReviewRequest(BaseModel):
    approve: bool
    reason: str = ""


class SessionMeta(BaseModel):
    id: str
    old_prd_name: str
    new_prd_name: str
    hara_name: str
    created_at: datetime
    review_status: str
    analyzed: bool

    model_config = {"from_attributes": True}


class SessionDetail(SessionMeta):
    diff_items: list[DiffItem] = []
    conclusion: StructuredConclusion | None = None
    ai_conclusion_text: str = ""
    review_reason: str = ""
    hara_columns: list[str] = []
    hara_record_count: int = 0
    analysis_round: int = 0
