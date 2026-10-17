"""Claude 어댑터(anthropic SDK). 근거 묶음은 바뀌지 않으므로 캐시 표시를 달아 질문마다 다시 읽지 않게 한다."""
from __future__ import annotations

import threading
from typing import Iterator

from .base import EFFORT, READ_TIMEOUT, LLMError, Provider, Request, error_text


def _messages(req: Request) -> list[dict]:
    out: list[dict] = []
    for q, a in req.turns:
        out += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
    content: list[dict] | str = req.question
    if req.images:
        import base64

        content = [{"type": "image", "source": {"type": "base64", "media_type": _media_type(img),
                                                 "data": base64.b64encode(img).decode()}} for img in req.images]
        content.append({"type": "text", "text": req.question})
    out.append({"role": "user", "content": content})
    return out


def _media_type(img: bytes) -> str:
    return "image/png" if img[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"


def classify(e: Exception, key: str) -> LLMError:
    import anthropic

    text = error_text(e, key)
    if isinstance(e, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return LLMError("key", text)
    if isinstance(e, anthropic.RateLimitError) or "credit balance" in text.lower():
        return LLMError("quota", text)
    if isinstance(e, anthropic.APITimeoutError):
        return LLMError("timeout", text)
    if isinstance(e, anthropic.APIConnectionError):
        return LLMError("network", text)
    return LLMError("other", text)


class ClaudeProvider(Provider):
    name = "claude"

    def __init__(self, key: str, client=None):
        self.key = key
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=key, max_retries=1, timeout=READ_TIMEOUT)
        self.client = client

    def stream(self, req: Request, cancel: threading.Event) -> Iterator[str]:
        system = [{"type": "text", "text": req.system}]
        if req.grounding:
            system.append({"type": "text", "text": req.grounding, "cache_control": {"type": "ephemeral"}})
        try:
            with self.client.messages.stream(model=req.model, max_tokens=req.max_tokens, system=system,
                                             messages=_messages(req),
                                             output_config={"effort": EFFORT[req.effort]}) as stream:
                for event in stream:
                    if cancel.is_set():
                        return
                    if event.type == "content_block_delta" and getattr(event.delta, "type", "") == "text_delta":
                        yield event.delta.text
        except LLMError:
            raise
        except Exception as e:
            raise classify(e, self.key) from None

    def check_key(self) -> None:
        try:
            self.client.models.list(limit=1)
        except Exception as e:
            raise classify(e, self.key) from None
