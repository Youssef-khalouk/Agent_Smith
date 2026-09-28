from pydantic import BaseModel, Field
import ast
import subprocess
from typing import List, Dict
import resource
from models import SandboxConfig
from sandbox.mcp_client import Mcps
from mcp_types._types import ListToolsResult # delme
import fire
import asyncio

SBX: SandboxConfig = SandboxConfig()


class SandBox():
    def __init__(self):
        self.final_answer_called: bool = False
        self.final_answer_value: str = ""
        self.mcp_client: Mcps = Mcps()
        self.tools_meta_data_swe: List[str] = []
        self.tools_meta_data_mbpp: List[str] = [
            "- final_answer(answer: str) -> None: call this when the task is finished. "
            "For MBPP, pass your solution code as a string. "
            "For SWE-bench, pass get_patch().\n"
        ]
        self.tool_names: List[str] = []
        asyncio.run(self.parse_mcp_tools())

    async def parse_mcp_tools(self):
        tools: ListToolsResult = await self.mcp_client.get_tools()
        meta_data: str
        arg_type: str
        type_hints: Dict[str, str] = {
            "integer": "int",
            "string": "str",
            "boolean": "bool",
            "number": "float"
        }
        self.tools_meta_data_swe = [
            "- final_answer(answer: str) -> None: call this when the task is finished. "
            "For MBPP, pass your solution code as a string. "
            "For SWE-bench, pass get_patch().\n"
        ]
        for tool in tools.tools:
            self.tool_names.append(tool.name)

        for tool in tools.tools:
            meta_data = ""
            meta_data += f"{tool.name}("
            input_shema = tool.input_schema["properties"]
            for index, arg in enumerate(input_shema):
                if index != 0:
                    meta_data += ", "
                meta_data += f"{arg}: "
                if "$ref" in input_shema[arg]:
                    meta_data += f"{input_shema[arg]['$ref'][8:]}"
                else:
                    if input_shema[arg]['type'] in type_hints:
                        arg_type = type_hints[input_shema[arg]['type']]
                    else:
                        arg_type = input_shema[arg]['type']
                    meta_data += f"{arg_type}"
            meta_data += f"):  "
            meta_data += f"Description: {tool.description}"
            self.tools_meta_data_swe.append(meta_data)

    def get_mbpp_tools(self) -> List[str]:
        return (self.tools_meta_data_mbpp)
    
    def get_swe_tools(self) -> List[str]:
        return(self.tools_meta_data_swe)

    def _final_answer(self, value: str) -> None:
        self.final_answer_called = True
        self.final_answer_value = value

    def create_environment(self, code: str) -> str:
        child_process = subprocess.Popen(
            ["uv", "run", "python3", "-m", "sandbox.executor", "exec", f"--code={code}", f"--tool_names={self.tool_names}"],
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        output: str = ""
        resource.prlimit(
            child_process.pid, resource.RLIMIT_DATA,
            [SBX.max_memory_mb * 1024 * 1024,
            SBX.max_memory_mb * 1024 * 1024]
        )
        stdout, stderr = child_process.communicate(
            timeout=SBX.max_execution_time_seconds)
        if stdout.startswith("__FINAL_ANSWER__SANDBOX__\n"):
            self._final_answer(stdout[26:])
        
        if stdout != "":
            output += f"Output: {stdout}.\n"
        
        if stderr != "":
            output += f"Stderr: {stderr}.\n"

        return output

    def exec_code(self, code: str,
                  config_file: str | None = None) -> str:
        result: str
        result = self.create_environment(code)
        return result
    

def main() -> None:
    sbx: SandBox = SandBox()
    sbx.initialize()
    fire.Fire(
        {
            ""
        }
    )

