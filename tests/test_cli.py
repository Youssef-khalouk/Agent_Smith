import json
import os
import subprocess
import tempfile
from pathlib import Path
from models.models import SWEBenchTaskInput


class FakeCrashingAgent:
    """Mock agent used to simulate runtime crashes during testing."""
    def __init__(self, **kwargs):
        pass

    def run(self, task):
        raise RuntimeError("simulated crash")


def write_fake_task(folder: Path) -> Path:
    task = SWEBenchTaskInput(
        instance_id="test_instance_123",
        problem_statement="fix bug",
        docker_image="alpine:latest",  # Small image for fast pulling
        eval_script="echo ok",
        hints_text="",
        repo="sympy/sympy"
    )
    task_file = folder / "task.json"
    task_file.write_text(task.model_dump_json(indent=4))
    return task_file


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        task_file = write_fake_task(tmp_path)
        output_file = tmp_path / "out" / "solution.json"

        # Prepare environment with the injected FakeCrashingAgent
        env = os.environ.copy()
        # Set module.Class path pointing to FakeCrashingAgent
        # (Assuming this test script is named test_crash_path.py)
        env["AGENT_SWEBENCH_AGENT_CLASS"] = f"tests.test_cli.FakeCrashingAgent"

        result = subprocess.run(
            [
                "uv", "run", "python", "-m", "agent_swebench",
                "--task-file", str(task_file),
                "--output", str(output_file),
                "--model-name", "fake/model",
                "--provider-url", "http://localhost:1",
            ],
            capture_output=True,
            text=True,
            env=env,
        )

        assert output_file.exists(), (
            f"CRASH PATH FAILED: no solution.json generated after crash.\n"
            f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )

        data = json.loads(output_file.read_text())
        assert data["success"] is False
        print("ACTUAL ERROR IN JSON:", repr(data["error"]))
        assert data["error"] == "simulated crash"
        assert data["benchmark"] == "swebench"
        assert data["task_id"] == "test_instance_123"

        print("CRASH PATH GREEN — the armor works.")


if __name__ == "__main__":
    main()
    #  uv run python3 -m tests.test_cli