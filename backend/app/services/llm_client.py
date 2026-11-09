"""推理客户端 (需求③ + 追加需求①②③)。

两种后端:
  - mock (默认): 内置规则引擎, 按 prompts.SYSTEM_PROMPT 的判定路径分类, 无需 API Key。
  - deepseek: OpenAI 兼容协议流式调用真实模型。

追加需求落地:
  ① "新增分析" 必须给出具体拟新增的危害事件及 S/E/C/ASIL 打分 (proposed_hazards)。
  ② "删减/变更" 必须定位到上传 HARA 中的危害事件 ID + 处置动作与理由 (hara_ref + hara_action)。
     —— 用 2~3 字 n-gram 对 HARA 各字段打分匹配, 不再只依赖固定特征词表。
  ③ 支持结合工程师"打回理由"重新分析 (feedback + round_no):
     核实并采纳人工理由 —— 命中的改动项升级为"新增分析"重评 S/E/C; 即便理由未命中具体改动,
     也默认采信工程师领域判断, 据其定位现有 HARA 并拟出具体新增/修改危害事件与打分, 更新对应内容。

ASIL 评分采用加法制 (用户追加规则): S+E+C 总分 10=D / 9=C / 8=B / 7=A / 其余=QM。
"""
import asyncio
import json
import re
from collections.abc import AsyncIterator

from ..config import settings
from . import prompts

# ---------- 关键词库 ----------
SAFETY_NEW_KEYWORDS = [
    "km/h", "kmh", "车速", "速度", "odd", "运行设计域", "运行场景", "场景", "高速",
    "匝道", "施工", "夜间", "制动", "转向", "驱动", "加速", "传感器", "雷达", "摄像头",
    "激光雷达", "超声波", "执行器", "ecu", "控制器", "线束", "接口", "can", "以太网",
    "总线", "冗余", "降级", "故障", "安全机制", "仲裁", "接管",
]
UI_KEYWORDS = [
    "ui", "界面", "文字", "提示", "文案", "措辞", "图标", "显示", "字体", "颜色",
    "弹窗", "语音播报", "菜单", "按钮", "布局", "标识",
]
FEATURE_WORDS = ["夜视", "巡航", "自动泊车", "制动", "转向", "aeb", "acc", "lka", "esp", "传感器", "高速", "匝道"]

_SPEED_RE = re.compile(r"(\d+)\s*[-~至]\s*(\d+)\s*km\s*/?\s*h", re.I)
_CJK_RE = re.compile(r"[\u4e00-\u9fa5A-Za-z]+")

# 从打回理由中提取"领域关键词": 与安全词表 + 常见底盘/接口词取交集
_FB_EXTRA_WORDS = ["线束", "接口", "底盘", "制动", "转向", "传感器", "车速", "匝道", "高速", "夜视", "总线", "冗余"]

# ---------- 拟新增危害事件模板库 (追加需求①) ----------
# (触发关键词, 危害事件, 触发场景, (S,E,C))
_HAZARD_TEMPLATES = [
    (["车速", "km/h", "速度"], "车速运行范围扩大后, 跟车距离控制不足或目标切割识别不及时导致追尾", "高速主干道跟车 (上限提高)", (3, 4, 2)),
    (["匝道", "汇入", "合流"], "匝道汇入时相邻车道切入目标识别延迟导致碰撞", "匝道汇入/合流", (3, 3, 2)),
    (["高速"], "高速工况下系统横向/纵向控制偏差导致偏离车道或追尾", "高速运行", (3, 4, 2)),
    (["传感器", "雷达", "摄像头", "激光雷达"], "前向传感器失效或误识别导致错误制动/加速", "前向感知失效", (3, 3, 3)),
    (["线束", "接口", "ecu", "控制器", "总线", "can", "以太网"], "安全相关ECU间通信/接口故障导致功能丢失或异常激活", "跨域通信/接口失效", (3, 3, 3)),
    (["制动"], "非预期制动或制动失效导致后车追尾", "紧急制动工况", (3, 3, 2)),
    (["转向"], "非预期转向介入导致偏离车道碰撞", "转向干预", (3, 3, 3)),
    (["夜间", "夜视", "施工"], "低光照/非结构化场景下弱势道路使用者识别失效导致碰撞", "夜间/复杂环境", (3, 2, 3)),
]


# ---------- ASIL 评分 (加法制: S+E+C 总分映射, 用户追加规则) ----------
_ASIL_BY_SCORE = {10: "ASIL D", 9: "ASIL C", 8: "ASIL B", 7: "ASIL A"}


