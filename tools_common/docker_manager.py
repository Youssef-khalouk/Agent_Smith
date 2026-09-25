# This file has exactly one job: manage the lifecycle of the chamber.
import docker
import uuid
import queue
import threading
import shlex  # library used to safely quote strings for Unix command lines.
# The Docker SDK is an official library (available primarily for Python and Go)
# that allows developers to interact with Docker engines and manage Docker
# resources directly through code,
# rather than running CLI commands like docker run or docker ps in a terminal.


class ContainerManager:
    # docker client lets Python gives Docker orders(commands)
    # ContainerManager -> Docker client -> Docker daemon
    def __init__(self, image_name, host_mount_path):
        self.image_name = image_name
        self.host_mount_path = host_mount_path
        # store running container made by start() to be usd by exec() later
        self.container = None
        # If no custom environment variables are found, it automatically
        # connects to the default local Docker Unix socket
        # /var/run/docker.sock
        self.client = docker.from_env()
        # gotta catch Docker daemon is not connected

    def __enter__(self):
        # gets assigned to the variable after the as keyword in a with
        # statement.
        return self
    # these methods turn the class into python context manager

    def __exit__(self, exc_type, exc_value, traceback):
        self.die()  # Automatically executes when leaving the with block
        # (whether the code inside finishes normally or crashes with
        # an exception).

    # pull happens at agent startup, the moment the task JSON is read.
    # Not lazily at first tool call

    def pull(self):
        exists = False
        images = self.client.images.list()
        for image in images:
            for tag in image.tags:
                if not self.image_name == tag:
                    continue
                else:
                    exists = True
        if exists is False:
            try:
                self.client.images.pull(self.image_name)
            except docker.errors.ImageNotFound:
                return (f"Error: Image '{self.image_name}' does "
                        f"not exist on the registry.")
            except docker.errors.APIError:
                return (f"Error: Invalid Docker image "
                        f"reference '{self.image_name}'.")
        return "method completed successfully"

    def start(self):
        try:
            container = self.client.containers.run(
                image=self.image_name,
                # Generates a Universally Unique Identifier (version 4)
                # based on random numbers, Converts the UUID into a raw
                # 32-character hexadecimal string
                name=f"agent-smith-{uuid.uuid4().hex[:8]}",
                command="sleep infinity",
                detach=True,
                volumes={
                    # "/home/ouchouir/agent"
                    self.host_mount_path: {
                        "bind": "/testbed"
                    }
                },
                working_dir="/testbed"
            )
        except docker.errors.ImageNotFound:
            return (f"Error: Image '{self.image_name}' does "
                    f"not exist on the registry.")
        except docker.errors.DockerException:
            return ("Error: Docker daemon is not running or socket "
                    "is unreachable.")
        except docker.errors.APIError as e:
            # HTTP 409 Conflict occurs when a container with that name
            # already exists
            if e.status_code == 409 or "Conflict" in str(e):
                return ("Error: A container with this name "
                        "already exists.")
            else:
                return e
        self.container = container
        return container

    def exec(self, command, timeout=60):
        # he whole purpose of exec() is to take the command inside the tool
        # run_command, intercept it everytime and run it inside the container
        if self.container is None:
            return "no running containers at the moment"
        self.container.reload()
        # reload checks the status of the container NOW since the status
        # get cached from the moment it got created and python does not update
        # its status if something went wrong
        if self.container.status != "running":
            return (f"Container is not running "
                    f"(status: {self.container.status})")
        # Thread-safe FIFO queue implementation using queue.Queue.
        # Handles internal mutex locking and thread synchronization
        # to prevent race conditions.
        result_queue = queue.Queue()
        # Wrap in GNU 'timeout' so stuck commands get killed inside
        # the container and return exit code 124 instead of hanging.
        wrapped_command = (f"timeout --foreground {timeout}s "
                           f"bash -c {shlex.quote(command)}")
        final_command = ["/bin/bash", "-c", wrapped_command]
        # This function runs inside the child thread

        def worker(comm, q):
            try:
                # exec_run returns a ExecResult tuple/object
                # containing (exit_code, output)
                exec_result = self.container.exec_run(
                    cmd=comm,
                    workdir="/testbed",
                    # forces exec_run() to return a 2-tuple for output
                    # instead: (stdout_bytes, stderr_bytes).
                    demux=True
                )
                q.put(exec_result)
            except Exception as e:
                q.put(e)
        # Instantiate the thread
        thread = threading.Thread(
            target=worker,
            args=(final_command, result_queue)
        )
        # Mark as a daemon thread to prevent process hanging.
        # If exec() times out or the main program finishes,
        # Python can exit immediately without waiting for this
        # background execution thread to complete
        thread.daemon = True
        thread.start()
        # makes the MAIN thread pause and wait for the CHILD thread to finish,
        # but for a maximum of timeout seconds + buffer.
        # It does NOT forcibly stop or kill the child thread when the
        # 60-second timer runs out.
        # !! The child thread continues running container.exec_run(...) in the
        # background. However, because you set thread.daemon = True, Python
        # will automatically abandon that stuck child thread later when your
        # whole script finishes.
        thread.join(timeout=timeout + 2)
        if thread.is_alive():
            # then the command is stuck
            timed_out = True
        else:
            # then the command finished, let's fetch the resutls
            timed_out = False
        if timed_out is True:
            stdout = ""
            stderr = ""
            # container returns 124 so the code knows it timed out
            exit_code = 124
        else:
            # exec_run() returns an ExecResult named tuple object,
            # which has properties .exit_code and .output.
            try:
                # !! TRANSER RESULT FROM WORKER THREAD TO MAIN THREAD !!
                exec_result = result_queue.get_nowait()
                if isinstance(exec_result, Exception):
                    # because of except above (q.put(e))
                    stdout = f"Error during execution: {exec_result}"
                    stderr = ""
                    exit_code = 1
                else:
                    stdout_bytes, stderr_bytes = exec_result.output
                    stdout = (stdout_bytes.decode(
                        "utf-8", errors="replace") if stdout_bytes else "")
                    stderr = (stderr_bytes.decode(
                        "utf-8", errors="replace") if stderr_bytes else "")
                    exit_code = exec_result.exit_code
                    if exit_code == 124:
                        timed_out = True
            except queue.Empty:
                stdout = ""
                stderr = ""
                exit_code = 124
                timed_out = True
        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "timed_out": timed_out
        }

    def die(self):
        if self.container is None:
            return
        self.container.remove(force=True)
        self.container = None


# manager = ContainerManager("swebench/sweb.eval.x86_64.sympy_1776_sympy-14711", "/home/ouchouir/agent")
# print("\n")
# print(manager.pull())
# print("\n")
# container = manager.start()
# print()
# print(manager.exec("echo 'hello from container'"))
# print()
# print(manager.exec("ls /non_existent_directory_123"))
# print()
# print(manager.exec(
#     "mkdir -p /tmp/subshell_test && cd /tmp/subshell_test && pwd"))
# print()
# print(manager.exec("sleep 10", timeout=2))
# manager.die()
# with manager:
#     manager.start()
# #     # raise ValueError("CRASH!")
#     print("Inside the block: Container is running and ready!")
# manager.die()
