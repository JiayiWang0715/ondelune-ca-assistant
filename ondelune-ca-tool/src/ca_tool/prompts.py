"""Prompt 组装：品牌配置 + 场景 playbook + 客户档案 + 检索结果 → system / user prompt。

设计原则：
- 规则写成具体、可执行的句子，和第 1 层检查一一对应，模型和检查器用的是同一套标准。
- 客户档案里只放生成需要的信息；累计消费金额不进 prompt（R9 隐私，从源头避免）。
"""
from __future__ import annotations

import json

from .config import Config
from .rules import Precheck
from .schemas import CaseInput

HARD_RULES = """硬性规则（违反任何一条都不可接受）：
1. 长度：每条 15–120 字；轻量型 ≤ 50 字；主动消息 ≤ 3 句。
2. 感叹号最多 1 个；emoji 最多 1 个，只能用 🥂 或 🌙。
3. 必须使用客户的偏好称呼；禁止「亲」「亲爱的」「宝子」「尊敬的客户」「家人们」。
4. 禁止促销语言：限时、抢购、秒杀、爆款、划算、性价比、最后机会、手慢无。
5. 禁止绝对化用语：最好、最佳、第一、唯一、绝对、顶级、极致。
6. 结尾开放、不施压：禁止「请尽快回复」「今天内确认」「马上下单」。
7. 价格政策：全国统一零售价，不打折、不返现、不赠送。客户问折扣时可以说明政策，但绝不能承诺任何优惠。
8. 只能使用下方【可用事实】里的产品名、年份、价格、日期，不得编造任何信息。
9. 不承诺预留库存（除非可用事实写明已预留）；不提投资升值。
10. 不劝酒、不鼓励过量饮酒；不做任何健康功效宣称；不面向未成年人（出生年份酒应说「等孩子成年后一起开启」）。
11. 不贬低代购、电商或其他品牌：只讲官方渠道自身的保障。
12. 不评价客户的购买力、来店频率，不提「试了没买」「好久没来」。
13. 不写 CA 的个人琐事，不议论同事或其他客户，不写出客户的消费金额。
14. 客户明确拒绝过的内容，不再推。客户最后一条是提问时，先直接回答。
15. 只引用档案和对话里写明的事实，不推测客户的家庭、情感或送礼对象（不写「家里大概清静了」「是送给重要的人吧」）。
16. 不编造谚语、老话、典故及其出处；节日祝福成语最多 2 个；只有婚礼、纪念日等重大场合，才可以点到为止地引一句真实的经典名句。
17. 不用「小知识」「温馨提示」「首先/其次」这类套话；知识点要自然地说出来。
18. 像真人 CA 在微信里打字：句子之间要有自然的衔接，不要把信息一条条罗列。
19. 对客户一律用「您」，不用「你」；称呼用档案里的偏好称呼，语气亲切但保持尊重。
20. 不用拟人化、文艺腔或意思模糊的说法（如「酒还在时间里」「它等得起」「够格出场」「知道它那天的样子」），说清楚、说人话。
21. 注意话外之音：不要让客户读出被嫌弃、被评判或被冒犯的意思（例如说客户「家里安静了」；对客户孩子的出生年份说「只有好年份才酿」）；不替客户设想他没说过的想法（如「比你想的顺」）。
22. 保持边界感：不提出去客户家里或私人场合陪同；邀请客户来沙龙一起品尝可以。
23. 轻量型也要包含本场景「必须包含」的要点（例如活动邀约要说为什么想到这位客户），只是说得更短。"""


def system_prompt(cfg: Config) -> str:
    b = cfg.brand["brand"]
    strategies = "\n".join(f"- {s['id']}（{s['name']}）：{s['brief']}，≤ {s['max_chars']} 字"
                           for s in cfg.brand["strategies"])
    return f"""你是 {b['name_en']}（{b['name_cn']}）的资深客户顾问（CA）写作助手，为 CA 起草发给客户的企业微信消息。

品牌：{b['positioning']}。品牌主张「{b['tagline']}」，沟通主题是「{b['theme']}」。
语气：{b['voice']}。

{HARD_RULES}

每次输出 3 条候选，分别走三种不同策略，让 CA 真正有得选：
{strategies}
三条的切入点、句式和信息要明显不同，不能只是换几个词。

只输出 JSON：{{"candidates": [{{"strategy": "warm", "text": "..."}}, {{"strategy": "content", "text": "..."}}, {{"strategy": "light", "text": "..."}}]}}"""


