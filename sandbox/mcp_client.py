from mcp.client.stdio import stdio_client
from mcp import Client, StdioServerParameters
from typing import Tuple, Dict, Any


class Mcps():

    async def get_tools(self):
        async with Client("http://localhost:8000/mcp") as client:
            tools = await client.list_tools()
        return tools    

    async def stdio_connection(self, tool_call: Tuple[str, Any]) -> Any:
        server_params = StdioServerParameters(
            command="uv",
            args=[
                "run",
                "python3",
                "mcp_tools_swebench.py"
            ]
        )
        async with Client(server_params) as client:
            result = await client.call_tool(
                tool_call[0],
                tool_call[1]
            )
        return result.structured_content

    async def http_connection(self, url: str, tool_call: Tuple[str, Any]) -> None:
        async with Client(url) as client:
            result = await client.call_tool(tool_call[0], tool_call[1])
        return (result.structured_content)

