import sys
from .sandbox import SandBox
from .mcp_client import Mcps
import subprocess


def interactive(sandbox: SandBox, config_file: str | None = None) -> None:
    while True:
        if not sandbox.is_ok:
            print('here')
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
        command_line: List[str] = sys.argv[2].split()
        print("Interactive sandbox launched successfully")
        sub_proc = subprocess.run(
            ["python3", command_line[1]],
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        sbx = SandBox(connection_type="stdio", model=command_line[1])
        if len(sys.argv) == 4:
            interactive(sbx, sys.argv[3])
        else:
            interactive(sbx)
    elif sys.argv[1] == "--mcp-server":
        url: str = sys.argv[2]
        print("Interactive sandbox launched successfully")
        sub_proc = subprocess.run(
            ["python3", "mcp_tools_mbbp.py", '--http'],
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        sbx = SandBox(url=url)
        if len(sys.argv) == 4:
            interactive(sbx, sys.argv[3])
        else:
            interactive(sbx)
    else:
        print("somthing went wrong!!")
if __name__ == "__main__":
    main()