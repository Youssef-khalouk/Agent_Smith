import builtins
from models import SandboxConfig
from typing import Dict
from pydantic import BaseModel
import fire


SBX: SandboxConfig = SandboxConfig()


def safe_open(file, flag):
    real_open = builtins.open
    path = os.path.abspath(os.fspath(file))
    for direct in SBX.allowed_directories:
        if direct in path:
            return (real_open(file, flag))
    raise ValueError("Access denied")


def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    real_import = builtins.__import__
    sbx: SandboxConfig = SandboxConfig()
    root = name.split(".")[0]
    if root not in SBX.authorized_imports:
        raise ValueError("Import not allowed")
    return (real_import(name, globals=None, locals=None, fromlist=(), level=0))


def final_answer(value: str) -> str:
    print ("__FINAL_ANSWER__SANDBOX__\n" + value)
    exit()

def exec_code(code: str) -> str:
    allowed_builtins: Dict[str, str] = {
        "print": builtins.print,
        "len": builtins.print,
        "range": builtins.range,
        "open": safe_open,
        "final_answer": final_answer,
        "__import__": safe_import
    }
    exec(code, {"__builtins__": allowed_builtins})

def main() -> None:
    fire.Fire({
        "exec": exec_code
    })


if __name__ == "__main__":
    main()