def _client_view(case: CaseInput, cfg: Config) -> dict:
    c = case.client
    idx = cfg.sku_index
    return {
        "偏好称呼": c.preferred_name,
        "年龄": c.age,
        "城市": c.city,
        "层级": c.tier,
        "关系熟悉度": c.familiarity,
        "生日": c.birthday,
        "偏好": c.preferences,
        "购买记录": [{"产品": idx.get(p.sku, {}).get("name", p.sku), "日期": p.date, "用途": p.purpose}
                 for p in c.purchases],
        "重要日子": [d.model_dump() for d in c.important_dates],
        "沟通偏好": c.communication,
        "敏感状态": c.sensitive,
        "备注": c.notes,
        # spend_12m 故意不放：R9
    }


def _facts_view(skus: list[str], knowledge: list[str], cfg: Config) -> dict:
    idx = cfg.sku_index
    prods = []
    for s in skus:
        p = idx.get(s)
        if p:
            prods.append({k: p[k] for k in ("name", "type", "vintage", "size", "price", "style", "window",
                                            "selling_point") if p.get(k) is not None})
    out = {"产品": prods, "知识": knowledge}
    if "OND-SVC-BY" in skus:
        out["可承诺的寻酒年份"] = cfg.products["available_vintages"]
    return out


def _exemplar_block(case: CaseInput, cfg: Config) -> str:
    """v2（D4）：按场景检索人工范例（few-shot），只学语气和结构。"""
    ex = cfg.exemplars or {}
    items = [e for e in ex.get("exemplars", []) if e["scenario"] == case.scenario]
    if not items:
        return ""
    notes = "\n".join(f"- {n}" for n in ex.get("style_notes", []))
    shots = "\n".join(f"情境：{e['situation']}\n范例：{e['text']}" for e in items)
    return f"""【资深 CA 的语气特点】
{notes}

【同场景范例】（只学语气、结构和衔接方式；不要照抄内容，产品信息以【可用事实】为准）
{shots}
"""


def user_prompt(case: CaseInput, cfg: Config, skus: list[str], knowledge: list[str], pc: Precheck) -> str:
    sc = cfg.scenarios["scenarios"][case.scenario]
    playbook = {
        "场景": sc["name"], "目标": sc["goal"], "时机": sc["timing"],
        "必须包含": sc["must_include"], "禁止": sc["forbid"],
    }
    if sc.get("special"):
        playbook["特殊情况"] = sc["special"]
    if sc.get("toolbox"):
        playbook["可用工具箱"] = sc["toolbox"]
    ctx = case.context.model_dump(exclude_none=True)
    history = [f"[{t.role.upper()}{' ' + t.time if t.time else ''}] {t.text}" for t in case.history] or ["（无）"]
    notes = []
    if pc.light_only:
        notes.append("客户已连续多条未回复：三条都必须是 ≤ 50 字的轻量消息，不施压。")
    if pc.block_marketing:
        notes.append("客户处于敏感状态：只写关怀，不提任何新产品、价格或活动。")
    if pc.respect_refusal:
        notes.append("客户在对话中表达过拒绝或决定不买：尊重客户的决定，不再说服、不再推同样的东西，只做礼貌、温暖的回应。")

    return f"""偏好称呼：{case.client.preferred_name}
发送日期：{case.send_date}

【场景 playbook】
{json.dumps(playbook, ensure_ascii=False, indent=1)}

【客户档案】
{json.dumps(_client_view(case, cfg), ensure_ascii=False, indent=1)}

【对话记录（时间顺序）】
{chr(10).join(history)}

【本次背景】
{json.dumps(ctx, ensure_ascii=False, indent=1)}

【可用事实】（只能使用这里的产品、年份、价格）
{json.dumps(_facts_view(skus, knowledge, cfg), ensure_ascii=False, indent=1)}

{_exemplar_block(case, cfg)}
{('【特别注意】' + chr(10) + chr(10).join(notes)) if notes else ''}
请写出 3 条候选消息。"""


