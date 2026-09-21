class Executor(BaseModel):
    allowed_directories: list[str] = ["/testbed", "/tmp/agent"]
    # system paths needed just to make python3 runnable — read-only
    system_directories: list[str] = ["/usr", "/lib", "/lib64", "/bin", "/home/reda/.local/share/uv"]
    root: str = "/tmp/sbx_root_dir"

    def exec(self):
        # unshare(CLONE_NEWUSER | CLONE_NEWNS)
        # map_root_user()
        subprocess.run(["mount", "--make-rprivate", "/"], check=True)

        os.makedirs(self.root, exist_ok=True)

        # system deps: read-only bind mounts
        for d in self.system_directories:
            if not os.path.isdir(d):
                continue
            target = os.path.join(self.root, d.lstrip("/"))
            os.makedirs(target, exist_ok=True)
            subprocess.run  (["mount", "--bind", d, target], check=True)
            subprocess.run(["mount", "-o", "remount,bind,ro", target], check=True)

        # sandbox work dirs: writable
        for d in self.allowed_directories:
            target = os.path.join(self.root, d.lstrip("/"))
            os.makedirs(target, exist_ok=True)
            subprocess.run(["mount", "--bind", d, target], check=True)

        proc_target = os.path.join(self.root, "proc")
        os.makedirs(proc_target, exist_ok=True)
        subprocess.run(["mount", "-t", "proc", "proc", proc_target], check=True)

        os.chroot(self.root)
        os.chdir("/")

        with open("log.txt", "w") as fd:
            os.dup2(fd.fileno(), 1)
            os.dup2(fd.fileno(), 2)

        python_path = "/home/reda/.local/share/uv/python/cpython-3.13.14-linux-x86_64-gnu/bin/python3"
        os.execv(python_path, [python_path, "mcp_client.py"])