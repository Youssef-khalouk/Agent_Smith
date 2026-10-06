from mcp.server.mcpserver import MCPServer
import sys
import io
import contextlib


mcp = MCPServer()


@mcp.tool()
def run_tests(code: str) -> str:
    """Run the code as Python code and return stdout/stderr."""

    stdout = io.StringIO()
    stderr = io.StringIO()

    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exec(code, {})
    except Exception as e:
        stderr.write(f"{type(e).__name__}: {e}")

    output = ""
    if stdout.getvalue().strip():
        output += f"STDOUT: {stdout.getvalue()}"
    if stderr.getvalue().strip():
        output += f"\nSTDERR: {stderr.getvalue()}"
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
