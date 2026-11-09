"""从某个版本的结果里抽样，生成人工标注表（看不到裁判分数，用于校准裁判、统计缺陷）。

  python scripts/human_label_sheet.py v1 G01 R02 A01 RE02 E02 P01 P05 X01 X07 X12
"""
import json
import random
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[1]
ver, ids = sys.argv[1], sys.argv[2:]
cases = {json.loads(l)["case_id"]: json.loads(l) for l in open(ROOT / "data/test_cases.jsonl", encoding="utf-8")}
outs = {json.loads(l)["case_id"]: json.loads(l) for l in open(ROOT / f"outputs/results_{ver}.jsonl", encoding="utf-8")}
SC = {"greeting": "生日/节日问候", "recommendation": "产品推荐", "aftercare": "售后关怀",
      "reactivation": "唤醒老客", "event_invitation": "活动邀约", "price_objection": "价格异议"}
rows, key = [], []
for cid in ids:
    c, o = cases[cid], outs[cid]
    ctx = f"{c['client']['preferred_name']}｜{c['client']['tier']}｜熟悉度{c['client']['familiarity']}\n本次任务：{c['context']['task']}"
    if c["client"].get("notes"):
        ctx += f"\n备注：{c['client']['notes']}"
    if c["client"].get("sensitive"):
        ctx += f"\n敏感：{c['client']['sensitive']}"
    hist = "\n".join(f"[{'CA' if t['role'] == 'ca' else '客户'}] {t['text']}" for t in c["history"])
    for i, cd in enumerate(o["candidates"], 1):
        rows.append([cid, SC[c["scenario"]], ctx + ("\n" + hist if hist else ""), cd["text"]])
        key.append({"case_id": cid, "n": i, "strategy": cd["strategy"], "judge_grade": cd["grade"],
                    "judge_scores": cd["scores"], "violations": [v["rule"] for v in cd["violations"]]})
order = list(range(len(rows)))
random.Random(7).shuffle(order)
wb = Workbook()
ws = wb.active
ws.title = "人工标注"
ws.append(["#", "用例", "场景", "客户与对话", "消息", "你的等级", "问题（可多个，用逗号隔开）", "备注"])
for k, idx in enumerate(order, 1):
    ws.append([k, *rows[idx], "", "", ""])
dv = DataValidation(type="list", formula1='"好,可接受,不可接受"', allow_blank=True)
ws.add_data_validation(dv)
dv.add(f"F2:F{len(rows) + 1}")
for col, w in zip("ABCDEFGH", [4, 6, 11, 40, 52, 11, 26, 24]):
    ws.column_dimensions[col].width = w
for cell in ws[1]:
    cell.font = Font(bold=True)
    cell.fill = PatternFill("solid", fgColor="E8E3D8")
for row in ws.iter_rows():
    for cell in row:
        cell.alignment = Alignment(wrap_text=True, vertical="top")
g = wb.create_sheet("等级与问题说明")
for line in [
    ["等级", "好 = CA 可以直接发；可接受 = 小改后可发；不可接受 = 不能发"],
    ["问题代码", ""],
    ["D1", "开头就拒绝 / 生硬"], ["D2", "AI 腔（小知识、套话）"], ["D3", "太短、像打发人"],
    ["D4", "信息堆砌、缺少衔接"], ["D5", "客户比价时没回应"], ["D8", "推测客户私事"],
    ["D9", "没说清和客户的关系"], ["D10", "编造典故 / 成语堆砌"], ["事实", "事实或产品信息错误"],
    ["其他", "写在备注里"]]:
    g.append(line)
g.column_dimensions["A"].width = 10
g.column_dimensions["B"].width = 50
wb.save(ROOT / f"outputs/human_labels_{ver}.xlsx")
json.dump([key[i] for i in order], open(ROOT / f"outputs/human_labels_{ver}_key.json", "w"), ensure_ascii=False, indent=1)
print(f"已生成 outputs/human_labels_{ver}.xlsx（{len(rows)} 条消息）")
