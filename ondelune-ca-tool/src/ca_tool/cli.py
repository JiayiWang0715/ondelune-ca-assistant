"""命令行入口。

  # 跑一个用例，打印 3 条候选和检查结果
  python -m ca_tool.cli one data/sample_cases.jsonl C01

  # 批量跑，导出 JSONL + Excel（版本号会写进每条结果）
  python -m ca_tool.cli batch data/sample_cases.jsonl --version v1

  # 覆盖配置里的模型，做模型对比
  python -m ca_tool.cli batch data/sample_cases.jsonl --version v1-qwen --generator qwen --judge deepseek
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from .config import ROOT, load_config
from .llm import build_llm
from .pipeline import Pipeline
from .report import export_excel
from .schemas import CaseInput, CaseOutput


def load_cases(path: str) -> list[CaseInput]:
    with open(path, encoding="utf-8") as f:
        return [CaseInput.model_validate_json(line) for line in f if line.strip()]


def make_pipeline(args) -> Pipeline:
    load_dotenv(ROOT / ".env")
    cfg = load_config()
    if args.generator:
        cfg.models["roles"]["generator"] = args.generator
    if args.judge:
        cfg.models["roles"]["judge"] = args.judge
    gen = build_llm("generator", cfg.models)
    judge = None if args.no_judge else build_llm("judge", cfg.models)
    return Pipeline(cfg, gen, judge, version=args.version)


def print_output(case, out):
    print(f"\n=== {case.case_id}｜{case.scenario}｜{case.client.preferred_name} ===")
    for w in out.warnings:
        print(f"  ⚠ {w}")
    for i, c in enumerate(out.candidates, 1):
        print(f"\n[{i}] {c.strategy}｜{c.grade}｜重写 {c.rewrites} 次")
        print(f"    {c.text}")
        for v in c.violations:
            print(f"    ✗ {v.rule} {v.detail}")
        if c.scores:
            print("    分数 " + " ".join(f"{k}={v:g}" for k, v in c.scores.items()))
        for h in c.history:
            print(f"    （重写前）{h['text']} ← {'; '.join(h['problems'])}")
    for v in out.set_violations:
        print(f"  ✗ SET {v.detail}")


def main():
    ap = argparse.ArgumentParser(prog="ca_tool")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("one", "batch"):
        p = sub.add_parser(name)
        p.add_argument("cases")
        if name == "one":
            p.add_argument("case_id")
        p.add_argument("--version", default="v1")
        p.add_argument("--generator")
        p.add_argument("--judge")
        p.add_argument("--no-judge", action="store_true")
        p.add_argument("--out", default=str(ROOT / "outputs"))
        if name == "batch":
            p.add_argument("--resume", action="store_true", help="跳过结果文件里已经跑完的用例，接着跑")
    args = ap.parse_args()

    pipe = make_pipeline(args)
    cases = load_cases(args.cases)
    if args.cmd == "one":
        case = next(c for c in cases if c.case_id == args.case_id)
        print_output(case, pipe.run(case))
        return

    od = Path(args.out)
    od.mkdir(parents=True, exist_ok=True)
    jpath = od / f"results_{args.version}.jsonl"
    done = {}
    if args.resume and jpath.exists():
        with open(jpath, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    o = CaseOutput.model_validate_json(line)
                    done[o.case_id] = o
        print(f"续跑：已有 {len(done)} 个用例的结果，跳过它们")
    # 每跑完一个用例就写一行，中途出错也不会丢失已完成的结果
    with open(jpath, "a" if args.resume else "w", encoding="utf-8") as f:
        for case in cases:
            if case.case_id in done:
                continue
            try:
                out = pipe.run(case)
            except Exception as e:  # noqa: BLE001  单个用例出错不影响整批
                out = CaseOutput(case_id=case.case_id, version=args.version, candidates=[],
                                 warnings=[f"运行出错：{type(e).__name__}: {e}"])
            done[case.case_id] = out
            f.write(out.model_dump_json() + "\n")
            f.flush()
            print_output(case, out)
    outs = [done[c.case_id] for c in cases]
    errors = [o.case_id for o in outs if any(w.startswith(("运行出错", "生成失败")) for w in o.warnings)]
    if errors:
        print(f"\n⚠ 这些用例出错，可以加 --resume 之前先从结果文件里删掉它们再重跑：{errors}")
    export_excel(cases, outs, pipe.cfg, str(od / f"results_{args.version}.xlsx"))
    print(f"\n已导出 {od / f'results_{args.version}.xlsx'}")


if __name__ == "__main__":
    main()
