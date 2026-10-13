import builtins
from models import SandboxConfig
from typing import Dict, List
from pydantic import BaseModel
import fire
from mcp import Client, StdioServerParameters as Params
import asyncio
import os
from sandbox.sandbox import SandBox
import json
from sandbox.security import configurate_sandbox
import sys
import io
import contextlib


SBX: SandboxConfig = SandboxConfig()
URL = ""
CONNECTION_TYPE = "http"
MODEL_STDIO= "mcp_tools_swebench.py"


def call_mcp_tool(function_name: str, kwargs: dict):
    request = {
        "type": "tool_call",
        "name": function_name,
        "arguments": kwargs
    }
    print(json.dumps(request), flush=True)

    response = json.loads(sys.stdin.readline())

    if not response["ok"]:
        print (response["error"])
        exit (1)
    
    return (response["result"])


def execute_tool(function_name: str, functions_keys) -> callable:
    def func(*args, **kwargs):
        func_args = functions_keys.get(function_name, [])
        for i, key in enumerate(func_args):
            if i < len(args):
                kwargs[key] = args[i]
            else:
                break
        return asyncio.run(call_mcp_tool(function_name, kwargs))
    return func


def safe_open(file, flag):
    real_open = builtins.open
    path = os.path.abspath(os.fspath(file))
    for direct in SBX.allowed_directories:
        if direct in path:
            return (real_open(file, flag))
    raise ValueError("Access denied")


def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    real_import = builtins.__import__
    sbx: SandboxConfig = SandboxConfig()
    root = name.split(".")[0]
    if root not in SBX.authorized_imports:
        raise ValueError("Import not allowed")
    return (real_import(name, globals=None, locals=None, fromlist=(), level=0))


def final_answer(value: str) -> str:
    print ("__FINAL_ANSWER__SANDBOX__\n" + value)
    exit()

def exec_code(tool_names: List[str],
              config_file: str | None,
              functions_keys: dict[str, list[str]],
              connection_type: str = "http",
              url: str = "http://localhost:8000/",
              model: str = "mcp_tools_swebench.py") -> str:
    code: str = input()
    global URL, CONNECTION_TYPE, MODEL_STDIO
    URL = url
    CONNECTION_TYPE = connection_type
    MODEL_STDIO = model
    configurate_sandbox(config_file, SBX)
    name_space: Dict[str, str] = {
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

    stdout = io.StringIO()
    stderr = io.StringIO()

    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exec(code, {"__builtins__": name_space})
    except Exception as e:
        stderr.write(f"{type(e).__name__}: {e}")

    output = {
        "stdout": "",
        "stderr": "",
        "status": "Done"
    }

    if stdout.getvalue().strip():
        output["stdout"] = stdout.getvalue()

    if stderr.getvalue().strip():
        output["stderr"] = stderr.getvalue()

    output = json.dumps(output)

    print (output)


def main() -> None:
    fire.Fire({
        "exec": exec_code
    })


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e)
