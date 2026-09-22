from sandbox.sandbox import SandBox

sbx = SandBox()

test_code = """
def add(x, y):
    return x + y


# test function

print(add(2, 3))
print(add(2, 5))
"""

final_code = """
final_answer("\\ndef add(x, y):\\n  return (x + y)")
"""

tool_calls = [test_code, final_code]

i = 0
while True:
    result = sbx.exec_code(tool_calls[i])
    print(result)
    i += 1
    if sbx.final_answer_called:
        print(f"Final_answer: {sbx.final_answer_value}")
        break

    if i == 2:
        print("Error: while loop did not break.")
        break
