"""把一批结果导出成 Excel：
- 「Test cases」页：brief 要求的 8 列（Case ID, Scenario, Client information, Conversation history,
  Product information, Output 1, Output 2, Output 3）+ 版本号
- 「Evaluation」页：每条候选一行，含规则违规、裁判分数、等级、重写次数和重写前版本
- 「Summary」页：按场景汇总的通过率和平均分
"""
from __future__ import annotations

import json
from collections import defaultdict

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from .config import Config
from .schemas import CaseInput, CaseOutput

HEAD_FILL = PatternFill("solid", fgColor="E8E3D8")
GRADE_FILL = {"不可接受": "F4CCCC", "可接受": "FFF2CC", "好": "D9EAD3"}


def _client_text(case: CaseInput, cfg: Config) -> str:
    c = case.client
    idx = cfg.sku_index
    lines = [f"{c.preferred_name}｜{c.age} 岁｜{c.city or ''}｜{c.tier}｜熟悉度 {c.familiarity}"]
    if c.birthday:
        lines.append(f"生日 {c.birthday}")
    if c.preferences:
        lines.append("偏好 " + json.dumps(c.preferences, ensure_ascii=False))
    for p in c.purchases:
        lines.append(f"购买 {p.date} {idx.get(p.sku, {}).get('name', p.sku)}（{p.purpose or ''}）")
    for d in c.important_dates:
        lines.append(f"{d.name} {d.date}{'（接受问候）' if d.accept_greeting else ''}")
    for k in ("communication", "sensitive", "notes"):
        if getattr(c, k):
            lines.append(f"{k}: {getattr(c, k)}")
    ctx = case.context.model_dump(exclude_none=True)
    if ctx:
        lines.append("背景 " + json.dumps(ctx, ensure_ascii=False))
    return "\n".join(lines)


def _product_text(case: CaseInput, out: CaseOutput, cfg: Config) -> str:
    idx = cfg.sku_index
    skus = list(dict.fromkeys(case.product_info + out.retrieved_skus))
    return "\n".join(f"{idx[s]['name']}｜¥{idx[s]['price']}｜{idx[s].get('window') or ''}｜{idx[s]['selling_point']}"
                     if s in idx and idx[s].get("price") else idx.get(s, {}).get("name", s) for s in skus) or "—"


def _style(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = HEAD_FILL
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")


def export_excel(cases: list[CaseInput], outputs: list[CaseOutput], cfg: Config, path: str) -> None:
    sc_names = {k: v["name"] for k, v in cfg.scenarios["scenarios"].items()}
    wb = Workbook()
    ws = wb.active
    ws.title = "Test cases"
    ws.append(["Case ID", "Scenario", "Client information", "Conversation history", "Product information",
               "Output 1", "Output 2", "Output 3", "Version", "Tool warnings"])
    for case, out in zip(cases, outputs):
        hist = "\n".join(f"[{'CA' if t.role == 'ca' else '客户'}] {t.text}" for t in case.history) or "—"
        texts = [c.text for c in out.candidates] or ["（工具建议不发送）"] * 3
        texts += [""] * (3 - len(texts))
        ws.append([case.case_id, sc_names[case.scenario], _client_text(case, cfg), hist,
                   _product_text(case, out, cfg), *texts[:3], out.version, "\n".join(out.warnings)])
    _style(ws, [8, 12, 40, 40, 36, 36, 36, 36, 8, 30])

    ev = wb.create_sheet("Evaluation")
    ev.append(["Case ID", "Scenario", "#", "Strategy", "Final text", "Grade", "Rule violations",
               "personalization", "scenario_fit", "brand_voice", "naturalness", "no_pressure",
               "Judge flags", "Judge comment", "Rewrites", "Before rewrite", "Set issues", "Version"])
    for case, out in zip(cases, outputs):
        for i, c in enumerate(out.candidates, 1):
            ev.append([case.case_id, sc_names[case.scenario], i, c.strategy, c.text, c.grade,
                       "\n".join(f"{v.rule} {v.detail}" for v in c.violations),
                       *[c.scores.get(k) for k in ("personalization", "scenario_fit", "brand_voice",
                                                   "naturalness", "no_pressure")],
                       ", ".join(k for k, v in c.judge_flags.items() if v), c.judge_comment, c.rewrites,
                       "\n---\n".join(f"{h['text']}\n（{'; '.join(h['problems'])}）" for h in c.history),
                       "\n".join(v.detail for v in out.set_violations), out.version])
            fill = GRADE_FILL.get(c.grade)
            if fill:
                ev.cell(row=ev.max_row, column=6).fill = PatternFill("solid", fgColor=fill)
    _style(ev, [8, 12, 4, 9, 44, 10, 30, 8, 8, 8, 8, 8, 14, 30, 8, 44, 24, 8])

    sm = wb.create_sheet("Summary")
    sm.append(["Scenario", "Cases", "Candidates", "好", "可接受", "不可接受", "Hard-rule pass (final)",
               "Avg score", "Rewritten candidates", "Not sent (blocked)"])
    agg = defaultdict(lambda: defaultdict(float))
    for case, out in zip(cases, outputs):
        a = agg[sc_names[case.scenario]]
        a["cases"] += 1
        if not out.candidates:
            a["blocked"] += 1
        for c in out.candidates:
            a["n"] += 1
            a[c.grade] += 1
            a["pass"] += 0 if c.violations else 1
            if c.scores:
                a["score_sum"] += sum(c.scores.values()) / len(c.scores)
                a["scored"] += 1
            a["rewritten"] += 1 if c.rewrites else 0
    for name, a in agg.items():
        n = a["n"] or 1
        sm.append([name, int(a["cases"]), int(a["n"]), int(a["好"]), int(a["可接受"]), int(a["不可接受"]),
                   f"{a['pass'] / n:.0%}" if a["n"] else "—", round(a["score_sum"] / a["scored"], 2) if a["scored"] else None,
                   int(a["rewritten"]), int(a["blocked"])])
    _style(sm, [14, 8, 10, 8, 8, 10, 18, 10, 18, 16])
    wb.save(path)
