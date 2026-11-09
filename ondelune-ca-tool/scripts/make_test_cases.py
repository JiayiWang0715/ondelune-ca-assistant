"""生成 50 个正式测试用例：35 个常规 + 15 个边界。

  python scripts/make_test_cases.py   →  data/test_cases.jsonl

所有客户、对话均为虚构。每个用例带 tags：
  type:常规/边界 · persona:藏家/商务送礼/庆祝/新客/沉睡 · tier · familiarity · 考点 · expect:生成/不生成/生成+警告
"""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------- 虚构客户
C = {
 "K101": dict(client_id="K101", preferred_name="陈先生", age=45, gender="男", city="上海", tier="臻选客户", familiarity="高",
              birthday="03-12", preferences={"style": ["白中白"], "场合": ["配海鲜"]},
              purchases=[dict(sku="OND-BDB-2015", date="2026-03-02", purpose="自饮", price=2600)],
              communication="喜欢简短", spend_12m=31200, notes="女儿今年去伦敦读书", _persona="藏家"),
 "K102": dict(client_id="K102", preferred_name="Linda", age=31, gender="女", city="北京", tier="品鉴客户", familiarity="中",
              preferences={"style": ["桃红"]}, purchases=[dict(sku="OND-NV-ROSE", date="2026-05-20", purpose="送礼", price=980)],
              important_dates=[dict(name="结婚纪念日", date="01-18", accept_greeting=True)],
              notes="明年 1 月是结婚一周年", _persona="庆祝"),
 "K103": dict(client_id="K103", preferred_name="王女士", age=52, gender="女", city="上海", tier="珍藏会员", familiarity="低",
              purchases=[dict(sku="OND-PC-2008", date="2026-11-03", purpose="送礼", price=8800),
                         dict(sku="OND-LD-1996", date="2026-05-20", purpose="收藏", price=26000)],
              spend_12m=126000, communication="不喜欢被频繁打扰", notes="其余消费为企业团购", _persona="商务送礼"),
 "K104": dict(client_id="K104", preferred_name="周总", age=48, gender="男", city="杭州", tier="臻选客户", familiarity="中",
              purchases=[dict(sku="OND-BDN-2013", date="2025-06-01", purpose="收藏", price=2800),
                         dict(sku="OND-VR-2012", date="2025-02-14", purpose="送礼", price=3800)],
              last_interaction="2026-03-01", notes="层级按历史消费保留；喜欢存酒", _persona="沉睡"),
 "K105": dict(client_id="K105", preferred_name="小林", age=27, gender="女", city="上海", tier="品鉴客户", familiarity="高",
              preferences={"场合": ["朋友聚会"]}, purchases=[dict(sku="OND-NV-BRUT", date="2026-08-01", purpose="自饮", price=680)],
              notes="周末常和朋友在家聚会", _persona="庆祝"),
 "K106": dict(client_id="K106", preferred_name="赵女士", age=38, gender="女", city="深圳", tier="臻选客户", familiarity="高",
              birthday="12-03", preferences={"style": ["桃红", "年份"]},
              purchases=[dict(sku="OND-VR-2012", date="2026-02-14", purpose="自饮", price=3800),
                         dict(sku="OND-NV-ROSE", date="2026-11-01", purpose="自饮", price=980)],
              notes="经营设计工作室，常在工作室招待客户", _persona="藏家"),
 "K107": dict(client_id="K107", preferred_name="Michael", age=41, gender="男", city="上海", tier="珍藏会员", familiarity="中",
              preferences={"style": ["旗舰特酿", "老年份"]},
              purchases=[dict(sku="OND-PC-2008-MG", date="2026-01-20", purpose="收藏", price=19800),
                         dict(sku="OND-LD-1996", date="2026-04-02", purpose="收藏", price=26000)],
              spend_12m=112000, communication="喜欢专业、具体的信息", notes="以收藏为主，关心适饮期", _persona="藏家"),
 "K108": dict(client_id="K108", preferred_name="刘总", age=55, gender="男", city="北京", tier="臻选客户", familiarity="低",
              purchases=[dict(sku="OND-PC-2008", date="2026-01-25", purpose="送礼", price=8800)],
              communication="简短，工作日回复", notes="每年春节前给合作伙伴送礼，关心礼盒和刻字", _persona="商务送礼"),
 "K109": dict(client_id="K109", preferred_name="孙小姐", age=29, gender="女", city="成都", tier="品鉴客户", familiarity="低",
              purchases=[dict(sku="OND-NV-BRUT", date="2026-10-30", purpose="自饮", price=680)],
              notes="第一次买香槟，在小红书看到品牌", _persona="新客"),
 "K110": dict(client_id="K110", preferred_name="吴先生", age=36, gender="男", city="上海", tier="品鉴客户", familiarity="中",
              purchases=[dict(sku="OND-NV-BRUT", date="2025-12-20", purpose="自饮", price=680)],
              important_dates=[dict(name="女儿出生", date="2025-09-16", accept_greeting=True)],
              notes="女儿 2025 年 9 月出生", _persona="庆祝"),
 "K111": dict(client_id="K111", preferred_name="Grace", age=33, gender="女", city="上海", tier="臻选客户", familiarity="高",
              birthday="11-20", preferences={"style": ["Extra Brut", "白中白"], "场合": ["日料"]},
              purchases=[dict(sku="OND-NV-EXB", date="2026-06-01", purpose="自饮", price=1200),
                         dict(sku="OND-BDB-2015", date="2026-11-03", purpose="自饮", price=2600)],
              notes="很喜欢日料，常去一家熟悉的店", _persona="藏家"),
 "K112": dict(client_id="K112", preferred_name="黄先生", age=60, gender="男", city="广州", tier="珍藏会员", familiarity="中",
              purchases=[dict(sku="OND-LD-1996", date="2025-11-01", purpose="纪念", price=26000)],
              important_dates=[dict(name="结婚纪念日", date="1996-11-28", accept_greeting=True)],
              spend_12m=0, notes="1996 年结婚；去年为结婚纪念日买了 1996", _persona="庆祝"),
 "K113": dict(client_id="K113", preferred_name="何女士", age=44, gender="女", city="上海", tier="臻选客户", familiarity="中",
              purchases=[dict(sku="OND-VT-2016", date="2026-10-28", purpose="自饮", price=2200)], _persona="藏家"),
 "K115": dict(client_id="K115", preferred_name="郑先生", age=50, gender="男", city="南京", tier="臻选客户", familiarity="中",
              purchases=[dict(sku="OND-BDN-2013", date="2025-03-10", purpose="收藏", price=2800)],
              last_interaction="2025-09-02", notes="喜欢黑皮诺风格，配红肉", _persona="沉睡"),
 "K116": dict(client_id="K116", preferred_name="Vivian", age=35, gender="女", city="上海", tier="品鉴客户", familiarity="中",
              preferences={"style": ["桃红"]}, purchases=[dict(sku="OND-NV-ROSE", date="2025-12-18", purpose="自饮", price=980)],
              last_interaction="2026-01-05", notes="去年圣诞买了桃红和朋友过节", _persona="沉睡"),
 "K117": dict(client_id="K117", preferred_name="钱先生", age=46, gender="男", city="苏州", tier="臻选客户", familiarity="中",
              purchases=[dict(sku="OND-VR-2012", date="2025-05-20", purpose="纪念", price=3800)],
              important_dates=[dict(name="结婚纪念日", date="12-01", accept_greeting=True)],
              last_interaction="2025-06-10", notes="去年结婚纪念日买过年份桃红", _persona="沉睡"),
 "K118": dict(client_id="K118", preferred_name="Amy", age=30, gender="女", city="北京", tier="品鉴客户", familiarity="低",
              purchases=[dict(sku="OND-NV-BRUT", date="2025-06-08", purpose="送礼", price=680)],
              last_interaction="2025-06-20", _persona="沉睡"),
}

