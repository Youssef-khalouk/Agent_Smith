from mcp.client.stdio import stdio_client
from mcp import Client, StdioServerParameters as Params
from typing import Tuple, Dict, Any
import requests


class Mcps():

    def __init__(self) -> None:
        self.server_params: Params = Params(
            command="uv",
            args=[
                "run",
                "python3",
                "mcp_tools_swebench.py",
                "--stdio"
            ]
        )
        self.client = None
        self.context = None

    async def get_tools_http(self, url: str) -> str | None: # 
        try:
            async with Client(f"{url}mcp") as client:
                tools = await client.list_tools()
        except Exception as e:
            return (f"MCP server connection failed: {e}")
        return tools
    
    async def get_tools_stdio(self) -> str | None:
        try:
            self.context = Client(self.server_params)
            self.client = self.context.__aenter__()
            tools = await self.client.list_tools()
        except Exception as e:
            print(e)
        return tools

    def close_stdio_connection(self) -> str:
        if self.context != None:
            self.context.__aexit__()
        else:
            return ("Connection already closed.")
        return ("Connection closed.")

    def pull_image(self, docker_image: any) -> None:
        try:
            response = requests.post(
                f"{self.url}setup",
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
                f"{self.url}ready",
                headers={"Authorization": "Bearer "},
                timeout=60,
            )
        except Exception as e:
            return f"server connection failed: {e}"
        return response
    
    def shutdown_image(self):
        try:
            response = requests.get(
                f"{self.url}shutdown",
                headers={"Authorization": "Bearer "},
                timeout=60,
            )
        except Exception as e:
            return f"server connection failed: {e}"
        return response

