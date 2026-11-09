"""后端核心逻辑冒烟测试 (不依赖 HTTP)。

验证: 示例数据 → difflib 差异 → Mock 三分类 → Markdown → docxtpl 报告生成。
运行:  .venv\\Scripts\\python.exe scripts\\smoke_test.py
"""
import sys
import uuid
from pathlib import Path

# Windows 控制台默认 gbk, 无法打印 emoji, 统一切到 utf-8
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import differ, llm_client, report_generator  # noqa: E402
from app.services.demo_data import HARA, NEW_PRD, OLD_PRD  # noqa: E402


class _FakeSession:
    def __init__(self):
        self.id = uuid.uuid4().hex
        self.old_prd_name = "示例_旧PRD.docx"
        self.new_prd_name = "示例_新PRD.docx"
        self.hara_name = "示例_旧HARA.xlsx"


def main() -> int:
    diff = differ.compute_diff(OLD_PRD, NEW_PRD)
    print(f"差异条目数: {len(diff)}")
    for d in diff:
        print(f"  {d['change_id']} [{d['type']}] 前: {d['before'][:30]!r} 后: {d['after'][:30]!r}")

    conclusion = llm_client.analyze(diff, HARA)
    cats = {}
    for f in conclusion["findings"]:
        cats[f["category"]] = cats.get(f["category"], 0) + 1
    print("分类统计:", cats)
    print("摘要:", conclusion["summary"])

    md = llm_client.render_markdown(conclusion)
    assert "新增分析" in md and "删减分析" in md and "完全复用" in md, "三类判定未齐全"

    s = _FakeSession()
    out = report_generator.generate(s, conclusion, "rejected", "AI 未识别底盘线束接口变更 (冒烟测试)")
    print("报告已生成:", out, "存在:", Path(out).exists())

    print("\n---- Markdown 预览 (前 600 字) ----")
    print(md[:600])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