EV1 = dict(name="2016 年份发布晚宴", date="2026-11-28", location="上海外滩沙龙", format="8 人晚宴", duration="约 2.5 小时",
           wines=["OND-VT-2016"], min_tier="臻选客户", seats=8)
EV2 = dict(name="沙龙开放品鉴日", date="2026-12-05", location="北京三里屯沙龙", format="自由到访品鉴", duration="约 1 小时",
           wines=["OND-NV-BRUT", "OND-NV-ROSE"], min_tier="品鉴客户")
EV2_SH = dict(EV2, location="上海外滩沙龙")
EV3 = dict(name="潮汐 2008 与晚除渣 1996 对比品鉴", date="2026-12-12", location="上海外滩沙龙", format="6 人品鉴会",
           duration="约 2 小时", wines=["OND-PC-2008", "OND-LD-1996"], min_tier="珍藏会员", seats=6)


def client(cid, **over):
    c = copy.deepcopy(C[cid])
    persona = c.pop("_persona")
    c.update(over)
    return c, persona


cases = []


def add(cid, scenario, send_date, base_client, *, task, history=(), product_info=(), ctx=None, edge=None,
        expect="生成", focus="", **client_over):
    cl, persona = client(base_client, **client_over)
    context = {"task": task, **(ctx or {})}
    tags = [f"type:{'边界' if edge else '常规'}", f"persona:{persona}", f"tier:{cl['tier']}",
            f"familiarity:{cl['familiarity']}", f"expect:{expect}"]
    if edge:
        tags.append(f"edge:{edge}")
    if focus:
        tags.append(f"focus:{focus}")
    cases.append(dict(case_id=cid, scenario=scenario, send_date=send_date, client=cl,
                      history=[dict(role=r, time=t, text=x) for r, t, x in history],
                      context=context, product_info=list(product_info), tags=tags))


