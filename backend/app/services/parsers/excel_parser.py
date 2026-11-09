"""旧 HARA (Excel 矩阵) 解析 (需求①), 使用 pandas。

HARA 通常以 Excel 矩阵记录。这里:
  1. 读取所有 sheet;
  2. 识别关键列 (危害事件 / S / E / C / ASIL / 安全目标 等, 支持中英文别名模糊匹配);
  3. 输出结构化 records + 供 AI 上下文的纯文本表示。
"""
from pathlib import Path
from typing import Any

import pandas as pd

# 关键列的别名匹配 (小写比较, 子串命中即可)
KEY_ALIASES: dict[str, list[str]] = {
    "id": ["编号", "序号", "id", "no", "条目", "no."],
    "hazard_event": ["危害事件", "hazard", "安全相关危害", "危险事件"],
    "function": ["功能", "function", "项功能", "item function"],
    "S": ["s", "严重度", "severity"],
    "E": ["e", "暴露率", "暴露", "exposure"],
    "C": ["c", "可控性", "可控", "controllability"],
    "asil": ["asil", "安全完整性", "asil 等级"],
    "safety_goal": ["安全目标", "safety goal", "sg"],
    "safety_requirement": ["安全需求", "safety requirement", "csr", "功能安全需求"],
}


def _match_header(header: str) -> str | None:
    """把 Excel 表头映射到标准字段名。返回 None 表示非关键字段。"""
    h = str(header).strip().lower()
    if not h:
        return None
    for std, aliases in KEY_ALIASES.items():
        for a in aliases:
            if a in h:
                return std
    return None


def extract(path: Path | str) -> dict[str, Any]:
    """解析 HARA Excel, 返回 {columns, records, text}。

    records: [{标准字段: 值, "_row": 行号, "_sheet": sheet名}, ...]
    text:    给 AI 的可读上下文 (每条目一行)。
    """
    path = Path(path)
    xls = pd.ExcelFile(path)
    records: list[dict[str, Any]] = []
    columns_seen: set[str] = set()

    for sheet in xls.sheet_names:
        # 不假设表头在第一行: 读原始, 再在前若干行里找含关键词的行作为表头
        raw = pd.read_excel(xls, sheet_name=sheet, header=None, dtype=object)
        if raw.empty:
            continue
        header_idx = _find_header_row(raw)
        if header_idx is None:
            continue
        headers = raw.iloc[header_idx].tolist()
        # 建立 列号 -> 标准字段 映射
        col_map = {ci: _match_header(h) for ci, h in enumerate(headers) if _match_header(h)}
        if not col_map:
            continue
        data = raw.iloc[header_idx + 1:]
        for r_off, row in data.iterrows():
            rec: dict[str, Any] = {"_row": int(r_off) + 1, "_sheet": sheet}
            has_value = False
            for ci, std in col_map.items():
                val = row.iloc[ci] if ci < len(row) else None
                if pd.isna(val):
                    val = None
                else:
                    val = str(val).strip() or None
                    has_value = has_value or val is not None
                rec[std] = val
                columns_seen.add(std)
            if has_value:
                records.append(rec)

    text = _records_to_text(records)
    return {
        "columns": sorted(columns_seen),
        "records": records,
        "text": text,
        "record_count": len(records),
    }


def _find_header_row(raw: pd.DataFrame) -> int | None:
    """在前 15 行里寻找包含最多可识别关键列的行作为表头。"""
    best_idx, best_hits = None, 0
    for i in range(min(15, len(raw))):
        hits = sum(1 for cell in raw.iloc[i].tolist() if _match_header(cell))
        if hits > best_hits:
            best_hits, best_idx = hits, i
    return best_idx if best_hits >= 1 else None


def _records_to_text(records: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for r in records:
        parts = [f"{k}={r[k]}" for k in ("id", "hazard_event", "function", "S", "E", "C", "asil", "safety_goal", "safety_requirement") if r.get(k)]
        if parts:
            lines.append(f"[{r['_sheet']} 行{r['_row']}] " + "; ".join(parts))
    return "\n".join(lines)
