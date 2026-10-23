from mcp.server.mcpserver import MCPServer
import threading
import asyncio
import time
import shutil
import signal
from contextlib import asynccontextmanager
from starlette.applications import Starlette
from starlette.routing import Route
# Route connects a URL path to a function
from starlette.responses import JSONResponse
# uvicorn — the engine that actually serves a Starlette app
import uvicorn
import os
import sys
import docker
from tools_common.workspace import DockerWorkspace, LocalWorkspace
from tools_common.filesystem import (
    read_file as read_file_impl,
    edit_file as edit_file_impl,
    list_files as list_files_impl,
)
from tools_common.execution import (
    run_command as run_command_impl,
    get_patch as get_patch_impl,
)
from tools_common.code_search import (
    search_code as search_code_impl,
    search_function_or_class_definition_in_code as def_search_impl,
    find_references as find_references_impl,
)
MAX_CHARACTERS = 3000
watch = False
MCP = MCPServer("MCP-SERVER")
last_activity_time = time.time()
activity_lock = threading.Lock()
client = docker.from_env()


def note_activity() -> None:
    """Poke the heartbeat timestamp on any agent action."""
    # global means im using the global variable, do not create a new one
    global last_activity_time
    with activity_lock:
        last_activity_time = time.time()


def watchman_loop() -> None:
    while server_state.snapshot()["state"] == "ready":
        time.sleep(30.0)
        if server_state.snapshot()["state"] != "ready":
            break
        with activity_lock:
            silence = time.time() - last_activity_time
        if silence > 900.0:
            stop_event.set()
            break


def start_watchman() -> None:
    note_activity()
    threading.Thread(
        target=watchman_loop, name="activity_watchman", daemon=True
    ).start()


class WorkspaceHolder:
    def __init__(self):
        # no eval_script nor workspace at birth
        self.workspace = None
        self.eval_script = None
        self.task_context = None


class ServerState():
    def __init__(self):
        # moods: "unconfigured", "preparing", "ready", "failed"
        self.state = "unconfigured"
        # progress text — "pulling image", "extracting repo"
        self.detail = ""
        # the failure reason, if failed
        self.error = None
        self.lock = threading.Lock()

    def set(self, state, detail="", error: str | None = None):
        """
        Update the server state, detail, and optional error message.
        """
        # only ONE thread can run this block at a time
        with self.lock:
            self.state = state
            self.detail = detail
            if state == "failed" or error is not None:
                self.error = error

    def snapshot(self):
        with self.lock:
            return {
                "state": self.state,
                "detail": self.detail,
                "error": self.error
            }


holder = WorkspaceHolder()
server_state = ServerState()


