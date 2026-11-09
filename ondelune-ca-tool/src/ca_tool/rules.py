"""第 1 层验证：确定性的硬规则检查（纯代码，不调用模型）。

规则编号与 Brand Book 一致：V = 调性规则，R = 红线，S = 场景 playbook，SET = 三条之间。
每条违规都返回 RuleViolation(rule, detail)，可以直接统计通过率。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from .config import Config
from .schemas import CaseInput, Candidate, RuleViolation

EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF☀-➿\U0001F000-\U0001F2FF]")
YEAR_RE = re.compile(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)")
PRICE_RE = re.compile(r"[¥￥]\s?([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s?(?:元|块)")
MD_RE = re.compile(r"(\d{1,2})\s?月\s?(\d{1,2})\s?[日号]")
SENT_SPLIT_RE = re.compile(r"[。！？!?…\n]+")
PUNCT_RE = re.compile(r"[\s，。！？、；：,.!?;:\"'“”‘’（）()…~～—\-]")


def _num(s: str) -> float:
    return float(s.replace(",", ""))


@dataclass
class CaseFacts:
    """从输入中收集的「允许出现的事实」，用于幻觉检查（R3）。"""
    allowed_skus: set[str] = field(default_factory=set)
    allowed_years: set[int] = field(default_factory=set)
    allowed_prices: set[float] = field(default_factory=set)
    allowed_md: set[tuple[int, int]] = field(default_factory=set)
    purchased_skus: set[str] = field(default_factory=set)
    allowed_aliases: set[str] = field(default_factory=set)   # 输入原文里出现过的产品名/风格词


@dataclass
class Precheck:
    """生成前的用例级判断：要不要提醒 CA、要不要切换模式。"""
    warnings: list[str] = field(default_factory=list)
    light_only: bool = False          # R13 触发后，三条都要轻量
    block_marketing: bool = False     # R10 敏感状态
    blocked: bool = False             # R7 未成年等，建议不发
    respect_refusal: bool = False     # v2 R12：客户表达过拒绝 / 决定不买


class RuleChecker:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        b = cfg.brand
        self.neg_words = b["negation_words"]
        self.wordlists = {
            k: {
                "rule": v["rule"],
                "negatable": v.get("negatable", False),
                "patterns": [re.compile(p) for p in v["patterns"]],
            }
            for k, v in b["wordlists"].items()
        }
        # 产品别名 → SKU 集合；按长度降序匹配，避免「潮汐」吃掉「潮汐 2008 大瓶」
        alias_map: dict[str, set[str]] = {}
        for p in cfg.product_list:
            for a in [p["name"], *p.get("aliases", [])]:
                alias_map.setdefault(a, set()).add(p["sku"])
        self.aliases = sorted(alias_map.items(), key=lambda kv: -len(kv[0]))

    # ------------------------------------------------------------------ 实体抽取
    def find_products(self, text: str) -> list[tuple[str, set[str]]]:
        """返回文本中提到的产品：(命中的名称, 候选 SKU 集合)。"""
        found, taken = [], [False] * len(text)
        for alias, skus in self.aliases:
            start = 0
            while (i := text.find(alias, start)) != -1:
                if not any(taken[i:i + len(alias)]):
                    found.append((alias, skus))
                    for j in range(i, i + len(alias)):
                        taken[j] = True
                start = i + 1
        return found

    @staticmethod
    def find_years(text: str) -> list[int]:
        return [int(y) for y in YEAR_RE.findall(text)]

    @staticmethod
    def find_prices(text: str) -> list[float]:
        out = []
        for a, b in PRICE_RE.findall(text):
            v = a or b
            if v:
                out.append(_num(v))
        return out

    @staticmethod
    def find_md(text: str) -> list[tuple[int, int]]:
        return [(int(m), int(d)) for m, d in MD_RE.findall(text)]

    # ------------------------------------------------------------------ 允许的事实
    def collect_facts(self, case: CaseInput, retrieved: list[str]) -> CaseFacts:
        idx = self.cfg.sku_index
        f = CaseFacts()
        f.purchased_skus = {p.sku for p in case.client.purchases}
        f.allowed_skus = set(case.product_info) | f.purchased_skus | set(retrieved)
        if case.context.event:
            f.allowed_skus |= set(case.context.event.wines)
        if case.context.reserved_sku:
            f.allowed_skus.add(case.context.reserved_sku)

        for sku in f.allowed_skus:
            p = idx.get(sku)
            if not p:
                continue
            if p.get("vintage"):
                f.allowed_years.add(p["vintage"])
            for k in ("window_start", "window_end"):
                if p.get(k):
                    f.allowed_years.add(p[k])
            if p.get("price"):
                f.allowed_prices.add(float(p["price"]))
        if "OND-SVC-BY" in f.allowed_skus:
            f.allowed_years |= set(self.cfg.products["available_vintages"])

        send = date.fromisoformat(case.send_date)
        f.allowed_years |= {send.year, send.year + 1}
        texts = [t.text for t in case.history] + [case.client.notes or "", str(case.client.preferences)]
        texts += [p.date for p in case.client.purchases]
        texts += [d.date for d in case.client.important_dates]
        ctx = case.context
        texts += [ctx.trigger or "", ctx.festival or ""]
        if ctx.event:
            texts += [ctx.event.date, ctx.event.name]
        for t in texts:
            f.allowed_years |= set(self.find_years(t))
            f.allowed_prices |= set(self.find_prices(t))
            f.allowed_md |= set(self.find_md(t))
        joined = "\n".join(texts)
        f.allowed_aliases = {a for a, _ in self.aliases if a in joined}
        # ISO / MM-DD 日期 → (月, 日)
        for t in texts + [case.client.birthday or ""]:
            for m in re.finditer(r"(?:\d{4}-)?(\d{1,2})-(\d{1,2})", t):
                f.allowed_md.add((int(m.group(1)), int(m.group(2))))
        return f

    # ------------------------------------------------------------------ 用例级预检
    def precheck(self, case: CaseInput) -> Precheck:
        pc = Precheck()
        sc = self.cfg.scenarios["scenarios"][case.scenario]
        c = case.client
        ctx = case.context
        send = date.fromisoformat(case.send_date)

        if c.age < 18:  # R7
            pc.blocked = True
            pc.warnings.append("R7：客户未满 18 岁，酒类品牌不应向其发送任何消息。")
        if c.sensitive:  # R10
            pc.block_marketing = True
            pc.warnings.append(f"R10：客户处于敏感状态（{c.sensitive}），只生成关怀类内容，不含任何营销信息。")
        # R13：末尾连续 CA 消息且客户未回复
        trailing = 0
        for t in reversed(case.history):
            if t.role == "ca":
                trailing += 1
            else:
                break
        if trailing >= 2 and sc["proactive"]:
            pc.light_only = True
            pc.warnings.append(f"R13：客户已连续 {trailing} 条未回复，建议暂缓；如必须发送，只用轻量型。")
        # R12（v2）：客户在对话中拒绝过或决定不买
        refusals = self.cfg.brand.get("refusal_phrases", [])
        client_said = [t.text for t in case.history if t.role == "client"]
        hit = next((m.group(0) for t in client_said for p in refusals if (m := re.search(p, t))), None)
        if hit:
            pc.respect_refusal = True
            if case.scenario == "price_objection":
                pc.warnings.append(f"R12：客户已表示「{hit}」，只做礼貌回应，不再说服。")
            else:
                pc.warnings.append(f"R12：客户曾表示「{hit}」，不应再推同样的内容，建议暂缓或只做关怀。")
        # R11
        no_cel = self.cfg.brand.get("no_celebration_days", {})
        if case.send_date in no_cel and case.scenario == "greeting":
            pc.warnings.append(f"R11：发送日是{no_cel[case.send_date]}，不宜发送庆祝类问候。")
        # V10：主动场景必须有具体触达理由
        if sc["proactive"]:
            has_reason = {
                "greeting": bool(ctx.festival) or (c.birthday == send.strftime("%m-%d")) or any(
                    d.accept_greeting and d.date[-5:] == send.strftime("%m-%d") for d in c.important_dates),
                "recommendation": bool(ctx.trigger or case.product_info),
                "aftercare": bool(c.purchases),
                "reactivation": bool(ctx.trigger),
                "event_invitation": bool(ctx.event),
            }.get(case.scenario, True)
            if not has_reason:
                pc.warnings.append("V10：输入中没有具体的触达理由，建议暂缓发送。")
        # 场景 5：层级资格
        if case.scenario == "event_invitation" and ctx.event:
            if self.cfg.tier_rank(c.tier) < self.cfg.tier_rank(ctx.event.min_tier):
                pc.warnings.append(f"S5：客户层级（{c.tier}）低于活动要求（{ctx.event.min_tier}），不应邀请。")
                pc.blocked = True
        # 纪念日问候只对接受的客户
        if case.scenario == "greeting" and not ctx.festival and c.birthday != send.strftime("%m-%d"):
            if any((not d.accept_greeting) and d.date[-5:] == send.strftime("%m-%d") for d in c.important_dates):
                pc.warnings.append("第 9 节：客户未表示接受纪念日问候，建议不发。")
        return pc

    # ------------------------------------------------------------------ 单条检查
    def _wordlist_hits(self, key: str, text: str) -> list[str]:
        wl = self.wordlists[key]
        hits = []
        for pat in wl["patterns"]:
            for m in pat.finditer(text):
                if wl["negatable"]:
                    window = text[max(0, m.start() - 4):m.start()]
                    if any(n in window for n in self.neg_words):
                        continue
                hits.append(m.group(0))
        return hits

    def check_candidate(self, cand: Candidate, case: CaseInput, facts: CaseFacts,
                        pc: Precheck | None = None) -> list[RuleViolation]:
        b = self.cfg.brand
        sc = self.cfg.scenarios["scenarios"][case.scenario]
        text = cand.text.strip()
        v: list[RuleViolation] = []
        add = lambda r, d: v.append(RuleViolation(rule=r, detail=d))  # noqa: E731
        pc = pc or Precheck()

        # V1 长度
        n = len(PUNCT_RE.sub("", text))
        strat = next((s for s in b["strategies"] if s["id"] == cand.strategy), None)
        max_chars = strat["max_chars"] if strat else b["length"]["max_chars"]
        min_chars = b["length"]["min_chars"]
        if cand.strategy == "light" and not sc["proactive"]:   # v2（D3）：回复客户时轻量型不能太短
            max_chars = b["length"].get("reply_light_max", max_chars)
            min_chars = b["length"].get("reply_light_min", min_chars)
        if pc.light_only:
            max_chars = min(max_chars, 50)
        if n > max_chars:
            add("V1", f"{n} 字，超过上限 {max_chars}")
        if n < min_chars:
            add("V1", f"{n} 字，少于下限 {min_chars}")
        # V2 感叹号与 emoji
        ex = text.count("!") + text.count("！")
        if ex > b["punctuation"]["max_exclamations"]:
            add("V2", f"感叹号 {ex} 个")
        emojis = EMOJI_RE.findall(text)
        if len(emojis) > b["punctuation"]["max_emoji"]:
            add("V2", f"emoji {len(emojis)} 个")
        bad = [e for e in emojis if e not in b["punctuation"]["emoji_whitelist"]]
        if bad:
            add("V2", f"非白名单 emoji：{''.join(bad)}")
        # V3 称呼
        if sc["proactive"] and case.client.preferred_name not in text:
            add("V3", f"没有使用偏好称呼「{case.client.preferred_name}」")
        # V11 句数（主动消息）
        if sc["proactive"]:
            sents = [s for s in SENT_SPLIT_RE.split(text) if s.strip()]
            if len(sents) > b["length"]["max_sentences"]:
                add("V11", f"{len(sents)} 句，超过 {b['length']['max_sentences']} 句")
        # 词表类规则：V3 V4 V5 V8 R1 R4 R5 R6 R7 R8 R14
        for key, wl in self.wordlists.items():
            if key == "R4_reserve" and case.context.reserved_sku:
                continue
            hits = self._wordlist_hits(key, text)
            if hits:
                add(wl["rule"], "命中：" + "、".join(dict.fromkeys(hits)))

        # R3 幻觉：产品、年份、价格、日期都必须来自输入
        found = self.find_products(text)
        mentions = [skus for _, skus in found]
        for alias, skus in found:
            if not (skus & facts.allowed_skus) and alias not in facts.allowed_aliases:
                add("R3", f"提到了输入中没有的产品「{alias}」")
        for y in self.find_years(text):
            if y not in facts.allowed_years:
                add("R3", f"年份 {y} 不在输入中")
        prices = self.find_prices(text)
        for p in prices:
            if p not in facts.allowed_prices:
                add("R3", f"价格 {p:g} 不在输入中")
        for md in self.find_md(text):
            if md not in facts.allowed_md:
                add("R3", f"日期 {md[0]}月{md[1]}日 不在输入中")
        # R9 隐私：不写出客户累计消费
        if case.client.spend_12m and any(abs(p - case.client.spend_12m) < 1 for p in prices):
            add("R9", "写出了客户的累计消费金额")
        # R10 敏感状态：不出现非已购产品、价格、活动
        if pc.block_marketing:
            non_purchased = [s for s in mentions if not (s & facts.purchased_skus)]
            ev = case.context.event
            if non_purchased or prices or (ev and ev.name in text):
                add("R10", "敏感状态下出现了营销内容（产品/价格/活动）")
        # R11 不宜庆祝的日子
        if case.send_date in b.get("no_celebration_days", {}):
            hits = [w for w in b["celebration_words"] if w in text]
            if hits:
                add("R11", "不宜庆祝的日子出现：" + "、".join(hits))

        # 场景 playbook 检查
        checks = sc.get("checks", {}) or {}
        if checks.get("no_product") and mentions:
            add("S1", "问候消息里出现了产品")
        if checks.get("no_price") and prices:
            add("S1", "问候消息里出现了价格")
        if "max_products" in checks:
            distinct = {frozenset(s) for s in mentions}
            if len(distinct) > checks["max_products"]:
                add("S2", f"推荐了 {len(distinct)} 款产品，超过 {checks['max_products']} 款")
        if checks.get("price_cap_multiplier") and case.client.purchases:
            hist_max = max((p.price or 0) for p in case.client.purchases)
            if hist_max:
                cap = hist_max * checks["price_cap_multiplier"]
                idx = self.cfg.sku_index
                for skus in mentions:
                    for s in skus:
                        price = (idx.get(s) or {}).get("price")
                        if price and price > cap and s not in facts.purchased_skus:
                            add("S2", f"{s} 价格 {price} 超过客户历史单笔最高 × {checks['price_cap_multiplier']}（{cap:g}）")
        if checks.get("first_sentence_no_policy"):   # v2（D1）：价格异议第一句只共情
            body = text.split("，", 1)[1] if text.startswith(case.client.preferred_name) else text
            first = SENT_SPLIT_RE.split(body)[0]
            hits = [w for w in ("折扣", "优惠", "统一价", "统一零售", "会员价", "让步", "没法少", "便宜不了") if w in first]
            if hits:
                add("S6", "第一句就谈价格政策：" + "、".join(hits))
        if checks.get("only_purchased_products"):
            others = [s for s in mentions if not (s & facts.purchased_skus)]
            if others:
                add("S3", "售后关怀里推荐了未购买的产品")
        return v

    # ------------------------------------------------------------------ 三条之间
    @staticmethod
    def _bigrams(text: str) -> set[str]:
        t = PUNCT_RE.sub("", text)
        return {t[i:i + 2] for i in range(len(t) - 1)}

    def jaccard(self, a: str, b: str) -> float:
        x, y = self._bigrams(a), self._bigrams(b)
        return len(x & y) / len(x | y) if (x | y) else 0.0

    def check_set(self, cands: list[Candidate]) -> list[RuleViolation]:
        v = []
        th = self.cfg.brand["similarity"]["max_jaccard"]
        for i in range(len(cands)):
            for j in range(i + 1, len(cands)):
                s = self.jaccard(cands[i].text, cands[j].text)
                if s > th:
                    v.append(RuleViolation(rule="SET", detail=f"第 {i + 1} 条与第 {j + 1} 条相似度 {s:.2f} > {th}"))
        if len(cands) != 3:
            v.append(RuleViolation(rule="SET", detail=f"候选数量为 {len(cands)}，应为 3"))
        return v
