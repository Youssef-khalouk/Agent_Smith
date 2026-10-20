from mcp.client.stdio import stdio_client
from mcp import Client, StdioServerParameters as Params
from typing import Tuple, Dict, Any
import requests
import asyncio
import threading
from models import DockerImage
import os
from time import sleep
import json


class McpClient():

    def __init__(self, args, docker_image: DockerImage | None = None) -> None:
        self.error = None
        self.is_ok = True
        self.args = args
        self.docker_image = docker_image
        self.mcp_file = args.mcp_stdio
        self.client = None
        self.context = None
        self.local_mcp_server = None

        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

        self.connection_type, self.url = self._get_connection_type_and_url(args)

        if not self._connect(): return None

        if self.docker_image is not None:
            if self.connection_type == "stdio":
                self._wait_for_docker_image()
            else:
                self._pull_docker_image_in_server()


    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def _run_async(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result()

    def _get_connection_type_and_url(self, args) -> (str, str | None):
        if args.mcp_http:
            return "http_server", args.mcp_http
        if args.mcp_stdio:
            return "stdio", None

        return "http_server", "http://localhost:8000/"

    def _connect(self) -> bool:
        if self.connection_type == "stdio":
            self._connect_stdio()
        elif self.connection_type == "http_server":
            self._connect_http_server()
        if self.is_ok:
            print("mcp server is connected.")
            return True
        return False

    def _connect_http_server(self) -> None:
        if self.url is None:
            raise Exception("you can not connect using None url!.")
        try:
            self.context = Client(f"{self.url}mcp")
            self.client = self._run_async(self.context.__aenter__())
        except Exception:
            self.error = "can't connect to mcp server, run mcp server first."
            self.is_ok = False
    
    def _connect_stdio(self) -> None:
        if self.mcp_file is None:
            raise Exception("you can not connect stdio using None local_mcp_server!.")
        import os
        env = os.environ.copy()
        if self.docker_image:
            for k, v in self.docker_image.model_dump().items():
                env[k.upper()] = str(v)

        self.local_mcp_server = Params(
            command="sh",
            args=[
                "-c",
                'exec uv run python3 "$1" --stdio 2>>log.txt',
                "sh",
                self.mcp_file,
            ],
            env=env,
        )
        try:
            self.context = Client(self.local_mcp_server)
            self.client = self._run_async(self.context.__aenter__())
        except Exception:
            self.error = "can't connect to mcp server, try again!"
            self.is_ok = False

    def _wait_for_docker_image(self) -> None:
        while True:
            result = self._check_docker_image()

            if isinstance(result, str):
                self.error = result
                self.is_ok = False
                return None
            if self.connection_type == "stdio":
                re = json.loads(result.contents[0].text)
            elif self.connection_type == "http_server":
                re = result.json()

            if re["state"] == "ready":
                return None

            if re["state"] == "failed":
                self.error = "somthing went wrong with pulling docker image."
                self.is_ok =  False
            sleep(1)
    
    def _pull_docker_image_in_server(self):
        response = self._setup_docker_image()
        if isinstance(response, str):
            self.error = response
            self.is_ok = False
        elif response.status_code == 200 or response.status_code == 202:
            self._wait_for_docker_image()
        else: # errors like 400, 409 ....
            try:
                self.error = response.json()["error"]
            except ValueError:
                self.error = "coudn't pull docker image in server. pull docker response dosn't contine json"
            except Exception as e:
                self.error = str(e)
            finally:
                self.is_ok = False

    def _setup_docker_image(self) -> None:
        try:
            return requests.post(
                f"{self.url}setup",
                headers={"Authorization": "Bearer "},
                json=self.docker_image.model_dump(),
                timeout=60,
            )
        except Exception as e:
            return f"server connection error: {e}"

    def _check_docker_image(self):
        if self.connection_type == "stdio":
            try:
                return self._run_async(self.client.read_resource("task://ready"))
            except Exception as e:
                return f"MCP server connection error: {e}"
        else:
            try:
                return requests.get(
                    f"{self.url}ready",
                    headers={"Authorization": "Bearer "},
                    timeout=60,
                )
            except Exception as e:
                return f"server connection error: {e}"

    def _shutdown_docker_image(self):
        try:
            return requests.post(
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
            return (f"MCP server connection error: {e}")
        
    def call_tool(self, function_name: str, kwargs: dict):
        try:
            result = self._run_async(self.client.call_tool(function_name, kwargs))
            return result.structured_content["result"]
        except Exception as e:
            print (f"MCP server connection failed: {e}")

    def close(self) -> None:
        if self.docker_image:
            if self.connection_type == "http_server" and self.is_ok:
                self._shutdown_docker_image()
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
