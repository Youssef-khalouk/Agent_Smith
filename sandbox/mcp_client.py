from mcp.client.stdio import stdio_client
from mcp import Client, StdioServerParameters as Params
from typing import Tuple, Dict, Any
import requests
import asyncio
import threading
from models import DockerImage
import os
from time import sleep


class Mcp_client():

    def __init__(self,
            url: str | None = None, 
            mcp_file: str | None = None, 
            docker_image: DockerImage | None = None) -> None:
        self.url = url
        self.docker_image = docker_image
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
        # seting the docker image to the environment variables
        if self.docker_image:
            for key, value in self.docker_image.model_dump().items():
                os.environ[key.upper()] = value

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

    def _pull_image(self) -> None:
        try:
            response = requests.post(
                f"{self.url}setup",
                headers={"Authorization": "Bearer "},
                json=self.docker_image.model_dump(),
                timeout=60,
            )
        except Exception as e:
            return f"server connection failed: {e}"
        return response

    def pull_docker_image(self) -> str | None:
        if not self.docker_image:
            return None
        response = self._pull_image()
        # if the server is not running the response get asigned with a string:
        # Failed to establish a new connection: [Errno 111] Connection refused"
        if isinstance(response, str):
            return response
        elif response.status_code in (400, 409):
            return response.json()["error"]
        elif response.status_code == 200 or response.status_code == 202:
            while True:
                result = self._check_docker_image(self.url)
                if (isinstance(result, str) or result.json()["state"] == "failed"):
                    return result
                if result.json()["state"] == "ready":
                    return None
                sleep(1)
        else:
            return response.json()["error"]
        return None

    def _check_docker_image(self, url: str):
        try:
            response = requests.get(
                f"{url}ready",
                headers={"Authorization": "Bearer "},
                timeout=60,
            )
        except Exception as e:
            return f"server connection failed: {e}"
        return response
    
    def _shutdown_image(self) -> None:
        try:
            response = requests.post(
                f"{self.url}shutdown",
                headers={"Authorization": "Bearer "},
                json={},
                timeout=60,
            )
        except Exception as e:
            print(f"shutdown docker image is failed: {e}")

    def call_tool(self, function_name: str, kwargs: dict):
        if not self.connection_type:
            raise Exception("connection type did not set yet!.")
        try:
            result = self._run_async(self.client.call_tool(function_name, kwargs))
        except Exception as e:
            print (f"MCP server connection failed: {e}")
        return result.structured_content["result"]

    def close(self) -> None:
        if self.docker_image:
            self._shutdown_image()
        try:
            # 1. Close the MCP connection first
            if self.context is not None:
                self._run_async(
                    self.context.__aexit__(None, None, None)
                )
                self.context = None
                self.client = None

        finally:
            try:
                # 2. Shut down the Docker image
                if self.docker_image:
                    self._shutdown_image()
            finally:
                # 3. Stop the event loop
                if self.loop.is_running():
                    self.loop.call_soon_threadsafe(self.loop.stop)

                # 4. Wait for the background thread to finish
                if self.thread.is_alive():
                    self.thread.join(timeout=5)

                # 5. Close the event loop
                if not self.loop.is_running() and not self.loop.is_closed():
                    self.loop.close()
