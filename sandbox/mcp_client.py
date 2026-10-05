from mcp.client.stdio import stdio_client
from mcp import Client, StdioServerParameters
from typing import Tuple, Dict, Any
import requests


class Mcps():

    async def get_tools(self, url: str = "http://localhost:8000/") -> str | None: # 
        try:
            async with Client(f"{url}mcp") as client:
                tools = await client.list_tools()
        except Exception as e:
            return (f"MCP server connection failed: {e}")
        return tools
    
    def pull_image(self, docker_image: any) -> None:
        try:
            response = requests.post(
                "http://localhost:8000/setup",
                headers={"Authorization": "Bearer "},
                json=docker_image,
                timeout=60,
            )
        except Exception as e:
            return f"server connection failed: {e}"
        return response

    def check_docker_image(self):
        try:
            response = requests.get(
                "http://localhost:8000/ready",
                headers={"Authorization": "Bearer "},
                timeout=60,
            )
        except Exception as e:
            return f"server connection failed: {e}"
        return response
    
    def shutdown_image(self):
        try:
            response = requests.get(
                "http://localhost:8000/ready",
                headers={"Authorization": "Bearer "},
                timeout=60,
            )
        except Exception as e:
            return f"server connection failed: {e}"
        return response

    async def stdio_connection(self, tool_call: Tuple[str, Any]) -> Any:
        try:
            result = ''
            server_params = StdioServerParameters(
                command="uv",
                args=[
                    "run",
                    "python3",
                    "mcp_tools_swebench.py",
                    "--stdio"
                ]
            )
            async with Client(server_params) as client:
                res = await client.list_tools()
                print(res)
                result = await client.call_tool(
                    tool_call[0],
                    tool_call[1]
                )
        except Exception as e:
            print(e)
        exit()
        return result.structured_content

    async def http_connection(self, tool_call: Tuple[str, Any],
                              url: str = "http://localhost:8000/mcp",) -> None:
        try:
            async with Client(url) as client:
                result = await client.call_tool(
                    tool_call[0],
                    tool_call[1]
                )
        except Exception as e:
            print(e)
        return (result.structured_content)

