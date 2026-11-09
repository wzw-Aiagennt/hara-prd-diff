"""文本句子切分。供 difflib 逐句比对使用 (需求②)。

按中英文句子结束符切分, 并折叠多余空白; 过滤空句。
"""
import re

# 中英文句子/行结束标点
_SPLIT_RE = re.compile(r"[。！？!?；;\n\r]+")
_WS_RE = re.compile(r"[ \t\u3000]+")


def normalize(text: str) -> str:
    """折叠空白, 保留单句内容。"""
    return _WS_RE.sub(" ", text).strip()


def split_sentences(text: str) -> list[str]:
    """将长文本切成"句子"列表, 每句去除首尾空白, 丢弃空句。"""
    if not text:
        return []
    parts = _SPLIT_RE.split(text)
    sentences: list[str] = []
    for p in parts:
        s = normalize(p)
        if s:
            sentences.append(s)
    return sentences