def _asil_score(s: int, e: int, c: int) -> str:
    """S(1~3)+E(1~4)+C(1~3) 相加: 10→ASIL D, 9→ASIL C, 8→ASIL B, 7→ASIL A, 其余(<7)→QM。"""
    return _ASIL_BY_SCORE.get(s + e + c, "QM")


def _has(text: str, kws: list[str]) -> list[str]:
    low = text.lower()
    return [k for k in kws if k.lower() in low]


# ---------- HARA 条目匹配 (追加需求②) ----------
def _grams(text: str) -> set[str]:
    """提取 2~3 字中文/字母片段的 n-gram, 用于与 HARA 字段做重叠打分。"""
    grams: set[str] = set()
    for seg in _CJK_RE.findall(text or ""):
        for n in (3, 2):
            grams.update(seg[i:i + n] for i in range(len(seg) - n + 1))
    return grams


def _match_hara_records(text: str, records: list[dict], top: int = 2) -> list[dict]:
    grams = _grams(text)
    scored: list[tuple[int, dict]] = []
    for r in records:
        blob = " ".join(str(v) for k, v in r.items() if v and not str(k).startswith("_"))
        score = sum(len(g) for g in grams if g in blob)
        if score:
            scored.append((score, r))
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored[:top]]


def _fmt_hara_ref(matched: list[dict]) -> str | None:
    """把匹配到的 HARA 记录格式化为 'ID / 危害事件' 列表。"""
    if not matched:
        return None
    parts = []
    for r in matched:
        rid = r.get("id") or f"行{r.get('_row')}"
        he = r.get("hazard_event") or r.get("function") or ""
        parts.append(f"{rid} / {he}" if he else str(rid))
    return " ; ".join(parts)


# ---------- 打回反馈 (追加需求③) ----------
def _fb_keywords(feedback: str | None) -> list[str]:
    if not feedback:
        return []
    fb = feedback.lower()
    vocab = [w.lower() for w in _FB_EXTRA_WORDS + FEATURE_WORDS]
    out: list[str] = []
    for w in dict.fromkeys(vocab):
        if w and w in fb and w not in out:
            out.append(w)
    return out


# ---------- 拟新增危害事件生成 (追加需求①) ----------
def _gen_hazards(text: str, change_id: str) -> list[dict]:
    hazards: list[dict] = []
    seen: set[str] = set()
    low = text.lower()
    for kws, event, scenario, (s, e, c) in _HAZARD_TEMPLATES:
        if event in seen:
            continue
        if any(k.lower() in low for k in kws):
            seen.add(event)
            asil = _asil_score(s, e, c)
            hazards.append({
                "event_id": f"NEW-{change_id.split('-')[-1]}-{len(hazards) + 1}",
                "hazard_event": event,
                "scenario": scenario,
                "S": f"S{s}", "E": f"E{e}", "C": f"C{c}",
                "ASIL": asil,
                "rationale": f"由变更引入新场景/新参数推演: S{s}+E{e}+C{c}={s + e + c}分 → {asil} (加法制)。",
            })
    if not hazards:
        hazards.append({
            "event_id": f"NEW-{change_id.split('-')[-1]}-1",
            "hazard_event": "变更引入的未知功能偏差可能导致车辆安全相关功能异常 (具体危害事件需工程师补充确认)",
            "scenario": "待确认",
            "S": "待评估", "E": "待评估", "C": "待评估", "ASIL": "待评估",
            "rationale": "规则引擎无法推演具体危害事件, 需人工分析。",
        })
    return hazards


