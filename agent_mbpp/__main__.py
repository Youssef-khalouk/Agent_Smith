import logging
logging.basicConfig(level=logging.WARNING)

from models import MBPPTaskInput, SolutionOutput, DockerImage
from pathlib import Path
from orchestrator import Agent
import os
from dotenv import load_dotenv
import argparse
from sandbox import SandBox, McpClient
from orchestrator import LLMProvider


load_dotenv()


def parse_arguments():
    parser = argparse.ArgumentParser()

    parser.add_argument("--task-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-name", required=True, help="Model id.")
    parser.add_argument("--provider-url", required=True, help="API base URL.")
    parser.add_argument("--mcp-stdio", default=None, help="MCP server command over stdio (default: local http).")
    parser.add_argument("--mcp-http", default=None, help="MCP server command over http.")
    parser.add_argument("--sandbox-config", default=None)
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()
    return args


def print_conversation(messages):
    content = ""
    this = "====================================="
    for d in messages:
        content += f"{this}[{d.get('role', 'None')}]{this}"
        content += f"\n{d.get('content', 'None')}\n\n\n\n\n"
    with open("messages.txt", "w") as file:
        file.write(content)


def verify_file(file_path: str) -> None:
    path: Path = Path(file_path)
    if not path.exists(): raise Exception(f"Error: file '{path}' not found.")
    if not path.is_file(): raise Exception(f"Error: file '{path}' is not a file.")


def agent_mbpp():
    try:
        args = parse_arguments()

        verify_file(args.task_file)

        api_keys = str(os.getenv("OPENROUTER_API_KEYS")).split(",")
        if not api_keys: raise Exception("No api keys provided in .env")

        with open(args.task_file, "r") as file:
            mbpp_task = MBPPTaskInput.model_validate_json(file.read())

        provider = LLMProvider(api_url=args.provider_url, 
                               model_name=args.model_name,
                               api_keys=api_keys,
                               logs=args.verbose)

        mcp_client = McpClient(args=args)
        if not mcp_client.is_ok: raise Exception(mcp_client.error)

        sandbox = SandBox(mcp_client=mcp_client,
                          config_file=args.sandbox_config,
                          logs=args.verbose)

        agent = Agent(  provider=provider,
                        sandbox=sandbox,
                        max_iterations=10,
                        max_input_tokens=6000,
                        max_output_tokens=1500,
                        timeout_seconds=120,
                        logs=args.verbose)

        solution: SolutionOutput = agent.run(mbpp_task)

        output_path = Path(args.output)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as file:
            file.write(solution.model_dump_json(indent=4))
        
        if args.verbose: print_conversation(agent.messages)

        print("Done.")

    except Exception as e:
        print(f"Error: {e}")
        exit(1)

    except KeyboardInterrupt as e:
        print("ctrl + c detected.")
        exit(1)
    
    finally:
        try:
            mcp_client.close()
            sandbox.close()
        except Exception:
            pass


if __name__ == "__main__":
    agent_mbpp()