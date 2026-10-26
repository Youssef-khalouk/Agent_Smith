# This file has exactly one job: manage the lifecycle of the chamber.
import subprocess
import docker  # type: ignore[import-untyped]
import uuid
import shutil
from pathlib import Path
import queue
import threading
import shlex  # library used to safely quote strings for Unix command lines.
# The Docker SDK is an official library (available primarily for Python and Go)
# that allows developers to interact with Docker engines and manage Docker
# resources directly through code,
# rather than running CLI commands like docker run or docker ps in a terminal.


class ContainerManager:
    """Manage Docker images and containers for executing commands in an
    isolated workspace."""
    # docker client lets Python gives Docker orders(commands)
    # ContainerManager -> Docker client -> Docker daemon
    def __init__(self, image_name, host_mount_path):
        """Initialize the Docker client and configure the image and host
        mount path."""
        self.image_name = image_name
        self.host_mount_path = Path(host_mount_path).resolve()
        # store running container made by start() to be usd by exec() later
        self.container = None
        # If no custom environment variables are found, it automatically
        # connects to the default local Docker Unix socket
        # /var/run/docker.sock
        self.client = docker.from_env()
        # gotta catch Docker daemon is not connected

    def __enter__(self):
        """Return the manager for use in a with statement."""
        # gets assigned to the variable after the as keyword in a with
        # statement.
        return self
    # these methods turn the class into python context manager

    def __exit__(self, exc_type, exc_value, traceback):
        """Remove the managed container when leaving a with statement."""
        self.die()  # Automatically executes when leaving the with block
        # (whether the code inside finishes normally or crashes with
        # an exception).

    # pull happens at agent startup, the moment the task JSON is read.
    # Not lazily at first tool call

    def pull(self):
        """Pull the Docker image if it is not already available locally."""
        exists = False
        images = self.client.images.list()
        for image in images:
            for tag in image.tags:
                if not self.image_name == tag:
                    continue
                else:
                    exists = True
        if exists is False:
            self.client.images.pull(self.image_name)
        return

    def start(self):
        """Create and start a Docker container with the workspace mounted
        at /testbed."""
        if self.container is not None:
            self.container.reload()
            if self.container.status == "running":
                return
        for con in self.client.containers.list(all=True):
            if con.name.startswith("agent-smith-"):
                con.remove(force=True)
                self.container = None
        container = self.client.containers.run(
            image=self.image_name,
            # Generates a Universally Unique Identifier (version 4)
            # based on random numbers, Converts the UUID into a raw
            # 32-character hexadecimal string
            name=f"agent-smith-{uuid.uuid4().hex[:8]}",
            command="sleep infinity",
            detach=True,
            volumes={
                # "e.g. /home/ouchouir/agent"
                self.host_mount_path: {
                    "bind": "/testbed"
                }
            },
            working_dir="/testbed"
        )
        self.container = container
        # git refuses to run git commands inside container as root because the
        # host user is not root
        # Tell Git inside container to trust /testbed directory
        # Fixes 'fatal: detected dubious ownership in repository' error
        exec_res = container.exec_run(
            "git config --global --add safe.directory /testbed")
        if exec_res.exit_code != 0:
            raise RuntimeError(f"Failed to configure git safe.directory: "
                               f"{exec_res.output.decode('utf-8')}")
        self.container.reload()
        return container

    def exec(self, command, work_dir, timeout=60):
        """Execute a command inside the running container and return its
        output, exit code, and timeout status."""
        # the whole purpose of exec() is to take the command inside the tool
        # run_command, intercepts it everytime and runs it inside the container
        if self.container is None:
            raise RuntimeError(
                "Cannot execute command: No container attached to manager.")
        if work_dir == "." or not work_dir:
            work_dir = "/testbed"
        elif not work_dir.startswith("/"):
            # "e.g. src/utils or tests"
            work_dir = f"/testbed/{work_dir}"
        else:
            work_dir = work_dir
        self.container.reload()
        # reload checks the status of the container NOW since the status
        # get cached from the moment it got created and python does not update
        # its status if something went wrong
        if self.container.status != "running":
            raise RuntimeError(f"Cannot execute command: Container status "
                               f"is '{self.container.status}'.")
        # Thread-safe FIFO queue implementation using queue.Queue.
        # Handles internal mutex locking and thread synchronization
        # to prevent race conditions.
        # The worker thread puts its result inside, and the main thread
        # reads it later.
        result_queue = queue.Queue()
        # -c: Take the following text and execute it as a terminal command
        # bash: tell Bash to execute the requested command ('python main.py')
        # shlex: turns "echo hello world" into 'echo hello world' so
        # command gets treated as one argument, rather than splitting it
        # into multiple arguments.
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
                    workdir=work_dir,
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
        # background. However, because i set thread.daemon = True, Python
        # will automatically abandon that stuck child thread later when the
        # whole script finishes.
        thread.join(timeout=timeout + 2)
        if thread.is_alive():
            # then the command is stuck
            timed_out = True
        else:
            # then the command finished, let's fetch the resutls
            timed_out = False
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
                    # GNU timeout kills the process at T=timeout
                    # (exit code 124). Because host
                    # join() has a +2s buffer, thread.is_alive() stays
                    # False and tricks the main
                    # thread into thinking it finished normally.
                    timed_out = True
                else:
                    timed_out = False
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
        """Forcefully remove the managed container and clear its reference."""
        if self.container is None:
            return
        try:
            self.container.remove(force=True)
        except docker.errors.NotFound:
            # Container was auto-removed (--rm) or already stopped/deleted
            pass
        finally:
            self.container = None

    def extract(self):
        """Extract the image's /testbed contents to the host mount path
        when the container is not running."""
        if self.container is not None:
            self.container.reload()
            if self.container.status == "running":
                return  # mid-task call: do nothing, mount is in use
        if self.host_mount_path.exists():
            # delete a directory and everything inside it
            shutil.rmtree(self.host_mount_path, ignore_errors=True)
        stage_dir = (
            self.host_mount_path.parent / f"tmp_{self.host_mount_path.name}")
        if stage_dir.exists():
            shutil.rmtree(stage_dir)
        blueprint = self.client.containers.create(image=self.image_name)
        try:
            try:
                # use subprocess to run terminal commands from inside a
                # Python script.
                subprocess.run(
                    ["docker", "cp", f"{blueprint.id}:/testbed/.",
                     stage_dir],
                    # check makes sure python crashes if upper command fails
                    check=True,
                    capture_output=True
                )
            finally:
                blueprint.remove(force=True)
            # Success! Move temporary folder to real destination
            stage_dir.rename(self.host_mount_path)
        except subprocess.CalledProcessError as err:
            # Cleanup broken download in stage_dir
            if stage_dir.exists():
                shutil.rmtree(stage_dir)
            stderr_text = err.stderr.decode() if err.stderr else str(err)
            raise RuntimeError(
                f"Docker extraction failed: {stderr_text}") from err
