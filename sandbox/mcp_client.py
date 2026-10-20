from mcp.client.stdio import stdio_client
from mcp import Client, StdioServerParameters as Params
from typing import Tuple, Dict, Any
import requests
import asyncio
import threading
from models import DockerImage
import os
from time import sleep


class McpClient():

    def __init__(self, args, docker_image: DockerImage | None = None) -> None:
        self.error = None
        self.is_ok = True
        self.container_name = "agent_smith"
        self.args = args
        self.docker_image = docker_image
        self.mcp_file = args.mcp_stdio
        self.client = None
        self.context = None
        self.local_mcp_server = None
        self.docker_container = None

        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

        self.connection_type, self.url = self._get_connection_type_and_url(args)
        self._connect()


    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def _run_async(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result()

    def _get_connection_type_and_url(self, args) -> (str, str | None):
        if args.mcp_http:
            return "http", args.mcp_http
        if args.mcp_stdio:
            return "stdio", None
        if args.mcp_server:
            return "http_server", args.mcp_server

        return "http", "http://localhost:8000/"

    def _connect(self) -> str:
        if self.connection_type == "stdio":
            self._connect_stdio()
        if self.connection_type == "http":
            self._connect_http()
        if self.connection_type == "http_server":
            self._connect_http_server()
    
    def _pull_docker_image_locally(self) -> None:
        import docker
        from docker.errors import NotFound, ImageNotFound
        client = docker.from_env()
        try:
            client.images.get(self.docker_image.docker_image)
        except docker.errors.ImageNotFound:
            client.images.pull(self.docker_image.docker_image)
        try:
            self.docker_container = client.containers.get(self.container_name)
            self._remove_docker_container()
        except NotFound:
            pass
        self.docker_container = client.containers.run(
            image=self.docker_image.docker_image,
            name=self.container_name,
            command="sleep infinity",
            detach=True)

    def _remove_docker_container(self) -> None:
        if self.docker_container:
            self.docker_container.reload()
            if self.docker_container.status == "running":
                self.docker_container.stop()
            self.docker_container.remove()
            self.docker_container = None

    def _connect_stdio(self) -> None:
        if self.mcp_file is None:
            raise Exception("you can not connect stdio using None local_mcp_server!.")

        self.local_mcp_server = Params(command="uv", args=["run", "python3", self.mcp_file, "--stdio"])

        self.context = Client(self.local_mcp_server)
        self.client = self._run_async(self.context.__aenter__())

        if self.docker_image:
            self._pull_docker_image_locally()

    def _connect_http(self) -> None:
        if self.url is None:
            raise Exception("you can not connect using None url!.")

        self.context = Client(f"{self.url}mcp")
        self.client = self._run_async(self.context.__aenter__())

        if self.docker_image:
            self._pull_docker_image_locally()

    def _connect_http_server(self) -> None:
        if self.url is None:
            raise Exception("you can not connect using None url!.")

        self.context = Client(f"{self.url}mcp")
        self.client = self._run_async(self.context.__aenter__())

        if self.docker_image:
            # pulling docker image in the server
            response = self._setup_docker_image()
            if isinstance(response, str):
                self.error = response
                self.is_ok = False
            elif response.status_code in (400, 409):
                self.error = response.json()["error"]
                self.is_ok = False
            elif response.status_code == 200 or response.status_code == 202:
                while True:
                    result = self._check_docker_image()
                    if (isinstance(result, str) or result.json()["state"] == "failed"):
                        self.error = result
                        self.is_ok = False
                    if result.json()["state"] == "ready":
                        return None
                    sleep(1)
            else:
                self.error = response.json()["error"]
                self.is_ok = False

    def _setup_docker_image(self) -> None:
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

    def _check_docker_image(self):
        try:
            response = requests.get(
                f"{self.url}ready",
                headers={"Authorization": "Bearer "},
                timeout=60,
            )
        except Exception as e:
            return f"server connection failed: {e}"
        return response

    def _shutdown_docker_image(self) -> None:
        try:
            response = requests.post(
                f"{self.url}shutdown",
                headers={"Authorization": "Bearer "},
                json={},
                timeout=60,
            )
        except Exception as e:
            print(f"shutdown docker image is failed: {e}")
    
    def get_tools(self) -> Any:
        try:
            return self._run_async(self.client.list_tools())
        except Exception as e:
            return (f"MCP server connection failed: {e}")
        
    def call_tool(self, function_name: str, kwargs: dict):
        try:
            result = self._run_async(self.client.call_tool(function_name, kwargs))
            return result.structured_content["result"]
        except Exception as e:
            print (f"MCP server connection failed: {e}")

    def close(self) -> None:
        if self.docker_image:
            if self.connection_type == "http_server":
                self._shutdown_docker_image()
            else:
                self._remove_docker_container()
        
        try:
            # 1. Close the MCP connection first
            if self.context is not None:
                self._run_async(self.context.__aexit__(None, None, None))
                self.context = None
                self.client = None

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
