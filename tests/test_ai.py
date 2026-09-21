from orchestrator import LLMProvider, Prompts
import os
import json
from dotenv import load_dotenv
import re, io, contextlib

load_dotenv()

import json
import re
from dataclasses import dataclass, field

CLOSED_FENCE = re.compile(r"```(?:python|py)?[ \t]*\n(.*?)```", re.DOTALL)
OPEN_FENCE = re.compile(r"```(?:python|py)?[ \t]*\n(.*)", re.DOTALL)
HERMES = re.compile(r"<tool_call>\s*(\{.*?\})\s*(?:</tool_call>|$)", re.DOTALL)
XML_INVOKE = re.compile(r'<invoke name="([^"]+)">(.*?)</invoke>', re.DOTALL)
XML_PARAM = re.compile(r'<parameter name="([^"]+)">(.*?)</parameter>', re.DOTALL)
REACT = re.compile(r"Action:\s*(\w+)\s*\n\s*Action Input:\s*(\{.*\})", re.DOTALL)

NO_CODE_MSG = (
    "No valid code block found in your response. "
    "Write your code inside a ```python ... ``` block followed by <end_code>."
)


@dataclass
class Extraction:
    code: str | None                       # None means nothing usable was found
    warnings: list[str] = field(default_factory=list)


def _to_call(name: str, args: dict) -> str | None:
    """Turn a tool name + arguments into a Python call (None if unsafe)."""
    if not name.isidentifier() or not all(k.isidentifier() for k in args):
        return None
    kwargs = ", ".join(f"{k}={v!r}" for k, v in args.items())
    return f"result = {name}({kwargs})\nprint(result)"


def _parse_value(raw: str):
    """XML parameters are strings: try to recover numbers, bools, lists."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _load_args(args) -> dict:
    if isinstance(args, str):               # OpenAI style: arguments is a JSON string
        args = json.loads(args)
    return args if isinstance(args, dict) else {}


def _fallback_calls(text: str) -> tuple[list[str], str]:
    """Convert non-Python tool call formats to Python. Returns (calls, format_name)."""
    calls: list[str] = []

    for raw in HERMES.findall(text):                       # (c) JSON / Hermes
        try:
            data = json.loads(raw)
            call = _to_call(data["name"], _load_args(data.get("arguments", {})))
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
        if call:
            calls.append(call)
    if calls:
        return calls, "JSON <tool_call>"

    for name, body in XML_INVOKE.findall(text):            # (b) XML invoke
        args = {k: _parse_value(v.strip()) for k, v in XML_PARAM.findall(body)}
        call = _to_call(name, args)
        if call:
            calls.append(call)
    if calls:
        return calls, "XML <invoke>"

    m = REACT.search(text)                                  # (d) ReAct
    if m:
        try:
            call = _to_call(m.group(1), _load_args(m.group(2)))
        except json.JSONDecodeError:
            call = None
        if call:
            return [call], "ReAct Action/Action Input"

    return [], ""


def extract_code(text: str) -> Extraction:
    text = text or ""

    # (a) Primary: ```python ... ``` block
    blocks = CLOSED_FENCE.findall(text)
    if blocks:
        warnings = []
        if len(blocks) > 1:
            warnings.append(
                f"{len(blocks)} code blocks found: only the FIRST was executed. "
                "Write exactly one code block per step."
            )
        return Extraction(blocks[0].strip("\n"), warnings)

    # Malformed: opening fence but no closing fence
    m = OPEN_FENCE.search(text)
    if m:
        code = m.group(1).split("<end_code>")[0].rstrip()
        if code.strip():
            return Extraction(
                code,
                ["Your code block was not closed with ```. Everything after the "
                 "opening fence was executed. Always close your block before <end_code>."],
            )

    # Other formats -> converted to Python calls
    calls, fmt = _fallback_calls(text)
    if calls:
        return Extraction(
            "\n".join(calls),
            [f"No python block found, but a {fmt} tool call was detected and converted "
             "to a Python call. Please answer with a ```python block next time."],
        )

    return Extraction(None, [NO_CODE_MSG])

provider = LLMProvider(
    api_url=os.environ.get("API_URL"),
    api_keys=str(os.getenv("OPENROUTER_API_KEYS")).split(","),
    model_name=os.environ.get("MODEL_NAME"),
)

FUNCTIONS = """- open_file(file) -> str        : open a file
- add_line(file, line) -> str   : append a line to an opened file
- final_answer(answer)          : call it when the task is finished and pass the code only as text after testing it.
"""

user_question = "create a function that can take array of strings and ckeck if there is any double strings and return bool."

files = {}
file_opend = ""


def open_file(file):
    files[file] = ""
    return "file opend"


def add_line(file, line):
    if file not in files:
        return "file is not opend"
    files[file] += "\n"
    files[file] += line
    return "line added."


answer = None


def final_answer(x):
    global answer
    answer = x


namespace = {"open_file": open_file, "add_line": add_line, "final_answer": final_answer}

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

print(Prompts.system_prompt(FUNCTIONS))
exit()
messages = [
    {
        "role": "system",
        "content": Prompts.system_prompt(FUNCTIONS)
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
    response = str(result.text)
    print("\n\n\n")
    print(response)
    print("\n\n\n")
    messages.append({"role": "assistant", "content": response})

    code = extract_code(result.text)

    if code is None:
        observation = "No python code block found. Write one inside ```python ... ```."
    else:
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                exec(code.code, namespace)   # TEMPORARY: real sandbox comes later
            observation = buf.getvalue() or "(no output)"
        except Exception as e:
            observation = f"Error: {type(e).__name__}: {e}"

    if answer is not None:
        break

    messages.append({
        "role": "user",
        "content": f"Observation:\n{observation}"
    })


print("answer:  ->   \n" + str(answer) + "\n\n\n")

print(json.dumps(messages, indent=4))
print(json.dumps(files, indent=4))
print("-------------------------------------------------")
print(files.get("main.py", None))
print("-------------------------------------------------")
