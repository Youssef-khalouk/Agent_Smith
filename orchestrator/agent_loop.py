from models import MBPPTaskInput, SWEBenchTaskInput, SolutionOutput, StepMetrics, DockerImage
from .extraction import extract_code
from sandbox.sandbox import SandBox
from .llm_providers import LLMProvider
from .prompts import Prompts
import time


class Agent:
    """
    Orchestrate the language model, sandbox, and iterative task-solving process.

    Manage task descriptions, prompt construction, code extraction and execution,
    iteration and resource limits, and collection of execution metrics. Support
    both MBPP programming tasks and SWE-bench software engineering tasks.
    """
    def __init__(self,
                 provider: LLMProvider,
                 sandbox: SandBox,
                 max_iterations: int,
                 max_input_tokens: int,
                 max_output_tokens: int,
                 timeout_seconds: int,
                 logs: bool = False):

        self.logs = logs
        if self.logs: print("\nInitalizeing Agent.")
        self.provider = provider
        self.sandbox = sandbox
        self.max_iterations: int = max_iterations
        self.max_input_tokens: int = max_input_tokens
        self.max_output_tokens: int = max_output_tokens
        self.timeout_seconds = timeout_seconds
        self.tools: str = ""
        self.messages: list = []

    def _describe(self, task: any) -> tuple[str, str, str]:
        """Return (task_id, benchmark, system_prompt, first user prompt) for a task object."""
        if isinstance(task, MBPPTaskInput):
            self.tools = "".join([f"{tool}\n" for tool in self.sandbox.get_tools_metadata()])
            task_id = str(task.task_id)
            benchmark = "mbpp"
            system_prompt = Prompts.system_prompt(self.tools, benchmark)
            task_prompt = Prompts.mbpp_task(task)

        elif isinstance(task, SWEBenchTaskInput):
            self.tools = "".join([f"{tool}\n" for tool in self.sandbox.get_tools_metadata()])
            task_id = task.instance_id
            benchmark = "swe_bench"
            system_prompt = Prompts.system_prompt(self.tools, benchmark)
            task_prompt = Prompts.swebench_task(task)
        else:
            raise TypeError(f"Unsupported task type: {type(task).__name__}")

        return (task_id, benchmark, system_prompt, task_prompt)

    def _limit_error(self, steps, start) -> str | None:
        """
        Check whether the agent has exceeded its execution or token limits.

        Compare elapsed time and cumulative input and output token usage against
        the configured limits.

        Args:
            steps: List of recorded metrics for completed agent iterations.
            start (float): Start time returned by time.time().

        Returns:
            str | None: A description of the exceeded limit, or None if all limits
                remain satisfied.
        """
        if time.time() - start >= self.timeout_seconds:
            return "Timeout reached"
        if sum(s.input_tokens for s in steps) >= self.max_input_tokens:
            return "Input token limit reached"
        if sum(s.output_tokens for s in steps) >= self.max_output_tokens:
            return "Output token limit reached"
        return None

    def _metrics(self, step, result, extracted_code, output) -> StepMetrics:
        """
        Build a metrics record for an agent iteration.

        Collect token usage, request latency, provider and model information,
        generated language model text, extracted code, sandbox output, and retry
        count into a StepMetrics object.

        Args:
            step (int): Current iteration number.
            result: Language model response containing text, usage, latency, and retries.
            extracted_code (str | None): Code extracted from the model response.
            output (str): Result or error message produced by sandbox execution.

        Returns:
            StepMetrics: Metrics recorded for the current iteration.
        """
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
        """
        Construct the final solution output and aggregate execution metrics.

        Calculate total requests, token usage, elapsed time, and iteration count,
        then package the solution, system prompt, per-step metrics, and any error
        into a SolutionOutput object.

        Args:
            task_id (str): Identifier of the task being solved.
            benchmark (str): Benchmark name associated with the task.
            success (bool): Whether the agent completed the task successfully.
            solution (str): Final solution or patch produced by the agent.
            steps (list[StepMetrics]): Metrics recorded for each agent iteration.
            start (float): Agent start time returned by time.time().
            error (str | None): Error message if the task was not completed.

        Returns:
            SolutionOutput: Final solution and aggregated execution metrics.
        """
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
        """
        Run the agent loop to solve an MBPP or SWE-bench task.

        Construct the initial conversation, repeatedly request language model
        responses, extract and execute generated code, and append observations
        to the conversation. Stop when a final answer is produced, the sandbox
        fails, an exception occurs, a resource limit is reached, or the maximum
        number of iterations is exhausted.

        Args:
            task (MBPPTaskInput | SWEBenchTaskInput): Task to solve.

        Returns:
            SolutionOutput: Final solution, success status, execution metrics,
                and any error encountered.
        """
        if self.logs: print("\trunning agent loop:")
        task_id, benchmark, system_prompt, task_prompt = self._describe(task)
        start = time.time()
        self.messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task_prompt}
        ]

        steps: list[StepMetrics] = []
        solution, success, error = "", False, None

        for step in range(1, self.max_iterations + 1):
            error = self._limit_error(steps, start)
            if error:
                break
            if not self.sandbox.is_ok:
                error = self.sandbox.get_error()
                break
            try:
                result = self.provider.generate(messages=self.messages)
            except Exception as e:
                error = f"LLM error: {type(e).__name__}: {e}"
                break

            extracted_code, thought = extract_code(result.text)
            if self.logs and extracted_code: print("\t\t" + thought + "\n")

            if extracted_code is None:
                observation = Prompts.no_python_code_found()
            else:
                try:
                    observation = self.sandbox.exec_code(extracted_code)
                except Exception as e:
                    observation = f"Error: {type(e).__name__}: {e}"
                finally:
                    steps.append(self._metrics(step, result, extracted_code, observation))

            code_block = f"```python\n{extracted_code}\n```" if extracted_code else ""
            self.messages.append({"role": "assistant", "content": f"Thought: {thought}\n{code_block}"})
            self.messages.append({"role": "user", "content": Prompts.observation(observation)})

            if self.sandbox.final_answer_called:
                solution = self.sandbox.final_answer_value
                success = True
                break
        else:
            error = "Max iterations reached without final_answer."
        if self.logs and error: print(error)
        return self._build_output(task_id, benchmark, success, solution, steps, start, error)
