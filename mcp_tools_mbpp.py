from mcp.server.mcpserver import MCPServer
import sys
import io
import contextlib


mcp = MCPServer()


@mcp.tool()
def run_tests(code: str) -> str:
    """Run the code as python code and return the captured output."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exec(code, {})
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"
    return buf.getvalue() or "" # or no output

@mcp.resource("task://context")
def task_resource() -> str:
    return ""

@mcp.prompt()
def debug_failing_test(error: str) -> str:
    return f"The test failed with: {error}. Think about which part of the logic is wrong."


def run_mcp(connection_type: str) -> None:
    if connection_type == "http":
        mcp.run(transport="streamable-http")
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
