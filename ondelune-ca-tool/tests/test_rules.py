"""第 1 层硬规则的单元测试：每条规则至少一个「应通过」和一个「应拦截」的例子。"""
import pytest

from ca_tool.config import load_config
from ca_tool.rules import RuleChecker
from ca_tool.schemas import CaseInput, Candidate

CFG = load_config()
RC = RuleChecker(CFG)


def make_case(**over):
    base = {
        "case_id": "T01",
        "scenario": "recommendation",
        "send_date": "2026-11-10",
        "client": {
            "client_id": "K001", "preferred_name": "陈先生", "age": 42, "tier": "臻选客户",
            "preferences": {"style": ["白中白"]},
            "purchases": [{"sku": "OND-BDB-2015", "date": "2026-03-02", "purpose": "自饮", "price": 2600}],
            "spend_12m": 31200,
        },
        "context": {"trigger": "2016 年份新发布"},
        "product_info": ["OND-VT-2016"],
    }
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k] = {**base[k], **v}
        else:
            base[k] = v
    return CaseInput.model_validate(base)


def rules_of(text, case=None, strategy="warm", pc=None):
    case = case or make_case()
    facts = RC.collect_facts(case, retrieved=[])
    return {v.rule for v in RC.check_candidate(Candidate(strategy=strategy, text=text), case, facts, pc)}


GOOD = "陈先生，记得您很喜欢白中白 2015 的矿物感。我们的年份 Brut 2016 刚刚发布，风格同样清爽，下次来沙龙可以先尝一杯。"


def test_good_message_passes():
    assert rules_of(GOOD) == set()


# ---------- V 调性 ----------
def test_v1_too_long():
    assert "V1" in rules_of("陈先生，" + "这款酒非常适合您" * 20)


def test_v1_light_limit():
    assert "V1" in rules_of(GOOD, strategy="light")  # 轻量型 ≤ 50 字


def test_v2_exclamations_and_emoji():
    assert "V2" in rules_of("陈先生，新年份到了！！欢迎来尝一尝。")
    assert "V2" in rules_of("陈先生，新年份到了😀 欢迎来沙龙尝一尝。")
    assert "V2" not in rules_of("陈先生，新年份到了🥂 欢迎来沙龙尝一尝。")


def test_v3_address():
    assert "V3" in rules_of("您好，年份 Brut 2016 刚刚发布，欢迎来沙龙尝一尝。")
    assert "V3" in rules_of("亲爱的陈先生，年份 Brut 2016 刚刚发布，欢迎来尝。")


def test_v4_v5_v8_wordlists():
    assert "V4" in rules_of("陈先生，年份 Brut 2016 是今年的爆款，欢迎来沙龙品尝。")
    assert "V5" in rules_of("陈先生，年份 Brut 2016 是我们最好的年份之一，欢迎来尝。")
    assert "V5" not in rules_of("陈先生，第一次喝年份 Brut 2016 的感受很特别，欢迎来尝。")
    assert "V8" in rules_of("陈先生，年份 Brut 2016 刚刚发布，请尽快回复我确认。")


def test_v11_sentences():
    assert "V11" in rules_of("陈先生好。年份 Brut 2016 发布了。风格清爽。适合配海鲜。欢迎来尝。")


# ---------- R 红线 ----------
def test_r1_discount_and_negation():
    obj = make_case(scenario="price_objection")
    assert "R1" in rules_of("理解您的考虑，这次可以给您打个九折。", obj)
    assert "R1" not in rules_of("理解您的考虑，我们全国统一价，不做折扣，但很欢迎您先来沙龙品鉴。", obj)


def test_r3_hallucinated_product_year_price_date():
    assert "R3" in rules_of("陈先生，潮汐 2008 也很适合您，欢迎来尝。")          # 产品不在输入
    assert "R3" in rules_of("陈先生，2011 年份的酒也很好，欢迎来沙龙。")          # 年份不在输入
    assert "R3" in rules_of("陈先生，年份 Brut 2016 只要 1999 元，欢迎来沙龙。")  # 价格不对
    assert "R3" not in rules_of("陈先生，年份 Brut 2016 是 2200 元，欢迎来沙龙尝一尝。")
    assert "R3" in rules_of("陈先生，12月3日沙龙有品鉴，欢迎来尝年份 Brut 2016。")  # 日期不在输入


def test_r3_style_word_from_input_allowed():
    # 「白中白」出现在客户偏好里，作为风格词提及不算编造
    case = make_case(purchases=[])
    case.client.purchases = []
    assert "R3" not in rules_of("陈先生，记得您喜欢白中白的风格，年份 Brut 2016 也很清爽，欢迎来尝。", case)


def test_r4_r5_r6_r8():
    assert "R4" in rules_of("陈先生，年份 Brut 2016 我先给您留一瓶。")
    assert "R5" in rules_of("陈先生，年份 Brut 2016 周末和朋友一醉方休吧。")
    assert "R6" in rules_of("陈先生，年份 Brut 2016 适量饮用对身体好。")
    assert "R6" not in rules_of("陈先生，祝您身体健康，年份 Brut 2016 欢迎来尝。")
    assert "R8" in rules_of("陈先生，年份 Brut 2016 放几年肯定升值。")


def test_r7_minor():
    assert "R7" in rules_of("陈先生，年份 Brut 2016 也可以给孩子尝一口。")
    pc = RC.precheck(make_case(client={"age": 17}))
    assert pc.blocked


