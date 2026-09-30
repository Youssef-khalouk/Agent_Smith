import logging
logging.basicConfig(level=logging.WARNING)

import fire
from models import SWEBenchTaskInput, SolutionOutput, DockerImage
from pathlib import Path
from orchestrator import Agent
import os
from dotenv import load_dotenv


load_dotenv()

def print_conversation(messages):
    content = ""
    for d in messages:
        for k, v in d.items():
            content += f"=====================[{k}]==================\n{v}\n\n\n\n\n"
    with open("messages.txt", "w") as file:
        file.write(content)


def verify_file(file_path: str) -> None:
    path: Path = Path(file_path)
    if not path.exists():
        raise Exception(f"Error: file '{path}' not found.")
    if not path.is_file():
        raise Exception(f"Error: file '{path}' is not a file.")

def agent_swe_bench(task_file: str, output: str, model_name: str, provider_url: str):
    try:
        verify_file(task_file)

        with open(task_file, "r") as file:
            swe_bench_task = SWEBenchTaskInput.model_validate_json(file.read())

        api_keys = str(os.getenv("OPENROUTER_API_KEYS")).split(",")
        
        agent = Agent(  api_url=provider_url,
                        model_name=model_name,
                        api_keys=api_keys,
                        max_iterations=30,
                        max_input_tokens=300000,
                        max_output_tokens=10000,
                        timeout_seconds=900)

        agent.set_docker_image(DockerImage(
                        instance_id=swe_bench_task.instance_id,
                        docker_image=swe_bench_task.docker_image,
                        eval_script=swe_bench_task.eval_script,
                        repo=swe_bench_task.repo))

        solution: SolutionOutput = agent.run(swe_bench_task)

        output_path = Path(output)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as file:
            file.write(solution.model_dump_json(indent=4))
        
        print_conversation(agent.messages) # this is for debugg stuf remove later.

    except Exception as e:
        print(f"Error: {e}")
        exit(1)


if __name__ == "__main__":
    fire.Fire(agent_swe_bench)