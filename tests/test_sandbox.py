import asyncio
from sandbox.sandbox import SandBox
from sandbox.mcp_client import Mcps
import traceback

sbx = SandBox()

code = """
import heapq
print(sorted([100, 5, 10, 20]))
"""

async def main():
    print(sbx.pull_image())
    exit()
    # await sbx.initialize()
    # result = sbx.exec_code(code=code, config_file="./sandbox_template.json")
    # print(result)
    # exit()
    # print(sbx)
    for name in sbx.tool_names:
        print(name)
    # print(result)
    mcp = Mcps()
    tools = await mcp.get_tools()
    # for tpl in tools.tools[0]:
    #     print(tpl)
    # exit()
    for data in sbx.tools_meta_data_swe:
        print(data)
    exit()
    result = await mcp.stdio_connection(("edit_file", {
        "filepath": "test.txt",
        "old_str": "reda",
        "new_str": "elouanass"
    }))
    tools = await mcp.get_tools()
    # for tool in tools.tools:
    #     for data in tool:
    #         print(data)
    # print(type(tools.tools[0]))
    import json
    array = []
    for tool in tools.tools:
        # print("\n\n\n")
        array.append(json.loads(tool.model_dump_json()))
    with open("tools_example.json", "w") as file:
        file.write(json.dumps(array, indent=4))

    # for x, y in tools.tools[0]:
    #     print(f"key: {x}")
    #     print(f"value: {y}")
    #     print()
    #     print()
    # print(result)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        traceback.print_exc()