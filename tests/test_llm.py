"""LLM 어댑터 시험. 가짜 SDK 응답으로 글 조각, 생각 깊이, 오류 바꾸기, 취소를 본다(인터넷 없음)."""
from __future__ import annotations

import os
import threading
from types import SimpleNamespace as NS

import anthropic
import httpx2
import openai
import pytest

from ppt_reader.llm.base import MODELS, LLMError, Request, make_provider, start_stream
from ppt_reader.llm.claude import ClaudeProvider
from ppt_reader.llm.gemini import GeminiProvider
from ppt_reader.llm.openai import OpenAIProvider

REQ = Request("m", "mid", "기본 지침", "<자료>근거</자료>", [("이전 질문", "이전 답")], "이번 질문")


class FakeStream:
    def __init__(self, events, error=None):
        self.events, self.error = events, error
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.closed = True
        return False

    def __iter__(self):
        for e in self.events:
            yield e
        if self.error:
            raise self.error


class Recorder:
    """client.<path>(**kwargs)를 받아 kwargs를 남기고 정해 둔 값을 돌려준다."""

    def __init__(self, result):
        self.result, self.kwargs = result, None

    def __call__(self, **kwargs):
        self.kwargs = kwargs
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def http_response(status: int) -> httpx2.Response:
    return httpx2.Response(status, request=httpx2.Request("POST", "https://api.example.com"))


def collect(provider, req=REQ, cancel=None):
    return list(provider.stream(req, cancel or threading.Event()))


# ---------------------------------------------------------------- Claude

def claude_events():
    return [NS(type="message_start"),
            NS(type="content_block_delta", delta=NS(type="thinking_delta", thinking="생각 조각")),
            NS(type="content_block_delta", delta=NS(type="text_delta", text="안녕")),
            NS(type="content_block_delta", delta=NS(type="text_delta", text="하세요.")),
            NS(type="message_stop")]


def test_claude_stream_text_only_and_effort():
    stream = Recorder(FakeStream(claude_events()))
    p = ClaudeProvider("k", client=NS(messages=NS(stream=stream)))
    assert collect(p) == ["안녕", "하세요."]  # 생각 조각은 버린다
    kw = stream.kwargs
    assert kw["output_config"] == {"effort": "medium"} and kw["max_tokens"] == 8192  # mid → medium
    assert kw["system"][1] == {"type": "text", "text": "<자료>근거</자료>", "cache_control": {"type": "ephemeral"}}
    assert kw["messages"] == [{"role": "user", "content": "이전 질문"}, {"role": "assistant", "content": "이전 답"},
                              {"role": "user", "content": "이번 질문"}]


@pytest.mark.parametrize("error, kind", [
    (anthropic.AuthenticationError("bad key", response=http_response(401), body=None), "key"),
    (anthropic.PermissionDeniedError("denied", response=http_response(403), body=None), "key"),
    (anthropic.RateLimitError("slow", response=http_response(429), body=None), "quota"),
    (anthropic.BadRequestError("Your credit balance is too low", response=http_response(400), body=None), "quota"),
    (anthropic.APITimeoutError(request=httpx2.Request("POST", "https://x")), "timeout"),
    (anthropic.APIConnectionError(request=httpx2.Request("POST", "https://x")), "network"),
    (anthropic.InternalServerError("boom", response=http_response(500), body=None), "other"),
])
def test_claude_errors(error, kind):
    p = ClaudeProvider("sk-ant-secret-1234567890", client=NS(messages=NS(stream=Recorder(FakeStream([], error)))))
    with pytest.raises(LLMError) as info:
        collect(p)
    assert info.value.kind == kind and "secret" not in info.value.detail


def test_claude_cancel_closes_stream():
    stream = FakeStream(claude_events())
    p = ClaudeProvider("k", client=NS(messages=NS(stream=Recorder(stream))))
    cancel = threading.Event()
    out = []
    for t in p.stream(REQ, cancel):
        out.append(t)
        cancel.set()
    assert out == ["안녕"] and stream.closed


# ---------------------------------------------------------------- OpenAI

def test_openai_stream_text_only_and_effort():
    events = [NS(type="response.created"), NS(type="response.reasoning_summary_text.delta", delta="생각"),
              NS(type="response.output_text.delta", delta="네, "), NS(type="response.output_text.delta", delta="맞아요."),
              NS(type="response.completed")]
    stream = Recorder(FakeStream(events))
    p = OpenAIProvider("k", client=NS(responses=NS(stream=stream)))
    assert collect(p) == ["네, ", "맞아요."]
    kw = stream.kwargs
    assert kw["reasoning"] == {"effort": "medium"} and kw["store"] is False and kw["max_output_tokens"] == 8192
    assert kw["instructions"] == "기본 지침\n\n<자료>근거</자료>"
    assert kw["input"][-1] == {"role": "user", "content": "이번 질문"} and len(kw["input"]) == 3


