import sys
from .sandbox import SandBox
from .mcp_client import McpClient
import subprocess
import time
from typing import List
import argparse
import os
import signal


def interactive(sandbox: SandBox) -> None:
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
        print(sandbox.exec_code(code))


def main() -> None:
    flag: bool = False
    parser = argparse.ArgumentParser(
        prog='sandbox_cli',
        description='Test the sandbox using CLI'
    )
    parser.add_argument('config_file', nargs='?', default=None)
    parser.add_argument('--mcp-stdio', '--mcp_stdio')
    parser.add_argument('--mcp-server', '--mcp_server')
    parser.add_argument('--mcp_http')
    try:
        args = parser.parse_args()
        if not args.mcp_stdio and (not args.mcp_server or not args.mcp_http):
            subproc = subprocess.Popen(
                ["uv", "run", "python3", "mcp_tools_mbpp.py", '--http'],
                start_new_session=True,
                stdout=subprocess.PIPE,
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            flag = True
            time.sleep(2)
        else:
            spliter: List[str] = args.mcp_stdio.split()
            args.mcp_stdio = spliter[1]
        mcp_client: McpClient = McpClient(args)
        sbx: SandBox = SandBox(mcp_client, args.config_file)
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