def create_bound_tools(holder: WorkspaceHolder) -> list:

    @MCP.tool()
    def read_file(filepath: str, start_line: int = 1,
                  end_line: int | None = None) -> str:
        """Read a file with line numbers (1-based, inclusive).

    Returns at most 200 lines per call. If truncated, reports the total
    line count and the next start_line.

    Always read a file before editing it.

    Args:
        filepath: Repository-relative path or absolute workspace path.
        start_line: First line to read (default: 1).
        end_line: Last line to read, or None for EOF (default: None).

    Returns:
        Numbered content, or an "Error:" message with the next tool to use.
    """
        note_activity()
        # Translate the schema-friendly None into the implementation's
        # -1 sentinel meaning "read to end of file".
        if holder.workspace is None:
            return ("Error: server is not configured yet. "
                    "Send POST /setup and wait for /ready to report 'ready'.")
        if end_line is None:
            end_line = -1
        return read_file_impl(holder.workspace, filepath, start_line, end_line)

    @MCP.tool()
    def edit_file(filepath: str, old_str: str, new_str: str) -> str:
        """Replace an exact string in a file.

    old_str must match the file content EXACTLY (read file first). If ambiguous 
    (multiple matches), it fails and reports lines; include surrounding context 
    to make it unique. Empty new_str deletes old_str.

    Args:
        filepath: Target file path.
        old_str: Exact string to replace (must be unique).
        new_str: Replacement string (empty to delete).

    Returns:
        Success message with edited line and context, or an error description.
    """
        note_activity()
        if holder.workspace is None:
            return ("Error: server is not configured yet. "
                    "Send POST /setup and wait for /ready to report 'ready'.")
        return edit_file_impl(holder.workspace, filepath, old_str, new_str)

    @MCP.tool()
    def list_files(directory: str = ".", pattern: str = "*",
                   offset: int = 0) -> str:
        """List files/directories matching a pattern (directories end with '/').

    Sorted, paginated (max 100/call; use offset for next page).

    Args:
        directory: Target directory, relative to repo root (default: ".").
        pattern: Glob pattern filter (default: "*").
        offset: Pagination offset to skip first N entries (default: 0).

    Returns:
        One entry per line with pagination hint, or an error message.
    """
        note_activity()
        if holder.workspace is None:
            return ("Error: server is not configured yet. "
                    "Send POST /setup and wait for /ready to report 'ready'.")
        return list_files_impl(holder.workspace, directory, pattern, offset)

    @MCP.tool()
    def run_command(command: str, workdir: str = ".") -> str:
        """Execute a shell command in the container.

    Non-zero exit codes are normal (check output for details like failed tests).
    Commands time out and preserve partial output.

    Args:
        command: Shell command (supports pipes, &&, redirects).
        workdir: Working directory relative to repo root (default: ".").

    Returns:
        Labeled stdout, stderr, and exit code, or a timeout report.
    """
        note_activity()
        if holder.workspace is None:
            return ("Error: server is not configured yet. "
                    "Send POST /setup and wait for /ready to report 'ready'.")
        return run_command_impl(holder.workspace, command, workdir)

    @MCP.tool()
    def get_patch() -> str:
        """Get the unified git diff of all changes made to the
        repository.

        This is the deliverable: call it after your edits and pass its
        exact output to final_answer(). Newly created files are
        included; file-permission-only changes are excluded.

        Returns:
            The unified diff of all current changes, or a warning
            message if no changes are detected (edit files before
            submitting).
        """
        note_activity()
        if holder.workspace is None:
            return ("Error: server is not configured yet. "
                    "Send POST /setup and wait for /ready to report 'ready'.")
        return get_patch_impl(holder.workspace)

    @MCP.tool()
    def search_code(pattern: str, file_pattern: str = "*.py",
                    offset: int = 0) -> str:
        """Grep-like regex search recursively across files matching file_pattern (skips hidden/binary).
    
    Args:
        pattern: Python regex pattern to search for.
        file_pattern: Glob filter for filenames (default: "*.py").
        offset: Pagination offset, number of matches to skip (max 100/call).
        
    Returns:
        Formatted lines ("path:line line_content") with total count, or error message.
    """
        note_activity()
        if holder.workspace is None:
            return ("Error: server is not configured yet. "
                    "Send POST /setup and wait for /ready to report 'ready'.")
        return search_code_impl(
            holder.workspace, pattern, file_pattern, offset)

    @MCP.tool()
    def search_function_or_class_definition_in_code(
                                    name: str, offset: int = 0) -> str:
        """Find exact definition of a function/class using AST (skips syntax errors).

    Output matches search_code format ("path:line line_content"), paginated.

    Args:
        name: Exact function or class name (e.g., "simplify").
        offset: Pagination offset to skip first N matches (default: 0).

    Returns:
        Definition lines found, or "no matches" message (suggesting search_code).
    """
        note_activity()
        if holder.workspace is None:
            return ("Error: server is not configured yet. "
                    "Send POST /setup and wait for /ready to report 'ready'.")
        return def_search_impl(
            workspace=holder.workspace, name=name, offset=offset)

    @MCP.tool()
    def find_references(
            name: str, filepath: str, line: int, offset: int = 0) -> str:
        """Find all whole-word USAGES of a symbol across the repository (excluding definition).

    Workflow: find definition first, then pass its filepath and line. 
    Output matches search_code format, paginated.

    Args:
        name: Function or class name to find.
        filepath: Path to the definition file.
        line: 1-based line number of the definition (excluded from results).
        offset: Pagination offset to skip first N matches (default: 0).

    Returns:
        All usage lines across the repository or an error message.
    """
        note_activity()
        if holder.workspace is None:
            return ("Error: server is not configured yet. "
                    "Send POST /setup and wait for /ready to report 'ready'.")
        return find_references_impl(
            holder.workspace, name, filepath, line, offset)

    @MCP.tool()
    def run_tests() -> str:
        """Run the official evaluation script for the current task
        inside the container.

        Executes the targeted test suite (FAIL_TO_PASS and PASS_TO_PASS tests).
        Execution runtime varies by task (from a few seconds to a few minutes).
        Use this frequently after making targeted edits to verify your changes.

        Note: Has a strict 600-second timeout to prevent runaway test processes
        while respecting the total 900-second task execution budget.

        Returns:
            The test run output, showing which tests pass or fail.
        """
        note_activity()
        if holder.workspace is None:
            return ("Error: server is not configured yet. "
                    "Send POST /setup and wait for /ready to report 'ready'.")
        if holder.eval_script is None:
            return ("Error: no eval script configured. "
                    "Send POST /setup and wait for /ready to report 'ready'.")
        test_results = holder.workspace.run_command_in_folder(
            command=holder.eval_script,
            folder_path=".",
            timeout=600
        )
        raw_stdout = test_results["stdout"] or ""
        raw_stderr = test_results["stderr"] or ""
        if len(raw_stdout) > MAX_CHARACTERS:
            stdout = raw_stdout[-MAX_CHARACTERS:]
        else:
            stdout = raw_stdout
        if len(raw_stderr) > MAX_CHARACTERS:
            stderr = raw_stderr[-MAX_CHARACTERS:]
        else:
            stderr = raw_stderr
        return (
            f"Command: [task evaluation script]\n"
            f"Exit Code: {test_results['exit_code']}\n"
            f"Timed Out: {test_results['timed_out']}\n\n"
            f"--- STDOUT ---\n{stdout}\n\n"
            f"--- STDERR ---\n{stderr}")
    return [
        read_file, edit_file, list_files,
        run_command, get_patch, search_code,
        search_function_or_class_definition_in_code,
        find_references, run_tests
        ]


