import subprocess
import os
from pydantic import BaseModel

class Executor(BaseModel):
    def exec(self):
        os.makedirs("/tmp/sbx_root_dir/", exist_ok=True)
        os.makedirs("/tmp/sbx_root_dir/testbed/", exist_ok=True)
        os.makedirs("/tmp/sbx_root_dir/tmp_agent/", exist_ok=True)
        os.makedirs("/tmp/sbx_root_dir/proc", exist_ok=True)
        subprocess.run(
            ["mount", "--make-rprivate", "/"],
            check=True
        )
        subprocess.run(
            ["mount", "--bind", "./testbed", "/tmp/sbx_root_dir/testbed"],
            check=True
        )
        subprocess.run(
            ["mount", "--bind", "./tmp/agent", "/tmp/sbx_root_dir/tmp_agent"],
            check=True
        )
        # subprocess.run(
        #     ["mount", "-t", "proc", "proc", "/tmp/sbx_root_dir/proc"],
        #     check=True
        # )
        os.chroot("/tmp/sbx_root_dir/")

        # We must also change the current directory.
        os.chdir("/")
        print("New root:", os.getcwd())
        print("testbed exists:", os.path.exists("/testbed"))
        print("agent exists:", os.path.exists("/tmp/agent"))
        print(
            "Desktop exists:",
            os.path.exists("/home/reda/Desktop")
        )
        with open("log.txt", "w") as fd:
            subprocess.run(
                ["python3", "mcp_client.py"],
                check=True,
                stdout=fd,
                stderr=fd,
                text=True
            )

def main():
    ex = Executor()
    ex.exec()

if __name__ == "__main__":
    main()

    