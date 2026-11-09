"""输入输出的数据结构。一个测试用例 = 一个 CaseInput。"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Scenario = Literal[
    "greeting", "recommendation", "aftercare", "reactivation", "event_invitation", "price_objection"
]


class Purchase(BaseModel):
    sku: str
    date: str                       # YYYY-MM-DD
    purpose: Optional[str] = None   # 自饮 / 送礼 / 收藏
    price: Optional[float] = None


class ImportantDate(BaseModel):
    name: str                       # 结婚纪念日 / 孩子出生 ...
    date: str                       # MM-DD 或 YYYY-MM-DD
    accept_greeting: bool = False   # Brand Book 第 9 节：只对接受的客户发纪念日问候


class Client(BaseModel):
    model_config = ConfigDict(extra="allow")
    client_id: str
    preferred_name: str             # 偏好称呼，V3 检查用
    age: int
    gender: Optional[str] = None
    city: Optional[str] = None
    tier: str = "品鉴客户"
    familiarity: Literal["高", "中", "低"] = "中"
    birthday: Optional[str] = None  # MM-DD
    preferences: dict = Field(default_factory=dict)
    purchases: list[Purchase] = Field(default_factory=list)
    important_dates: list[ImportantDate] = Field(default_factory=list)
    communication: Optional[str] = None
    sensitive: Optional[str] = None  # 投诉 / 近期丧亲 / 戒酒 ... 有值即进入敏感状态（R10）
    spend_12m: Optional[float] = None
    last_interaction: Optional[str] = None
    notes: Optional[str] = None


class Turn(BaseModel):
    role: Literal["ca", "client"]
    time: Optional[str] = None
    text: str


class Event(BaseModel):
    name: str
    date: str
    location: str
    format: str                     # 形式，例如 "6 人品鉴晚宴"
    duration: str                   # 预计时长
    wines: list[str] = Field(default_factory=list)  # SKU
    min_tier: str = "品鉴客户"
    seats: Optional[int] = None


class Context(BaseModel):
    model_config = ConfigDict(extra="allow")
    festival: Optional[str] = None
    trigger: Optional[str] = None   # 触达理由（V10）
    event: Optional[Event] = None
    reserved_sku: Optional[str] = None  # 输入中已确认的预留（R4 放行）


class CaseInput(BaseModel):
    case_id: str
    scenario: Scenario
    send_date: str                  # YYYY-MM-DD
    client: Client
    history: list[Turn] = Field(default_factory=list)
    context: Context = Field(default_factory=Context)
    product_info: list[str] = Field(default_factory=list)  # 场景提供的 SKU
    tags: list[str] = Field(default_factory=list)           # 测试集维度标签，如 edge/sensitive


class Candidate(BaseModel):
    strategy: str                   # warm / content / light
    text: str


class RuleViolation(BaseModel):
    rule: str
    detail: str


class CandidateResult(BaseModel):
    strategy: str
    text: str
    violations: list[RuleViolation] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)
    judge_flags: dict[str, bool] = Field(default_factory=dict)
    judge_comment: str = ""
    grade: str = "未评"              # 不可接受 / 可接受 / 好
    rewrites: int = 0
    history: list[dict] = Field(default_factory=list)   # 重写前的版本，用于 before/after


class CaseOutput(BaseModel):
    case_id: str
    version: str
    candidates: list[CandidateResult]
    warnings: list[str] = Field(default_factory=list)   # 例如「建议暂缓发送」
    set_violations: list[RuleViolation] = Field(default_factory=list)  # 三条之间的问题（相似度）
    retrieved_skus: list[str] = Field(default_factory=list)