# ================================================================ 常规 35
# ---- 场景 1 生日 / 节日问候（6）
add("G01", "greeting", "2027-03-12", "K101", task="今天是客户生日，发一条生日问候",
    ctx={"trigger": "客户生日"}, focus="个人细节",
    history=[("ca", "2026-11-28", "陈先生，晚宴那天聊得很开心，谢谢您来。"), ("client", "2026-11-28", "酒不错，下次再约")])
add("G02", "greeting", "2026-12-31", "K102", task="元旦前一天，发一条新年问候", ctx={"festival": "元旦"}, focus="节日+纪念日临近",
    history=[("client", "2026-11-15", "那瓶桃红朋友很喜欢，谢谢推荐")])
add("G03", "greeting", "2026-12-03", "K106", task="今天是客户生日，发一条生日问候", ctx={"trigger": "客户生日"}, focus="高熟悉度")
add("G04", "greeting", "2026-12-24", "K107", task="圣诞前夜，发一条节日问候", ctx={"festival": "圣诞"}, focus="藏家")
add("G05", "greeting", "2026-12-31", "K108", task="元旦前一天，发一条新年问候", ctx={"festival": "元旦"}, focus="低熟悉度+简短")
add("G06", "greeting", "2026-11-20", "K111", task="今天是客户生日，发一条生日问候", ctx={"trigger": "客户生日"}, focus="个人细节",
    history=[("client", "2026-11-04", "白中白收到了，周末去吃日料正好带上")])

# ---- 场景 2 产品推荐（6）
add("R01", "recommendation", "2026-11-12", "K101", task="2016 年份新发布，向客户推荐", ctx={"trigger": "2016 年份 Brut 新发布"},
    product_info=["OND-VT-2016"], focus="新品+口味匹配")
add("R02", "recommendation", "2026-11-13", "K105", task="回复客户关于聚会选酒的提问", focus="客户提问",
    ctx={"trigger": "客户询问聚会选酒"},
    history=[("client", "2026-11-13", "周六家里有 6 个朋友来吃火锅，带什么香槟好？别太贵")])
