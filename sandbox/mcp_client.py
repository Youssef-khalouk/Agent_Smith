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
        """
        Initialize the MCP client and establish a connection to an MCP server.

        Configure the connection using the provided command-line arguments, start
        a background asyncio event loop, and connect through stdio or HTTP. If a
        Docker image configuration is provided, initiate image setup and wait for
        the server to report its readiness.

        Args:
            args: Parsed command-line arguments containing connection settings and
                logging preferences.
            docker_image (DockerImage | None): Optional Docker image configuration
                used to prepare the task execution environment.
        """
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
        """
        Record an error and mark the MCP client as unavailable.

        Args:
            error (str): Error message describing the failure.

        Returns:
            None
        """
        self.error = error
        self.is_ok = False
        return None

    def _run_loop(self) -> None:
        """
        Run the client's asyncio event loop indefinitely in the background thread.

        Set the event loop for the current thread and start processing asynchronous
        tasks until the loop is stopped.

        Returns:
            None
        """
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def _run_async(self, coro) -> any:
        """
        Submit a coroutine to the background event loop and wait for its result.

        Args:
            coro: Coroutine to execute on the client's asyncio event loop.

        Returns:
            Any: Result produced by the coroutine.
        """
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result()

    def _get_connection_type_and_url(self, args) -> tuple[str, str | None]:
        """
        Determine the MCP connection type and server URL from command-line arguments.

        Prefer an explicitly configured HTTP endpoint, otherwise select stdio when
        an MCP server script is provided. Fall back to the default local HTTP
        endpoint when neither option is specified.

        Args:
            args: Parsed command-line arguments containing MCP connection settings.

        Returns:
            tuple[str, str | None]: Connection type and server URL, or None for
                the URL when using stdio.
        """
        if args.mcp_http:
            return "http_server", args.mcp_http
        if args.mcp_stdio:
            return "stdio", None

        return "http_server", "http://localhost:8000/"

    def _connect_http(self) -> None:
        """
        Establish an MCP client connection to an HTTP server.

        Create the MCP client context using the configured server URL and enter
        the asynchronous context through the background event loop. Record an
        error if the URL is missing or the connection fails.

        Returns:
            None
        """
        if self.url is None:
            return self._set_error("you can not connect using None url!.")
        try:
            self.context = Client(f"{self.url}mcp")
            self.client = self._run_async(self.context.__aenter__())
        except Exception:
            return self._set_error("can't connect to mcp server, run mcp server first.")

    def _connect_stdio(self) -> None:
        """
        Launch and connect to a local MCP server using stdio communication.

        Configure the local server command and environment, then establish the
        MCP client connection through the background event loop. Record an error
        if the server script is missing or the connection cannot be established.

        Returns:
            None
        """
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
        """
        Wait until the Docker image setup process completes.

        Repeatedly check the server's readiness status, returning when the task
        environment is ready or recording an error if setup fails or a request
        produces an invalid response.

        Returns:
            None
        """
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
        """
        Request Docker image setup through the HTTP server.

        Send the Docker image configuration to the server and wait for setup to
        complete when the server accepts the request. Record an error if the
        request fails or the server returns an unsuccessful status.

        Returns:
            None
        """
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
        """
        Initialize the Docker task environment through the stdio MCP connection.

        Read the setup resource, check for immediate setup failures, and wait
        until the server reports that the Docker environment is ready.

        Returns:
            None
        """
        try:
            result = self._run_async(self.client.read_resource("task://setup"))
            re = json.loads(result.contents[0].text)
            if re["state"] == "failed":
                return self._set_error(re["error"])
        except Exception as e:
            return self._set_error(f"MCP server connection error: {e}")

        self._wait_for_docker_image()

    def _setup_docker_image(self) -> None:
        """
        Send a request to the HTTP server to initialize the Docker task environment.

        Submit the Docker image configuration as JSON to the server's setup
        endpoint.

        Returns:
            requests.Response | str: HTTP response on success, or an error message
                if the request fails.
        """
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
        """
        Check the readiness status of the Docker task environment.

        Query the MCP readiness resource when using stdio or send an HTTP GET
        request to the server's readiness endpoint.

        Returns:
            The readiness response from the MCP resource or HTTP server, or an
            error message if the request fails.
        """
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
        """
        Request shutdown of the Docker task environment through the HTTP server.

        Send a POST request to the server's shutdown endpoint and print an error
        message if the request fails.

        Returns:
            The HTTP response on success, or None if the request fails.
        """
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
        """
        Retrieve the list of tools exposed by the connected MCP server.

        Returns:
            Any: The tool listing returned by the MCP client, or an error message
                if the request fails.
        """
        try:
            return self._run_async(self.client.list_tools())
        except Exception as e:
            return (f"MCP server connection error: {e}")
        
    def call_tool(self, function_name: str, kwargs: dict) -> any:
        """
        Invoke a tool on the connected MCP server.

        Execute the specified tool with the supplied arguments and return the
        result from its structured response.

        Args:
            function_name (str): Name of the MCP tool to invoke.
            kwargs (dict): Arguments to pass to the tool.

        Returns:
            Any: The tool's result, or None if an exception occurs.
        """
        try:
            result = self._run_async(self.client.call_tool(function_name, kwargs))
            return result.structured_content["result"]
        except Exception as e:
            print (f"MCP server connection failed: {e}")

    def close(self) -> None:
        """
        Close the MCP connection and release background event-loop resources.

        Shut down the Docker task environment when applicable, exit the MCP client
        context, stop the background event loop, wait for its thread to terminate,
        and close the event loop.

        Returns:
            None
        """
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
