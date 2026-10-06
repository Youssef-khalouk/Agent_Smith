import time
import requests
from models import LLMResponse
from time import sleep


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
        self.count_ersponses = 0
    
    def _get_reasoning_params(self):
        model = self.model_name.lower()

        # Groq GPT-OSS
        if model.startswith("openai/gpt-oss"):
            return {"include_reasoning": False}

        # Groq Qwen
        if model.startswith("qwen/qwen3"):
            return {"reasoning_effort": "none"}

        # Mistral reasoning models
        if "mistral" in model:
            return {"reasoning_effort": "none"}

        # Cohere reasoning
        if "command-a-reasoning" in model:
            return {
                "thinking": {
                    "type": "disabled"
                }
            }
        return {}

    def _current_key(self) -> str:
        return self.api_keys[self._key_index]

    def _rotate_key(self):
        self._key_index = (self._key_index + 1) % len(self.api_keys)
        if self._key_index == 0:
            print("\nall the keys exhausted. wait for 15 second and try again...\n")
            sleep(15)

    def generate(self, messages: list[dict], stop_sequences: list[str] = []) -> LLMResponse:
        last_error = None
        # for attempt in range(len(self.api_keys)):
        while True:
            if self.count_ersponses >= 20:
                break
            start = time.time()
            try:
                response = requests.post(
                    f"{self.api_url}",
                    headers={"Authorization": f"Bearer {self._current_key()}"},
                    json={
                        "model": self.model_name,
                        "messages": messages,
                        # "stop": stop_sequences,
                        **self._get_reasoning_params()
                    },
                    timeout=60,
                )
                if response.status_code == 429:
                    raise RateLimitError(f" Rate limited on key index {self._key_index}")
                response.raise_for_status()  # raise any error if there is.
                data = response.json()
                latency_ms = (time.time() - start) * 1000
                self.count_ersponses += 1
                return LLMResponse(
                    text=data["choices"][0]["message"].get("content", ""),
                    input_tokens=data["usage"]["prompt_tokens"],
                    output_tokens=data["usage"]["completion_tokens"],
                    latency_ms=latency_ms,
                    retries=self.count_ersponses,
                )
            except (RateLimitError, requests.RequestException) as e:
                if last_error == None:
                    last_error = str(e)
                else:
                    last_error += str(e)
                self._rotate_key()

        raise RuntimeError(f"All API keys exhausted. error: {last_error}")
