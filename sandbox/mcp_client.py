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
        if args.verbose: print("\nInitalizeing McpClient.")
        self.error = None
        self.is_ok = True
        self.args = args
        self.docker_image = docker_image
        self.mcp_file = args.mcp_stdio
        self.client = None
        self.context = None
        self.local_mcp_server = None
        self.env = {}
        if self.docker_image:
            self.env = {k.upper(): v for k, v in self.docker_image.model_dump().items()}

        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

        self.connection_type, self.url = self._get_connection_type_and_url(args)

        if args.verbose: print(f"\tconnection type: {self.connection_type}.")
        if args.verbose: print("\tconnecting mcp server...")

        if self.connection_type == "stdio":
            self._connect_stdio()
        elif self.connection_type == "http_server":
            self._connect_http()
        
        if not self.is_ok: return None

        if args.verbose: print("\tmcp server is connected.")

        if self.docker_image is not None:
            if args.verbose: print("\tpulling docker image...")

            if self.connection_type == "stdio":
                self._pull_docker_image_in_stdio()
            else:
                self._pull_docker_image_in_server()

            if args.verbose and self.is_ok: print("\tdocker image is pulled seccessfully.")

    def _set_error(self, error: str) -> None:
        self.error = error
        self.is_ok = False
        return None

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def _run_async(self, coro) -> any:
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result()

    def _get_connection_type_and_url(self, args) -> tuple[str, str | None]:
        if args.mcp_http:
            return "http_server", args.mcp_http
        if args.mcp_stdio:
            return "stdio", None

        return "http_server", "http://localhost:8000/"

    def _connect_http(self) -> None:
        if self.url is None:
            return self._set_error("you can not connect using None url!.")
        try:
            self.context = Client(f"{self.url}mcp")
            self.client = self._run_async(self.context.__aenter__())
        except Exception:
            return self._set_error("can't connect to mcp server, run mcp server first.")

    def _connect_stdio(self) -> None:
        if self.mcp_file is None:
            return self._set_error("you can not connect stdio using None local_mcp_server!.")

        if self.args.verbose: print("\trunning local mcp server.")

        self.local_mcp_server = Params(
            command="sh",
            args=[
                "-c",
                'exec uv run python3 "$1" --stdio 2>>log.txt',
                "sh",
                self.mcp_file,
            ],
            env=self.env,
        )
        try:
            self.context = Client(self.local_mcp_server)
            self.client = self._run_async(self.context.__aenter__())
        except Exception:
            return self._set_error("can't connect to mcp server, try again!")

    def _wait_for_docker_image(self) -> None:
        while True:
            result = self._check_docker_image()

            if isinstance(result, str):
                return self._set_error(result)
            try:
                if self.connection_type == "stdio":
                    re = json.loads(result.contents[0].text)
                else:
                    re = result.json()
            except Exception as e:
                return self._set_error(f"Error: {e}")

            if re["state"] == "ready": return None

            if re["state"] == "failed":
                return self._set_error(re["error"])

            sleep(1)

    def _pull_docker_image_in_server(self):
        response = self._setup_docker_image()
        if isinstance(response, str):
            return self._set_error(response)
        elif response.status_code == 200 or response.status_code == 202:
            self._wait_for_docker_image()
        else: # errors like 400, 409 ....
            try:
                self.error = response.json()["error"]
            except Exception as e:
                return self._set_error(e)

    def _pull_docker_image_in_stdio(self) -> None:
        try:
            result = self._run_async(self.client.read_resource("task://setup"))
            re = json.loads(result.contents[0].text)
            if re["state"] == "failed":
                return self._set_error(re["error"])
        except Exception as e:
            return self._set_error(f"MCP server connection error: {e}")

        self._wait_for_docker_image()

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
        
    def call_tool(self, function_name: str, kwargs: dict) -> any:
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
