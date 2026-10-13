from models import SandboxConfig
import json
import ast


def configurate_sandbox(config_file: str | None,
                        sbx_config: SandboxConfig) -> None:
    if config_file != None:
        with open(config_file, "r") as fd:
            content = json.load(fd)
        sbx_config.set_authorized_imports(
            content[0]["authorized_imports"]
        )
        sbx_config.set_authorized_directories(
            content[0]["allowed_directories"]
        )
        sbx_config.set_max_execution_time(
            content[0]["max_execution_time_seconds"]
        )
        sbx_config.set_max_memory_mb(
            content[0]["max_memory_mb"]
        )
