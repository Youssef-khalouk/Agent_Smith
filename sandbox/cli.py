import sys
from .sandbox import SandBox
from .mcp_client import Mcps
import subprocess


def interactive(sandbox: SandBox,
                config_file: str | None = None) -> str:
    while True:
        try:
            code = input(">>> ")
        except (EOFError, KeyboardInterrupt):
            break

        if code.strip() == "exit":
            break
        print (sandbox.exec_code(code, config_file))


def main() -> None:
    args: int = len(sys.argv)
    sbx = SandBox()
    if args == 1:
        print("Interactive sandbox launched successfully")
        interactive(sbx)
    if args == 2:
        print("Interactive sandbox launched successfully")
        interactive(sbx, sys.argv[1])
    if sys.argv[1] == "--mcp-stdio":
        command_line: List[str] = sys.argv[2].split()
        print("Interactive sandbox launched successfully")
        sub_proc = subprocess.run(
            [command_line[0], command_line[1]],
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        interactive(sbx, sys.argv[3])
    if sys.argv[1] == "--mcp-server":
        print("Interactive sandbox launched successfully")
        url: str = sys.argv[2]
        sub_proc = subprocess.run(
            ["python3", "mcp_tools_mbbp.py", '--http'],
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        interactive(sbx)

if __name__ == "__main__":
    main()