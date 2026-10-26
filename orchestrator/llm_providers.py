import time
import requests
from models import LLMResponse
from time import sleep


class RateLimitError(Exception):
    """Exception raised when an API request exceeds the provider's rate limit."""
    pass


class LLMProvider:
    """
    Generic OpenAI-compatible provider (works for OpenRouter, Groq, etc.).
    """

    def __init__(self, api_url: str, model_name: str, api_keys: list[str], logs: bool = False):
        """Initialize the language model provider.

        Args:
            api_url: The endpoint URL for the language model API.
            model_name: The identifier of the model to use.
            api_keys: API keys used to authenticate requests and retry with
                alternative keys when rate limits or request errors occur.
            logs: Whether to enable initialization logging.

        Raises:
            Exception: If the API URL, model name, or API key list is empty.
        """
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
        """
        Return reasoning parameters appropriate for the configured model.

        Determine model-specific settings for disabling or controlling reasoning
        based on the model name.

        Returns:
            A dictionary of additional API request parameters for reasoning
            configuration, or an empty dictionary if no special settings apply.
        """
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
        """
        Send a chat completion request and return the parsed model response.

        Try the configured API keys sequentially, including optional stop sequences
        and model-specific reasoning parameters. Measure request latency, extract
        the generated text and token usage, and record the number of the key used
        as the retry count.

        Args:
            messages: The conversation messages to send to the model.
            stop_sequences: Optional sequences that instruct the model when to stop
                generating text.

        Returns:
            An LLMResponse containing the generated text, token usage, request
            latency, and retry count.

        Raises:
            RuntimeError: If all configured API keys fail or are rate-limited.
        """
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
