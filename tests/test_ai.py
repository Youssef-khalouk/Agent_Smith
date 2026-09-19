from orchestrator import LLMProvider
import os
import json
from dotenv import load_dotenv


load_dotenv()

provider = LLMProvider(
    api_url=os.environ.get("API_URL"),
    api_keys=str(os.getenv("OPENROUTER_API_KEYS")).split(","),
    model_name=os.environ.get("MODEL_NAME"),
)

user_question = "open main.py and create a function that can take array of strings and ckeck if there is any double strings and return bool."

files = {}
file_opend = ""

def open_file(file):
    files[file] = ""
    return "file opend"

def add_line(file, line):
    global file_opend
    if file not in files:
        return "file is not opend"
    files[file] += "\n"
    files[file] += line
    return "line added."

def execute_tool(tool: dict) -> str:
    tool_name = tool["function"]["name"]
    print(f"tool called: {tool_name}")
    if tool_name == "done":
        return "done"
    if tool_name == "open_file":
        try:
            return open_file(**json.loads(tool["function"]["arguments"]))
        except Exception as e:
            raise Exception("arguments are not valid.")
    elif tool_name == "add_line":
        try:
            return add_line(**json.loads(tool["function"]["arguments"]))
        except Exception as e:
            raise Exception("arguments are not valid.")
    else:
        raise Exception("tool doesn't exist.")

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
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": "call this function when you are done with task.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

provider.set_tools(tools)

assistant_message = {
    "role": "assistant",
    "content": None,
    "tool_calls": []
}

messages = [
    {
        "role": "system",
        "content": "You are an autonomous coding agent."
    },
    {
        "role": "user",
        "content": user_question
    }
]

assistant_in = False

loop = True
while loop:
    try:
        # print(json.dumps(messages, indent=4))
        result = provider.generate(messages=messages, stop_sequences=["<end_code>"])
    except Exception as e:
        print(e)
        break
    if result.text:
        print("response text: " + str(result.text))
        messages.append( {
            "role": "assistant",
            "content": str(result.text)
        })
        messages.append({
            "role": "user",
            "content": "use tools only."
        })

    if result.tool_calls:
        for tool in result.tool_calls:
            tool_result = ""
            try:
                tool_result = execute_tool(tool)
            except Exception as e:
                tool_result = e
                print("Error: " + e)

            if tool_result == "done":
                loop = False
                break

            if not assistant_in:
                messages.append(assistant_message)
                assistant_in = True

            assistant_message["tool_calls"].append(tool)
            messages.append({
                "role": "tool",
                "tool_call_id": tool["id"],
                "content": tool_result
            })

    # print()
    # print("input tokens: " + str(result.input_tokens))
    # print("output tokens: " + str(result.output_tokens))
    # print("latency_ms: " + str(result.latency_ms))
    # print("retries: " + str(result.retries))
    # print("response text: " + str(result.text))
    # print("tool_calls: " + str(result.tool_calls))
    # print()

print(json.dumps(messages, indent=4))
print(json.dumps(files, indent=4))
print(files["main.py"])


