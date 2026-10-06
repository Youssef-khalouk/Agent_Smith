import sys
from .sandbox import SandBox
from .mcp_client import Mcps
import subprocess


def interactive(sandbox: SandBox, config_file: str | None = None) -> None:
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
        print (sandbox.exec_code(code, config_file))


def main() -> None:
    args: int = len(sys.argv)
    if args == 1:
        sbx: SandBox = SandBox()
        print("Interactive sandbox launched successfully")
        interactive(sbx)
    elif args == 2:
        sbx: SandBox = SandBox()
        print("Interactive sandbox launched successfully")
        interactive(sbx, sys.argv[1])
    elif sys.argv[1] == "--mcp-stdio":
        sbx = SandBox(connection_type="stdio")
        command_line: List[str] = sys.argv[2].split()
        print("Interactive sandbox launched successfully")
        sub_proc = subprocess.run(
            [command_line[0], command_line[1]],
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        interactive(sbx, sys.argv[3])
    elif sys.argv[1] == "--mcp-server":
        url: str = sys.argv[2]
        sbx = SandBox(url=url)
        print("Interactive sandbox launched successfully")
        sub_proc = subprocess.run(
            ["python3", "mcp_tools_mbbp.py", '--http'],
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        interactive(sbx)
    else:
        print("somthing went wrong!!")
if __name__ == "__main__":
    main()