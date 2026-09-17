import time
import requests
from pydantic import BaseModel


class LLMResponse(BaseModel):
    text: str | None = None
    tool_calls: list | None = None
    input_tokens: int
    output_tokens: int
    latency_ms: float
    retries: int = 0


class RateLimitError(Exception):
    pass


class LLMProvider:
    """
    Generic OpenAI-compatible provider (works for OpenRouter, Groq, etc.).
    """

    def __init__(self, api_url: str, api_keys: list[str], model_name: str):
        self.api_url = api_url
        self.api_keys = api_keys
        self.model_name = model_name
        self._key_index = 0
        self.tools = []

    def _current_key(self) -> str:
        return self.api_keys[self._key_index]

    def _rotate_key(self):
        self._key_index = (self._key_index + 1) % len(self.api_keys)

    def set_tools(self, tools: list) -> None:
        self.tools = tools

    def generate(self, messages: list[dict], stop_sequences: list[str] = []) -> LLMResponse:
        last_error = None
        for attempt in range(len(self.api_keys)):
            start = time.time()
            try:
                response = requests.post(
                    f"{self.api_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._current_key()}"},
                    json={
                        "model": self.model_name,
                        "messages": messages,
                        "tools": self.tools,
                        "stop": stop_sequences,
                        "max_tokens": 1000,
                    },
                    timeout=60,
                )
                if response.status_code == 429:
                    raise RateLimitError(f"Rate limited on key index {self._key_index}")
                response.raise_for_status()  # raise any error if there is.
                data = response.json()
                latency_ms = (time.time() - start) * 1000

                return LLMResponse(
                    text=data["choices"][0]["message"].get("content", None),
                    tool_calls=data["choices"][0]["message"].get("tool_calls", None),
                    input_tokens=data["usage"]["prompt_tokens"],
                    output_tokens=data["usage"]["completion_tokens"],
                    latency_ms=latency_ms,
                    retries=attempt,
                )
            except (RateLimitError, requests.RequestException) as e:
                last_error = e
                self._rotate_key()

        raise RuntimeError(f"All API keys exhausted. Last error: {last_error}")