# ---------- 结构化分析 (Mock 规则引擎) ----------
def analyze(diff_items: list[dict], hara: dict, feedback: str | None = None, round_no: int = 1) -> dict:
    records = hara.get("records", []) if isinstance(hara, dict) else []
    fb_kws = _fb_keywords(feedback)
    findings: list[dict] = []
    counts = {"reuse": 0, "new": 0, "removed": 0}
    fb_hit_any = False

    for d in diff_items:
        before, after = d.get("before", ""), d.get("after", "")
        combined = f"{before} {after}"
        cat, finding, fb_hit = _classify(d, before, after, combined, records, fb_kws)
        if fb_hit:
            finding["feedback_adopted"] = True  # 追加需求③: 该项为核实并采纳人工理由后的更新
        counts[cat] = counts.get(cat, 0) + 1
        fb_hit_any = fb_hit_any or fb_hit
        findings.append(finding)

    summary = (
        f"共识别 {len(diff_items)} 处文本改动: 完全复用 {counts.get('reuse', 0)} 处, "
        f"新增分析 {counts.get('new', 0)} 处, 删减分析 {counts.get('removed', 0)} 处。"
    )
    if counts.get("new"):
        summary += " 存在影响功能安全的高风险变更, 原 HARA 需补充/重评。"
    elif counts.get("removed"):
        summary += " 主要为功能删减, 需同步清理对应 HARA 条目。"
    else:
        summary += " 变更未触及安全相关逻辑, 原 HARA 可整体复用。"

    round_note = ""
    if feedback and round_no > 1:
        if not fb_hit_any:
            findings.append(_feedback_finding(feedback, fb_kws, records))
            counts["new"] = counts.get("new", 0) + 1
        summary = f"【第 {round_no} 轮重分析】已核实并采纳工程师打回理由, 更新对应结论内容。" + summary
        round_note = f"【第 {round_no} 轮重分析】已核实并采纳打回理由: 「{feedback}」"

    return {"summary": summary, "findings": findings, "round_note": round_note, "analysis_round": round_no}


def _classify(d: dict, before: str, after: str, combined: str, records: list[dict],
              fb_kws: list[str]) -> tuple[str, dict, bool]:
    """按 SYSTEM_PROMPT 规则返回 (category, finding, 是否被反馈命中/改写)。"""
    ctype = d.get("type", "replace")
    safety_hits = _has(combined, SAFETY_NEW_KEYWORDS)
    ui_hits = _has(combined, UI_KEYWORDS)
    fb_hits = [k for k in fb_kws if k in combined.lower()] if fb_kws else []
    speed = _SPEED_RE.findall(before)
    speed2 = _SPEED_RE.findall(after)
    speed_changed = speed and speed2 and speed != speed2

    # C. 删减: diff 删除, 或改动前有实质内容而改动后为空 —— 必须给出 HARA 危害事件 ID + 理由 (追加需求②)
    if ctype == "delete" or (before and not after and _has(before, FEATURE_WORDS)):
        matched = _match_hara_records(before, records, top=2)
        ref = _fmt_hara_ref(matched)
        reason = (f"功能「{(before or '')[:40]}…」在新 PRD 中已移除, 其对应危害事件不再发生于整车, "
                  f"建议删除/归档该 HARA 条目并同步更新安全目标清单。")
        return "removed", {
            "change_id": d["change_id"], "category": "removed", "category_label": "删减分析",
            "before": before, "after": after,
            "impact": "该功能在新 PRD 中被移除, 相关安全前提不再成立。",
            "risk_level": "medium",
            "hara_ref": ref,
            "hara_action": "删除/归档现有HARA" if ref else "需人工定位HARA条目",
            "proposed_hazards": None,
            "sec": None,
            "recommendation": reason,
            "gbt_ref": "GB/T 34590.3-2022 (危害分析与风险评估)",
        }, False

    # B. 新增分析: 命中安全关键词 / 车速变化 / 打回反馈命中 (追加需求③强制升级)
    if safety_hits or speed_changed or fb_hits:
        sec = _suggest_sec(before, after, combined, speed_changed)
        matched = _match_hara_records(combined, records, top=2)
        ref = _fmt_hara_ref(matched)
        action = "修改现有HARA (重评S/E/C)" if ref else "新增HARA条目"
        hazards = _gen_hazards(combined, d["change_id"])
        note = None
        if fb_hits and not safety_hits and not speed_changed:
            note = f"本轮依据工程师打回意见强制升级重判 (反馈命中: {'、'.join(fb_hits)})"
        return "new", {
            "change_id": d["change_id"], "category": "new", "category_label": "新增分析",
            "before": before, "after": after,
            "impact": _impact_text(safety_hits, speed_changed),
            "risk_level": _risk_from_asil(sec["ASIL"]),
            "hara_ref": ref,
            "hara_action": action,
            "proposed_hazards": hazards,
            "sec": sec,
            "recheck_note": note,
            "recommendation": ("需将拟新增危害事件纳入 HARA 矩阵, 复核关联现有条目的 S/E/C/ASIL, 并更新安全需求与验证计划。"
                               + (f" 理由: {note}。" if note else "")),
            "gbt_ref": "GB/T 34590.5-2022 (产品级危害分析与风险评估, ASIL 的确定与分解)",
        }, bool(fb_hits)

    # A. 完全复用: 仅 UI 文字
    if ui_hits and not safety_hits:
        return "reuse", {
            "change_id": d["change_id"], "category": "reuse", "category_label": "完全复用",
            "before": before, "after": after,
            "impact": "仅涉及界面文字/提示语等 UI 表述调整, 未触及控制逻辑、ODD 场景、传感器/接口。",
            "risk_level": "low", "hara_ref": None, "hara_action": "无需变更",
            "proposed_hazards": None, "sec": None, "recheck_note": None,
            "recommendation": "对功能安全无影响, 原 HARA 相关条目可完全复用, 无需重评。",
            "gbt_ref": "GB/T 34590.1-2022 (术语与概念)",
        }, False

    # 兜底: 无法明确归类 → 提示人工确认
    return "new", {
        "change_id": d["change_id"], "category": "new", "category_label": "新增分析(需人工确认)",
        "before": before, "after": after,
        "impact": "改动语义未命中已知安全关键词, 但存在潜在影响, 建议工程师确认是否触及控制逻辑/接口。",
        "risk_level": "medium",
        "hara_ref": _fmt_hara_ref(_match_hara_records(combined, records, top=1)),
        "hara_action": "待人工定位",
        "proposed_hazards": _gen_hazards(combined, d["change_id"]),
        "sec": {"S": "待评估", "E": "待评估", "C": "待评估", "ASIL": "待评估", "rationale": "规则引擎无法确定分类, 需人工判断。"},
        "recheck_note": None,
        "recommendation": "请人工判断该改动是否影响功能安全; 若涉及接口/逻辑, 走新增分析流程。",
        "gbt_ref": "GB/T 34590.5-2022",
    }, False


