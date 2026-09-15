from orchestrator import LLMProvider
import os
from dotenv import load_dotenv


load_dotenv()

provider = LLMProvider(
    api_url="https://openrouter.ai/api/v1",
    api_keys=str(os.getenv("OPENROUTER_API_KEYS")).split(","),
    model_name="openai/gpt-4o",
)
try:
    result = provider.generate(
        messages=[
            {"role": "system", "content": "system_prompt"},
            {"role": "user", "content": "create swap function in python."}
        ],
        stop_sequences=["<end_code>"],
    )
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    retries: int = 0
    print()
    print("input tokens: " + str(result.input_tokens))
    print("output tokens: " + str(result.output_tokens))
    print("latency_ms: " + str(result.latency_ms))
    print("retries: " + str(result.retries))
    print("response text: " + result.text)
    print()

except Exception as e:
    print(e)
