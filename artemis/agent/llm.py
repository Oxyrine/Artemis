"""One module wrapping one provider. Any OpenAI-compatible endpoint (Groq by default) works via env."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


@dataclass
class ToolCallReq:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    text: str | None = None
    tool_calls: list[ToolCallReq] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    error: str | None = None  # provider rejected the tool call; fed back to the model, not fatal


class LLMClient(Protocol):
    model: str

    def chat(self, messages: list[dict], tools: list[dict] | None = None, *,
             json_mode: bool = False) -> LLMResponse: ...


class LLMError(Exception):
    pass


def _seconds(v) -> float | None:
    """'29.9s' | '1m2.5s' | '12' -> seconds."""
    import re
    if v is None:
        return None
    m = re.fullmatch(r"(?:(\d+)m)?(?:([\d.]+)s?)?", str(v).strip())
    return (int(m.group(1) or 0) * 60 + float(m.group(2) or 0)) if m and (m.group(1) or m.group(2)) else None


class OpenAICompatClient:
    """temperature 0, fixed max tokens, 30 s timeout, one retry on timeout/5xx/429 (the SDK honours
    retry-after). The API key comes from the environment and is never logged."""

    def __init__(self, base_url: str, api_key: str, model: str, *, max_tokens: int = 1024):
        if not api_key or not model:
            raise LLMError("set LLM_API_KEY and LLM_MODEL (see .env.example)")
        from openai import OpenAI
        self._c = OpenAI(base_url=base_url, api_key=api_key, timeout=30.0, max_retries=0)
        self.model, self._max_tokens = model, max_tokens
        self.throttled_seconds = 0.0  # time spent waiting out 429s; the loop's wall-time bound excludes it

    def _create_with_backoff(self, kw: dict, attempts: int = 8):
        """Small TPM tiers (e.g. 8k/min) 429 constantly: sleep for the server's reset hint and try again."""
        import time

        from openai import APIConnectionError, InternalServerError, RateLimitError
        retried = False
        for i in range(attempts):
            try:
                return self._c.chat.completions.create(**kw)
            except (APIConnectionError, InternalServerError):  # timeout / 5xx: exactly one retry
                if retried:
                    raise
                retried = True
            except RateLimitError as e:
                if i == attempts - 1:
                    raise
                h = getattr(getattr(e, "response", None), "headers", {}) or {}
                wait = _seconds(h.get("retry-after") or h.get("x-ratelimit-reset-tokens")) or 15.0
                wait = min(wait + 1.0, 65.0)
                self.throttled_seconds += wait
                time.sleep(wait)

    def chat(self, messages, tools=None, *, json_mode=False) -> LLMResponse:
        kw: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": 0,
                              "max_tokens": self._max_tokens}
        if tools:
            kw.update(tools=tools, tool_choice="auto", parallel_tool_calls=False)
        if json_mode:
            kw["response_format"] = {"type": "json_object"}
        try:
            r = self._create_with_backoff(kw)
        except Exception as e:  # surface as data-free error; never include request/headers
            body = getattr(e, "body", None)
            err = body.get("error", body) if isinstance(body, dict) else {}
            if err.get("code") == "tool_use_failed" or "tool_use_failed" in str(e):  # invalid call: let it retry
                return LLMResponse(error=str(err.get("message") or e)[:700])
            raise LLMError(f"{type(e).__name__}: {e}") from None
        m, calls = r.choices[0].message, []
        for tc in m.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {"__unparseable__": tc.function.arguments}
            calls.append(ToolCallReq(tc.id, tc.function.name, args))
        u = r.usage
        return LLMResponse(m.content, calls, getattr(u, "prompt_tokens", 0), getattr(u, "completion_tokens", 0))


class ScriptedLLM:
    """Offline stand-in: a list of responses (or a callable(messages)->response), served in order."""

    def __init__(self, script: list[LLMResponse] | Callable[[list[dict]], LLMResponse], model: str = "scripted"):
        self.model, self._script, self.calls = model, script, 0

    def chat(self, messages, tools=None, *, json_mode=False) -> LLMResponse:
        self.calls += 1
        if callable(self._script):
            return self._script(messages)
        if not self._script:
            raise LLMError("ScriptedLLM exhausted")
        return self._script.pop(0)


def tool_msg(name: str, **args) -> LLMResponse:
    """Test helper: a response that calls one tool."""
    return LLMResponse(tool_calls=[ToolCallReq(f"call_{name}", name, args)], tokens_in=100, tokens_out=20)


def assistant_message(resp: LLMResponse) -> dict:
    m: dict[str, Any] = {"role": "assistant", "content": resp.text}
    if resp.tool_calls:
        m["tool_calls"] = [{"id": t.id, "type": "function",
                            "function": {"name": t.name, "arguments": json.dumps(t.arguments)}}
                           for t in resp.tool_calls]
    return m
