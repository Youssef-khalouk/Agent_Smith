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

    def __init__(self, api_url: str, model_name: str, api_keys: list[str], logs: bool = False):
        self.logs = logs
        if self.logs: print("\nInitalizeing LLM Provider.")
        self.api_url = api_url
        self.model_name = model_name
        self.api_keys = api_keys

        if self.api_url.strip() == "":
            raise Exception("provider url is empty!.")
        if self.model_name.strip() == "":
            raise Exception("model name is empty!.")
        if self.api_keys == []:
            raise Exception("there is no api key provided.")
    
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


    def generate(self, messages: list[dict], stop_sequences: list[str] = []) -> LLMResponse:
        stop_seq = {"stop": stop_sequences} if stop_sequences else {}
        last_error = None
        keys_len = len(self.api_keys)
        for attempt in range(keys_len):
            carent_key = attempt % keys_len # in case i try keys multiple times.
            start = time.time()
            try:
                response = requests.post(
                    f"{self.api_url}",
                    headers={"Authorization": f"Bearer {self.api_keys[carent_key]}"},
                    json={
                        "model": self.model_name,
                        "messages": messages,
                        **stop_seq,
                        **self._get_reasoning_params()
                    },
                    timeout=60,
                )
                if response.status_code == 429:
                    raise RateLimitError(f" Rate limited on key index {carent_key} ")
                response.raise_for_status()  # raise any error if there is.
                data = response.json()
                latency_ms = (time.time() - start) * 1000
                return LLMResponse(
                    text=data["choices"][0]["message"].get("content", ""),
                    input_tokens=data["usage"]["prompt_tokens"],
                    output_tokens=data["usage"]["completion_tokens"],
                    latency_ms=latency_ms,
                    retries=carent_key,
                )
            except (RateLimitError, requests.RequestException) as e:
                if last_error == None:
                    last_error = str(e)
                else:
                    last_error += str(e)

        raise RuntimeError(f"All API keys exhausted. error: {last_error}")
