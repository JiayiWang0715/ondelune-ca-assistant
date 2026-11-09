"""模型调用层。所有国内主流平台都提供 OpenAI 兼容的 /chat/completions 接口，
所以这里只用标准库 urllib 实现一个通用客户端，换模型 = 改 config/models.yaml。

MockLLM 用于没有 API key 时把整条流程跑通（离线、确定性、可测试）。
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Protocol


class LLM(Protocol):
    name: str

    def chat(self, system: str, user: str, temperature: float = 0.7, json_mode: bool = True) -> str: ...


class OpenAICompatLLM:
    def __init__(self, name: str, base_url: str, api_key: str, model: str, timeout: int = 60):
        self.name = f"{name}:{model}"
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def chat(self, system: str, user: str, temperature: float = 0.7, json_mode: bool = True) -> str:
        body = {
            "model": self.model,
            "temperature": temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        last_err = None
        for attempt in range(3):
            req = urllib.request.Request(
                self.url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    data = json.loads(r.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as e:
                last_err = f"HTTP {e.code} {e.read().decode('utf-8', 'ignore')[:300]}"
                # 部分供应商（如经 Hugging Face 路由的模型）不支持 response_format：去掉后重试
                if e.code == 400 and "response_format" in body:
                    body.pop("response_format")
                    continue
                if e.code in (401, 403, 404):
                    break
                time.sleep(2 ** attempt)
            except (urllib.error.URLError, TimeoutError, KeyError) as e:
                last_err = e
                time.sleep(2 ** attempt)
        raise RuntimeError(f"{self.name} 调用失败：{last_err}")


class MockLLM:
    """离线模拟模型：根据 prompt 里的称呼和场景拼出合规的示例消息，
    并故意在 rewrite 前的第一版里埋一个违规，用来演示「检查 → 重写」闭环。"""

    name = "mock"

    def chat(self, system: str, user: str, temperature: float = 0.7, json_mode: bool = True) -> str:
        if "【任务：裁判打分】" in system:
            return json.dumps({
                "scores": {"personalization": 4, "scenario_fit": 4, "brand_voice": 4, "naturalness": 4, "no_pressure": 5},
                "flags": {"R2_disparage": False, "R12_pushed_after_refusal": False, "V12_unanswered_question": False},
                "comment": "模拟裁判：整体自然，个性化细节可以更具体。",
            }, ensure_ascii=False)
        name = re.search(r"偏好称呼：(\S+)", user)
        name = name.group(1) if name else "您"
        if "【任务：重写】" in system:
            return json.dumps({"text": f"{name}，想到您上次提起的那顿家宴，这周沙龙安静些，有空来坐坐。"}, ensure_ascii=False)
        return json.dumps({"candidates": [
            {"strategy": "warm", "text": f"{name}，记得您说过喜欢清爽一点的风格，最近天气转凉，很适合开一瓶慢慢喝。"},
            {"strategy": "content", "text": f"{name}，分享一个小知识：年份香槟侍酒温度比无年份略高一点，香气会更舒展。"},
            {"strategy": "light", "text": f"{name}，这周沙龙到了新酒，限时品鉴，有空来坐坐。"},  # 故意含「限时」→ V4
        ]}, ensure_ascii=False)


def build_llm(role: str, models_cfg: dict) -> LLM:
    provider = models_cfg["roles"][role]
    p = models_cfg["providers"][provider]
    if provider == "mock":
        return MockLLM()
    key = os.environ.get(p["api_key_env"] or "")
    if not key:
        raise RuntimeError(f"缺少环境变量 {p['api_key_env']}（请写进项目根目录的 .env）")
    return OpenAICompatLLM(provider, p["base_url"], key, p["model"])


def parse_json(text: str) -> dict:
    """模型偶尔会在 JSON 外面包一层 ```json，这里统一剥掉。"""
    t = text.strip()
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        raise ValueError(f"模型输出不是 JSON：{t[:200]}")
    return json.loads(m.group(0))
