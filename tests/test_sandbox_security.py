import asyncio
from sandbox.sandbox import SandBox
from sandbox.mcp_client import Mcps

sbx = SandBox()

code = """
from math import *
print(addition(a=2, b=4))
"""

async def main():

    await sbx.initialize()
    # print(sbx.tool_names)
    # for tool in sbx.tools_meta_data:
    #     print(tool)
    result = sbx.exec_code(code)
    print(result)
    res = ""
    mcp = Mcps()
    tools = await mcp.get_tools()
    # print(f"{tools.tools}\n\n")
    # print(f"{tools.tools[1]}\n\n")
    # print(f"{tools.tools[0]}\n\n")
    # print(f"{tools.tools[2]}\n\n")
    # print(f"{tools.tools[3]}\n\n")
    # for d in tools.tools[1]:
    #     # print(d)
    #     pass
    # res += f"{tools.tools[1].name}("
    # # print()
    # # print()
    # for d in tools.tools[1]:
    #     if d[0] == "input_schema":
    #         for i, arg in enumerate(d[1]["properties"]):
    #             if i != 0:
    #                 res += ", "
    #             print(arg)
    #             print(d[1]["properties"][arg]["type"])
    #             res += f"{arg}: {d[1]['properties'][arg]['type']}"
    #         # print(d[1]["properties"])
    #     # print(d)
    # res += ")"
    # res += f" Description: {tools.tools[1].description}"
    # print()
    # print()
    # print(res)
    # print(type(tools.tools[0]))
    # for tool in tools.tools:
    #     # print(tool.input_schema["properties"])
    #     for arg in tool.input_schema["properties"]:
    #         if "$ref" in tool.input_schema["properties"][arg]:
    #             print(tool.input_schema["properties"][arg]["$ref"][8:])
    #     # print(tool.input_schema)

if __name__ == "__main__":
    asyncio.run(main())