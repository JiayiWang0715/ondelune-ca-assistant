"""把 v1、v2 的结果合成一个提交用的 Excel（C 部分）。

  python scripts/build_submission_excel.py
"""
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

ROOT = Path(__file__).resolve().parents[1]
out = Workbook()
out.remove(out.active)
readme = out.create_sheet("说明")
for row in [
    ["Maison Ondelune CA 话术工具：50 个测试用例（所有品牌、客户、对话均为虚构）"],
    [""],
    ["工作表", "内容"],
    ["v2 Test cases（最终版）", "brief 要求的 8 列 + 版本号 + 工具提示。最终提交以此为准"],
    ["v2 Evaluation", "v2 每条候选：等级、规则违规、裁判 5 维分数、重写次数与重写前版本"],
    ["v2 Summary", "v2 按场景汇总"],
    ["v1 Test cases（修改前）", "同样 50 个用例在 v1 的输出，用于前后对比"],
    ["v1 Evaluation / v1 Summary", "v1 的评估明细与汇总"],
    [""],
    ["版本", "v1：首次冻结版本（2026-11-08）；v2：根据 v1 人工标注修改后的版本（2026-11-09）"],
    ["模型", "生成 deepseek-flash（DeepSeek-V4.1-Flash-1017），裁判 deepseek-v4-pro（DeepSeek-V4-Pro-0813）；v2 中 17 个用例因余额不足经 Hugging Face 调用同一模型补跑"],
    ["输出为空", "工具判断不应发送（如客户未成年、活动层级不符），原因写在「Tool warnings」列"],
    ["未评分", "v2 有 3 条消息因网络超时未获得裁判分数（已通过硬规则检查）"],
]:
    readme.append(row)
readme.column_dimensions["A"].width = 26
readme.column_dimensions["B"].width = 110
readme["A1"].font = Font(bold=True, size=13)
for c in readme[3]:
    c.font = Font(bold=True)

for ver, label in [("v2", "（最终版）"), ("v1", "（修改前）")]:
    src = load_workbook(ROOT / f"outputs/results_{ver}.xlsx")
    for name in ["Test cases", "Evaluation", "Summary"]:
        ws_src = src[name]
        ws = out.create_sheet(f"{ver} {name}" + (label if name == "Test cases" else ""))
        for row in ws_src.iter_rows(values_only=True):
            ws.append(list(row))
        for col, dim in ws_src.column_dimensions.items():
            ws.column_dimensions[col].width = dim.width
        for r_src, r in zip(ws_src.iter_rows(), ws.iter_rows()):
            for c_src, c in zip(r_src, r):
                if c_src.fill and c_src.fill.fgColor and c_src.fill.fill_type:
                    c.fill = PatternFill("solid", fgColor=c_src.fill.fgColor.rgb)
                c.alignment = Alignment(wrap_text=True, vertical="top")
                if c_src.font and c_src.font.bold:
                    c.font = Font(bold=True)
        ws.freeze_panes = "B2"
out.save(ROOT / "outputs/C_50_test_cases.xlsx")
print("已生成 outputs/C_50_test_cases.xlsx")
