from tools_common.workspace import (
    LocalWorkspace,
    PathOutsideRootError,
)

CAP_NUMBER = 2000
TIMEOUT = 90  # got to change it to 60 or 90 later


def run_command(workspace: LocalWorkspace, command: str,
                workdir: str = ".") -> str:
    # workdir="." = workspace root
    stdout_truncated = False
    stderr_truncated = False
    try:
        message = workspace.run_command_in_folder(
            command, workdir, TIMEOUT
        )
    except PathOutsideRootError:
        return (f"Error: Path '{workdir}' is outside the allowed root "
                f"'{workspace.root_dir}'. Re-issue using a path inside "
                f"'{workspace.root_dir}'.")
    except FileNotFoundError:
        return (
            f"Error: directory '{workdir}' not found. "
            f"Check the path and call list_files on the parent directory.")
    except NotADirectoryError:
        return (
            f"Error: '{workdir}' is not a directory."
        )
    if message["timed_out"] is True:
        par_stdout = message["stdout"]
        par_stderr = message["stderr"]
        if par_stdout == "":
            par_stdout = "(none)"
        elif len(par_stdout) > CAP_NUMBER:
            par_stdout = par_stdout[-CAP_NUMBER:]
            par_stdout = (
                f"partial stdout truncated: showing last {CAP_NUMBER} "
                f"of {len(message['stdout'])} characters\n"
                f"{par_stdout}"
            )
        if par_stderr == "":
            par_stderr = "(none)"
        elif len(par_stderr) > CAP_NUMBER:
            par_stderr = par_stderr[-CAP_NUMBER:]
            par_stderr = (
                f"partial stderr truncated: showing last {CAP_NUMBER} "
                f"of {len(message['stderr'])} characters\n"
                f"{par_stderr}"
            )
        time_out_msg = (f"Command: {command}\n"
                        f"Working directory: {workdir}\n"
                        f"TIMEOUT: command was killed  "
                        f"after {TIMEOUT} seconds (it did not finish).\n"
                        f"--- partial stdout ---\n"
                        f"{par_stdout}\n"
                        f"--- partial stderr ---\n"
                        f"{par_stderr}")
        return time_out_msg

    if message["stdout"] == "":
        stdout = "(empty)"
    else:
        if len(message["stdout"]) > CAP_NUMBER:
            stdout = message["stdout"][-CAP_NUMBER:]
            stdout_truncated = True
        else:
            stdout = message["stdout"]
    if message["stderr"] == "":
        stderr = "(empty)"
    else:
        if len(message["stderr"]) > CAP_NUMBER:
            stderr = message["stderr"][-CAP_NUMBER:]
            stderr_truncated = True
        else:
            stderr = message["stderr"]
    if stdout_truncated is True:
        stdout_header = (f"stdout truncated: showing last {CAP_NUMBER} "
                         f"of {len(message['stdout'])} characters\n")
    else:
        stdout_header = ""
    if stderr_truncated is True:
        stderr_header = (f"stderr truncated: showing last {CAP_NUMBER} "
                         f"of {len(message['stderr'])} characters\n")
    else:
        stderr_header = ""

    success_msg = (f"Command: {command}\n"
                   f"Working directory: {workdir}\n"
                   f"Exit code: {message['exit_code']}\n\n"
                   f"--- stdout ---\n"
                   f"{stdout_header}"
                   f"{stdout}\n\n"
                   f"--- stderr ---\n"
                   f"{stderr_header}"
                   f"{stderr}")
    return success_msg


def get_patch(workspace: LocalWorkspace) -> str:
    # Register untracked files as "intent to add".
    # This makes new files appear in `git diff` without fully staging them.
    # ".": current directory
    # ".": helps us stay in root because self.root_dir / "."
    # example self.root_dir = /tmp/my_project / "." → /tmp/my_project
    add_result = workspace.run_command_in_folder(
        "git add -N .",
        "."
    )
    if add_result["exit_code"] != 0:
        return (f"ERROR: this workspace is not a git repository "
                f"— get_patch only works inside one.:"
                f"\n{add_result['stderr'].strip()}")
    # get THE REPOSITORY (sympy) changes, while ignoring
    # permission-mode changes.
    diff_result = workspace.run_command_in_folder(
        "git -c core.fileMode=false diff",
        ".")
    # if git was not initilaized in the repo(sympy)
    # or git not installed at all
    if diff_result['exit_code'] != 0:
        return (f"ERROR: Failed to generate patch. Git returned an error:"
                f"\n{diff_result['stderr'].strip()}")
    if diff_result["stdout"] == "":
        return ("WARNING: No changes detected — the diff is completely "
                "empty. Make sure to modify files using edit_file.")
    patch = (f"Command: git -c core.fileMode=false diff\n\n"
             f"--- patch ---\n\n"
             f"{diff_result['stdout']}")
    return patch
