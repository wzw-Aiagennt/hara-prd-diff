"""PDF PRD 解析 (需求①), 使用 pdfplumber。

提取每页文字 + 简单表格。复杂流程图/图片同样无法转文本, 前期只取文字与表格。
"""
from pathlib import Path

import pdfplumber


def extract_text(path: Path | str) -> str:
    path = Path(path)
    page_texts: list[str] = []
    table_texts: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            if t.strip():
                page_texts.append(t.strip())
            for table in page.extract_tables():
                for row in table:
                    cells = [" ".join(str(c).split()) if c is not None else "" for c in row]
                    dedup: list[str] = []
                    for c in cells:
                        if not dedup or c != dedup[-1]:
                            dedup.append(c)
                    line = " | ".join(dedup).strip(" |")
                    if line:
                        table_texts.append(line)

    out = "\n".join(page_texts)
    if table_texts:
        out += "\n\n[表格内容]\n" + "\n".join(table_texts)
    return out
