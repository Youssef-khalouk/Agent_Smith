from mcp.server.mcpserver import MCPServer
import sys
import io
import contextlib
from models import SandboxConfig
import builtins
from pathlib import Path


mcp = MCPServer()
SBX = SandboxConfig()


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

@mcp.tool()
def run_tests(code: str) -> str:
    """Run the code as Python code and return stdout/stderr."""

    stdout = io.StringIO()
    stderr = io.StringIO()
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
        "round": builtins.round,
        "isinstance": builtins.isinstance,
        "open": safe_open,
        "__import__": safe_import
    }
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exec(code, {"__builtins__": name_space})
    except Exception as e:
        stderr.write(f"{type(e).__name__}: {e}")

    output = ""
    if stdout.getvalue().strip():
        output += f"stdout: {stdout.getvalue()}"
    if stderr.getvalue().strip():
        output += f"\nstderr: {stderr.getvalue()}"
    return output

@mcp.resource("task://current")
def task_resource() -> str:
    return ""

@mcp.prompt()
def debug_failing_test(error: str) -> str:
    return f"The test failed with: {error}. Think about which part of the logic is wrong."


def run_mcp(connection_type: str) -> None:
    if connection_type == "http":
        mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
    elif connection_type == "stdio":
        mcp.run(transport="stdio")
    else:
        raise ValueError("Connection type doesn't exist ! Try 'http' or 'stdio'")


def main() -> None:
    if "--http" in sys.argv:
        run_mcp("http")
    else:
        run_mcp("stdio")


if __name__ == "__main__":
    main()