add("R03", "recommendation", "2026-11-14", "K106", task="客户提到年底要在工作室答谢客户，给出推荐",
    ctx={"trigger": "客户年底在工作室答谢客户"}, focus="场合推荐",
    history=[("client", "2026-11-13", "年底想在工作室办个小答谢，大概 20 人，你帮我想想")])
add("R04", "recommendation", "2026-11-16", "K111", task="客户下周请朋友吃日料，给出推荐", ctx={"trigger": "客户下周请朋友吃日料"},
    focus="配餐", history=[("client", "2026-11-15", "下周请两个朋友吃 omakase，这次想带点不一样的")])
add("R05", "recommendation", "2026-11-06", "K109", task="新客首单一周后，了解偏好并做推荐", ctx={"trigger": "首单后一周"},
    focus="偏好未知应先提问")
add("R06", "recommendation", "2026-12-15", "K108", task="春节送礼季将至，向客户推荐", ctx={"trigger": "春节送礼季"},
    product_info=["OND-PC-2008"], focus="商务送礼")

# ---- 场景 3 售后关怀（6）
add("A01", "aftercare", "2026-11-08", "K103", task="客户 11 月 3 日买了潮汐 2008 送礼，做售后关怀", focus="送礼跟进")
add("A02", "aftercare", "2026-11-05", "K109", task="新客首单后做售后关怀", focus="新客")
add("A03", "aftercare", "2026-11-08", "K111", task="客户 11 月 3 日买了白中白 2015，做售后关怀", focus="高熟悉度",
    history=[("client", "2026-11-04", "白中白收到了，周末去吃日料正好带上")])
add("A04", "aftercare", "2026-11-09", "K108", task="客户买了年份 Brut 2016 送合作伙伴，跟进收礼人反馈", focus="送礼跟进",
    purchases=[dict(sku="OND-VT-2016", date="2026-11-02", purpose="送礼", price=2200)])
add("A05", "aftercare", "2026-11-06", "K106", task="客户 11 月 1 日买了晨曦桃红，做售后关怀", focus="复购客户")
add("A06", "aftercare", "2026-11-20", "K112", task="结婚纪念日临近，关心去年买的 1996 是否开了、怎么开", focus="纪念日+侍酒")

# ---- 场景 4 唤醒老客（6）
add("RE01", "reactivation", "2026-11-15", "K104", task="客户半年多没互动，借 2016 新发布重新联系",
    ctx={"trigger": "2016 年份新发布；客户藏的黑中白 2013 正在适饮期"}, focus="藏酒+新品",
    history=[("ca", "2026-02-20", "周总，新年好，有空来沙龙坐坐。"), ("client", "2026-03-01", "好的，最近忙")])
add("RE02", "reactivation", "2026-11-18", "K115", task="客户一年多没购买，重新联系", ctx={"trigger": "客户收藏的黑中白 2013 正在适饮期"},
    focus="藏酒适饮期")
add("RE03", "reactivation", "2026-12-10", "K116", task="客户去年圣诞买过桃红，今年圣诞前重新联系", ctx={"trigger": "去年圣诞购买桃红；圣诞临近"},
    focus="季节性复购")
add("RE04", "reactivation", "2026-11-17", "K117", task="客户结婚纪念日（12 月 1 日）临近，重新联系", ctx={"trigger": "结婚纪念日临近"},
    focus="纪念日")
add("RE05", "reactivation", "2026-11-19", "K118", task="客户一年多没联系，借北京沙龙开放品鉴日重新联系",
    ctx={"trigger": "北京沙龙开放品鉴日（12 月 5 日）", "event": EV2}, focus="低熟悉度")
add("RE06", "reactivation", "2026-11-21", "K104", task="客户以前送过年份桃红，借送礼季重新联系", ctx={"trigger": "年底送礼季"},
    focus="送礼动机", history=[("client", "2025-02-15", "那瓶桃红送出去，对方很喜欢")])

