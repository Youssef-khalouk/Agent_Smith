import builtins
from models import SandboxConfig
from typing import Dict, List
from pydantic import BaseModel
import fire
from mcp import Client
import asyncio
import os
from sandbox.sandbox import SandBox
import json
from sandbox.security import configurate_sandbox


SBX: SandboxConfig = SandboxConfig()


async def call_mcp_tool(function_name: str, kwargs: dict):
    async with Client("http://localhost:8000/mcp") as client:
        result = await client.call_tool(function_name, kwargs)

    return result.structured_content

def execute_tool(function_name: str) -> callable:
    def func(**kwargs):
        return asyncio.run(
            call_mcp_tool(function_name, kwargs)
        )
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

def exec_code(code: str,
              tool_names: List[str],
              config_file: str | None) -> str:
    configurate_sandbox(config_file, SBX)
    name_space: Dict[str, str] = {
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
        name_space[tool] = execute_tool(tool)

    exec(code, {"__builtins__": name_space})

def main() -> None:
    fire.Fire({
        "exec": exec_code
    })


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e)
