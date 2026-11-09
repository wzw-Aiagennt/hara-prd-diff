"""Word (.docx) PRD 解析 (需求①)。

大模型无法直接读 Word, 这里用 python-docx 提取:
  - 段落文字 (含标题层级)
  - 表格: 逐行转 "列1 | 列2 | ..." 的简单文本, 保留单元格顺序

防坑: PRD 内的复杂流程图 (SmartArt / 图片) 无法转纯文本, 前期策略是
"只提取文字 + 简单表格", 图片/流程图留待后续多模态处理。
"""
from pathlib import Path

from docx import Document
from docx.document import Document as _Doc
from docx.table import Table
from docx.text.paragraph import Paragraph


def _iter_block_items(parent: _Doc):
    """按文档原始顺序迭代段落与表格。"""
    for child in parent.element.body.iterchildren():
        if child.tag.endswith("}p"):
            yield Paragraph(child, parent)
        elif child.tag.endswith("}tbl"):
            yield Table(child, parent)


def _table_to_text(table: Table) -> str:
    lines: list[str] = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            txt = " ".join(cell.text.split())
            cells.append(txt)
        # 去重相邻合并单元格 (python-docx 合并单元格会重复)
        dedup: list[str] = []
        for c in cells:
            if not dedup or c != dedup[-1]:
                dedup.append(c)
        line = " | ".join(dedup).strip(" |")
        if line:
            lines.append(line)
    return "\n".join(lines)


def extract_text(path: Path | str) -> str:
    """提取 docx 纯文本。表格内容以竖线分隔行追加在正文之后。"""
    path = Path(path)
    doc = Document(str(path))
    para_texts: list[str] = []
    table_texts: list[str] = []
    for block in _iter_block_items(doc):
        if isinstance(block, Paragraph):
            t = block.text.strip()
            if t:
                para_texts.append(t)
        elif isinstance(block, Table):
            tt = _table_to_text(block)
            if tt:
                table_texts.append(tt)

    out = "\n".join(para_texts)
    if table_texts:
        out += "\n\n[表格内容]\n" + "\n".join(table_texts)
    return out
