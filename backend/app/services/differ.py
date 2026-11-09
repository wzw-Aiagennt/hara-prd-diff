"""差异比对 (需求②)。

核心防坑: 不把两份几万字长文直接扔给 AI。先用 difflib 做"逐句"比对,
只提取真正改动的句子对 (改动前 / 改动后), 再交给 AI 判断影响。

细化: difflib 的 replace opcode 会把"连续多句改动"合并成一个大块, 直接
当作一条 diff 会过粗 (例如"删除夜视"被吞进"车速变更"块)。这里在 replace
块内按句子相似度做贪心配对, 拆成逐条: 相似句 → replace, 未匹配旧句 → delete,
未匹配新句 → insert。从而让每一处真实改动各自独立判定。

输出: [{change_id, type, before, after}]  type: replace | insert | delete
"""
import difflib

from ..utils.text_split import split_sentences

# 两句视为"同一处的修改"的最低相似度
_MATCH_THRESHOLD = 0.5


def _ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(a=a, b=b, autojunk=False).ratio()


def compute_diff(old_text: str, new_text: str) -> list[dict]:
    old_sents = split_sentences(old_text)
    new_sents = split_sentences(new_text)

    sm = difflib.SequenceMatcher(a=old_sents, b=new_sents, autojunk=False)
    raw: list[tuple[str, str, str]] = []  # (type, before, after)

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag == "delete":
            raw += [("delete", s, "") for s in old_sents[i1:i2]]
        elif tag == "insert":
            raw += [("insert", "", s) for s in new_sents[j1:j2]]
        elif tag == "replace":
            raw += _pair_block(old_sents[i1:i2], new_sents[j1:j2])

    return [
        {"change_id": f"C-{n:03d}", "type": t, "before": b, "after": a}
        for n, (t, b, a) in enumerate(raw, start=1)
    ]


def _pair_block(old_block: list[str], new_block: list[str]) -> list[tuple[str, str, str]]:
    """在 replace 块内按相似度贪心配对, 拆成逐条改动。"""
    used_new = [False] * len(new_block)
    results: list[tuple[str, str, str]] = []

    for o in old_block:
        best_j, best_r = -1, 0.0
        for j, n in enumerate(new_block):
            if used_new[j]:
                continue
            r = _ratio(o, n)
            if r > best_r:
                best_r, best_j = r, j
        if best_j >= 0 and best_r >= _MATCH_THRESHOLD:
            used_new[best_j] = True
            results.append(("replace", o, new_block[best_j]))
        else:
            results.append(("delete", o, ""))

    for j, n in enumerate(new_block):
        if not used_new[j]:
            results.append(("insert", "", n))

    return results
