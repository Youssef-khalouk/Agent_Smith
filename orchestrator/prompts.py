from models import MBPPTaskInput, SWEBenchTaskInput

importent = """
IMPORTANT:
- You must output executable Python code, and your thought process.
- NEVER answer with normal conversational text.
- Do not output your thinking nor reasoning nor explanation.
- Every response must contain thought (Thought: ...) followed by Python code block.
- The Python code must be between ```Python (python code) ```.
- Use the available tools through Python code.
- Make sure to test code before you call final_answer(answer).
"""

class Prompts:

    @staticmethod
    def system_prompt(tools: str = "") -> str:
        return (
            "You are an autonomous coding agent.\n"
            "Each turn, write a short Thought always, then ONE python code block, make sure its one block, then <end_code>.\n"
            "\n"
            "Functions available inside the code block:\n"
            f"{tools}\n"
            "Use print() to see results. The output will be sent back to you as \"Observation:\".\n"
            "\n"
            f"{importent}\n"
            "Example:\n"
            "Thought: I need to open main.py first.\n"
            "```python\n"
            "print(open_file(\"main.py\"))\n"
            "```<end_code>\n"
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