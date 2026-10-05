import sys
from .sandbox import SandBox
from .mcp_client import Mcps


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
    if args == 1:
        sbx = SandBox()
        print("Interactive sandbox launched successfully")
        interactive(sbx)
    if args == 2:
        sbx = SandBox()
        print("Interactive sandbox with custom "
              "configuration launched successfully.")
        interactive(sbx, sys.argv[1])
    if sys.argv[1] == "--mcp-stdio":
        pass

if __name__ == "__main__":
    main()