import fire
import shutil
from models import SWEBenchTaskInput, SolutionOutput
from pathlib import Path
from orchestrator import Agent
from datetime import datetime
import tempfile
import time
import docker
import importlib
import os
from dotenv import load_dotenv
from tools_common.docker_manager import ContainerManager


load_dotenv()


def verify_file(file_path: str) -> None:
    path: Path = Path(file_path)
    if not path.exists():
        print(f"Error: file '{path}' not found.")
        exit(1)
    if not path.is_file():
        print(f"Error: file '{path}' is not a file.")
        exit(1)


def agent_swe_bench(task_file: str, output: str, model_name: str, provider_url: str):
    verify_file(task_file)
    with open(task_file, "r") as file:
        try:
            swe_bench_task = SWEBenchTaskInput.model_validate_json(file.read())
        except Exception as error:
            print(f"Error: {error}")
            exit(1)

    api_keys = str(os.getenv("OPENROUTER_API_KEYS")).split(",")

    os.environ["SWEBENCH_IMAGE"] = swe_bench_task.docker_image
    os.environ["SWEBENCH_EVAL_SCRIPT"] = swe_bench_task.eval_script
    os.environ["SWEBENCH_MOUNT"] = f"/tmp/testbed_{swe_bench_task.instance_id}"

    # 3. Create the per-task mount directory on host
    mount_dir = Path(os.environ["SWEBENCH_MOUNT"])
    mount_dir.mkdir(parents=True, exist_ok=True)

   
   

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    task_start_time = time.time()
    solution = None
    try:
        # ---------------------------------------------------------------------
        # agent_class = Agent                       # the default: C's real one
        # fake_path = os.environ.get("AGENT_SWEBENCH_AGENT_CLASS")
        # if fake_path:
        #     module, cls = fake_path.rsplit(".", 1)
        #     agent_class = getattr(importlib.import_module(module), cls)
        # agent = agent_class(api_url=provider_url,
        #                     model_name=model_name,
        #                     api_keys=api_keys,
        #                     max_iterations=30,
        #                     max_input_tokens=300000,
        #                     max_output_tokens=10000,
        #                     timeout_seconds=900)
        # ---------------------------------------------------------------------
        agent = Agent(  api_url=provider_url,
                        model_name=model_name,
                        api_keys=api_keys,
                        max_iterations=30,
                        max_input_tokens=300000,
                        max_output_tokens=10000,
                        timeout_seconds=900)

        solution: SolutionOutput = agent.run(swe_bench_task)
    except Exception as err:
        elapsed = time.time() - task_start_time
        solution = failure_output(swe_bench_task, err, elapsed)
    finally:
        try:
            write_solution_atomically(output_path, solution)
        except Exception as write_error:
            # make an error file next to the output.
            error_path = output_path.with_suffix(".error.txt")
            error_path.write_text(
                f"agent crashed AND output write failed:\n"
                f"{write_error}\n"
                f"original error: {solution.error if solution else 'unknown'}")
        try:
            sweep_agent_smith_containers()
        except Exception as sweep_error:
            print(f"WARNING: container sweep failed: {sweep_error}")
        try:
            shutil.rmtree(os.environ["SWEBENCH_MOUNT"], ignore_errors=True)
        except Exception:
            pass


def write_solution_atomically(output_path, solution):
    parent_folder = Path(output_path).parent
    fd, temp_path = tempfile.mkstemp(dir=parent_folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
            temp_file.write(solution.model_dump_json(indent=4))
            temp_file.flush()
            os.fsync(temp_file.fileno())
        temp_file_path = Path(temp_path)
        temp_file_path.replace(output_path)
    except Exception:
        Path(temp_path).unlink(missing_ok=True)
        raise


def failure_output(task, error, elapsed_seconds):
    return SolutionOutput(
        task_id=task.instance_id,
        benchmark="swebench",
        success=False,
        solution="",
        iterations=0,
        total_requests=0,
        total_input_tokens=0,
        total_output_tokens=0,
        total_time_seconds=elapsed_seconds,
        steps=[],  # No completed iteration metrics
        system_prompt="",
        error=str(error),  # Captures the exception message or timeout reason
        timestamp=datetime.now().isoformat()

    )


def sweep_agent_smith_containers():
    client = docker.from_env()
    for con in client.containers.list(all=True):
        if con.name.startswith("agent-smith-"):
            con.remove(force=True)



if __name__ == "__main__":
    fire.Fire(agent_swe_bench)
