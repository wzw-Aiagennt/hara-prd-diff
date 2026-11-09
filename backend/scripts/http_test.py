"""接口级端到端测试 (需先启动 uvicorn)。

验证: health → 建 demo 会话 → SSE 流式 (meta/token/done) → 打回缺理由应 422 →
认可/带理由打回 → 导出 Word → 会话详情。
运行:  .venv\\Scripts\\python.exe scripts\\http_test.py
"""
import json
import re
import sys
from pathlib import Path

import httpx

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = "http://127.0.0.1:8000"


def _num(tag) -> int | None:
    m = re.search(r"(\d+)", str(tag))
    return int(m.group(1)) if m else None


def _asil_add(s: int, e: int, c: int) -> str:
    """ASIL 加法制 (用户追加规则): S+E+C 总分 10=D/9=C/8=B/7=A/其余=QM。"""
    return {10: "ASIL D", 9: "ASIL C", 8: "ASIL B", 7: "ASIL A"}.get(s + e + c, "QM")


def sse_collect(client: httpx.Client, sid: str) -> dict:
    got = {"meta": None, "tokens": 0, "done": None}
    with client.stream("GET", f"{BASE}/api/sessions/{sid}/stream") as resp:
        event = None
        for line in resp.iter_lines():
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data = line.split(":", 1)[1].strip()
                if event == "meta":
                    got["meta"] = json.loads(data)
                elif event == "token":
                    got["tokens"] += 1
                elif event == "done":
                    got["done"] = json.loads(data)
    return got


def main() -> int:
    with httpx.Client(timeout=60) as c:
        print("health:", c.get(f"{BASE}/api/health").json())

        sid = c.post(f"{BASE}/api/sessions/demo").json()["id"]
        print("demo session id:", sid)

        s = sse_collect(c, sid)
        assert s["meta"] and s["done"], "SSE 未收到 meta/done"
        print(f"SSE: diff条目={len(s['meta']['diff_items'])}, token块={s['tokens']}, findings={len(s['done']['findings'])}")
        cats = {}
        for f in s["done"]["findings"]:
            cats[f["category"]] = cats.get(f["category"], 0) + 1
        print("分类:", cats)
        assert {"reuse", "new", "removed"} <= set(cats), "三类判定未齐全"

        # 追加需求①: new 条目必须带具体拟新增危害事件 + SEC 打分; ASIL 需符合加法制
        for f in s["done"]["findings"]:
            if f["category"] == "new":
                hz = f.get("proposed_hazards") or []
                assert hz and hz[0].get("hazard_event") and hz[0].get("ASIL"), "新增分析缺少具体危害事件/打分"
                for h in hz:
                    sv, ev, cv = _num(h.get("S")), _num(h.get("E")), _num(h.get("C"))
                    if None not in (sv, ev, cv):
                        assert h["ASIL"] == _asil_add(sv, ev, cv), f"ASIL 不符合加法制: {h}"
        print("追加①通过: new 条目均含拟新增危害事件, 且 ASIL 符合 S+E+C 加法制")

        # 追加需求②: removed 条目必须定位到上传 HARA 的危害事件ID + 理由/处置
        removed = [f for f in s["done"]["findings"] if f["category"] == "removed"]
        assert removed and removed[0].get("hara_ref") and "HARA-01" in removed[0]["hara_ref"], "删减未定位到 HARA 危害事件ID"
        assert removed[0].get("hara_action") and removed[0].get("recommendation"), "删减缺少处置动作/理由"
        print(f"追加②通过: 删减定位 → {removed[0]['hara_ref']} ({removed[0]['hara_action']})")

        # 打回但缺理由 → 422
        r = c.post(f"{BASE}/api/sessions/{sid}/review", json={"approve": False, "reason": "   "})
        print("打回缺理由:", r.status_code, r.json().get("detail", "")[:30])
        assert r.status_code == 422

        # 带理由打回 → 200
        r = c.post(f"{BASE}/api/sessions/{sid}/review", json={"approve": False, "reason": "AI 未识别出底盘线束接口已更改"})
        print("带理由打回:", r.status_code, r.json()["review_status"])

        # 追加需求③: 打回后再次 stream → 第2轮, 应核实并采纳人工理由 (命中升级或 C-FB01 更新条目)
        s2 = sse_collect(c, sid)
        assert s2["meta"]["analysis_round"] == 2, f"轮次应为2, 实际 {s2['meta']['analysis_round']}"
        assert s2["meta"]["feedback_applied"], "应携带打回理由重分析"
        adopted = [f for f in s2["done"]["findings"] if f.get("feedback_adopted")]
        assert adopted, "重分析未体现核实并采纳人工理由 (feedback_adopted)"
        fb = next((f for f in adopted if f["change_id"] == "C-FB01"), None)
        if fb:
            assert fb.get("proposed_hazards") and fb.get("hara_action"), "未命中改动的理由也应据人工意见拟出具体更新内容"
        assert "重分析" in s2["done"]["summary"], "摘要应标注重分析轮次"
        print(f"追加③通过: 第2轮已核实并采纳人工理由, 采纳条目: {[f['change_id'] for f in adopted]}")

        # 导出 Word
        rp = c.get(f"{BASE}/api/sessions/{sid}/report")
        out = Path(__file__).resolve().parent / "downloaded_report.docx"
        out.write_bytes(rp.content)
        print("导出报告:", rp.status_code, "字节=", len(rp.content), "->", out)
        assert rp.status_code == 200 and len(rp.content) > 3000

        # 会话详情
        detail = c.get(f"{BASE}/api/sessions/{sid}").json()
        print("详情: review_status=", detail["review_status"], "含理由=", bool(detail["review_reason"]), "HARA列=", detail["hara_columns"])

    print("\n[OK] 后端端到端全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
