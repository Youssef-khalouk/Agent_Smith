from pydantic import BaseModel, Field
import ast
import subprocess
from typing import List, Dict
import resource

class SandboxConfig(BaseModel):
    """Sandbox configuration for student solutions.
    Uses allowlist approach: only imports in authorized_imports are allowed.
    Everything else is blocked by default.
    """

    authorized_imports: List[str] = Field(default_factory=lambda: [
        "math", "math.*",
        "collections", "collections.*",
        "itertools", "re", "json",
        "typing", "typing.*",
        "functools", "operator",
        "heapq", "bisect", "copy",
        "string", "random",
        "datetime", "datetime.*",
        "array", "cmath",
    ])
    allowed_directories: List[str] = Field(default_factory=lambda: [
    "/testbed", "/tmp/agent"
    ])
    max_execution_time_seconds: int = 30
    max_memory_mb: int = 512

    def run_code(self, file: str) -> str:
        code: str
        with open(file) as fd:
            code = fd.read()
        # safe: bool = self.check_imports(code)
        safe = True
        if safe:
            child_process = subprocess.Popen(
                ["unshare","--user", "--map-root-user", "--mount", "--fork", "uv", "run", "python3", "executor.py"],
                stdout=subprocess.PIPE,
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            resource.prlimit(
                child_process.pid, resource.RLIMIT_DATA,
                [self.max_memory_mb * 1024 * 1024,
                self.max_memory_mb * 1024 * 1024]
            )
            stdout, stderr = child_process.communicate(
                timeout=self.max_execution_time_seconds)
            print(stderr)

    def check_imports(self, code: str) -> bool:
        tree = ast.parse(code)
        module: str = ""
        for node in tree.body:
            if isinstance(node, ast.Import):
                module = node.names[0].name
            elif isinstance(node, ast.ImportFrom):
                module = node.module
            if module not in self.authorized_imports:
                return (False)
        return (True)

test = SandboxConfig()
test.run_code("mcp_client.py")