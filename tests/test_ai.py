from orchestrator import LLMProvider
import os
from dotenv import load_dotenv


load_dotenv()

provider = LLMProvider(
    api_url=os.environ.get("API_URL"),
    api_keys=str(os.getenv("OPENROUTER_API_KEYS")).split(","),
    model_name=os.environ.get("MODEL_NAME"),
)

tools = [
    {
        "type": "function",
        "function": {
            "name": "open_file",
            "description": "Open a file and return its contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "description": "Path of the file to open."
                    }
                },
                "required": ["file"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_line",
            "description": "Add a line of text to a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "description": "Path of the file to modify."
                    },
                    "line": {
                        "type": "string",
                        "description": "The line of text to add."
                    }
                },
                "required": ["file", "line"]
            }
        }
    }
]

provider.set_tools(tools)

try:
    messages = [
        {
            "role": "system",
            "content": "You are an autonomous coding agent."
        },
        {
            "role": "user",
            "content": "Open test.py and add two line: print('Hello') and line: exit(0)."
        },

        # LLM requests BOTH tools
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "open_file",
                        "arguments": "{\"file\":\"test.py\"}"
                    }
                },
                {
                    "id": "call_456",
                    "type": "function",
                    "function": {
                        "name": "add_line",
                        "arguments": "{\"file\":\"test.py\",\"line\":\"print('Hello')\"}"
                    }
                }
            ]
        },

        # Result of open_file
        {
            "role": "tool",
            "tool_call_id": "call_123",
            "content": ""
        },

        # Result of add_line
        {
            "role": "tool",
            "tool_call_id": "call_456",
            "content": "Line successfully added to test.py."
        }
    ]

    result = provider.generate(messages=messages, stop_sequences=["<end_code>"])

    print()
    print("input tokens: " + str(result.input_tokens))
    print("output tokens: " + str(result.output_tokens))
    print("latency_ms: " + str(result.latency_ms))
    print("retries: " + str(result.retries))
    print("response text: " + str(result.text))
    print("tool_calls: " + str(result.tool_calls))
    print()

except Exception as e:
    print(e)