@MCP.resource("task://setup")
def setup_docker_image() -> dict:
    try:
        docker_info = {
            "image_name": os.environ["DOCKER_IMAGE"],
            "eval_script": os.environ["EVAL_SCRIPT"],
            "problem": os.environ["PROBLEM_STATEMENT"],
            "instance_id": os.environ["INSTANCE_ID"],
            "mount_path": os.environ.get("SWEBENCH_MOUNT", f"/tmp/testbed_{os.environ['INSTANCE_ID']}"),
            "hints": os.environ.get("HINTS_TEXT", ""),
        }
        threading.Thread(
            target=prepare_workspace, args=(holder, server_state),
            kwargs=docker_info, daemon=True
        ).start()
        return {"state": "preparing", "error": ""}

    except KeyError as e:
        return {"state": "failed", "error": f"could not read environ {e.args[0]}."}
    except Exception as e:
        return {"state": "failed", "error": f"environ error: {e}."}


@MCP.resource("task://ready")
def is_docker_image_ready() -> dict:
    return server_state.snapshot()


@MCP.resource("task://context")
def task_context_resource() -> str:
    """The current task: problem statement,
    instance id, hints."""
    if holder.task_context is None:
        return ("no task configured yet")
    problem = holder.task_context["problem_statement"]
    instance_id = holder.task_context["instance_id"]
    hints = holder.task_context["hints"]
    return "\n".join([problem, instance_id, hints])