def _feedback_finding(feedback: str, fb_kws: list[str], records: list[dict]) -> dict:
    """追加需求③: 核实并采纳工程师打回理由 —— 即便理由未直接命中 PRD 文本改动,
    也默认采信工程师领域判断: 据理由定位现有 HARA、拟出具体的新增/修改危害事件与
    S/E/C/ASIL, 明确"已采纳并更新对应内容", 而非仅列为待核实项。"""
    kw_text = "、".join(fb_kws) if fb_kws else "相关功能/接口/场景要素"
    combined = f"{feedback} {kw_text}"
    matched = _match_hara_records(feedback, records, top=2)
    ref = _fmt_hara_ref(matched)
    action = "修改现有HARA (按工程师理由补充重评)" if ref else "新增HARA条目 (依据工程师理由)"
    return {
        "change_id": "C-FB01", "category": "new", "category_label": "新增分析(已采纳人工理由)",
        "before": "(PRD 文本 diff 未直接覆盖)", "after": feedback,
        "impact": f"经核实, 工程师打回理由指向 {kw_text}; 该要素在文本差异中未显式出现, 可能位于接口矩阵/原理图/附件, 已依据人工意见更新风险评估内容。",
        "risk_level": "high",
        "hara_ref": ref,
        "hara_action": action,
        "proposed_hazards": _gen_hazards(combined, "FB01"),
        "sec": _suggest_sec("", feedback, combined, False),
        "recheck_note": "本轮已核实并采纳工程师打回理由, 据此更新 HARA 判定 (命中人工领域判断)。",
        "feedback_adopted": True,
        "recommendation": f"已采纳工程师意见: 针对「{feedback}」补充/修订涉及 {kw_text} 的危害事件与控制措施, 更新对应 HARA 条目及安全需求; 请复核拟新增危害事件的 S/E/C 打分。",
        "gbt_ref": "GB/T 34590.5-2022",
    }


def _suggest_sec(before: str, after: str, combined: str, speed_changed: bool) -> dict:
    """依据 GB/T 34590-5 给出 S/E/C 建议值。"""
    s = 3 if _has(combined, ["高速", "制动", "转向", "失控", "碰撞", "车速"]) or speed_changed else 2
    e = 4 if _has(combined, ["高速", "匝道", "日常", "始终", "主干道"]) else (2 if _has(combined, ["施工", "夜间", "偶发"]) else 3)
    c = 3 if _has(combined, ["驾驶员无法", "不可控", "接管", "自动", "无人"]) else (2 if _has(combined, ["预警", "提示"]) else 1)
    asil = _asil_score(s, e, c)
    rationale = f"严重度取 S{s}; 运行频率取 E{e}; 驾驶员可控性取 C{c}; 按 S+E+C 加法制 {s}+{e}+{c}={s + e + c}分 → ASIL={asil}。"
    return {
        "S": f"S{s} (严重度{s})", "E": f"E{e} (暴露率{e})", "C": f"C{c} (可控性{c})",
        "ASIL": asil, "rationale": rationale,
    }


