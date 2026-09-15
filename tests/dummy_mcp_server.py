# Import the main MCPServer class from the ModelContextProtocol
from mcp.server.mcpserver import MCPServer
import sys

# make an MCP server instance and give it the internal name "dummy"
mcp = MCPServer("dummy")

# Register the following Python function as an executable MCP tool primitive


@mcp.tool()
def an_echo(text: str) -> str:
    """Repeat the text back."""
    return text


@mcp.tool()
def addition(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


# Start the server listening on STDIO or http server for JSON-RPC msgs
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--http":
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
# stdio:npx @modelcontextprotocol/inspector uv run python dummy_mcp_server.py
# ->Opens a browser where i can inspect tools(above funcs) and click "Run Tool"
# !NO PRINT DEBUGGING to avoid agent reading print content as JSON-RPC = crash
# http: uv run python dummy_mcp_server.py + npx @modelcontextprotocol/inspector
