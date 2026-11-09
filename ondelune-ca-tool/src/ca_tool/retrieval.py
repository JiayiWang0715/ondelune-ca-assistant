"""检索层（结构化 RAG）。

产品库只有 11 个 SKU，可以整表塞进 prompt；但真实品牌有上千个 SKU 和历史话术库，
所以这里按「场景 → 过滤 → 打分 → 取 top-k」检索，只把相关的产品和知识交给模型。
这样既减少幻觉（模型只看到该看的产品），也让架构能扩展到大目录。
"""
from __future__ import annotations

from datetime import date

from .config import Config
from .schemas import CaseInput

TOP_K = 3


def _pref_terms(case: CaseInput) -> set[str]:
    terms: set[str] = set()
    for v in case.client.preferences.values():
        if isinstance(v, list):
            terms |= {str(x) for x in v}
        elif v:
            terms.add(str(v))
    if case.context.trigger:
        terms.add(case.context.trigger)
    return terms


def _match_score(p: dict, terms: set[str]) -> int:
    tags = set(p.get("style", [])) | set(p.get("occasions", []))
    score = 0
    for t in terms:
        for tag in tags:
            if tag and (tag in t or t in tag):
                score += 1
    return score


def retrieve(case: CaseInput, cfg: Config) -> tuple[list[str], list[str]]:
    """返回 (检索到的 SKU 列表, 相关知识片段)。"""
    idx = cfg.sku_index
    purchased = [p.sku for p in sorted(case.client.purchases, key=lambda p: p.date, reverse=True)]
    year = date.fromisoformat(case.send_date).year
    knowledge: list[str] = []
    sc = case.scenario

    if sc == "greeting":
        return [], knowledge

    if sc == "aftercare":
        skus = purchased[:1]
        sk = cfg.products["serving_knowledge"]
        knowledge += [sk["storage"]]
        if skus and idx.get(skus[0], {}).get("vintage"):
            knowledge.append(sk["serving_vintage"])
        else:
            knowledge.append(sk["serving_nv"])
        return skus, knowledge

    if sc == "event_invitation":
        ev = case.context.event
        return (list(ev.wines) if ev else []), knowledge

    if sc == "reactivation":
        # 由头：藏酒进入适饮期，或新年份发布
        in_window = [s for s in purchased if (idx.get(s, {}).get("window_start") or 9999) <= year
                     <= (idx.get(s, {}).get("window_end") or 0)]
        new = [p["sku"] for p in cfg.product_list if p.get("new_release")]
        return list(dict.fromkeys(case.product_info + in_window[:1] + new[:1]))[:TOP_K], knowledge

    # recommendation / price_objection：按偏好打分，排除超价位和已购（复购除外）
    hist_max = max([p.price or 0 for p in case.client.purchases] or [0])
    cap = hist_max * 2 if hist_max else None
    terms = _pref_terms(case)
    cands = []
    for p in cfg.product_list:
        if p["type"] == "服务" or not p.get("price"):
            continue
        if p["sku"] in purchased and sc == "recommendation":
            continue
        if cap and p["price"] > cap:
            continue
        cands.append((_match_score(p, terms) + (1 if p.get("new_release") else 0), -p["price"], p["sku"]))
    cands.sort(reverse=True)
    ranked = [s for *_, s in cands]

    if sc == "price_objection":
        # 主产品 + 同风格更低价位的替代
        main = case.product_info[:1]
        alts = []
        if main and main[0] in idx:
            mp = idx[main[0]]
            alts = [s for s in ranked if s != main[0] and idx[s]["price"] < mp["price"]
                    and set(idx[s]["style"]) & set(mp["style"])]
            if not alts:
                alts = [s for s in ranked if s != main[0] and idx[s]["price"] < mp["price"]]
        return list(dict.fromkeys(main + alts[:1])), knowledge

    return list(dict.fromkeys(case.product_info + ranked))[:TOP_K], knowledge
