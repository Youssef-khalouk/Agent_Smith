from models import MBPPTaskInput, SWEBenchTaskInput


MBPP_PROMPT = """
You are an autonomous coding agent solving an MBPP programming task.

IMPORTANT:
- Every response must contain exactly: a short Thought, then ONE python code block, then <end_code>.
- Don't send me reasoning.
- Only return the requested response in the specified format.
- The Thought explains what you are about to do and why, in one or two lines.
- The code must be inside a single ```python ... ``` block. Never split it into multiple blocks.
- Never write an Observation yourself. Wait for the real one after your code runs.
- Use print() to see results. The output is sent back to you as "Observation:".
- Test your solution before calling final_answer.
- Only call final_answer once you have verified it works.
- final_answer(answer) ends the task.

Functions available inside the code block:
{tools}

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


SWEBENCH_PROMPT = """
You are an autonomous coding agent solving a SWE-bench software engineering task.

IMPORTANT:
- Every response must contain exactly: a short Thought, then ONE python code block, then <end_code>.
- Don't send me reasoning.
- Only return the requested response in the specified format.
- The Thought explains what you are about to do and why, in one or two lines.
- The code must be inside a single ```python ... ``` block. Never split it into multiple blocks.
- Never write an Observation yourself. Wait for the real one after your code runs.
- Use print() to see results. The output is sent back to you as "Observation:".
- Inspect the repository and relevant files before making changes.
- Run tests after making changes to verify the fix.
- Only call final_answer once you have verified the fix works.
- final_answer(get_patch()) ends the task.
- The repository is located at '{mount_path}'. All file paths must be inside it.

Functions available inside the code block:
{tools}

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
66:     \"\"\"Validate email format.\"\"\"
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
edit_file(
    "/testbed/src/mail.py",
    "pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z]{2,}$'",
    "pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z]{3,}$'"
)
print(run_tests())
```<end_code>

Observation:
All tests passed.

Thought: Tests pass, I'll submit the patch.
```python
final_answer(get_patch())
```<end_code>
"""


class Prompts:
    """
    Provide system prompts, task descriptions, and observation messages for coding agents.

    Define benchmark-specific instructions for MBPP and SWE-bench tasks and
    format task inputs, execution observations, and warning messages.
    """
    @staticmethod
    def system_prompt(tools: str = "", benchmark="mbpp", mount_path: str = ".") -> str:
        """
        Build the system prompt for the specified benchmark.

        Insert the available tool descriptions and, for SWE-bench tasks, the
        repository mount path into the appropriate prompt template.

        Args:
            tools: Descriptions of the tools available to the agent.
            benchmark: The benchmark identifier, either "mbpp" or "swe_bench".
            mount_path: The repository path used for SWE-bench tasks.

        Returns:
            The formatted system prompt.

        Raises:
            ValueError: If the benchmark is not supported.
        """
        if benchmark == "mbpp":
            return MBPP_PROMPT.replace("{tools}", tools)

        if benchmark == "swe_bench":
            return SWEBENCH_PROMPT.replace("{tools}", tools).replace("{mount_path}", mount_path)

        raise ValueError(f"Unsupported benchmark: {benchmark}")

    @staticmethod
    def mbpp_task(task: MBPPTaskInput) -> str:
        """
        Format an MBPP task into a user prompt.

        Combine the task definition, function signature, test imports, and test
        cases into a single string for the coding agent.

        Args:
            task: The MBPP task input containing its definition and tests.

        Returns:
            A formatted string describing the programming task and its tests.
        """
        user_content = task.task_definition
        user_content += f"\nfunction_definition: {task.function_definition}"
        user_content += "\ntest_imports:\n" + "\n".join(s for s in task.test_imports)
        user_content += "\ntest_list:\n" + "\n".join(s for s in task.test_list)
        return user_content

    @staticmethod
    def swebench_task(task: SWEBenchTaskInput) -> str:
        """
        Format a SWE-bench task into a user prompt.

        Combine the problem statement, hints, and repository identifier into a
        single string for the coding agent.

        Args:
            task: The SWE-bench task input containing problem and repository details.

        Returns:
            A formatted string describing the software engineering task.
        """
        user_content = task.problem_statement
        user_content += f"\nhints_text: {task.hints_text}"
        user_content += f"\nrepo: {task.repo}"
        return user_content

    @staticmethod
    def no_python_code_found() -> str:
        """
        Return an observation instructing the agent to provide a Python code block.

        Returns:
            A message explaining the required code-block format.
        """
        return "No python code block found. Write one inside ```python ... ```<end_code>."

    @staticmethod
    def malformed_code_interpreted(reason: str) -> str:
        """
        Create a warning explaining that malformed code was still interpreted.

        Args:
            reason: The explanation of why the code block was considered malformed.

        Returns:
            A warning message containing the reason.
        """
        return f"Warning: your code block was malformed but was interpreted anyway ({reason})."

    @staticmethod
    def timeout_partial_output(output: str) -> str:
        """
        Create a warning containing partial output from a timed-out execution.

        Args:
            output: The output produced before execution was terminated.

        Returns:
            A warning message describing the timeout and including partial output.
        """
        return f"Warning: execution hit the timeout. Partial output before it was killed:\n{output}"

    @staticmethod
    def truncated_output(output: str) -> str:
        """
        Create a warning indicating that tool output was truncated.

        Args:
            output: The truncated tool output.

        Returns:
            A warning message followed by the available output.
        """
        return f"Warning: tool output was truncated due to size limits.\n{output}"

    @staticmethod
    def edit_error(detail: str) -> str:
        """
        Create a warning describing a syntax error or lint violation after an edit.

        Args:
            detail: Details about the syntax error or lint violation.

        Returns:
            A warning message containing the error details.
        """
        return f"Warning: your edit introduced a syntax error or lint violation: {detail}"

    @staticmethod
    def observation(output: str) -> str:
        """
        Format execution output as an observation for the coding agent.

        Args:
            output: The output returned by code execution or a tool.

        Returns:
            A string prefixed with the "Observation:" label.
        """
        return f"Observation:\n{output}"
