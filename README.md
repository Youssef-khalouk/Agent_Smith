## Tool Implementation Details

### The workspace abstraction

All tools are kitchen-blind: they never touch paths, containers, or "where am I" logic. Each tool asks a workspace — a waiter with one menu (`read_file_text`, `edit_file_text`, `list_directory_entries`, `search_files_for_pattern`, `search_function_or_class_definitions`, `find_name_references`, `run_command_in_folder`) — and formats the answer.

Two implementations exist behind the same interface:

- **LocalWorkspace** — files on the host (MBPP, and the host side of the mount)
- **DockerWorkspace** — composes LocalWorkspace (file tools, through the window) with ContainerManager.exec (commands, through the door)

The same tool code serves both worlds — verified by running the identical test suite against both workspaces (`tests/test_tools.py` locally, `tests/test_tools_with_docker.py` against a real container). Zero `if benchmark ==` branches exist inside tool code.

- `tools_common/workspace.py` — the workspaces, the exception family, the facts layer
- `tools_common/filesystem.py` — `read_file`, `edit_file`, `list_files`
- `tools_common/execution.py` — `run_command`, `get_patch`
- `tools_common/code_search.py` — `search_code`, `search_function_or_class_definition_in_code`, `find_references`

### The nine mandatory tools

| Tool | Contract | Output format |
|------|----------|---------------|
| `read_file(filepath, start_line, end_line)` | 1-based inclusive bounds, 200-line cap with a pagination hint telling the LLM the next `start_line` | `cat -n` style: `42: content` |
| `edit_file(filepath, old_str, new_str)` | exact string replace; refuses ambiguous matches and reports all line numbers; writes atomically (temp file + rename) | success message + a context window around the edit |
| `list_files(directory, pattern)` | glob patterns, sorted, `/` suffix on directories, 100-entry pagination via `offset` | one entry per line |
| `search_code(pattern, file_pattern)` | regex search, skips `.git` and binary files, 100-match pagination | `/absolute/path.py:42 content` |
| `search_function_or_class_definition_in_code(name)` | AST-based, so it survives syntax errors in the tree | same format |
| `find_references(name, filepath, line)` | word-boundary search across the workspace, excluding the definition line | same format |
| `run_command(command, workdir)` | returns stdout, stderr AND exit code; timeout kill with partial-output rescue; tail-kept output cap (failures print at the end) | labeled sections |
| `get_patch()` | runs `git -c core.fileMode=false diff` with intent-to-add (`git add -N`) so new files are included; permission-only changes excluded | the unified diff |
| `run_tests()` | executes the task's eval script through the door, 600s timeout, tail-kept output | labeled test output |

Optional parameters beyond the subject's contracts are exactly two: `offset` (pagination on list/search/find_references — required by the exam's cumulative token limits, since truncation hints reference it) and `end_line=None` on `read_file` (the same parameter with a clearer default). `search_function_or_class_definition_in_code` matches the subject's signature exactly — no additions. The subject permits additional tools and parameters ("you may implement any additional tools you consider useful"); these are the minimum the graded constraints forced, and nothing more.

### Tool design philosophy

**Facts in the workspace, messages in the tools.** The workspace layer raises raw facts (exceptions, counts, result packets); the tool layer translates them into text the LLM can act on. This keeps all LLM-facing behavior in one place and lets the workspace stay protocol-free and testable with zero MCP anywhere.

**Every error is a signpost.** Error messages tell the LLM what happened and what to try next ("file not found — call list_files to discover valid files"). Messages only reference tools and parameters that actually exist by their registered names.

**A failing command is a successful tool call.** A non-zero exit code is returned as a normal, labeled result — the agent needs test failures as information, not as tool errors. Only tool-level problems (timeout, command could not start) are errors.

**Output budgets by design.** Every tool caps its output (lines, matches, entries, characters) with a continuation hint where a continuation parameter exists — the same frugality that the exam's token limits (6k input for MBPP, 300k for SWE-bench) demand.

### Docker infrastructure

`ContainerManager` (`tools_common/docker_manager.py`) owns the container lifecycle with five abilities:

- **pull** — eager, at task start; instant no-op if the image exists
- **extract** — the ceremony: create a stopped blueprint container → copy `/testbed` to a host staging sibling folder → atomic rename onto the mount → discard the blueprint. Wipe-on-birth: a recycled task can never inherit stale state (the previous agent's edits die with the mount)
- **start** — bind mount + `sleep infinity` + git safe-directory pre-wiring; idempotent by construction: guard (already running? return) → reaper (sweep stale `agent-smith-*` orphans) → create
- **exec** — background thread + container-side GNU timeout self-kill (exit 124) + host-side deadline with partial-output rescue; returns the facts packet (stdout, stderr, exit_code, timed_out)
- **die** — force-remove, crash-guaranteed through context managers

Two invariants, both test-enforced: at most one `agent-smith-*` container alive at any moment (double-start returns the same container ID; a startup reaper sweeps orphans from previous runs), and `docker ps -a` is empty after every exit path — including deliberate crashes mid-task.

### The SWE-bench MCP server

`mcp_tools_swebench.py` (repository root, per the subject) exposes the nine tools, a resource (`task://context` — problem statement, instance id, hints) and a prompt (`fix_issue` — the agent workflow scaffold). Tools are bound closures: the server constructs one workspace and each tool's LLM-facing signature contains exactly the subject's parameters — the workspace is captured by the closure, never visible to the LLM (verified by schema inspection).

Configuration arrives per transport:

- **stdio (the graded path)** — environment variables at process birth: `SWEBENCH_IMAGE`, `SWEBENCH_MOUNT`, `SWEBENCH_EVAL_SCRIPT`, plus the task-context fields. Spawn order is the readiness guarantee: the ceremony completes before `MCP.run()` serves, so a client's `initialize` blocks until tools are live. No lifecycle machinery is needed — the connection closing IS the shutdown: stdin EOF ends `run()`, the with-block exits, the container dies. One task, one process.
- **streamable HTTP (remote-capable, beyond the subject's requirements)** — the server additionally offers runtime configuration: `POST /setup` (with force support for crash recovery), `GET /ready` (state polling: unconfigured → preparing → ready / failed with the actual error visible), `POST /shutdown` (the task-end signal). The task lifetime is decoupled from the server lifetime: ending a task releases the container, wipes the mount, and reopens setup — every new task gets a fresh world. An idle watchdog reclaims tasks whose client died silently (900 seconds without a tool call — a threshold that always exceeds the test-run timeout, so a patient agent is never reclaimed).

Both transports are served from one process: the FastMCP streamable app is mounted at `/mcp` inside a Starlette application that also carries the custom endpoints, with the MCP session manager kept alive through the application lifespan.

### Testing

The tools layer is covered by roughly 140 checks across four files:

- `tests/test_tools.py` — the local suite: every tool, every error path, exact output formats, pagination, path security, binary files, permission refusals (~65 checks)
- `tests/test_tools_with_docker.py` — the duel: the same tool calls against a real DockerWorkspace — the ceremony lifecycle (extraction, restart freshness, double-start identity, crash cleanup, the reaper), the door (timeouts with partial output, workdir security, the escape-containment proof: a command that escapes the workspace on LocalWorkspace is contained by the chamber on DockerWorkspace), file tools on the real repo, run_tests against the real eval script, and the patch round-trip (edit through the window → git through the door → patch applied to a fresh world)
- `tests/dummy_mcp_server.py` — a minimal two-tool MCP server over both transports; the rehearsal partner for the exam's unknown-MCP-server test

### Benchmark Results and Analysis

To be filled after the benchmark runs (5 models × 3 SWE-bench tasks, per the subject's V.7 requirements): results table, provider reliability, intermediary metrics, the ablation study, and data-driven conclusions. The backing solution.json files are stored in `benchmark_runs/` (tracked in git).

### Running my components

```bash
# the SWE-bench MCP server
python mcp_tools_swebench.py --stdio   # stdio — the graded path
python mcp_tools_swebench.py --http    # streamable HTTP, env-configured
```

```bash
# driving the remote lifecycle
curl http://127.0.0.1:8000/ready
curl -X POST http://127.0.0.1:8000/setup -H "Content-Type: application/json" \
     -d '{"docker_image": "...", "eval_script": "...", "instance_id": "...",
          "problem_statement": "...", "hints_text": ""}'
curl -X POST http://127.0.0.1:8000/shutdown
```

```bash
# the test suite
make test_tools               # local, no Docker needed
make test_tools_in_container  # requires the Docker daemon
```

### Resources

#### References

- [Model Context Protocol — documentation](https://modelcontextprotocol.io) — the Tools concept and the Python SDK quickstart
- [MCP vs API Explained](https://youtu.be/7yNvsFrwpp0) — Relationship between MCP and API
- [MCP build guid](https://youtu.be/He8tUwLzLnU) — the building steps of an MCP server
- [Reason for MCP](https://youtu.be/kn6dxL53NkM) — Explanation of the issue that MCP fixed

### AI usage disclosure (my components)

AI tools were used throughout as a learning partner and code reviewer, not as a code generator. The working method was: research a concept, implement it independently, then submit it for review — bugs and design flaws found in review were fixed by hand, and every design decision (the workspace abstraction, the window/door split, the lifecycle guarantees, the wipe-on-birth policy, the token-budget-driven tool philosophy) can be explained and defended by its author. All code in my components (tools_common/, mcp_tools_swebench.py, the test files) was written by me. AI was additionally used for explaining unfamiliar concepts (MCP, Docker internals, async lifespans) and drafting project-management artifacts (the Jira backlog).