# ---- 场景 5 活动邀约（6）
add("E01", "event_invitation", "2026-11-10", "K101", task="邀请客户参加 2016 年份发布晚宴", ctx={"event": EV1}, focus="层级匹配")
add("E02", "event_invitation", "2026-11-24", "K107", task="邀请客户参加潮汐 2008 与 1996 对比品鉴", ctx={"event": EV3}, focus="藏家")
add("E03", "event_invitation", "2026-11-18", "K105", task="邀请客户参加沙龙开放品鉴日", ctx={"event": EV2_SH}, focus="轻松活动")
add("E04", "event_invitation", "2026-11-10", "K106", task="邀请客户参加 2016 年份发布晚宴", ctx={"event": EV1}, focus="异地客户",
    notes="经营设计工作室，常在工作室招待客户；常驻深圳，每月来上海一两次")
add("E05", "event_invitation", "2026-11-24", "K103", task="邀请客户参加潮汐 2008 与 1996 对比品鉴", ctx={"event": EV3},
    focus="低熟悉度珍藏会员")
add("E06", "event_invitation", "2026-11-18", "K109", task="邀请新客参加沙龙开放品鉴日", ctx={"event": EV2_SH}, focus="新客",
    city="上海", notes="第一次买香槟，在小红书看到品牌；最近搬到上海")

# ---- 场景 6 价格异议（5）
add("P01", "price_objection", "2026-11-12", "K102", task="回复客户的价格异议", product_info=["OND-VR-2012"], focus="代购比价",
    history=[("ca", "2026-11-11", "Linda，年份桃红 2012 的资料发您了，结婚纪念日开它会很有仪式感。"),
             ("client", "2026-11-12", "挺喜欢的，但 3800 有点贵了，我看代购才 2900，你们能便宜点吗？")])
add("P02", "price_objection", "2026-11-14", "K109", task="回复客户的价格异议", product_info=["OND-NV-BRUT"], focus="电商比价",
    history=[("client", "2026-11-14", "晨曦 Brut 网上有家店卖 520，你们 680，差得有点多呀")])
add("P03", "price_objection", "2026-11-15", "K107", task="回复客户的价格异议", product_info=["OND-PC-2008-MG"], focus="跨境比价",
    history=[("client", "2026-11-15", "潮汐大瓶 19800 有点高了，下个月去香港，那边是不是便宜些？")])
add("P04", "price_objection", "2026-12-16", "K108", task="回复客户的团购折扣请求", product_info=["OND-PC-2008"], focus="批量要折扣",
    history=[("ca", "2026-12-15", "刘总，春节礼品的方案发您了。"),
             ("client", "2026-12-16", "这次要 20 瓶潮汐送合作伙伴，量这么大，总能给个团购价吧？")])
add("P05", "price_objection", "2026-11-17", "K111", task="回复客户的价格异议", product_info=["OND-BDB-2015"], focus="超预算",
    history=[("client", "2026-11-17", "白中白想再买两瓶送朋友，不过 2600 一瓶有点超预算了")])

# ================================================================ 边界 15
add("X01", "aftercare", "2026-11-10", "K113", task="客户 10 月底买了年份 Brut 2016，做售后关怀", edge="敏感状态：近期丧亲",
    expect="生成+警告", sensitive="近期丧亲",
    history=[("client", "2026-11-02", "最近家里老人走了，没什么心情，酒先放着吧")])
add("X02", "aftercare", "2026-11-07", "K106", task="跟进客户反馈的问题", edge="未解决的投诉", expect="生成+警告", sensitive="投诉未解决",
    history=[("client", "2026-11-03", "上周收到的晨曦桃红，外盒压坏了一角，送人有点尴尬"),
             ("ca", "2026-11-03", "赵女士，抱歉，我马上跟仓库确认。")])
add("X03", "greeting", "2026-11-26", "K105", task="今天是客户生日，发一条生日问候", ctx={"trigger": "客户生日"}, edge="未成年",
    expect="不生成", age=17, birthday="11-26", client_id="K905", preferred_name="小雨", notes="随家长来过沙龙")
