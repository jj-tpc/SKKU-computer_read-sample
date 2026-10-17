"""LLM 공통 경계. 제공자별 어댑터(claude, openai, gemini)가 차이를 감추고, 밖에는 글 조각 흐름과 다섯 공통 오류만 보인다."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable, Iterator

from ..voice.cloud import scrub

EFFORT = {"low": "low", "mid": "medium", "high": "high"}
# 생각 토큰도 출력 한도에 들어가서, 한도를 작게 잡으면 답이 비거나 잘린다
MAX_TOKENS = {"low": 4096, "mid": 8192, "high": 16384}
READ_TIMEOUT = 160.0  # SDK가 조각 사이에서 기다리는 한도. 실제 시간 초과는 session이 생각 깊이에 맞춰 잰다
MODELS = {  # 첫 항목이 기본
    "claude": ("claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5", "claude-fable-5-1"),
    "openai": ("gpt-6-luna", "gpt-6.1-sol", "gpt-6-sol", "gpt-6-astra"),
    "gemini": ("gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.6-flash", "gemini-4-argon"),
}
PROVIDER_NAMES = {"claude": "Claude", "openai": "OpenAI", "gemini": "Gemini"}


class LLMError(Exception):
    """kind: "key" | "quota" | "network" | "timeout" | "other". detail은 제공자 오류의 첫 줄(키 값은 지운다)."""

    def __init__(self, kind: str, detail: str = ""):
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail


@dataclass
class Request:
    model: str
    effort: str  # "low" | "mid" | "high"
    system: str  # 기본 지침 + 개인 지침 (바뀌지 않음)
    grounding: str  # 근거 묶음 (바뀌지 않음, 캐시 대상)
    turns: list[tuple[str, str]] = field(default_factory=list)  # 대화 기억 (질문, 답)
    question: str = ""  # 이번 질문 (지금 화면의 장 포함)
    images: tuple[bytes, ...] = ()  # 캡션 요청에서만
    max_tokens: int = 0  # 0이면 생각 깊이에 맞춘 한도

    def __post_init__(self):
        if not self.max_tokens:
            self.max_tokens = MAX_TOKENS.get(self.effort, MAX_TOKENS["low"])


class Provider:
    name = ""

    def stream(self, req: Request, cancel: threading.Event) -> Iterator[str]:
        """답 글 조각만 낸다. 생각 조각은 버린다. cancel이 서면 스트림을 닫고 끝낸다."""
        raise NotImplementedError

    def check_key(self) -> None:
        """모델 목록 API를 한 번 부른다. 실패하면 LLMError."""
        raise NotImplementedError


def make_provider(name: str, key: str) -> Provider:
    if name == "claude":
        from .claude import ClaudeProvider

        return ClaudeProvider(key)
    if name == "openai":
        from .openai import OpenAIProvider

        return OpenAIProvider(key)
    if name == "gemini":
        from .gemini import GeminiProvider

        return GeminiProvider(key)
    raise ValueError(name)


def error_text(e: Exception, key: str) -> str:
    message = getattr(e, "message", None) or str(e) or type(e).__name__
    status = getattr(e, "status_code", None) or getattr(e, "code", None)
    return scrub(f"{status} {message}" if isinstance(status, int) else str(message), key)


def start_stream(provider: Provider | Callable[[], Provider], req: Request, on_chunk: Callable[[str], None],
                 on_done: Callable[[], None], on_error: Callable[[LLMError], None]) -> threading.Event:
    """질문마다 작업 스레드 하나에서 답을 받는다. 돌려준 Event를 세우면 취소한다. 콜백은 그 스레드에서 불린다.

    provider 대신 만드는 함수를 주면 그 스레드에서 만든다. SDK를 처음 불러오는 데 1초쯤 걸려 화면이 멈추지 않게 한다.
    """
    cancel = threading.Event()

    def work():
        nonlocal provider
        try:
            if not hasattr(provider, "stream"):
                provider = provider()
            for text in provider.stream(req, cancel):
                if cancel.is_set():
                    return
                if text:
                    on_chunk(text)
            if not cancel.is_set():
                on_done()
        except LLMError as e:
            if not cancel.is_set():
                on_error(e)
        except Exception as e:  # 어댑터가 놓친 오류도 다섯 종류 중 하나로
            if not cancel.is_set():
                on_error(LLMError("other", error_text(e, getattr(provider, "key", ""))))

    threading.Thread(target=work, name=f"llm-{getattr(provider, 'name', 'stream')}", daemon=True).start()
    return cancel
