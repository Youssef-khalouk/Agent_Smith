from pydantic import BaseModel, Field
import ast
import subprocess
from typing import List, Dict
import resource
from models import SandboxConfig


SBX: SandboxConfig = SandboxConfig()

class SandBox():
    def __init__(self):
        self.final_answer_called: bool = False
        self.final_answer_value: str = ""
    
    def _final_answer(self, value: str) -> None:
        self.final_answer_called = True
        self.final_answer_value = value

    def create_environment(self, code: str) -> str:
        child_process = subprocess.Popen(
            ["uv", "run", "python3", "-m", "sandbox.executor", "exec", f"--code={code}"],
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        resource.prlimit(
            child_process.pid, resource.RLIMIT_DATA,
            [SBX.max_memory_mb * 1024 * 1024,
            SBX.max_memory_mb * 1024 * 1024]
        )
        stdout, stderr = child_process.communicate(
            timeout=SBX.max_execution_time_seconds)
        if stdout.startswith("__FINAL_ANSWER__SANDBOX__\n"):
            self._final_answer(stdout[26:])    
        return(stdout, stderr)

    def exec_code(self, code) -> str:
        result: str
        result = self.create_environment(code)
        return (result)
    
    def get_tools() -> str:
        pass

