"""把两次运行的结果打乱成 A/B 盲评表。

  python scripts/blind_compare.py cmp-qwen cmp-deepseek

- 每个用例随机决定哪个模型放 A、哪个放 B（固定随机种子，可复现）
- 用模型「第一次生成」的版本（重写前），比较的是模型本身的写作，不受重写流程影响
- 答案存在 outputs/blind_key.json，评完再看
"""
import json
import random
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

ROOT = Path(__file__).resolve().parents[1]
a_ver, b_ver = sys.argv[1], sys.argv[2]
cases = {json.loads(l)["case_id"]: json.loads(l) for l in open(ROOT / "data/sample_cases.jsonl", encoding="utf-8")}


def load(v):
    out = {}
    for line in open(ROOT / f"outputs/results_{v}.jsonl", encoding="utf-8"):
        o = json.loads(line)
        if o["candidates"]:
            out[o["case_id"]] = [c["history"][0]["text"] if c["history"] else c["text"] for c in o["candidates"]]
    return out


runs = {a_ver: load(a_ver), b_ver: load(b_ver)}
SC = {"greeting": "生日/节日问候", "recommendation": "产品推荐", "aftercare": "售后关怀",
      "reactivation": "唤醒老客", "event_invitation": "活动邀约", "price_objection": "价格异议"}
rng = random.Random(20261107)
wb = Workbook()
ws = wb.active
ws.title = "盲评"
ws.append(["用例", "场景", "客户情况与对话", "方案 A", "方案 B", "你选（A / B / 差不多）", "理由"])
key = {}
for cid in sorted(set(runs[a_ver]) & set(runs[b_ver])):
    order = [a_ver, b_ver]
    rng.shuffle(order)
    key[cid] = {"A": order[0], "B": order[1]}
    c = cases[cid]
    ctx = f"{c['client']['preferred_name']}｜{c['client'].get('tier', '')}\n" + (c["client"].get("notes") or "")
    ctx += "\n" + "\n".join(f"[{'CA' if t['role'] == 'ca' else '客户'}] {t['text']}" for t in c.get("history", []))
    fmt = lambda msgs: "\n\n".join(f"{i}. {m}" for i, m in enumerate(msgs, 1))  # noqa: E731
    ws.append([cid, SC[c["scenario"]], ctx.strip(), fmt(runs[order[0]][cid]), fmt(runs[order[1]][cid]), "", ""])
for col, w in zip("ABCDEFG", [7, 12, 34, 52, 52, 14, 30]):
    ws.column_dimensions[col].width = w
for cell in ws[1]:
    cell.font = Font(bold=True)
    cell.fill = PatternFill("solid", fgColor="E8E3D8")
for row in ws.iter_rows():
    for cell in row:
        cell.alignment = Alignment(wrap_text=True, vertical="top")
wb.save(ROOT / "outputs/blind_compare.xlsx")
json.dump(key, open(ROOT / "outputs/blind_key.json", "w"), ensure_ascii=False, indent=1)
print(f"已生成 outputs/blind_compare.xlsx（{len(key)} 个用例）；答案在 outputs/blind_key.json，评完再看")
