"""从结果文件里删掉失败的用例（生成失败、运行出错、裁判调用失败），之后用 --resume 只重跑这些。

  python scripts/drop_failed.py v2
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / f"outputs/results_{sys.argv[1]}.jsonl"
keep, dropped = [], []
for line in open(path, encoding="utf-8"):
    if not line.strip():
        continue
    o = json.loads(line)
    bad = any(w.startswith(("运行出错", "生成失败")) for w in o["warnings"]) or any(
        c["judge_comment"].startswith("裁判调用失败") for c in o["candidates"])
    (dropped if bad else keep).append((o["case_id"], line))
with open(path, "w", encoding="utf-8") as f:
    for _, line in keep:
        f.write(line if line.endswith("\n") else line + "\n")
print(f"保留 {len(keep)} 个，删掉 {len(dropped)} 个待重跑：{[c for c, _ in dropped]}")
