"""按扩展名分发到对应解析器 (需求①)。"""
from pathlib import Path

from . import docx_parser, excel_parser, pdf_parser

DOCX_EXT = {".docx"}
PDF_EXT = {".pdf"}
EXCEL_EXT = {".xlsx", ".xlsm", ".xls"}


def extract_document(path: Path | str) -> str:
    """PRD (Word/PDF) → 纯文本。"""
    ext = Path(path).suffix.lower()
    if ext in DOCX_EXT:
        return docx_parser.extract_text(path)
    if ext in PDF_EXT:
        return pdf_parser.extract_text(path)
    if ext in EXCEL_EXT:
        # 兜底: 若把表格型 PRD 传成 Excel, 也用其 text 表示
        return excel_parser.extract(path)["text"]
    raise ValueError(f"不支持的 PRD 文件类型: {ext}")


def extract_hara(path: Path | str) -> dict:
    """旧 HARA (Excel) → 结构化 dict。"""
    ext = Path(path).suffix.lower()
    if ext not in EXCEL_EXT:
        raise ValueError(f"HARA 需为 Excel 文件 (.xlsx/.xls), 当前: {ext}")
    return excel_parser.extract(path)