@MCP.prompt()
def fix_issue() -> str:
    """Prompt guiding the autonomous agent through repository bug fixes."""
    return (
        "You are an autonomous software engineer fixing a real bug in a real "
        "repository inside a container. Your goal: produce a correct, "
        "minimal patch and submit it via final_answer().\n\n"
        "First, understand the task. Read the resource task://context for the "
        "issue description, the instance id, and any hints. The problem "
        "statement is a real GitHub issue — read it completely before "
        "touching anything.\n\n"
        "Then, explore before you edit. Use "
        "search_function_or_class_definition_in_code to find where the "
        "relevant code is defined, then search_code and find_references to "
        "understand how it is used. Read files with read_file before editing "
        "them — the line numbers in its output are the ground truth. "
        "Never guess at file contents.\n\n"
        "Edit surgically. edit_file replaces an exact string: copy old_str "
        "EXACTLY from the file, including indentation — if it matches in "
        "multiple places the edit is refused and the line numbers are "
        "reported; add surrounding lines to make it unique. Make the smallest "
        "change that fixes the issue. Do not reformat, rename, or 'improve' "
        "unrelated code.\n\n"
        "Verify with the tests. run_tests executes the official test suite. "
        "It may take seconds or minutes — be patient, and do not call it "
        "repeatedly: make focused edits between runs. A non-zero exit code is "
        "normal output, not a tool failure — read it, it tells you which "
        "tests fail and why. If tests fail, use read_file and search_code "
        "on the failing test file to understand what is expected. The tests "
        "that must newly pass are the FAIL_TO_PASS set from the task "
        "context.\n\n"
        "Iterate efficiently. Outputs may be truncated with a hint showing "
        "how to continue (offset or start_line parameters). Error messages "
        "tell you what to do next — follow them. If you are stuck after "
        "several attempts, re-read the issue: the answer is often in a "
        "detail you skimmed.\n\n"
        "Submit the deliverable. When the tests pass, call get_patch() to "
        "retrieve the unified diff of all your changes — this patch IS the "
        "deliverable. Check it: it should contain exactly your intended edits "
        "and nothing else. Then call final_answer() with the patch as the "
        "argument. Never submit an empty patch."
    )


stop_event = threading.Event()
# Creates/initializes a new event object.
# light switch that multiple threads can look at, wait for, or flip.


def prepare_workspace(
        holder, state: ServerState, image_name, mount_path,
        eval_script, problem, instance_id, hints):
    try:
        # announce the mood before starting work.
        state.set("preparing", "pulling image")
        with DockerWorkspace(mount_path, image_name) as dws:
            # attaches the workspace to your holder object so
            # HTTP routes can use it.
            holder.workspace = dws
            holder.eval_script = eval_script
            holder.task_context = {
                "problem_statement": problem,
                "instance_id": instance_id,
                "hints": hints
            }
            state.set("ready")
            if watch is True:
                start_watchman()
            # his line freezes the background thread right there.
            # stop_event is never set to green (stop_event.set()), the
            # thread pauses forever inside the with block.
            # now agent gets a chance to use container until green light.
            stop_event.wait()
            holder.workspace = None
            holder.eval_script = None
            holder.task_context = None
            shutil.rmtree(mount_path, ignore_errors=True)
            stop_event.clear()
            # Resets the internal flag from True back to False
            # so Any future calls to stop_event.wait() will block again.
            state.set("unconfigured")
    except Exception as e:
        state.set("failed", error=str(e))


async def setup_endpoint(request):
    """
    HTTP POST /setup handler to initialize workspace in background thread.

    Workflow:
    1. Parses incoming JSON payload containing setup parameters.
    2. Validates required fields: 'image_name' and 'eval_script'.
    3. Atomically checks that server state is 'unconfigured'
    (rejects with 409 if active).
    4. Spawns a background thread (prepare_workspace) to pull
    Docker images and build container.
    5. Returns 202 Accepted immediately to avoid HTTP connection
    timeouts during long tasks.
    """
    # read the package 
    # becomes a Python dictionary assigned to data

    data = await request.json()
    required_keys = [
        "docker_image", "eval_script", "problem_statement", "instance_id",
        "hints_text"]
    missing_fields = [k for k in required_keys if k not in data]
    if missing_fields:
        return JSONResponse(
            {"error": f"missing fields: {', '.join(missing_fields)}"},
            status_code=400,
        )
    if server_state.snapshot()["state"] == "preparing":
        return JSONResponse(
            {"error": "setup already in progress — wait for /ready "
                      "or restart the server"},
            status_code=409)
    elif server_state.snapshot()["state"] == "failed":
        server_state.set("unconfigured")
    elif server_state.snapshot()["state"] == "ready":
        stop_event.set()
        while server_state.snapshot()["state"] != "unconfigured":
            time.sleep(0.05)
        if server_state.snapshot()["state"] != "unconfigured":
            return JSONResponse(
                {"error": "already configured"}, status_code=409)
    mount_path = f"/tmp/testbed_{data.get('instance_id')}"
    # daemon so the thread dies once the main process ends
    # this is the thread that will be frozen forever in the with block
    threading.Thread(target=prepare_workspace, args=(
        holder, server_state, data["docker_image"], mount_path,
        data["eval_script"], data["problem_statement"],
        data["instance_id"], data["hints_text"]), daemon=True).start()
    # return this immediately to avoid timeout
    # the client polls /ready
    return JSONResponse({"state": "preparing"}, status_code=202)