def _impact_text(safety_hits: list[str], speed_changed: bool) -> str:
    bits = []
    if speed_changed:
        bits.append("车速运行范围发生变化")
    if safety_hits:
        uniq = "、".join(sorted(set(safety_hits), key=safety_hits.index)[:6])
        bits.append(f"触及安全相关要素({uniq})")
    return "; ".join(bits) or "命中安全关键词"


def _risk_from_asil(asil: str) -> str:
    if "D" in asil:
        return "high"
    if "C" in asil or "B" in asil:
        return "medium"
    return "low"


# ---------- Markdown 渲染 ----------
_CAT_ICON = {"reuse": "🟢", "new": "🔴", "removed": "🟡"}


def render_markdown(conclusion: dict) -> str:
    f = conclusion.get("findings", [])
    out: list[str] = []
    if conclusion.get("round_note"):
        out += [conclusion["round_note"], ""]
    out += ["## 一、总体结论", conclusion.get("summary", ""), "", "## 二、逐条差异判定", ""]
    for item in f:
        key = item["category"].split("-")[0]
        icon = _CAT_ICON.get(key, "⚪")
        out.append(f"### {icon} {item['change_id']} · {item['category_label']}  (风险: {item['risk_level']})")
        if item.get("before"):
            out.append(f"- 改动前: {item['before']}")
        if item.get("after"):
            out.append(f"- 改动后: {item['after']}")
        out.append(f"- 影响: {item['impact']}")
        if item.get("recheck_note"):
            out.append(f"- ⚠ 重分析说明: {item['recheck_note']}")
        if item.get("hara_ref"):
            out.append(f"- 现有 HARA 定位: {item['hara_ref']}  →  处置: {item.get('hara_action', '')}")
        elif item.get("hara_action"):
            out.append(f"- HARA 处置: {item['hara_action']}")
        sec = item.get("sec")
        if sec:
            out.append(f"- S/E/C 建议: S={sec.get('S')}, E={sec.get('E')}, C={sec.get('C')}, **ASIL={sec.get('ASIL')}**")
            if sec.get("rationale"):
                out.append(f"  - 依据: {sec['rationale']}")
        hazards = item.get("proposed_hazards")
        if hazards:
            out.append(f"- 拟新增危害事件 ({len(hazards)} 条):")
            for hz in hazards:
                out.append(
                    f"  {hz['event_id']}「{hz['hazard_event']}」\n"
                    f"      场景: {hz['scenario']} | S={hz['S']} E={hz['E']} C={hz['C']} → ASIL={hz['ASIL']}"
                )
        out.append(f"- 建议: {item['recommendation']}")
        if item.get("gbt_ref"):
            out.append(f"- 参考条款: {item['gbt_ref']}")
        out.append("")
    return "\n".join(out)


# ---------- 流式输出 ----------
async def stream(conclusion: dict) -> AsyncIterator[str]:
    """把结论按打字机式分块产出。"""
    md = render_markdown(conclusion)
    for token in re.findall(r"\S+\s*|\s+", md):
        yield token
        await asyncio.sleep(0.02)


async def stream_deepseek(diff_items: list[dict], hara: dict, feedback: str | None = None) -> AsyncIterator[str]:
    """真实 DeepSeek 流式 (后续启用)。逐 token 产出原始 JSON 文本。"""
    from openai import AsyncOpenAI  # 延迟导入, mock 模式无需

    client = AsyncOpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
    hara_text = hara.get("text", "") if isinstance(hara, dict) else ""
    resp = await client.chat.completions.create(
        model=settings.deepseek_model,
        stream=True,
        messages=[
            {"role": "system", "content": prompts.SYSTEM_PROMPT},
            {"role": "user", "content": prompts.build_user_prompt(diff_items, hara_text, feedback)},
        ],
    )
    async for chunk in resp:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta


def parse_deepseek_json(raw: str) -> dict:
    """从模型返回文本中稳健地抽取 JSON。"""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"```$", "", raw).strip()
    m = re.search(r"\{.*\}", raw, re.S)
    return json.loads(m.group(0)) if m else {"summary": raw, "findings": []}
