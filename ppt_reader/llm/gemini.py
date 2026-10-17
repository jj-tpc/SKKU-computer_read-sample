"""Gemini 어댑터(google-genai). 지침과 근거는 system_instruction에 넣는다."""
from __future__ import annotations

import threading
from typing import Iterator

from .base import EFFORT, READ_TIMEOUT, LLMError, Provider, Request, error_text


def classify(e: Exception, key: str) -> LLMError:
    text = error_text(e, key)
    name = type(e).__name__.lower()
    code = getattr(e, "code", None)
    if "timeout" in name:
        return LLMError("timeout", text)
    if isinstance(code, int):
        if code in (401, 403) or (code == 400 and "api key" in text.lower()):
            return LLMError("key", text)
        if code == 429:
            return LLMError("quota", text)
        return LLMError("other", text)
    if "connect" in name or "network" in name or isinstance(e, (ConnectionError, OSError)):
        return LLMError("network", text)
    return LLMError("other", text)


class GeminiProvider(Provider):
    name = "gemini"

    def __init__(self, key: str, client=None):
        self.key = key
        if client is None:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=int(READ_TIMEOUT * 1000)))
        self.client = client

    def stream(self, req: Request, cancel: threading.Event) -> Iterator[str]:
        from google.genai import types

        contents = []
        for q, a in req.turns:
            contents += [types.Content(role="user", parts=[types.Part(text=q)]),
                         types.Content(role="model", parts=[types.Part(text=a)])]
        parts = [types.Part.from_bytes(data=img, mime_type="image/png" if img[:4] == b"\x89PNG" else "image/jpeg")
                 for img in req.images]
        parts.append(types.Part(text=req.question))
        contents.append(types.Content(role="user", parts=parts))
        config = types.GenerateContentConfig(
            system_instruction=req.system + ("\n\n" + req.grounding if req.grounding else ""),
            thinking_config=types.ThinkingConfig(thinking_level=EFFORT[req.effort]),
            max_output_tokens=req.max_tokens)
        try:
            for chunk in self.client.models.generate_content_stream(model=req.model, contents=contents,
                                                                    config=config):
                if cancel.is_set():
                    return
                for cand in (chunk.candidates or [])[:1]:
                    for part in (cand.content.parts if cand.content and cand.content.parts else []):
                        if part.text and not part.thought:  # 생각 조각은 버린다
                            yield part.text
        except LLMError:
            raise
        except Exception as e:
            raise classify(e, self.key) from None

    def check_key(self) -> None:
        try:
            next(iter(self.client.models.list(config={"page_size": 1})), None)
        except Exception as e:
            raise classify(e, self.key) from None