async def ready_endpoint(request):
    """
    HTTP GET /ready handler to poll server status.

    Returns the current state snapshot dict
    ('state', 'detail', and optional 'error')
    with an HTTP 200 OK status regardless of internal state.
    """
    return JSONResponse(server_state.snapshot())


async def shutdown_endpoint(request):
    snapshot = server_state.snapshot()
    # only turn off the switch if a thread is actually waiting!
    if snapshot["state"] != "ready":
        return JSONResponse({"state": snapshot["state"],
                             "note": "no active task"})
    stop_event.set()
    # Changes the internal flag from False to True.
    # flip the master light switch to ON
    deadline = time.time() + 60
    while time.time() < deadline:
        if server_state.snapshot()["state"] in ("unconfigured", "failed"):
            break
        await asyncio.sleep(0.05)
    return JSONResponse(server_state.snapshot())


@asynccontextmanager
async def lifespan(app):
    # 1. STARTUP: Start MCPServer's background session manager
    # The MCP session manager must stay running while the HTTP server is alive.
    # Normally MCP.run() starts it for us, but in remote mode we create
    # the Starlette app ourselves, so we have to manage it here.
    async with MCP.session_manager.run():
        # 2. THE RUNNING PHASE: Pause here while the server is alive and serving requests
        # Keep the session manager alive for the entire lifetime of the server.
        yield
    # 3. SHUTDOWN: When the server stops, the 'async with' block exits
    # and automatically cleans up the MCP sessions safely.
    # When I use MCP.run(), the MCP SDK manages its lifecycle for me. When I
    # create my own Starlette app and mount MCP.streamable_http_app(), I must
    # explicitly keep the MCP session manager alive using Starlette's lifespan


def main() -> None:
    if "--http" in sys.argv:
        global watch
        watch = True
        create_bound_tools(holder)
        # list of declarations that map URL paths to Python functions
        # and assign their HTTP methods (POST and GET).
        routes = [
            Route("/setup", setup_endpoint, methods=["POST"]),
            Route("/ready", ready_endpoint, methods=["GET"]),
            Route("/shutdown", shutdown_endpoint, methods=["POST"])
        ]
        # initialize a Starlette application (which FastAPI is built on top of) and
        # hand it your routes list (/setup and /ready).
        # Now app has POST /setup and GET /ready, but it is still
        # missing the protagonist of the show: MCP
        app = Starlette(routes=routes, lifespan=lifespan)
        # attach a new path to the app that will handle
        # MCP protocol tools and capabilities
        # streamable_http_app() extracts the underlying
        # sub-application inside your MCP instance.
        # Take any incoming hhtp request whose URL path starts with /mcp and
        # translates it into MCP protocol messages for your tools.
        # !! Now we have all three endpoints (/setup, /ready, and /mcp)
        # unified inside a single web application.
        app.mount("/", MCP.streamable_http_app())
        # Starts the Uvicorn http web server listening on port 8000
        # turns your custom web server and your MCP server into a
        # single, unified service running under one PID on port 8000
        try:
            uvicorn.run(app, host="0.0.0.0", port=8000)
        finally:
            stop_event.set()
            deadline = time.time() + 60
            while time.time() < deadline:
                if server_state.snapshot()["state"] in ("unconfigured", "failed"):
                    break
                time.sleep(0.05)
        return
    else:
        # 1. Register tools NOW — they exist, holder.workspace is still None,
        #    and each tool gracefully answers "not configured yet" if called early.
        create_bound_tools(holder)
        try:
            MCP.run()   # blocks until the client disconnects
        finally:
            stop_event.set()
            deadline = time.time() + 60
            while time.time() < deadline:
                if server_state.snapshot()["state"] in ("unconfigured", "failed"):
                    break
                time.sleep(0.05)


if __name__ == "__main__":
    main()