def test_r9_spend_privacy():
    assert "R9" in rules_of("陈先生，感谢您今年在我们这里消费了 31200 元。")


def test_r10_sensitive_blocks_marketing():
    case = make_case(scenario="aftercare", client={"sensitive": "近期丧亲"})
    pc = RC.precheck(case)
    assert pc.block_marketing
    assert "R10" in rules_of("陈先生，节哀。年份 Brut 2016 刚刚发布。", case, pc=pc)
    assert "R10" not in rules_of("陈先生，这段时间辛苦了，有任何需要随时告诉我。", case, pc=pc)


def test_r11_no_celebration_on_qingming():
    case = make_case(scenario="greeting", send_date="2027-04-05", context={"festival": None})
    assert "R11" in rules_of("陈先生，祝您节日快乐。", case)


def test_r13_unanswered_switches_to_light():
    case = make_case(history=[
        {"role": "client", "text": "好的谢谢"},
        {"role": "ca", "text": "陈先生，新年份到了"},
        {"role": "ca", "text": "陈先生，周末有品鉴会"},
    ])
    pc = RC.precheck(case)
    assert pc.light_only
    assert "V1" in rules_of(GOOD, case, pc=pc)


def test_r14_judging():
    assert "R14" in rules_of("陈先生，好久没来了，年份 Brut 2016 欢迎来尝。")


# ---------- S 场景 ----------
def test_s1_greeting_no_product():
    case = make_case(scenario="greeting", context={"festival": "中秋"})
    assert "S1" in rules_of("陈先生，中秋快乐，配一瓶年份 Brut 2016 正合适。", case)
    assert rules_of("陈先生，中秋快乐，愿您和家人共度一个安静美好的团圆夜。", case) == set()


def test_s2_too_many_products_and_price_cap():
    assert "S2" in rules_of("陈先生，年份 Brut 2016、晨曦 桃红和零度都很适合您。",
                            make_case(product_info=["OND-VT-2016", "OND-NV-ROSE", "OND-NV-EXB"]))
    assert "S2" in rules_of("陈先生，潮汐 2008 很适合您收藏，欢迎来尝。",
                            make_case(product_info=["OND-PC-2008"]))  # 8800 > 2600×2


def test_s3_aftercare_no_cross_sell():
    case = make_case(scenario="aftercare")
    assert "S3" in rules_of("陈先生，白中白 2015 喝得还好吗？年份 Brut 2016 也刚发布。", case)


def test_s5_tier_eligibility():
    case = make_case(scenario="event_invitation", client={"tier": "品鉴客户"}, context={"event": {
        "name": "2016 年份发布晚宴", "date": "2026-11-28", "location": "上海沙龙",
        "format": "8 人晚宴", "duration": "约 2.5 小时", "min_tier": "臻选客户"}})
    assert RC.precheck(case).blocked


def test_v10_no_reason_warning():
    case = make_case(scenario="reactivation", context={"trigger": None})
    assert any("V10" in w for w in RC.precheck(case).warnings)


# ---------- SET ----------
def test_similarity():
    a = Candidate(strategy="warm", text=GOOD)
    b = Candidate(strategy="content", text=GOOD.replace("刚刚", "刚"))
    c = Candidate(strategy="light", text="陈先生，2016 新年份到了，有空来尝尝。")
    assert any(v.rule == "SET" for v in RC.check_set([a, b, c]))
    d = Candidate(strategy="content", text="陈先生，2016 是个凉爽的年份，酸度很漂亮，配生蚝会很出彩。")
    assert not any(v.rule == "SET" for v in RC.check_set([a, d, c]))


# ---------- v2 新增规则 ----------
def test_v13_ai_tone():
    assert "V13" in rules_of("陈先生，分享一个小知识：年份 Brut 2016 很适合配海鲜，欢迎来尝。")


def test_r16_fabricated_lore():
    assert "R16" in rules_of("陈先生，香槟区的老话是：好酒不怕等。年份 Brut 2016 欢迎来尝。")


def test_s6_first_sentence_policy():
    obj = make_case(scenario="price_objection")
    assert "S6" in rules_of("陈先生，价格是全国统一的，没有折扣。不过很欢迎您来沙龙先尝尝。", obj)
    assert "S6" not in rules_of("陈先生，理解您的考虑。我们一直坚持全国统一价，也欢迎您来沙龙先尝尝。", obj)


def test_reply_light_not_too_short():
    obj = make_case(scenario="price_objection")
    assert "V1" in rules_of("陈先生，理解，欢迎来尝。", obj, strategy="light")


def test_r12_refusal_precheck():
    case = make_case(history=[{"role": "client", "text": "最近不需要了，谢谢"}])
    pc = RC.precheck(case)
    assert pc.respect_refusal and any("R12" in w for w in pc.warnings)


def test_r12_no_false_positive_on_budget():
    case = make_case(history=[{"role": "client", "text": "2600 一瓶有点超预算了"}])
    assert not RC.precheck(case).respect_refusal


def test_v14_use_nin():
    assert "V14" in rules_of("陈先生，年份 Brut 2016 很适合你，欢迎来沙龙尝。")
    assert "V14" not in rules_of(GOOD)


def test_v13_literary_vague():
    assert "V13" in rules_of("陈先生，2025 年的酒还在时间里，等它够格出场再告诉您。")
