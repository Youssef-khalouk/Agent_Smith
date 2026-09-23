from sandbox import Mcps
import asyncio

mcp_client = Mcps()

async def main():
    result = await mcp_client.http_connection("http://localhost:8000/mcp", ("addition", {"a": 4, "b": 5}))
    # result = await mcp_client.stdio_connection(("addition", {"a": 4, "b": 5}))
    print(result)

asyncio.run(main())
