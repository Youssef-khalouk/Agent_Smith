from models import MBPPTaskInput, SWEBenchTaskInput, SolutionOutput, StepMetrics
from .extraction import extract_code
from sandbox.sandbox import SandBox
from .llm_providers import LLMProvider
from .prompts import Prompts
import time


class Agent:
    def __init__(self,
                 api_url: str,
                 model_name: str,
                 api_keys = [],
                 max_iterations: int = 10,
                 max_input_tokens: int = 6000,
                 max_output_tokens: int = 1500,
                 timeout_seconds: int = 120):

        self.provider = LLMProvider(api_url=api_url, api_keys=api_keys, model_name=model_name)
        self.sandbox = SandBox()
        self.max_iterations: int = max_iterations
        self.max_input_tokens: int = max_input_tokens
        self.max_output_tokens: int = max_output_tokens
        self.timeout_seconds = timeout_seconds
        self.tools: str = ""

    def _describe(self, task: any) -> tuple[str, str, str]:
        """Return (task_id, benchmark, first user prompt) for a task object."""
        if isinstance(task, MBPPTaskInput):
            self.tools = "".join([f"{tool}\n" for tool in self.sandbox.get_mbpp_tools()])
            return str(task.task_id), "mbpp", Prompts.mbpp_task(task)
        if isinstance(task, SWEBenchTaskInput):
            self.tools = "".join([f"{tool}\n" for tool in self.sandbox.get_swe_tools()])
            return task.instance_id, "swebench", Prompts.swebench_task(task)
        raise TypeError(f"Unsupported task type: {type(task).__name__}")

    def _limit_error(self, steps, start) -> str | None:
        if time.time() - start >= self.timeout_seconds:
            return "Timeout reached"
        if sum(s.input_tokens for s in steps) >= self.max_input_tokens:
            return "Input token limit reached"
        if sum(s.output_tokens for s in steps) >= self.max_output_tokens:
            return "Output token limit reached"
        return None

    def _metrics(self, step, result, extracted_code, output) -> StepMetrics:
        return StepMetrics(
            step=step,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            request_time_ms=result.latency_ms,
            api_url=self.provider.api_url,
            model_name=self.provider.model_name,
            llm_output=str(result.text),
            sandbox_input=extracted_code or "",
            sandbox_output=output,
            retries=result.retries,
        )

    def _build_output(self, task_id, benchmark, success, solution, steps, start, error) -> SolutionOutput:
        return SolutionOutput(
            task_id=task_id,
            benchmark=benchmark,
            success=success,
            solution=solution,
            system_prompt=Prompts.system_prompt(self.tools),
            iterations=len(steps),
            total_requests=sum(1 + s.retries for s in steps),
            total_input_tokens=sum(s.input_tokens for s in steps),
            total_output_tokens=sum(s.output_tokens for s in steps),
            total_time_seconds=time.time() - start,
            steps=steps,
            error=error
        )

    def run(self, task: MBPPTaskInput | SWEBenchTaskInput) -> SolutionOutput:
        task_id, benchmark, task_prompt = self._describe(task)
        start = time.time()
        messages = [
            {"role": "system", "content": Prompts.system_prompt(self.tools)},
            {"role": "user", "content": task_prompt}
        ]

        steps: list[StepMetrics] = []
        solution, success, error = "", False, None

        for step in range(1, self.max_iterations + 1):
            error = self._limit_error(steps, start)
            if error:
                break
            try:
                result = self.provider.generate(messages=messages, stop_sequences=["<end_code>"])
            except Exception as e:
                error = f"LLM error: {type(e).__name__}: {e}"
                break

            extracted_code, thought = extract_code(result.text)
            print("\n" + thought)
            if extracted_code is None:
                observation = Prompts.no_python_code_found()
            else:
                try:
                    observation = self.sandbox.exec_code(extracted_code)
                except Exception as e:
                    observation = f"Error: {type(e).__name__}: {e}"
            
            steps.append(self._metrics(step, result, extracted_code, str(observation)))
            
            messages.append({"role": "assistant", "content": result.text})
            messages.append({"role": "user", "content": Prompts.observation(observation)})

            if self.sandbox.final_answer_called:
                solution = self.sandbox.final_answer_value
                success = True
                break
        else:
            error = "Max iterations reached without final_answer."
        return self._build_output(task_id, benchmark, success, solution, steps, start, error)
