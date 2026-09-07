import json
import os
import re
import socket
import time
import urllib.request
import urllib.error
from dataclasses import dataclass

from .cases import Challenge


# 这是游戏引擎可执行的“策略意图”词表，而非各关答案；模型必须自行判断其中哪些适用。
STRATEGY_CATALOG = {
    "maintain_low_hp": "维持单位低生命值以持续触发低血量增益",
    "trade_for_extra_action": "用低价值承伤换取额外行动和行动顺序优势",
    "block_center_route": "占据或封锁通往中心资源点的关键路线",
    "feed_strongest_unit": "集中资源让攻击最高单位持续扩大优势",
    "preserve_weakest_unit": "刻意维持一名单位为最弱者以反复获得补偿",
    "rush_then_block": "利用机动优势先抢路线，再阻断对方通行",
}


@dataclass
class Candidate:
    strategy_id: str
    rationale: str
    actions: list[str]
    confidence: float


@dataclass
class AnalysisResult:
    candidates: list[Candidate]
    attempts: int


class ModelCallError(RuntimeError):
    def __init__(self, kind: str, attempts: int, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.attempts = attempts


def _to_text(value) -> str:
    """兼容 OpenAI、GLM 及部分网关的字符串/分段内容格式。"""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(_to_text(item) for item in value)
    if isinstance(value, dict):
        for key in ("text", "content", "output_text"):
            if key in value:
                return _to_text(value[key])
    return ""


def _parse_strategy_payload(envelope: dict) -> tuple[dict, str]:
    """从不同兼容接口的响应中提取第一个含 strategies 的 JSON 对象。"""
    choices = envelope.get("choices") or []
    message = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
    sources = [
        ("message.content", message.get("content")),
        ("message.reasoning_content", message.get("reasoning_content")),
        ("envelope.output_text", envelope.get("output_text")),
        ("envelope.content", envelope.get("content")),
    ]
    for source, raw in sources:
        text = _to_text(raw).strip()
        if not text:
            continue
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
        possible = [text]
        first, last = text.find("{"), text.rfind("}")
        if first != -1 and last > first:
            possible.append(text[first:last + 1])
        for item in possible:
            try:
                parsed = json.loads(item)
                if isinstance(parsed, dict) and isinstance(parsed.get("strategies"), list):
                    return parsed, source
            except json.JSONDecodeError:
                continue
    available = {key: (type(value).__name__ if value is not None else "none") for key, value in sources}
    raise ModelCallError("invalid_model_output", 1, f"未找到可解析的 strategies JSON；响应字段摘要：{available}")


def _parse_json_payload(envelope: dict) -> dict:
    """提取任意 JSON 对象，供盲测的行动计划使用。"""
    choices = envelope.get("choices") or []
    message = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
    values = [message.get("content"), message.get("reasoning_content"), envelope.get("output_text"), envelope.get("content")]
    for raw in values:
        text = _to_text(raw).strip()
        if not text:
            continue
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
        first, last = text.find("{"), text.rfind("}")
        for item in (text, text[first:last + 1] if first != -1 and last > first else ""):
            try:
                parsed = json.loads(item)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
    raise ModelCallError("invalid_model_output", 1, "模型响应中没有可解析的 JSON 对象。")


class FixtureProvider:
    """仅用于检查评测链路；不可作为模型表现。"""
    def analyze(self, case: Challenge) -> AnalysisResult:
        return AnalysisResult([Candidate(case.expected_strategy, case.expected_description, ["observe", "exploit_rule"], 0.99)], 1)


class GLMProvider:
    def __init__(self, timeout_seconds: int = 120, retries: int = 2) -> None:
        self.key = os.environ.get("GLM_API_KEY")
        self.base_url = os.environ.get("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
        self.model = os.environ.get("GLM_MODEL", "glm-5.1")
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        if not self.key:
            raise RuntimeError("未检测到 GLM_API_KEY。请在环境变量中配置赛事平台的 API 密钥。")

    def analyze(self, case: Challenge) -> AnalysisResult:
        prompt = f'''你是回合制策略游戏中的蓝方策略分析员。请只基于公开规则寻找可执行的非预期策略；不要编造游戏状态，不要给出代码。

挑战：{case.title}
目标：{case.objective}
公开规则：{case.public_rule}
已验证的规则 DSL：{json.dumps(case.dsl, ensure_ascii=False)}
基础状态：红蓝各两名抽象单位；双方都必须遵守公共规则；中心资源点是关键位置；每局最多 8 回合。

候选 strategy_id 只能从以下可执行意图词表中选择；不是每个意图都适用于当前挑战：
{json.dumps(STRATEGY_CATALOG, ensure_ascii=False)}

返回严格 JSON，不要 Markdown：
{{"strategies":[{{"strategy_id":"简短英文_snake_case标签","rationale":"中文理由","actions":["动作1","动作2"],"confidence":0到1}}]}}
给出 1 到 3 个候选策略。'''
        # 压力测试评估结构化策略，不评估长链推理。关闭思考可避免输出额度被 reasoning_content 耗尽。
        payload = json.dumps({"model": self.model, "messages": [{"role":"user", "content": prompt}], "temperature": 0.2, "thinking": {"type": "disabled"}, "max_tokens": 1024, "response_format": {"type": "json_object"}}, ensure_ascii=False).encode()
        request = urllib.request.Request(self.base_url + "/chat/completions", data=payload, headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"}, method="POST")
        envelope = None
        last_error = None
        for attempt in range(1, self.retries + 2):
            print(f"[{case.id}] 正在请求 GLM（第 {attempt}/{self.retries + 1} 次，最长等待 {self.timeout_seconds} 秒）...", flush=True)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    envelope = json.loads(response.read().decode())
                break
            except (TimeoutError, socket.timeout, urllib.error.URLError, urllib.error.HTTPError) as exc:
                last_error = exc
                if attempt <= self.retries:
                    print(f"[{case.id}] 请求未完成：{exc}；2 秒后重试。", flush=True)
                    time.sleep(2)
        if envelope is None:
            detail = str(last_error)
            kind = "timeout" if "timed out" in detail.lower() else "transport_error"
            raise ModelCallError(kind, self.retries + 1, detail)
        try:
            data, _source = _parse_strategy_payload(envelope)
        except ModelCallError as exc:
            exc.attempts = attempt
            raise
        candidates = []
        for item in data.get("strategies", [])[:3]:
            candidates.append(Candidate(str(item.get("strategy_id", "")), str(item.get("rationale", "")), list(item.get("actions", [])), float(item.get("confidence", 0))))
        return AnalysisResult(candidates, attempt)

    def ask_json(self, case_id: str, prompt: str) -> tuple[dict, int]:
        """带重试的通用 JSON 请求；不在此处评价模型答案。"""
        payload = json.dumps({"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": 0, "thinking": {"type": "disabled"}, "max_tokens": 1200, "response_format": {"type": "json_object"}}, ensure_ascii=False).encode()
        request = urllib.request.Request(self.base_url + "/chat/completions", data=payload, headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"}, method="POST")
        envelope, last_error = None, None
        for attempt in range(1, self.retries + 2):
            print(f"[{case_id}] 正在请求 GLM（第 {attempt}/{self.retries + 1} 次，最长等待 {self.timeout_seconds} 秒）...", flush=True)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    envelope = json.loads(response.read().decode())
                break
            except (TimeoutError, socket.timeout, urllib.error.URLError, urllib.error.HTTPError) as exc:
                last_error = exc
                if attempt <= self.retries:
                    print(f"[{case_id}] 请求未完成：{exc}；2 秒后重试。", flush=True)
                    time.sleep(2)
        if envelope is None:
            detail = str(last_error)
            raise ModelCallError("timeout" if "timed out" in detail.lower() else "transport_error", self.retries + 1, detail)
        try:
            return _parse_json_payload(envelope), attempt
        except ModelCallError as exc:
            exc.attempts = attempt
            raise
