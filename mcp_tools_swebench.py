from mcp.server.mcpserver import MCPServer
import os
import sys
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
MCP = MCPServer("MCP-SERVER")


def create_bound_tools(workspace: DockerWorkspace, eval_script: str) -> list:
    """Bind the raw tool implementations to one workspace and register
    them with the MCP server.

    The closures below capture `workspace` from this enclosing scope and
    expose only the PDF-facing parameters.

    Returns the list of bound tool functions (the server has already
    registered them; the list exists for direct testing and inspection).
    """

    @MCP.tool()
    def read_file(filepath: str, start_line: int = 1,
                  end_line: int | None = None) -> str:
        """Read a file's content with line numbers (cat -n style).

        Output format: "<line_number>: <line_content>" with right-aligned
        line numbers. Lines are 1-based and both bounds are inclusive.
        Output is capped at 200 lines per call; when truncated, the result
        states the total line count and the start_line to use for the next
        chunk.

        Always read a file (or a slice of it) before editing it.

        Args:
            filepath: Path to the file, relative to the repository root
                (absolute paths inside the workspace are also accepted).
            start_line: First line to read (1-based, inclusive). Defaults
                to 1.
            end_line: Last line to read (inclusive). Use None (default)
                to read to the end of the file.

        Returns:
            The numbered file content, or an error message starting with
            "Error:" that describes the problem and which tool to call
            next.
        """
        # Translate the schema-friendly None into the implementation's
        # -1 sentinel meaning "read to end of file".
        if end_line is None:
            end_line = -1
        return read_file_impl(workspace, filepath, start_line, end_line)

    @MCP.tool()
    def edit_file(filepath: str, old_str: str, new_str: str) -> str:
        """Replace an exact string in a file with a new string.

        old_str must match the file content EXACTLY, including
        indentation and whitespace — always read the file first and copy
        the text precisely. If old_str appears more than once, the edit
        is refused and all matching line numbers are reported: include
        surrounding lines in old_str to make it unique. An empty new_str
        deletes old_str.

        Args:
            filepath: Path to the file to edit.
            old_str: The exact string to replace (must be unique in the
                file).
            new_str: The replacement string (empty string deletes
                old_str).

        Returns:
            A success message with the edited line number and the
            surrounding context, or an error message explaining the
            failure and how to recover.
        """
        return edit_file_impl(workspace, filepath, old_str, new_str)

    @MCP.tool()
    def list_files(directory: str = ".", pattern: str = "*",
                   offset: int = 0) -> str:
        """List files and directories in a directory matching a pattern.

        Directories are suffixed with "/". Entries are sorted. Results
        are paginated: at most 100 entries per call; when more exist,
        the result says so and you can use offset for the next page.

        Args:
            directory: Directory to list, relative to the repository
                root. Defaults to the root.
            pattern: Glob pattern for entry names (e.g. "*.py").
                Defaults to "*" (everything).
            offset: Skip the first N matching entries (pagination).
                Defaults to 0.

        Returns:
            The matching entries, one per line, possibly with a
            pagination hint — or an error message.
        """
        return list_files_impl(workspace, directory, pattern, offset)

    @MCP.tool()
    def run_command(command: str, workdir: str = ".") -> str:
        """Execute a shell command inside the container, in the
        repository by default.

        Returns clearly labeled sections: stdout, stderr, and the exit
        code. A non-zero exit code is a NORMAL result, not a tool
        failure — read the output, it usually contains the information
        you need (e.g. which tests failed). Commands are killed after a
        timeout; any partial output printed before the kill is
        preserved.

        Args:
            command: The shell command to run (pipes, &&, and
                redirects are supported).
            workdir: Working directory for the command, relative to the
                repository root. Defaults to the repository root.

        Returns:
            The command's output with its exit code, or a timeout
            report including partial output.
        """
        return run_command_impl(workspace, command, workdir)

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
        return get_patch_impl(workspace)

    @MCP.tool()
    def search_code(pattern: str, file_pattern: str = "*.py",
                    offset: int = 0) -> str:
        """Search file contents for a regex pattern (grep-like).

        Searches all files whose names match file_pattern, recursively,
        skipping hidden/VCS directories and binary files. Output format:
        "/absolute/path/to/file.py:<line_number> <line_content>".
        Results are paginated: at most 100 matches per call; use offset
        for the next page.

        Args:
            pattern: Regular expression to search for (Python re
                syntax).
            file_pattern: Glob pattern selecting which file names to
                search (e.g. "*.py"). Defaults to "*.py".
            offset: Skip the first N matches (pagination). Defaults
                to 0.

        Returns:
            Matching lines in the standard format with a total count,
            or a "no matches" / "invalid regex" error message.
        """
        return search_code_impl(workspace, pattern, file_pattern, offset)

    @MCP.tool()
    def search_function_or_class_definition_in_code(
                                    name: str, offset: int = 0) -> str:
        """Find where a function or class is DEFINED, by exact name.

        Uses AST parsing, so it is precise (files with syntax errors
        are skipped, not crashed on). Output format matches
        search_code: "/absolute/path.py:<line_number> <line_content>".

        Args:
            name: Exact function or class name (e.g. "simplify").
            offset: Skip the first N matches (pagination). Defaults
                to 0.

        Returns:
            The definition lines found, or a "no matches" message
            suggesting search_code for a broader search.
        """
        return def_search_impl(workspace=workspace, name=name, offset=offset)

    @MCP.tool()
    def find_references(
            name: str, filepath: str, line: int, offset: int = 0) -> str:
        """Find all USAGES of a symbol across the repository, excluding
        its definition.

        The standard workflow: first locate the definition with
        search_function_or_class_definition_in_code, then pass its
        filepath and line here. Matches whole words only. Output format
        matches search_code.

        Args:
            name: The function or class name to find references to.
            filepath: Path to the file containing the definition
                (relative or absolute inside the workspace).
            line: Line number of the definition (1-based) — this line
                is excluded from the results.
            offset: Skip the first N matches (pagination). Defaults
                to 0.

        Returns:
            All usage lines across the repository (excluding the
            definition line), or an error message.
        """
        return find_references_impl(workspace, name, filepath, line, offset)

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
        
        test_results = workspace.run_command_in_folder(
            command=eval_script,
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


def main() -> None:
    image_name = os.environ.get("SWEBENCH_IMAGE", "swebench/sweb.eval.x86_64.sympy_1776_sympy-14711")
    mount_path = os.environ.get("SWEBENCH_MOUNT", "/tmp/testbed")
    eval_script = os.environ.get(
        "SWEBENCH_EVAL_SCRIPT", """#!/bin/bash
        source /opt/miniconda3/bin/activate testbed
        ./bin/test sympy/core/tests/test_symbol.py""")
    with DockerWorkspace(mount_path, image_name=image_name) as ws:
        # 3. Bind tools to workspace and server instance
        create_bound_tools(ws, eval_script)
        if "--http" in sys.argv:
            MCP.run(transport="streamable-http")
        else:
            MCP.run()   # stdio is the default

    # --------------------STDIO-----------------
    # use command to start server using stdio, opens the Web UI automatically:
    # npx @modelcontextprotocol/inspector uv run python mcp_tools_swebench.py
    # ------------------HTTP-------------------
    # TERMINAL COMMANDS IN ORDER:
    # terminal 1: uv run python mcp_tools_swebench.py --http
    # terminal 2: npx @modelcontextprotocol/inspector http://localhost:8000/mcp


if __name__ == "__main__":
    main()
