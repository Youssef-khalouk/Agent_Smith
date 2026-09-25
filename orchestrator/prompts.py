from models import MBPPTaskInput, SWEBenchTaskInput


class Prompts:

    @staticmethod
    def system_prompt(tools: str = "") -> str:
        return (
            "You are an autonomous coding agent.\n"
            "Each turn, write a short Thought always, then ONE python code block, then <end_code>.\n"
            "\n"
            "Functions available inside the code block:\n"
            f"{tools}\n"
            "- final_answer(answer): call this when the task is finished. "
            "For MBPP, pass your solution code as a string. "
            "For SWE-bench, pass get_patch().\n"
            "\n"
            "Use print() to see results. The output will be sent back to you as \"Observation:\".\n"
            "\n"
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