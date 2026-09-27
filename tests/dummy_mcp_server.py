from mcp.server.mcpserver import MCPServer
import sys
import fire
from pydantic import BaseModel

# make an MCP server instance and give it the internal name "dummy"
MCP = MCPServer("dummy")

class Personne(BaseModel):
    name: str

@MCP.tool()
def an_echo(text: str) -> str:
    """Repeat the text back."""
    return text

@MCP.tool()
def addition(a: int, b: float) -> int:
    """Add two numbers."""
    return a + b

# Start the server listening on STDIO or http server for JSON-RPC msgs
def run_mcp(connection_type: str) -> None:
    if connection_type == "http":
        MCP.run(transport="streamable-http")
    elif connection_type == "stdio":
        MCP.run(transport="stdio")
    else:
        raise ValueError("Connection type doesn't exist ! Try 'http' or 'stdio'")

def main() -> None:
    fire.Fire(
        {
            "start_mcp": run_mcp
        }
    )


if __name__ == "__main__":
    main()
# stdio:npx @modelcontextprotocol/inspector uv run python dummy_mcp_server.py
# ->Opens a browser where i can inspect tools(above funcs) and click "Run Tool"
# !NO PRINT DEBUGGING to avoid agent reading print content as JSON-RPC = crash
# http: uv run python dummy_mcp_server.py --http + npx @modelcontextprotocol/inspector
