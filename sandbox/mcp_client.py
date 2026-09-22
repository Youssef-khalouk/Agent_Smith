from mcp.server import MCPServer
from mcp import Client


def main() -> None:
    with Client("http://localhost:8000/mcp") as client:
        result = await client.call_tool("add", {"a": 1, "b": 2})
        print(result.structured_content)  # {'result': 3}


if __name__ == "__main__":
    main()