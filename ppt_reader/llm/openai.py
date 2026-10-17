"""OpenAI 어댑터(openai SDK, Responses API). 지침과 근거는 instructions에 넣고, 대화를 서버에 저장하지 않는다."""
from __future__ import annotations

import base64
import threading
from typing import Iterator

from .base import EFFORT, READ_TIMEOUT, LLMError, Provider, Request, error_text


def _input(req: Request) -> list[dict]:
    out: list[dict] = []
    for q, a in req.turns:
        out += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
    if req.images:
        parts = [{"type": "input_image", "image_url": "data:image/png;base64," + base64.b64encode(img).decode()}
                 for img in req.images]
        parts.append({"type": "input_text", "text": req.question})
        out.append({"role": "user", "content": parts})
    else:
        out.append({"role": "user", "content": req.question})
    return out


def classify(e: Exception, key: str) -> LLMError:
    import openai

    text = error_text(e, key)
    if isinstance(e, (openai.AuthenticationError, openai.PermissionDeniedError)):
        return LLMError("key", text)
    if isinstance(e, openai.RateLimitError):  # 사용량 제한과 요금 부족이 둘 다 429다
        return LLMError("quota", text)
    if isinstance(e, openai.APITimeoutError):
        return LLMError("timeout", text)
    if isinstance(e, openai.APIConnectionError):
        return LLMError("network", text)
    return LLMError("other", text)


class OpenAIProvider(Provider):
    name = "openai"

    def __init__(self, key: str, client=None):
        self.key = key
        if client is None:
            import openai

            client = openai.OpenAI(api_key=key, max_retries=1, timeout=READ_TIMEOUT)
        self.client = client

    def stream(self, req: Request, cancel: threading.Event) -> Iterator[str]:
        instructions = req.system + ("\n\n" + req.grounding if req.grounding else "")
        try:
            with self.client.responses.stream(model=req.model, instructions=instructions, input=_input(req),
                                              reasoning={"effort": EFFORT[req.effort]}, store=False,
                                              max_output_tokens=req.max_tokens) as stream:
                for event in stream:
                    if cancel.is_set():
                        return
                    if event.type == "response.output_text.delta":
                        yield event.delta
        except LLMError:
            raise
        except Exception as e:
            raise classify(e, self.key) from None

    def check_key(self) -> None:
        try:
            self.client.models.list()
        except Exception as e:
            raise classify(e, self.key) from None
