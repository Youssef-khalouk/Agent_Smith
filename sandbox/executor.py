import builtins
from models import SandboxConfig
from typing import Dict, List
from pydantic import BaseModel
import fire
from mcp import Client, StdioServerParameters as Params
import os
from sandbox.sandbox import SandBox
import json
from sandbox.security import configurate_sandbox
import sys
import io
import contextlib
from path import Path


MAIN_STDOUT = sys.stdout
MAIN_STDIN = sys.stdin

class Tool_Fieled(Exception):
    ...


SBX: SandboxConfig = SandboxConfig()


def call_mcp_tool(function_name: str, kwargs: dict):
    request = {
        "type": "tool_call",
        "name": function_name,
        "arguments": kwargs
    }
    print(json.dumps(request), file=MAIN_STDOUT, flush=True)
    line = MAIN_STDIN.readline()
    response_line = json.loads(line)
    if not response_line["ok"]:
        raise Tool_Fieled(response_line["error"])
    return (response_line["result"])


def execute_tool(function_name: str, functions_keys) -> callable:
    def func(*args, **kwargs):
        func_args = functions_keys.get(function_name, [])
        for i, key in enumerate(func_args):
            if i < len(args):
                kwargs[key] = args[i]
            else:
                break
        return call_mcp_tool(function_name, kwargs)
    return func


def safe_open(file, mode="r", *args, **kwargs):
    path = Path(file).resolve()
    for directory in SBX.allowed_directories:
        allowed = Path(directory).resolve()
        try:
            path.relative_to(allowed)
            return builtins.open(path, mode, *args, **kwargs)
        except ValueError:
            continue
    raise PermissionError(f"Access denied: {path}")


def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    real_import = builtins.__import__
    root = name.split(".")[0]
    if root not in SBX.authorized_imports:
        raise ValueError("Import not allowed")
    return (real_import(name, globals=None, locals=None, fromlist=(), level=0))


def final_answer(value: str) -> str:
    output = {
        "type": "final_answer",
        "value": value
    }
    print(json.dumps(output), file=MAIN_STDOUT, flush=True)
    return "final answer is called, done."

def exec_code(tool_names: List[str], config_file: str | None, functions_keys: dict[str, list[str]]) -> str:

    configurate_sandbox(config_file, SBX)
    name_space = {
        "sorted": builtins.sorted,
        "print": builtins.print,
        "int": builtins.int,
        "bool": builtins.bool,
        "str": builtins.str,
        "float": builtins.float,
        "list": builtins.list,
        "dict": builtins.dict,
        "tuple": builtins.tuple,
        "set": builtins.set,
        "len": builtins.len,
        "range": builtins.range,
        "enumerate": builtins.enumerate,
        "zip": builtins.zip,
        "min": builtins.min,
        "max": builtins.max,
        "sum": builtins.sum,
        "abs": builtins.abs,
        "open": safe_open,
        "final_answer": final_answer,
        "__import__": safe_import
    }
    for tool in tool_names:
        name_space[tool] = execute_tool(tool, functions_keys)

    while True:
        code: str = input()

        stdout = io.StringIO()
        stderr = io.StringIO()

        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exec(code, {"__builtins__": name_space})
        except Tool_Fieled as e:
            result = {"type": "error", "error": str(e)}
            print(json.dumps(result), flush=True)
            continue
        except Exception as e:
            stderr.write(f"{type(e).__name__}: {str(e)}")

        output = {
            "type": "code_result",
            "stdout": stdout.getvalue().strip(),
            "stderr": stderr.getvalue().strip(),
        }
        print(json.dumps(output), flush=True)


def main() -> None:
    fire.Fire({"exec": exec_code})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e)
