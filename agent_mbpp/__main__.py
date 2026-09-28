import fire
from models import MBPPTaskInput, SolutionOutput
from pathlib import Path
from orchestrator import Agent
import os
from dotenv import load_dotenv


load_dotenv()


def verify_file(file_path: str) -> None:
    path: Path = Path(file_path)
    if not path.exists():
        print(f"Error: file '{path}' not found.")
        exit(1)
    if not path.is_file():
        print(f"Error: file '{path}' is not a file.")
        exit(1)

def agent_mbpp(task_file: str, output: str, model_name: str, provider_url: str):
    verify_file(task_file)

    with open(task_file, "r") as file:
        try:
            mbpp_task = MBPPTaskInput.model_validate_json(file.read())
        except Exception as error:
            print(f"Error: {error}")
            exit(1)

    api_keys = str(os.getenv("OPENROUTER_API_KEYS")).split(",")
    
    agent = Agent(api_url=provider_url, model_name=model_name, api_keys=api_keys)
    solution: SolutionOutput = agent.run(mbpp_task)
    

    output_path = Path(output)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as file:
        file.write(solution.model_dump_json(indent=4))


if __name__ == "__main__":
    fire.Fire(agent_mbpp)