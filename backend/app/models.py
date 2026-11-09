"""SQLAlchemy 数据模型: 一次分析会话 = 一条 AnalysisSession。

字段按需求分块:
  ① 上传解析: old/new PRD 文本、HARA 结构化结果
  ② 差异:     diff_json (difflib 逐句改动对)
  ③ AI 结论:  structured_json (分类结论 + S/E/C) / ai_conclusion (流式全文)
  ⑤ 人工判断: review_status / review_reason
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now()


class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)

    # ---- ① 文件与解析结果 ----
    old_prd_name: Mapped[str] = mapped_column(String(255), default="")
    new_prd_name: Mapped[str] = mapped_column(String(255), default="")
    hara_name: Mapped[str] = mapped_column(String(255), default="")
    old_prd_text: Mapped[str] = mapped_column(Text, default="")
    new_prd_text: Mapped[str] = mapped_column(Text, default="")
    hara_json: Mapped[str] = mapped_column(Text, default="{}")  # {columns, records, text}

    # ---- ② 差异 ----
    diff_json: Mapped[str] = mapped_column(Text, default="[]")  # [{change_id,type,before,after}]

    # ---- ③ AI 结论 ----
    ai_conclusion: Mapped[str] = mapped_column(Text, default="")  # 流式全文 (markdown)
    structured_json: Mapped[str] = mapped_column(Text, default="{}")  # {summary, findings}
    analyzed: Mapped[int] = mapped_column(DateTime, nullable=True)
    # 分析轮次 (追加需求③): 每次 stream 分析 +1; >1 时若上轮被打回则携带反馈重分析
    analysis_round: Mapped[int] = mapped_column(Integer, default=0)

    # ---- ⑤ 人工判断 ----
    review_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|approved|rejected
    review_reason: Mapped[str] = mapped_column(Text, default="")
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    # ---- 元信息 ----
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
