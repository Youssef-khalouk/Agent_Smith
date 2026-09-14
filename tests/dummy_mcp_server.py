# Import the main MCPServer class from the ModelContextProtocol
from mcp.server.mcpserver import MCPServer

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


# Start the server listening on standard input/output pipes for JSON-RPC msgs
if __name__ == "__main__":
    mcp.run(transport="stdio")
# testing:npx @modelcontextprotocol/inspector uv run python dummy_mcp_server.py
# ->Opens a browser where i can inspect tools(above funcs) and click "Run Tool"
# !NO PRINT DEBUGGING to avoid agent reading print content as JSON-RPC = crash