@pytest.mark.parametrize("error, kind", [
    (openai.AuthenticationError("Incorrect API key provided: sk-pr****7890", response=http_response(401), body=None),
     "key"),
    (openai.RateLimitError("You exceeded your current quota", response=http_response(429), body=None), "quota"),
    (openai.APITimeoutError(request=httpx2.Request("POST", "https://x")), "timeout"),
    (openai.APIConnectionError(request=httpx2.Request("POST", "https://x")), "network"),
    (openai.BadRequestError("bad", response=http_response(400), body=None), "other"),
])
def test_openai_errors(error, kind):
    p = OpenAIProvider("sk-proj-secret-1234567890", client=NS(responses=NS(stream=Recorder(FakeStream([], error)))))
    with pytest.raises(LLMError) as info:
        collect(p)
    assert info.value.kind == kind and "sk-pr" not in info.value.detail


# ---------------------------------------------------------------- Gemini

def gemini_chunk(*parts):
    return NS(candidates=[NS(content=NS(parts=[NS(text=t, thought=th) for t, th in parts]))])


def test_gemini_stream_text_only_and_effort():
    gen = Recorder(iter([gemini_chunk(("생각 조각", True), ("반가", False)), gemini_chunk(("워요.", False)),
                         NS(candidates=[])]))
    p = GeminiProvider("k", client=NS(models=NS(generate_content_stream=gen)))
    assert collect(p) == ["반가", "워요."]
    config = gen.kwargs["config"]
    assert config.thinking_config.thinking_level.name == "MEDIUM" and config.max_output_tokens == 8192  # mid → medium
    assert config.system_instruction == "기본 지침\n\n<자료>근거</자료>"
    assert [c.role for c in gen.kwargs["contents"]] == ["user", "model", "user"]


class GenaiError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


class ConnectTimeout(Exception):
    pass


@pytest.mark.parametrize("error, kind", [
    (GenaiError(400, "API key not valid. Please pass a valid API key."), "key"),
    (GenaiError(403, "denied"), "key"),
    (GenaiError(429, "Resource has been exhausted"), "quota"),
    (GenaiError(503, "overloaded"), "other"),
    (ConnectTimeout("timed out"), "timeout"),
    (ConnectionError("down"), "network"),
])
def test_gemini_errors(error, kind):
    p = GeminiProvider("AIza-secret", client=NS(models=NS(generate_content_stream=Recorder(error))))
    with pytest.raises(LLMError) as info:
        collect(p)
    assert info.value.kind == kind


# ---------------------------------------------------------------- 공통

def test_start_stream_runs_in_thread_and_reports():
    events = []
    done = threading.Event()

    class P:
        name, key = "fake", "k"

        def stream(self, req, cancel):
            yield "가"
            yield "나"
            raise LLMError("network", "끊김")

    start_stream(P(), REQ, events.append, lambda: events.append("done"),
                 lambda e: (events.append(e.kind), done.set()))
    assert done.wait(3)
    assert events == ["가", "나", "network"]


def test_start_stream_accepts_factory():
    """앱은 SDK를 작업 스레드에서 불러오려고 제공자 대신 만드는 함수를 넘긴다."""
    events = []
    done = threading.Event()

    class P:
        name, key = "fake", "k"

        def stream(self, req, cancel):
            yield "답"

    start_stream(lambda: P(), REQ, events.append, lambda: (events.append("done"), done.set()),
                 lambda e: (events.append(e.kind), done.set()))
    assert done.wait(3)
    assert events == ["답", "done"]


def test_models_and_defaults_match_settings():
    from ppt_reader.settings import DEFAULT_MODELS

    assert {p: MODELS[p][0] for p in MODELS} == DEFAULT_MODELS
    assert isinstance(make_provider("openai", "k"), OpenAIProvider)


@pytest.mark.live
@pytest.mark.parametrize("provider, env", [("claude", "PPT_READER_LIVE_CLAUDE"), ("openai", "PPT_READER_LIVE_OPENAI"),
                                           ("gemini", "PPT_READER_LIVE_GEMINI")])
def test_live_short_answer(provider, env):
    key = os.environ.get(env)
    if not key:
        pytest.skip(f"{env}에 키가 없음")
    p = make_provider(provider, key)
    p.check_key()
    text = "".join(collect(p, Request(MODELS[provider][0], "low", "한 문장으로 답해.", "", [], "1 더하기 1은?")))
    assert text.strip()
