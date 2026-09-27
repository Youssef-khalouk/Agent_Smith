import asyncio
from sandbox.sandbox import SandBox
from sandbox.mcp_client import Mcps

sbx = SandBox()

code = """
with open('/home/reda/Desktop/test.txt', 'r') as fd:
    print('good')
print(addition(a=2, b=4))
"""

async def main():
    await sbx.initialize()
    result = sbx.exec_code(code)
    for data in sbx.tools_meta_data:
        print(data)
    # print(result)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(e)