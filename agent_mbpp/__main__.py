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
    """
    Parse and return command-line arguments for the MBPP agent.

    Configure arguments for the task input file, output file, language model,
    provider API endpoint, MCP connection, sandbox configuration, and verbose
    logging.

    Returns:
        argparse.Namespace: Parsed command-line arguments.
    """
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
    """
    Write the agent's conversation history to a text file.

    Format each message with its role and content, then save the complete
    conversation to messages.txt in the current working directory.

    Args:
        messages: Sequence of conversation messages containing role and content
            fields.

    Returns:
        None
    """
    content = ""
    this = "====================================="
    for d in messages:
        content += f"{this}[{d.get('role', 'None')}]{this}"
        content += f"\n{d.get('content', 'None')}\n\n\n\n\n"
    with open("messages.txt", "w") as file:
        file.write(content)


def verify_file(file_path: str) -> None:
    """
    Validate that the specified path exists and refers to a regular file.

    Args:
        file_path (str): Path to the file to validate.

    Raises:
        Exception: If the path does not exist or does not refer to a file.

    Returns:
        None
    """
    path: Path = Path(file_path)
    if not path.exists(): raise Exception(f"Error: file '{path}' not found.")
    if not path.is_file(): raise Exception(f"Error: file '{path}' is not a file.")


def agent_mbpp():
    """
    Run the MBPP code-generation agent and save its solution.

    Parse command-line arguments, validate and load the MBPP task, initialize
    the language model provider, MCP client, sandbox, and agent, then execute
    the task. Save the resulting solution as formatted JSON and optionally
    write the conversation history when verbose logging is enabled.

    Print an error message and exit with a nonzero status if execution fails.
    Attempt to close the MCP client and sandbox during cleanup.

    Returns:
        None
    """
    try:
        args = parse_arguments()

        verify_file(args.task_file)

        api_keys = str(os.getenv("OPENROUTER_API_KEYS", "")).split(",")

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