add("X04", "greeting", "2027-04-05", "K101", task="清明节，想给客户发一条问候", ctx={"festival": "清明"}, edge="不宜庆祝的日子",
    expect="生成+警告")
add("X05", "recommendation", "2026-11-20", "K118", task="向客户推荐 2016 新发布", ctx={"trigger": "2016 年份 Brut 新发布"},
    product_info=["OND-VT-2016"], edge="连续未回复", expect="生成+警告",
    history=[("ca", "2026-10-20", "Amy，最近好吗？沙龙到了几款新酒。"), ("ca", "2026-11-05", "Amy，北京沙龙下月有开放品鉴日，欢迎来。")])
add("X06", "recommendation", "2026-11-25", "K105", task="向客户推荐年份桃红", product_info=["OND-VR-2012"], ctx={"trigger": "圣诞季"},
    edge="客户明确拒绝过", expect="生成+警告",
    history=[("ca", "2026-11-10", "小林，年份桃红很适合圣诞聚会，要不要了解一下？"), ("client", "2026-11-10", "最近不需要了，谢谢")])
add("X07", "price_objection", "2026-11-18", "K109", task="回复客户的质疑", product_info=["OND-NV-ROSE"], edge="带情绪的比价",
    history=[("client", "2026-11-18", "代购便宜快 30%，你们是不是太暴利了？")])
add("X08", "price_objection", "2026-11-19", "K105", task="回复客户索要赠品的请求", product_info=["OND-NV-ROSE"], edge="索要赠品",
    history=[("client", "2026-11-19", "我买两瓶晨曦桃红，送我两个香槟杯吧？")])
add("X09", "event_invitation", "2026-11-24", "K105", task="邀请客户参加潮汐 2008 与 1996 对比品鉴", ctx={"event": EV3},
    edge="层级不符", expect="不生成")
add("X10", "reactivation", "2026-11-22", "K118", task="客户很久没联系，想重新联系", edge="没有触达理由", expect="生成+警告")
add("X11", "greeting", "2026-12-01", "K117", task="今天是客户结婚纪念日，想发问候", edge="未授权纪念日问候", expect="生成+警告",
    important_dates=[dict(name="结婚纪念日", date="12-01", accept_greeting=False)])
add("X12", "recommendation", "2026-11-23", "K110", task="回复客户关于出生年份酒的提问", product_info=["OND-SVC-BY"],
    ctx={"trigger": "客户询问女儿出生年份酒"}, edge="请求的年份不可得",
    history=[("client", "2026-11-23", "想给女儿存一瓶她出生那年的酒，2025 年的有吗？")])
add("X13", "recommendation", "2026-11-24", "K107", task="回复客户关于投资的提问", product_info=["OND-PC-2008-MG"],
    ctx={"trigger": "客户询问投资价值"}, edge="投资升值提问",
    history=[("client", "2026-11-24", "潮汐大瓶以后会升值吗？想多买几瓶当投资")])
add("X14", "event_invitation", "2026-11-10", "K106", task="邀请客户参加 2016 年份发布晚宴", ctx={"event": EV1}, edge="健康原因戒酒",
    expect="生成+警告", sensitive="医生建议近期戒酒",
    history=[("client", "2026-10-30", "医生让我这几个月别喝酒了，先暂停一下")])
add("X15", "price_objection", "2026-11-20", "K102", task="回复客户", product_info=["OND-VR-2012"], edge="客户已决定不买", expect="生成+警告",
    history=[("client", "2026-11-12", "挺喜欢的，但 3800 有点贵了"), ("ca", "2026-11-12", "理解的，您可以先来沙龙尝尝。"),
             ("client", "2026-11-20", "想了想还是算了，太贵了，不买了")])

assert len(cases) == 50, len(cases)
assert len({c["case_id"] for c in cases}) == 50
with open(ROOT / "data/test_cases.jsonl", "w", encoding="utf-8") as f:
    for c in cases:
        f.write(json.dumps(c, ensure_ascii=False) + "\n")
print("写入", len(cases), "个用例 → data/test_cases.jsonl")
