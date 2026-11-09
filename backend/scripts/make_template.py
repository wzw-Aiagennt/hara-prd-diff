"""生成标准 Word 报告模板 templates/report_template.docx (需求⑥)。

运行一次即可:  .venv\\Scripts\\python.exe scripts\\make_template.py
模板使用 docxtpl(Jinja2) 语法: {{variable}} 占位 + {%tr for %} 表格行循环。
"""
import sys
from pathlib import Path

# 允许从 backend/ 目录以脚本方式运行
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from docx.enum.table import WD_TABLE_ALIGNMENT  # noqa: E402
from docx.shared import Pt  # noqa: E402
from app.config import settings  # noqa: E402

COLUMNS = ["变更编号", "判定类别", "风险", "改动前", "改动后", "影响分析", "S/E/C·ASIL", "现有HARA定位与处置", "拟新增危害事件", "处置建议/理由"]


def _set(cell, text: str, bold: bool = False, size: int = 9) -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    run = p.add_run(text)
    run.bold = bold
    run.font.size = Pt(size)


def build() -> Path:
    from docx import Document

    doc = Document()
    doc.add_heading("PRD 变更 · HARA 影响分析报告", level=0)

    doc.add_paragraph("会话编号: {{ session_id }}    生成时间: {{ generated_at }}    分析轮次: 第 {{ analysis_round }} 轮")
    doc.add_paragraph("旧 PRD: {{ old_prd_name }}")
    doc.add_paragraph("新 PRD: {{ new_prd_name }}")
    doc.add_paragraph("旧 HARA: {{ hara_name }}")

    doc.add_heading("一、总体结论", level=1)
    doc.add_paragraph("{{ summary }}")

    doc.add_heading("二、逐条差异判定明细", level=1)

    table = doc.add_table(rows=1, cols=len(COLUMNS))
    table.style = "Light Grid Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    hdr = table.rows[0].cells
    for i, name in enumerate(COLUMNS):
        _set(hdr[i], name, bold=True)

    # for 标记行 (docxtpl 会移除该行并循环中间数据行)
    start = table.add_row().cells
    _set(start[0], "{%tr for f in findings %}")

    # 数据行
    data = table.add_row().cells
    _set(data[0], "{{ f.change_id }}")
    _set(data[1], "{{ f.category_label }}")
    _set(data[2], "{{ f.risk }}")
    _set(data[3], "{{ f.before }}")
    _set(data[4], "{{ f.after }}")
    _set(data[5], "{{ f.impact }}")
    _set(data[6], "{{ f.sec_text }}")
    _set(data[7], "{{ f.hara_ref }}")
    _set(data[8], "{{ f.hazards_text }}")
    _set(data[9], "{{ f.recommendation }}")

    # endfor 标记行
    end = table.add_row().cells
    _set(end[0], "{%tr endfor %}")

    doc.add_paragraph("")
    doc.add_heading("三、人工审核意见", level=1)
    doc.add_paragraph("审核状态: {{ review_status_label }}")
    doc.add_paragraph("纠正理由 / 备注: {{ review_reason }}")
    doc.add_paragraph(
        "说明: 本报告由差异比对工具(difflib) + 基于 GB/T 34590 的分析智能体自动生成, "
        "并经功能安全工程师人工复核。打回意见已完整记录于上。"
    )

    out = settings.template_path
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    return out


if __name__ == "__main__":
    path = build()
    print(f"[ok] Word 模板已生成: {path}")
