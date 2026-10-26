import sys
from .sandbox import SandBox
from .mcp_client import McpClient
import subprocess
import time
from typing import List
import argparse
import os
import signal
from pathlib import Path
from models import SWEBenchTaskInput, DockerImage


def interactive(sandbox: SandBox) -> None:
    """
    Run an interactive command-line session with the sandbox.

    Accept Python code for execution and
    support special commands to list
    available MCP tools or exit the session.
    Stop when the sandbox becomes
    invalid or the user interrupts the session.

    Args:
        sandbox (SandBox): Sandbox instance used
        to execute code and retrieve
        available MCP tool metadata.

    Returns:
        None
    """
    print("Interactive sandbox run successfully !")
    while True:
        if not sandbox.is_ok:
            print (sandbox.error)
            break
        try:
            code = input(">>> ")

        except (EOFError, KeyboardInterrupt):
            break

        if code.strip() == "exit":
            break
        if code.strip() == "list_tools":
            for tool in sandbox.tools_meta_data_no_description:
                print(tool)
            continue
        print(sandbox.exec_code(code))


def main() -> None:
    """
    Parse command-line arguments and initialize the sandbox environment.

    Validate configuration and task files, configure the MCP connection,
    initialize the MCP client and sandbox, and launch the interactive session.

    Supported arguments:
        config_file: Optional path to the sandbox configuration file.
        --mcp-stdio: MCP server command or script for stdio communication.
        --mcp-http: MCP server configuration for HTTP communication.
        --verbose: Enable verbose sandbox logging.
        --task-file: Optional path to the Docker image configuration file.

    Returns:
        None
    """
    flag: bool = False
    parser = argparse.ArgumentParser(
        prog='sandbox_cli',
        description='Test the sandbox using CLI'
    )
    parser.add_argument('config_file', nargs='?', default=None)
    parser.add_argument('--mcp-stdio', '--mcp_stdio', default=None)
    parser.add_argument('--mcp-http', '--mcp_http', default=None)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--task-file", default=None)
    try:
        args = parser.parse_args()
        if args.config_file:
            if not Path(args.config_file).exists():
                raise ValueError("Configuration file doesn't exist !")
        if args.mcp_stdio:
            spliter: List[str] = args.mcp_stdio.split()
            args.mcp_stdio = spliter[-1]
        if not args.mcp_stdio and not args.mcp_http:
            args.mcp_stdio = "mcp_tools_mbpp.py"

        #+++++++++++++++++++++++++++++++++++++++++++++++++++++
        # lcode li zedt ->
        docker_image = None
        if args.task_file and (args.mcp_http or "swe" in args.mcp_stdio):
            path: Path = Path(args.task_file)
            if not path.exists(): raise Exception(f"file '{path}' not found.")
            if not path.is_file(): raise Exception(f"file '{path}' is not a file.")
            with open(args.task_file, "r") as file:
                docker_image = DockerImage.model_validate_json(file.read())
        #+++++++++++++++++++++++++++++++++++++++++++++++++++++

        mcp_client: McpClient = McpClient(args, docker_image)
        if not mcp_client.is_ok:
            print(mcp_client.error)
            exit(1)

        sbx: SandBox = SandBox(mcp_client, args.config_file, logs=args.verbose)
        interactive(sbx)
        if flag:
            try:
                os.killpg(subproc.pid, signal.SIGTERM)
                subproc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(subproc.pid, signal.SIGKILL)
                subproc.wait()
            except ProcessLookupError:
                pass
    except IndexError as e:
        print("You didn't provide enough arguments")
        print(e)
    except Exception as e:
        print(e)
    finally:
        try:
            sbx.close()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except IndexError as e:
        print("here")
    except Exception as e:
        print(e)
        exit()