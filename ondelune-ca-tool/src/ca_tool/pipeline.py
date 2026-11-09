"""固定流程（workflow），不是开放式 agent：

  预检 → 检索 → 生成 3 条 → 第 1 层硬规则 → 第 2 层 LLM 裁判 → 不合格的单条重写（≤ N 轮）→ 输出

只在「要不要重写」这一处让模型的判断影响流程，其余步骤固定、可复现、可审计。
"""
from __future__ import annotations

import json
import re

from .config import Config
from .llm import LLM, parse_json
from .prompts import (JUDGE_SYSTEM, full_system_with_rules, judge_user, rewrite_user, system_prompt,
                      user_prompt)
from .retrieval import retrieve
from .rules import RuleChecker
from .schemas import CandidateResult, CaseInput, CaseOutput, Candidate, RuleViolation

SCORE_KEYS = ["personalization", "scenario_fit", "brand_voice", "naturalness", "no_pressure"]
STRATEGY_ORDER = ["warm", "content", "light"]


def grade(violations: list[RuleViolation], scores: dict, flags: dict) -> str:
    """Brand Book 第 7 节的结果分级。"""
    if violations or any(flags.values()) or (scores and min(scores.values()) <= 2):
        return "不可接受"
    if scores and min(scores.values()) >= 4:
        return "好"
    if not scores:
        return "通过硬规则（未评分）"
    return "可接受"


def _single_message(out: dict, strategy: str) -> str:
    """重写结果兜底：模型偶尔返回 3 条、编号列表或嵌套 JSON，这里只取一条。"""
    if "candidates" in out:
        cands = out["candidates"]
        pick = next((c for c in cands if c.get("strategy") == strategy), cands[0] if cands else {})
        return (pick.get("text") or "").strip()
    text = str(out.get("text", "")).strip()
    if text.startswith("{"):
        try:
            return _single_message(json.loads(text), strategy)
        except ValueError:
            pass
    lines = [re.sub(r"^\s*\d+[.、)]\s*", "", l).strip() for l in text.splitlines() if l.strip()]
    return lines[0] if lines else ""


class Pipeline:
    def __init__(self, cfg: Config, generator: LLM, judge: LLM | None, version: str = "v1"):
        self.cfg = cfg
        self.gen = generator
        self.judge = judge
        self.version = version
        self.checker = RuleChecker(cfg)
        self.max_rounds = cfg.models["generation"]["max_rewrite_rounds"]
        self.t_gen = cfg.models["generation"]["temperature"]
        self.t_judge = cfg.models["judging"]["temperature"]

    # ---------------------------------------------------------------- 单条评估
    def _evaluate(self, res: CandidateResult, case, facts, pc) -> None:
        res.violations = self.checker.check_candidate(Candidate(strategy=res.strategy, text=res.text), case, facts, pc)
        if self.judge:
            try:
                out = parse_json(self.judge.chat(JUDGE_SYSTEM, judge_user(case, self.cfg, res.text, res.strategy),
                                                 temperature=self.t_judge))
                res.scores = {k: float(out["scores"][k]) for k in SCORE_KEYS}
                res.judge_flags = {k: bool(v) for k, v in out.get("flags", {}).items()}
                res.judge_comment = out.get("comment", "")
            except Exception as e:  # 裁判失败不阻断流程，但要留痕
                res.judge_comment = f"裁判调用失败：{e}"
        res.grade = grade(res.violations, res.scores, res.judge_flags)

    def _problems(self, res: CandidateResult) -> list[str]:
        p = [f"{v.rule}：{v.detail}" for v in res.violations]
        p += [f"裁判标记 {k}" for k, v in res.judge_flags.items() if v]
        p += [f"{k} 只有 {s:g} 分" for k, s in res.scores.items() if s <= 2]
        if p and res.judge_comment:
            p.append(f"裁判意见：{res.judge_comment}")
        return p

    # ---------------------------------------------------------------- 主流程
    def run(self, case: CaseInput) -> CaseOutput:
        pc = self.checker.precheck(case)
        skus, knowledge = retrieve(case, self.cfg)
        out = CaseOutput(case_id=case.case_id, version=self.version, candidates=[],
                         warnings=list(pc.warnings), retrieved_skus=skus)
        if pc.blocked:
            out.warnings.append("工具判断本次不应发送，未生成候选。")
            return out

        facts = self.checker.collect_facts(case, skus)
        sys_p = system_prompt(self.cfg)
        usr_p = user_prompt(case, self.cfg, skus, knowledge, pc)
        raw, last_err = None, None
        for _ in range(2):   # 模型偶尔返回空内容或非 JSON：重试一次
            try:
                raw = parse_json(self.gen.chat(sys_p, usr_p, temperature=self.t_gen))
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
        if raw is None:
            out.warnings.append(f"生成失败（已重试）：{last_err}")
            return out
        cands = raw.get("candidates", [])[:3]
        cands.sort(key=lambda c: STRATEGY_ORDER.index(c["strategy"]) if c.get("strategy") in STRATEGY_ORDER else 9)

        results = [CandidateResult(strategy=c.get("strategy", "?"), text=c.get("text", "").strip()) for c in cands]
        for res in results:
            self._evaluate(res, case, facts, pc)
            while res.grade == "不可接受" and res.rewrites < self.max_rounds:
                problems = self._problems(res)
                res.history.append({"text": res.text, "grade": res.grade, "problems": problems})
                try:
                    new = parse_json(self.gen.chat(full_system_with_rules(self.cfg),
                                                   rewrite_user(res.text, res.strategy, problems, usr_p),
                                                   temperature=self.t_gen))
                except Exception as e:  # noqa: BLE001  重写失败不拖垮整批，保留上一版并留痕
                    res.history[-1]["problems"].append(f"重写调用失败：{e}")
                    res.rewrites += 1
                    continue
                res.text = _single_message(new, res.strategy) or res.text
                res.rewrites += 1
                self._evaluate(res, case, facts, pc)

        out.candidates = results
        out.set_violations = self.checker.check_set([Candidate(strategy=r.strategy, text=r.text) for r in results])
        return out
