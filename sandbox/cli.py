import fire
from mcp_client import Mcps


def main() -> None:
    fire.Fire(
        {
            "--mcp-stdio": Mcps().stdio_connection,
            "--mcp-server": Mcps().http_connection,
        }
    )


if __name__ == "__main__":
    main()