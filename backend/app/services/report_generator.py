"""Word 报告生成 (需求⑥), 使用 docxtpl。

防坑: 不让 AI 直接输出整篇 Word。AI 只产出结构化 JSON (findings),
这里用标准模板 (templates/report_template.docx, 含 {{variable}} 与表格循环) 套版。
"""
from pathlib import Path
from typing import Any

from docxtpl import DocxTemplate

from ..config import settings

_RISK_LABEL = {"high": "高", "medium": "中", "low": "低"}


def _sec_text(sec: dict | None) -> str:
    if not sec:
        return "—"
    return f"S:{sec.get('S') or '-'} / E:{sec.get('E') or '-'} / C:{sec.get('C') or '-'} / ASIL:{sec.get('ASIL') or '-'}"


def _hazards_text(hazards: list[dict] | None) -> str:
    """拟新增危害事件多行文本 (追加需求①进入 Word 报告)。"""
    if not hazards:
        return "—"
    lines = []
    for hz in hazards:
        lines.append(
            f"{hz.get('event_id', '')}「{hz.get('hazard_event', '')}」"
            f" 场景: {hz.get('scenario', '-')} | S={hz.get('S', '-')}/E={hz.get('E', '-')}/C={hz.get('C', '-')} → {hz.get('ASIL', '-')}"
        )
    return "\n".join(lines)


def _hara_cell(finding: dict) -> str:
    """现有 HARA 定位 + 处置动作 (追加需求②进入报告)。"""
    ref = finding.get("hara_ref")
    action = finding.get("hara_action") or ""
    if ref:
        return f"{ref}\n处置: {action}"
    return action or "—"


def build_context(session: Any, conclusion: dict, review_status: str, review_reason: str) -> dict:
    findings_ctx: list[dict] = []
    for f in conclusion.get("findings", []):
        findings_ctx.append(
            {
                "change_id": f.get("change_id", ""),
                "category_label": f.get("category_label", ""),
                "risk": _RISK_LABEL.get(f.get("risk_level", "low"), f.get("risk_level", "")),
                "before": f.get("before") or "(无 / 新增)",
                "after": f.get("after") or "(无 / 已删除)",
                "impact": f.get("impact", ""),
                "sec_text": _sec_text(f.get("sec")),
                "hara_ref": _hara_cell(f),
                "hazards_text": _hazards_text(f.get("proposed_hazards")),
                "recommendation": ((f.get("recommendation", "")) + (" | " + f["recheck_note"] if f.get("recheck_note") else "")),
            }
        )

    review_label = {"approved": "✅ 已认可", "rejected": "⛔ 不认可 / 已打回", "pending": "⏳ 待审核"}.get(review_status, review_status)

    return {
        "session_id": session.id,
        "generated_at": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "analysis_round": conclusion.get("analysis_round", 1),
        "old_prd_name": session.old_prd_name,
        "new_prd_name": session.new_prd_name,
        "hara_name": session.hara_name,
        "summary": conclusion.get("summary", ""),
        "findings": findings_ctx,
        "review_status_label": review_label,
        "review_reason": review_reason or "(无)",
        "human_note_block": "有" if review_reason else "无",
    }


def generate(session: Any, conclusion: dict, review_status: str, review_reason: str, out_path: Path | None = None) -> Path:
    if not settings.template_path.exists():
        raise FileNotFoundError(
            f"未找到 Word 模板: {settings.template_path}。请先运行 scripts/make_template.py 生成模板。"
        )
    out_path = out_path or (settings.reports_dir / f"report_{session.id}.docx")
    doc = DocxTemplate(str(settings.template_path))
    context = build_context(session, conclusion, review_status, review_reason)
    doc.render(context)
    doc.save(str(out_path))
    return out_path
