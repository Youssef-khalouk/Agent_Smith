from mcp.client.stdio import stdio_client
from mcp import Client, StdioServerParameters as Params
from typing import Tuple, Dict, Any
import requests
import asyncio
import threading


class Mcp_client():

    def __init__(self, url: str | None = None, mcp_file: str | None = None) -> None:
        self.url = url
        self.mcp_file = mcp_file
        self.connection_type: str = "stdio" if mcp_file else "http" if url else ""
        self.client = None
        self.context = None
        self.mcp_server = None
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
    
    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
    
    def _run_async(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result()

    def connect_stdio(self, mcp_file: str | None = None) -> None:
        if mcp_file:
            self.mcp_file = mcp_file
        if self.mcp_file is None:
            raise Exception("you can not connect stdio using None mcp_server!.")
        self.mcp_server = Params(command="uv", args=[
                                                "run",
                                                "python3",
                                                self.mcp_file,
                                                "--stdio"])
        self.context = Client(self.mcp_server)
        self.client = self._run_async(self.context.__aenter__())
        self.connection_type = "stdio"

    def connect_http(self, url: str | None = None) -> None:
        if url:
            self.url = url
        if self.url is None:
            raise Exception("you can not connect using None url!.")
        self.context = Client(f"{self.url}mcp")
        self.client = self._run_async(self.context.__aenter__())
        self.connection_type = "http"

    def get_tools(self) -> Any:
        if not self.connection_type:
            raise Exception("connection type did not set yet!.")
        try:
            tools = self._run_async(self.client.list_tools())
        except Exception as e:
            return (f"MCP server connection failed: {e}")
        return tools

    def close_stdio_connection(self) -> str:
        if self.context != None:
            self._run_async(self.context.__aexit__(None, None, None))

    def pull_image(self, docker_image: any, url: str) -> None:
        try:
            response = requests.post(
                f"{url}setup",
                headers={"Authorization": "Bearer "},
                json=docker_image,
                timeout=60,
            )
        except Exception as e:
            return f"server connection failed: {e}"
        return response

    def check_docker_image(self, url: str):
        try:
            response = requests.get(
                f"{url}ready",
                headers={"Authorization": "Bearer "},
                timeout=60,
            )
        except Exception as e:
            return f"server connection failed: {e}"
        return response
    
    def shutdown_image(self, url: str):
        try:
            response = requests.post(
                f"{url}shutdown",
                headers={"Authorization": "Bearer "},
                json={},
                timeout=60,
            )
        except Exception as e:
            return f"server connection failed: {e}"
        return response

    def call_tool(self, function_name: str, kwargs: dict):
        if not self.connection_type:
            raise Exception("connection type did not set yet!.")
        try:
            result = self._run_async(self.client.call_tool(function_name, kwargs))
        except Exception as e:
            print (f"MCP server connection failed: {e}")
        return result.structured_content["result"]
