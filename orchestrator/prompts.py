from models import MBPPTaskInput, SWEBenchTaskInput


MBPP_EXAMPLE = """
Example:
Thought: I'll write a first version and add an assertion to verify that the function behaves correctly.
```python
solution = \"\"\"
def add(a, b):
    return a - b

assert add(1, 2) == 3
\"\"\"
print(run_tests(solution))
```<end_code>

Observation:
Stdout: AssertionError: assert add(1, 2) == 3
Expected: 3
Got: -1

Thought: The assertion failed because the function subtracts instead of adding. I'll change the operator and run the assertion again.
```python
solution = \"\"\"
def add(a, b):
    return a + b

assert add(1, 2) == 3
\"\"\"
print(run_tests(solution))
```<end_code>

Observation:
Stdout: 

Thought: The assertion passed, so the solution is verified. I'll now submit the solution without the test assertion.
```python
solution = \"\"\"
def add(a, b):
    return a + b
\"\"\"
final_answer(solution)
```<end_code>

"""


SWEBENCH_EXAMPLE = '''
Example:
Thought: I'll find where the function is defined before changing anything.
```python
print(search_function_or_class_definition_in_code("is_valid_email"))
```<end_code>

Observation:
/testbed/src/mail.py:65 def is_valid_email(mail: str) -> bool:

Thought: Let's read that part of the file to see the current logic.
```python
print(read_file("/testbed/src/mail.py", 60, 75))
```<end_code>

Observation:
65: def is_valid_email(mail: str) -> bool:
66:     """Validate email format."""
67:     pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$'
68:     return bool(re.match(pattern, mail))

Thought: The regex looks correct. I'll run the tests to see the real failure.
```python
print(run_tests())
```<end_code>

Observation:
1 failed: test_email_with_plus_sign - AssertionError

Thought: I'll fix the pattern, rerun the tests, then submit the patch.
```python
edit_file("/testbed/src/mail.py",
          "pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z]{2,}$'",
          "pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z]{2,}$'")
print(run_tests())
```<end_code>

Observation:
All tests passed.

Thought: Tests pass, I'll submit the patch.
```python
final_answer(get_patch())
```<end_code>
'''


class Prompts:

    @staticmethod
    def system_prompt(tools: str = "", benchmark="mbpp") -> str:
        return (
            "You are an autonomous coding agent.\n"
            "\n"
            "IMPORTANT:\n"
            "- Every response must contain exactly: a short Thought, then ONE python code block, then <end_code>.\n"
            "- Don't send me reasoning.\n"
            "- Only return the requested response in the specified format.\n"
            "- The Thought explains what you are about to do and why, in one or two lines.\n"
            "- The code must be inside a single ```python ... ``` block. Never split it into multiple blocks.\n"
            "- Never write an Observation yourself. Wait for the real one after your code runs.\n"
            "- Use print() to see results. The output is sent back to you as \"Observation:\".\n"
            "- Test your solution before calling final_answer. Only call final_answer once you have verified it works.\n"
            "- final_answer(answer) ends the task.\n"
            "\n"
            "Functions available inside the code block:\n"
            f"{tools}"
            "\n"
            f"{SWEBENCH_EXAMPLE if benchmark == 'swe_bench' else MBPP_EXAMPLE if benchmark == 'mbpp' else ''}"
        )


    @staticmethod
    def mbpp_task(task: MBPPTaskInput) -> str:
        user_content = task.task_definition
        user_content += f"\nfunction_definition: {task.function_definition}"
        user_content += "\ntest_imports:\n" + "\n".join(s for s in task.test_imports)
        user_content += "\ntest_list:\n" + "\n".join(s for s in task.test_list)
        return user_content

    @staticmethod
    def swebench_task(task: SWEBenchTaskInput) -> str:
        user_content = task.problem_statement
        user_content += f"\ninstance_id: {task.instance_id}"
        user_content += f"\ndocker_image: {task.docker_image}"
        user_content += f"\neval_script: {task.eval_script}"
        user_content += f"\nhints_text: {task.hints_text}"
        user_content += f"\nrepo: {task.repo}"
        return user_content
    
    @staticmethod
    def no_python_code_found() -> str:
        return "No python code block found. Write one inside ```python ... ```<end_code>."

    @staticmethod
    def malformed_code_interpreted(reason: str) -> str:
        return f"Warning: your code block was malformed but was interpreted anyway ({reason})."

    @staticmethod
    def timeout_partial_output(output: str) -> str:
        return f"Warning: execution hit the timeout. Partial output before it was killed:\n{output}"

    @staticmethod
    def truncated_output(output: str) -> str:
        return f"Warning: tool output was truncated due to size limits.\n{output}"

    @staticmethod
    def edit_error(detail: str) -> str:
        return f"Warning: your edit introduced a syntax error or lint violation: {detail}"

    @staticmethod
    def observation(output: str) -> str:
        return f"Observation:\n{output}"