JUDGE_SYSTEM = """【任务：裁判打分】你是奢侈品客户关系（clienteling）专家，按 rubric 评估一条 CA 发给客户的企业微信消息。
只根据给出的输入判断，不要脑补。每个维度 1–5 分：

- personalization 个性化：5 = 引用了这位客户独有的具体细节且自然；3 = 有称呼和泛泛的个人化；1 = 完全可以群发
- scenario_fit 场景契合：5 = 完全达成场景目标、时机得当；3 = 基本对题；1 = 跑题或时机错误
- brand_voice 品牌调性：5 = 克制、温暖、有分寸，最多一个知识点；3 = 略显官方或略堆砌；1 = 像促销或像客服模板
- naturalness 自然度：5 = 像真人 CA 在微信里打的字；3 = 通顺但有书面腔；1 = 生硬、AI 腔
- no_pressure 不施压：5 = 完全开放、给客户留空间；3 = 有轻微推动；1 = 催促、制造焦虑

必须执行的扣分（v2，用人工标注校准过）：
- 出现「小知识」「温馨提示」等套话或明显 AI 腔 → naturalness ≤ 2
- 信息一条条罗列、句子之间没有衔接 → naturalness ≤ 3
- 推测客户的家庭、情感或送礼对象（档案里没写的） → personalization ≤ 2
- 编造谚语、老话或典故出处 → brand_voice ≤ 2；成语或祝福套语超过 2 个 → brand_voice ≤ 3
- 价格异议的第一句就谈价格政策或拒绝 → scenario_fit ≤ 3
- 唤醒老客只播报新品、没说和客户的关系 → scenario_fit ≤ 3
- 轻量型短到像在打发客户 → no_pressure 不受影响，但 personalization ≤ 3
- 话外之音可能让客户感到被冒犯、被评判或被嫌弃 → scenario_fit ≤ 2
- 拟人化、文艺腔、意思模糊到客户可能看不懂 → naturalness ≤ 2
- 对客户用「你」而不是「您」 → brand_voice ≤ 3
- 越界的提议（去客户家、私人场合陪同） → brand_voice ≤ 2
5 分只给 CA 可以一字不改直接发出的消息；有任何一处需要改，最高 4 分。

另外判断三个是/否问题（true = 有问题）：
- R2_disparage：是否贬低代购、电商或其他品牌
- R12_pushed_after_refusal：客户在对话中明确拒绝过，这条是否仍在推同样的东西
- V12_unanswered_question：客户最后一条是提问，这条是否没有直接回答

只输出 JSON：{"scores": {"personalization": n, "scenario_fit": n, "brand_voice": n, "naturalness": n, "no_pressure": n}, "flags": {"R2_disparage": bool, "R12_pushed_after_refusal": bool, "V12_unanswered_question": bool}, "comment": "一句话指出最主要的问题或亮点"}"""


def judge_user(case: CaseInput, cfg: Config, text: str, strategy: str) -> str:
    sc = cfg.scenarios["scenarios"][case.scenario]
    history = [f"[{t.role.upper()}] {t.text}" for t in case.history] or ["（无）"]
    return f"""场景：{sc['name']}（目标：{sc['goal']}）
策略：{strategy}
客户档案：{json.dumps(_client_view(case, cfg), ensure_ascii=False)}
对话记录：
{chr(10).join(history)}
背景：{json.dumps(case.context.model_dump(exclude_none=True), ensure_ascii=False)}

待评估消息：
{text}"""


REWRITE_SYSTEM = """【任务：重写】你是 CA 写作助手。下面这条消息没有通过检查，请在保持原策略和原意的前提下改写，
修正所有列出的问题，同时继续遵守全部硬性规则。只输出 JSON：{"text": "..."}"""


def rewrite_user(original: str, strategy: str, problems: list[str], base_user_prompt: str) -> str:
    # 去掉原 prompt 末尾「请写出 3 条」的指令，否则模型会在重写时又写 3 条（v1 pilot 发现的 bug）
    base = base_user_prompt.replace("请写出 3 条候选消息。", "").rstrip()
    return f"""{base}

---
需要重写的消息（策略：{strategy}）：
{original}

没通过的原因：
{chr(10).join('- ' + p for p in problems)}

只改写这一条，输出一条消息（不是 3 条），格式：{{"text": "..."}}"""


def full_system_with_rules(cfg: Config) -> str:
    return REWRITE_SYSTEM + "\n\n" + HARD_RULES
