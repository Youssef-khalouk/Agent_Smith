from pydantic import BaseModel, Field
import ast
import subprocess
from typing import List, Dict, Any
import resource
from models import SandboxConfig, DockerImage
from sandbox.mcp_client import Mcps
from mcp_types._types import ListToolsResult
import fire
import asyncio
import json
from sandbox.security import configurate_sandbox
from time import sleep


SBX: SandboxConfig = SandboxConfig()


class SandBox():
    def __init__(self):
        self.error: str | None = None
        self.is_ok: bool = True
        self.final_answer_called: bool = False
        self.final_answer_value: str = ""
        self.mcp_client: Mcps = Mcps()
        self.tools_meta_data: List[str] = [
            "- def final_answer(answer: str) -> None: call this when the task is finished. "
            "For MBPP, pass your solution code as a string. "
            "For SWE-bench, pass get_patch().\n"
        ]
        self.tool_names: List[str] = []
        self.functions_keys_list: Dict[str, List[str]] = {}
        asyncio.run(self.parse_mcp_tools())

    
    def get_error(self) -> str:
        return (self.error)

    def is_ok(self) -> bool:
        return (self.is_ok)

    def _extract_data(self, tool: dict) -> str:
        def __extract_types(key: str, dictionary: Dict[Any, Any]):
            arg_type: str = ""
            if "$ref" in dictionary[key]:
                meta_data += f"{dictionary[key]['$ref'][8:]}"
            elif "type" in dictionary[key]:
                arg_type = __convert_type_hint(dictionary[key]["type"])
            elif "anyOf" in dictionary[key]:
                for i, _type in enumerate(dictionary[key]["anyOf"]):
                    if i != 0:
                        arg_type += " | "
                    arg_type += __convert_type_hint(_type["type"])
            return (arg_type)

        def __convert_type_hint(data: str) -> str:
            type_hints: Dict[str, str] = {
                "integer": "int",
                "string": "str",
                "boolean": "bool",
                "number": "float",
                "null": "None"
            }
            arg_type = type_hints.get(data, None)
            if not arg_type:
                arg_type = data
            return arg_type
        arg_type: str
        return_type: str
        keys: List[str] = []
        meta_data = f"- def {tool.name}("
        input_schema = tool.input_schema["properties"]
        output_schema = tool.output_schema["properties"]
        for index, arg in enumerate(input_schema):
            keys.append(arg)
            arg_type = ""
            if index != 0:
                meta_data += ", "
            meta_data += f"{arg}: "
            arg_type = __extract_types(arg, input_schema)
            meta_data += f"{arg_type}"
        self.functions_keys_list[tool.name] = keys
        meta_data += f") -> "
        return_type = __extract_types("result", output_schema)
        meta_data += f"{return_type}: "
        meta_data += f"Description: {tool.description}"
        return meta_data
    
    def pull_image(self, image: DockerImage | None = None) -> None:
        data = image.model_dump()
        print("docker image is pulling ...")
        response = self.mcp_client.pull_image(data)
        print(response.status_code)

        if response.status_code == 200 or response.status_code == 202:
            while True:
                result = self.mcp_client.check_docker_image()
                if result.json()["state"] == "ready":
                    break
                sleep(1)
            print("docker image is pulled seccessfuly.")

    def shotdown_image(self, image: DockerImage | None = None) -> None:
        pass

    async def parse_mcp_tools(self):
        tools: ListToolsResult | str = await self.mcp_client.get_tools()
        if isinstance(tools, str):
            self.is_ok = False
            self.error = tools
            print (tools)
            exit(1)
        self.tools_meta_data_swe = [
            "- def final_answer(answer: str) -> None: call this when the task is finished. "
            "For MBPP, pass your solution code as a string. "
            "For SWE-bench, pass get_patch().\n"
        ]
        for tool in tools.tools:
            self.tool_names.append(tool.name)
            self.tools_meta_data_swe.append(self._extract_data(tool))
    
    def get_tools(self) -> List[str]:
        return(self.tools_meta_data)

    def _final_answer(self, value: str) -> None:
        self.final_answer_called = True
        self.final_answer_value = value

    def create_environment(self, code: str,
                           config_file: str | None) -> str:
        child_process = subprocess.Popen(
            ["uv", "run", "python3", "-m",
             "sandbox.executor", "exec",
             f"--code={code}",
             f"--tool_names={self.tool_names}",
             f"--config_file={config_file}",
             f"--functions_keys={self.functions_keys_list}"],
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
            output += f"Stdout: {stdout}"
        
        if stderr.startswith("MCP server connection failed:"):
            self.error = stderr
            self.is_ok = False

        if stderr != "":
            output += f"Stderr: {stderr}"

        return output

    def exec_code(self, code: str,
                  config_file: str | None = None) -> str:
        result: str
        configurate_sandbox(config_file, SBX)
        result = self.create_environment(code, config_file)
        return result


