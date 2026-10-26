import subprocess
from typing import List, Dict, Any
import resource
from models import SandboxConfig
from sandbox.mcp_client import McpClient
from mcp_types._types import ListToolsResult
import fire
import asyncio
import json
from sandbox.security import configurate_sandbox
from mcp import StdioServerParameters as Params
import os
import signal


SBX: SandboxConfig = SandboxConfig()


class SandBox():
    def __init__(self, mcp_client: McpClient, config_file: str | None = None, logs: bool = False) -> None:
        """
        Initialize the sandbox and prepare the MCP tools and code executor.

        Store the configuration and client, initialize sandbox status and final
        answer tracking, retrieve and parse MCP tool metadata, and start the
        executor subprocess.

        Args:
            mcp_client (McpClient): Client used to communicate with the MCP server.
            config_file (str | None): Optional path to the sandbox configuration file.
            logs (bool): Whether to enable verbose initialization logs.
        """
        self.logs = logs
        if self.logs: print("\nInitalizeing sandbox.")
        self.config_file = config_file
        self.error: str | None = None
        self.is_ok: bool = True
        self.final_answer_called: bool = False
        self.final_answer_value: str = ""
        self.mcp_client: McpClient = mcp_client
        self.tools_meta_data: List[str] = [
            "- def final_answer(answer: str) -> None: call this when the task is finished. "
            "For MBPP, pass your solution code as a string. "
            "For SWE-bench, pass get_patch().\n"
        ]
        self.tools_meta_data_no_description = [
            "- def final_answer(answer: str) -> None:"
        ]
        self.tool_names: List[str] = []
        self.functions_keys_list: Dict[str, List[str]] = {}
        self.tools: ListToolsResult = None
        self.server_params: Params = None
        self.executor: subprocess = None
        self._parse_mcp_tools()

        self._init_executor()

    def _init_executor(self) -> None:
        """
        Start the executor subprocess inside an isolated user and network namespace.

        Pass the available tool names, sandbox configuration, and tool argument
        metadata to the executor. Configure the subprocess memory limit using
        the sandbox's maximum memory setting.

        Returns:
            None
        """
        if self.logs: print("\trunning subprocess executor.")
        self.executor = subprocess.Popen(
            ["unshare", "--user", 
             "--map-root-user", "--net", "--",
             "uv", "run", "python3", "-m",
             "sandbox.executor", "exec",
             f"--tool_names={self.tool_names}",
             f"--config_file={self.config_file}",
             f"--functions_keys={self.functions_keys_list}"],
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
        """
        Return the error recorded during sandbox initialization or execution.

        Returns:
            str: The error message, or None if no error has been recorded.
        """
        return (self.error)

    def is_ok(self) -> bool:
        """
        Return the sandbox's current operational status.

        Returns:
            bool: True if the sandbox is operational, otherwise False.
        """
        return (self.is_ok)

    def _extract_data(self, tool: dict) -> str:
        """
        Extract MCP tool metadata and generate a Python-style function signature.

        Parse the tool's input and output schemas, convert JSON Schema types into
        Python type hints, record the ordered argument names, and format the tool
        signature and description for use in the sandbox.

        Args:
            tool (dict): MCP tool definition containing its name, schemas, and
                description.

        Returns:
            tuple[str, str]: The generated function signature and tool description.
        """
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
        return meta_data, f"Description: {tool.description}"

    def _parse_mcp_tools(self):
        """
        Retrieve MCP tools and prepare their metadata for sandbox execution.

        Fetch the available tools from the MCP client, record their names, extract
        their function signatures and descriptions, and populate the metadata and
        argument-name collections. Mark the sandbox as unavailable if retrieval
        or parsing fails.

        Returns:
            None
        """
        if self.logs: print("\tgeting tools and parse them.")
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
        for tool in self.tools.tools:
            self.tool_names.append(tool.name)
            tool_data, description = self._extract_data(tool)
            self.tools_meta_data.append(tool_data + description)
            self.tools_meta_data_no_description.append(tool_data)

    def get_tools_metadata(self) -> List[str]:
        """
        Return the formatted metadata for the available MCP tools.

        Returns:
            List[str]: Tool signatures, descriptions, and final-answer instructions.
        """
        return(self.tools_meta_data)

    def _final_answer(self, value: str) -> None:
        """
        Record the final answer returned by the executor.

        Mark that the final-answer function has been called and store the supplied
        answer value.

        Args:
            value (str): Final answer produced by the executor.

        Returns:
            None
        """
        self.final_answer_called = True
        self.final_answer_value = value

    def exec_code(self, code: str) -> str:
        """
        Execute code in the sandbox and process responses from the executor.

        Send the code to the executor subprocess as JSON, then read and handle
        responses containing execution output, errors, final answers, or MCP tool
        calls. Forward tool calls to the MCP client and return their results to
        the executor.

        Args:
            code (str): Python code to execute inside the sandbox.

        Returns:
            str: Captured standard output, standard error, or the final answer.
                May return None when execution fails.
        """
        code = {"code": code}
        self.executor.stdin.write(f"{json.dumps(code)}\n")
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
                    result += "STDOUT: " + line['stdout']
                if line["stderr"]:
                    result += "\nSTDERR: " + line['stderr']
                break
            elif line["type"] == "final_answer":
                self._final_answer(line["value"])
                return self.final_answer_value
            elif line["type"] == "tool_call":
                try:
                    response["result"] = self.mcp_client.call_tool(line["name"], line["arguments"])
                    response = json.dumps(response)
                except Exception as e:
                    self.is_ok = False
                    self.error = e
                    response["ok"] = False
                    response["error"] = e
                self.executor.stdin.write(f"{response}\n")
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

    def close(self) -> None:
        """
        Close the MCP client and terminate the executor subprocess.

        Release the MCP connection, check whether the executor is still running,
        and attempt graceful termination. Forcefully terminate the executor if it
        does not stop within the timeout.

        Returns:
            None
        """
        self.mcp_client.close()
        if self.executor is None:
            return
        if self.executor.poll() is not None:
            return
        try:
            os.killpg(self.executor.pid, signal.SIGTERM)
            self.executor.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(self.executor.pid, signal.SIGKILL)
            self.executor.wait()
        except ProcessLookupError:
            pass

