import sys
from .sandbox import SandBox
from .mcp_client import Mcp_client
import subprocess
import time


def interactive(sandbox: SandBox) -> None:
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
        print (sandbox.exec_code(code))


def main() -> None:
    args: int = len(sys.argv)
    try:
        if args == 1:
            subproc = subprocess.Popen(
                ["uv", "run", "python3", "mcp_tools_swebench.py", '--http'],
                stdout=subprocess.PIPE,
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            time.sleep(2)
            sbx: SandBox = SandBox()
            print("Interactive sandbox launched successfully")
            interactive(sbx)
        elif args == 2 and sys.argv[1] not in ("--mcp-stdio", "--mcp-server"):
            subproc = subprocess.Popen(
                ["uv", "run", "python3", "mcp_tools_swebench.py", '--http'],
                stdout=subprocess.PIPE,
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            time.sleep(2)
            sbx: SandBox = SandBox()
            print("Interactive sandbox launched successfully")
            interactive(sbx, sys.argv[1])
        elif sys.argv[1] == "--mcp-stdio" and len(sys.argv) in (3, 4):
            try:
                command_line: List[str] = sys.argv[2].split()
                print("Interactive sandbox launched successfully")
                sub_proc = subprocess.run(
                    ["python3", command_line[1]],
                    stdout=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                sbx = SandBox(connection_type="stdio", model=command_line[1], config_file=sys.argv[3])
                interactive(sbx)
            except IndexError as e:
                print("You didn't provide enough arguments")
        elif sys.argv[1] == "--mcp-server" and len(sys.argv) == 3:
            url: str = sys.argv[2]
            print("Interactive sandbox launched successfully")
            sbx = SandBox(url=url)
            interactive(sbx)
        else:
            print("somthing went wrong!!")
    except IndexError as e:
        print("You didn't provide enough arguments")
        print(e)
    except Exception as e:
        print(e)

if __name__ == "__main__":
    try:
        main()
    except IndexError as e:
        print("here")
    except Exception as e:
        print(e)
        exit()