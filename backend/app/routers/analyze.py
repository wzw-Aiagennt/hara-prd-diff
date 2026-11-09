"""差异比对 + AI 流式结论 (需求②③④ + 追加需求③)。

GET /api/sessions/{sid}/stream  以 Server-Sent Events 推送:
  event: meta   -> 差异条目 + 摘要 + 分析轮次 (前端先渲染 diff 区)
  event: token  -> 结论文本增量 (打字机)
  event: done   -> 结构化结论 JSON (前端渲染结论卡片 + 供审核/导出)

追加需求③: 若上一轮结论被"不认可打回", 再次分析时自动将打回理由作为 feedback
注入推理, 结合人工意见重新判断; analysis_round 逐轮递增并持久化。
"""
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from ..config import settings
from ..database import SessionLocal
from ..models import AnalysisSession
from ..services import differ, llm_client

router = APIRouter(prefix="/api", tags=["analyze"])


def _persist(sid: str, conclusion: dict, raw_text: str) -> None:
    """deepseek 分支: 流式结束后把真实模型结论写回库 (供审核 / 报告)。"""
    db = SessionLocal()
    try:
        s = db.get(AnalysisSession, sid)
        if s:
            s.structured_json = json.dumps(conclusion, ensure_ascii=False)
            s.ai_conclusion = raw_text
            db.commit()
    finally:
        db.close()


@router.get("/sessions/{sid}/stream")
async def stream_analysis(sid: str):
    db = SessionLocal()
    try:
        s = db.get(AnalysisSession, sid)
        if not s:
            raise HTTPException(404, "会话不存在")
        old_text, new_text = s.old_prd_text, s.new_prd_text
        hara = json.loads(s.hara_json or "{}")

        # 追加需求③: 上轮被打回 → 本轮携带工程师纠正理由重新分析
        round_no = (s.analysis_round or 0) + 1
        feedback = s.review_reason if (s.review_status == "rejected" and s.review_reason) else None

        # ② 逐句差异
        diff_items = differ.compute_diff(old_text, new_text)
        s.diff_json = json.dumps(diff_items, ensure_ascii=False)

        provider = settings.llm_provider
        conclusion: dict
        markdown = ""
        if provider == "deepseek":
            # 真实模型: 结构化先由规则引擎兜底, 保证报告可用; 流式取模型原文 JSON
            conclusion = llm_client.analyze(diff_items, hara, feedback=feedback, round_no=round_no)
        else:
            # ③ Mock 规则引擎 (含反馈重分析)
            conclusion = llm_client.analyze(diff_items, hara, feedback=feedback, round_no=round_no)
            markdown = llm_client.render_markdown(conclusion)

        s.structured_json = json.dumps(conclusion, ensure_ascii=False)
        if markdown:
            s.ai_conclusion = markdown
        s.analyzed = datetime.now()
        s.analysis_round = round_no
        if feedback:
            # 反馈已在本轮消费: 审核状态回到待审核, 等待工程师对新一轮结论再次判断 (理由保留入报告历史)
            s.review_status = "pending"
        db.add(s)
        db.commit()
    finally:
        db.close()

    async def event_gen():
        yield {"event": "meta", "data": json.dumps(
            {"session_id": sid, "provider": provider, "diff_items": diff_items,
             "summary": conclusion.get("summary", ""), "analysis_round": round_no,
             "feedback_applied": bool(feedback)},
            ensure_ascii=False)}

        final_conclusion = conclusion
        if provider == "deepseek":
            acc: list[str] = []
            async for tok in llm_client.stream_deepseek(diff_items, hara, feedback=feedback):
                acc.append(tok)
                yield {"event": "token", "data": tok}
            raw = "".join(acc)
            try:
                final_conclusion = llm_client.parse_deepseek_json(raw)
            except Exception:
                final_conclusion = conclusion  # 解析失败保留规则兜底结论
            # 持久化真实模型结论与全文, 供后续审核 / 报告使用
            _persist(sid, final_conclusion, raw)
        else:
            async for tok in llm_client.stream(conclusion):
                yield {"event": "token", "data": tok}

        yield {"event": "done", "data": json.dumps(final_conclusion, ensure_ascii=False)}

    return EventSourceResponse(event_gen())
