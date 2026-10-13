from pydantic import BaseModel, Field
import ast
import subprocess
from typing import List, Dict, Any
import resource
from models import SandboxConfig, DockerImage
from sandbox.mcp_client import Mcp_client
from mcp_types._types import ListToolsResult
import fire
import asyncio
import json
from sandbox.security import configurate_sandbox
from time import sleep
from mcp import StdioServerParameters as Params


SBX: SandboxConfig = SandboxConfig()


class SandBox():
    def __init__(self, connection_type: str = "http",
                 url: str = "http://localhost:8000/",
                 model: str = "mcp_tools_swebench.py",
                 config_file: str | None = None) -> None:
        self.config_file = config_file
        self.connection_type: str = connection_type
        self.url: str = url
        self.error: str | None = None
        self.is_ok: bool = True
        self.final_answer_called: bool = False
        self.final_answer_value: str = ""
        self.mcp_client: Mcp_client = Mcp_client()
        self.tools_meta_data: List[str] = [
            "- def final_answer(answer: str) -> None: call this when the task is finished. "
            "For MBPP, pass your solution code as a string. "
            "For SWE-bench, pass get_patch().\n"
        ]
        self.model_stdio: str = model
        self.tool_names: List[str] = []
        self.functions_keys_list: Dict[str, List[str]] = {}
        self.tools: ListToolsResult = None
        self.server_params: Params = None
        self.executor: subprocess = None
        self.connect_client()
        self.parse_mcp_tools()
        self.init_executor()

    def connect_client(self) -> None:
        if self.connection_type == "stdio":
            self.mcp_client.connect_stdio(self.model_stdio)
        else:
            self.mcp_client.connect_http(self.url)


    def init_executor(self) -> None:
        self.executor = subprocess.Popen(
            ["unshare", "--user", 
             "--map-root-user", "--net", "--",
             "uv", "run", "python3", "-m",
             "sandbox.executor", "exec",
             f"--tool_names={self.tool_names}",
             f"--config_file={self.config_file}",
             f"--functions_keys={self.functions_keys_list}",
             f"--connection_type={self.connection_type}",
             f"--url={self.url}",
             f"--model={self.model_stdio}"],
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        resource.prlimit(
            self.executor.pid, resource.RLIMIT_DATA,
            [SBX.max_memory_mb * 1024 * 1024,
            SBX.max_memory_mb * 1024 * 1024]
        )

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
        response = self.mcp_client.pull_image(data, self.url)
        # if the server is not running the response get asigned with a string:
        # Failed to establish a new connection: [Errno 111] Connection refused"
        if isinstance(response, str):
            self.error = response
            self.is_ok = False
            return
        elif response.status_code in (400, 409):
            self.error = response.json()["error"]
            self.is_ok = False
            return
        elif response.status_code == 200 or response.status_code == 202:
            while True:
                result = self.mcp_client.check_docker_image(self.url)
                if (isinstance(result, str) or result.json()["state"] == "failed"):
                    self.error = result
                    self.is_ok = False
                    retrueturn
                if result.json()["state"] == "ready":
                    break
                sleep(1)
        else:
            self.error = response.json()["error"]
            self.is_ok = False
            return

    def shotdown_image(self, image: DockerImage | None = None) -> None:
        result = self.mcp_client.shutdown_image(self.url)

    def parse_mcp_tools(self):
        try:
            self.tools = self.mcp_client.get_tools()
        except Exception as e:
            self.error = e
            self.is_ok = False
            return
        if isinstance(self.tools, str):
            self.is_ok = False
            self.error = self.tools
            return
        self.tools_meta_data_swe = [
            "- def final_answer(answer: str) -> None: call this when the task is finished. "
            "For MBPP, pass your solution code as a string. "
            "For SWE-bench, pass get_patch().\n"
        ]
        for tool in self.tools.tools:
            self.tool_names.append(tool.name)
            self.tools_meta_data.append(self._extract_data(tool))
    
    def get_tools_metadata(self) -> List[str]:
        return(self.tools_meta_data)

    def _final_answer(self, value: str) -> None:
        self.final_answer_called = True
        self.final_answer_value = value

    def exec_code(self, code: str) -> str:
        self.executor.stdin.write(f"{code}\n")
        self.executor.stdin.flush()
        configurate_sandbox(self.config_file, SBX)
        result: str = ""
        
        while True:
            response: Dict[str, Any] = {
                "ok": True,
                "result": "",
                "error": ""
            }
            line = self.executor.stdout.readline()
            try:
                line = json.loads(line)
            except Exception as e:
                self.is_ok = False
                self.error = f"unknown excutor result: {line}"
                return

            if line["type"] == "code_result":
                if line["stdout"]:
                    result += f"STDOUT: {line['stdout']}\n"
                if line["stderr"]:
                    result += f"STDERR: {line['stderr']}"
                    self.is_ok = False
                    self.error = line["stderr"]
                break
            elif line["type"] == "final_answer":
                self._final_answer(line["value"])
                return
            elif line["type"] == "tool_call":
                try:
                    response["result"] = self.mcp_client.call_tool(line["name"], line["arguments"])
                    response = json.dumps(response)
                except Exception as e:
                    self.is_ok = False
                    self.error = e
                    response["ok"] = False
                    response["error"] = e

                self.executor.stdin.write(f"{json.dumps(response)}\n")
                self.executor.stdin.flush()
            elif line["type"] == "error":
                self.is_ok = False
                self.error = line["error"]
                return
            else:
                self.is_ok = False
                self.error = f"unknowen type result: {line}"
                return 

        return result



