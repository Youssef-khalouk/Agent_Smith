"""
tests/test_docker.py — THE DUEL, Docker leg.
============================================

Runs the tools against DockerWorkspace: file tools through the window
(the mounted folder), program tools through the door (docker exec).

Run from the REPO ROOT (module mode — the import lesson):

    uv run python -m tests.test_tools_with_docker

Expected runtime: 1–3 minutes (two 85MB extractions + door commands).
Requires: Docker daemon running + the SWE-bench image (pulls if missing,
which may take a long time on first run).

⚠️⚠️⚠️ PREREQUISITES — READ BEFORE PANICKING AT FAILURES ⚠️⚠️⚠️

D11 and D12 will FAIL until you add two small things to
DockerWorkspace.run_command_in_folder (in tools_common/workspace.py):

  FIX 1 (for D11 — security): BEFORE delegating to exec, validate the
        workdir exactly like LocalWorkspace does:
          - resolve (self.root_dir / folder_path)
          - if NOT is_relative_to(self.root_dir):
                raise PathOutsideRootError(...)
        The tool layer in execution.py ALREADY catches PathOutsideRootError
        and writes the "outside the allowed root" message. You only need
        to raise it. (~5 lines)

  FIX 2 (for D12 — translation): the host-relative workdir must become a
        container-side path for exec: workdir "." → "/testbed",
        "sympy" → "/testbed/sympy". Pass that to the manager's exec
        instead of letting it default to /testbed. (~3 lines)

If D18 fails with "dubious ownership" — the safe.directory landmine is
not wired into start(); add it (you had it working before).

Phases:
  Phase 1  — the ceremony: extraction, idempotency, crash cleanup, reaper
  Phase 2  — the door: exec facts, timeout, identity, security, escape
  Phase 3  — the window + the receipt: tools on the REAL sympy repo,
             edit through the window, git through the door

Invariant checked at every step: at most ONE agent-smith-* container
alive at any moment. Final line proves ZERO remain.
"""

import os          # for os.getuid() — comparing file ownership
import shutil      # for rmtree — cleaning mount folders
import subprocess  # for docker CLI calls (orphan planting, ps checks)
import tempfile    # for fresh empty mount folders
from pathlib import Path

from tools_common.workspace import DockerWorkspace
from tools_common.filesystem import read_file, edit_file, list_files
from tools_common.execution import run_command, get_patch
from tools_common.code_search import (
    search_code,
    search_function_or_class_definition_in_code,
)

# The same starter image used in every lesson since week 1.
IMAGE = "swebench/sweb.eval.x86_64.sympy_1776_sympy-14711"

# The reaper sweeps anything with this prefix — our planted orphan
# must use it too, or the reaper would ignore it.
FAKE_ORPHAN_NAME = "agent-smith-fake-orphan"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def check(condition: bool, message: str) -> None:
    """Fail loudly with a message if the condition is False."""
    if not condition:
        raise AssertionError(message)


def list_container_names() -> list:
    """
    Ask Docker for the names of ALL containers (running AND dead —
    the -a flag from Lesson 1). Uses the CLI because the test must
    see Docker's GLOBAL state, not the manager's in-memory view —
    that's the whole point of leak detection (the count-vs-identity
    lesson: Python memory dies with the process, containers don't).
    """
    result = subprocess.run(
        ["docker", "ps", "-a", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [name for name in result.stdout.splitlines() if name.strip()]


def agent_smith_containers() -> list:
    """All containers matching our naming prefix (leaks included)."""
    return [n for n in list_container_names()
            if n.startswith("agent-smith-")]


def fresh_mount() -> Path:
    """
    A brand-new EMPTY temp folder for a mount.

    Why empty: extraction renames the staging sibling ONTO this path —
    POSIX rename onto a NON-empty directory explodes with
    'OSError 39: Directory not empty' (the crash you already met).
    An empty target is fine; that's why mkdtemp (which guarantees an
    empty new dir) is exactly what we need.
    """
    return Path(tempfile.mkdtemp())


def remove_fake_orphan_best_effort() -> None:
    """Kill the planted orphan if it somehow survived (test hygiene)."""
    subprocess.run(
        ["docker", "rm", "-f", FAKE_ORPHAN_NAME],
        capture_output=True,   # ignore errors — it's usually already gone
    )


# --------------------------------------------------------------------------
# PHASE 1 — THE CEREMONY
# --------------------------------------------------------------------------

def phase_1_ceremony() -> Path:
    """
    Tests D1–D6: extraction, .git survival, restart idempotency,
    double-start identity, crash cleanup, and the orphan reaper.

    All six share ONE mount folder: the first workspace performs the
    real extraction; every later workspace on the same mount must SKIP
    extraction (the .git guard) — which is exactly what we verify.
    """
    print("=" * 60)
    print("PHASE 1 — THE CEREMONY")
    print("=" * 60)

    mount = fresh_mount()
    try:
        # ---- D1 + D2: first start = real extraction ----
        print("\n[D1] Fresh mount → extraction → repo visible through door")
        with DockerWorkspace(str(mount), image_name=IMAGE) as ws:
            # The door works AND the repo is really there — the
            # automated version of your hand-made 'ls /testbed' artifact.
            result = run_command(ws, "ls /testbed")
            check("sympy" in result,
                  "D1: the repo is not visible through the door — "
                  "extraction or mounting failed")
        # The with-block exited: the container must already be gone.
        check(len(agent_smith_containers()) == 0,
              "D1b: container survived the with-block exit")
        print("  ✓ extraction works, repo present, container cleaned")

        print("\n[D2] .git survived the extraction (the treasure check)")
        check((mount / ".git").exists(),
              "D2: .git missing from the extracted repo — hidden files "
              "were skipped; patches would be impossible")
        print("  ✓ .git present on the host side of the window")

        # ---- D3: restart on the same mount must SKIP extraction ----
        print("\n[D3] Restart on same mount → extraction skipped, "
              "sentinel survives")
        # Plant a file AFTER extraction, host-side, through the window.
        sentinel = mount / "sentinel_d3.txt"
        sentinel.write_text("I survived the restart\n", encoding="utf-8")

        with DockerWorkspace(str(mount), image_name=IMAGE) as ws2:
            # If extraction ran again it would either crash
            # ('Directory not empty') or wipe our sentinel.
            check(sentinel.exists(),
                  "D3: sentinel destroyed — extraction did NOT skip on "
                  "a prepared mount (the .git guard failed)")
            result = run_command(ws2, "echo still-alive")
            check("still-alive" in result,
                  "D3: door broken after restart")
        print("  ✓ extraction skipped, sentinel intact, door alive")

            # ---- D4: double-start must return the SAME container ----
            # (moved inside a workspace lifetime — see below)
        # D4 runs inside its own workspace for clarity:
        print("\n[D4] Double start → same container identity")
        with DockerWorkspace(str(mount), image_name=IMAGE) as ws4:
            first_id = ws4.container_manager.container.id
            ws4.start()  # second call: guard must return early
            second_id = ws4.container_manager.container.id
            check(first_id == second_id,
                  "D4: start() replaced the container — the idempotency "
                  "guard is unreachable (check guard/reaper ORDER in "
                  "ContainerManager.start: guard FIRST, reaper second)")
        print("  ✓ idempotent: same container across double start")

        # ---- D5: a crash inside the with must still clean up ----
        print("\n[D5] Crash inside with-block → zero orphans")
        try:
            with DockerWorkspace(str(mount), image_name=IMAGE):
                # Deliberate violence — the graded scenario.
                raise ValueError("simulated crash")
        except ValueError:
            pass  # expected: the exception escapes the with-block
        check(len(agent_smith_containers()) == 0,
              "D5: crash left orphan containers behind — the exam's "
              "cleanup check would FAIL")
        print("  ✓ crash-guaranteed cleanup works")

        # ---- D6: the reaper sweeps stale containers from dead runs ----
        print("\n[D6] Planted orphan → swept by the reaper at start()")
        remove_fake_orphan_best_effort()  # hygiene: no leftovers from old runs
        subprocess.run(
            ["docker", "run", "-d",
             "--name", FAKE_ORPHAN_NAME,
             IMAGE, "sleep", "infinity"],
            check=True, capture_output=True,
        )
        # Simulates: a previous process died hard (SIGKILL) and its
        # container leaked. A NEW workspace start must sweep it.
        with DockerWorkspace(str(mount), image_name=IMAGE) as ws6:
            result = run_command(ws6, "echo reaper-test")
            check("reaper-test" in result,
                  "D6: workspace unusable after orphan sweep")
        names = agent_smith_containers()
        check(FAKE_ORPHAN_NAME not in names,
              "D6: the reaper did not remove the planted orphan")
        check(len(names) == 0,
              "D6b: unexpected agent-smith containers remain")
        print("  ✓ reaper swept the orphan, no leaks")

        return mount
    finally:
        # The mount is regenerable from the image at any time —
        # the ceremony can always rebuild it. So we clean it.
        shutil.rmtree(mount, ignore_errors=True)


# --------------------------------------------------------------------------
# PHASE 2 + 3 — THE DOOR, THE WINDOW, THE RECEIPT
# --------------------------------------------------------------------------

def phase_2_and_3() -> None:
    """
    One long-lived workspace on a REAL extracted sympy repo:

      Phase 2 (the door):   run_command / exec behavior
      Phase 3 (the window): file tools + search on real source code
      The receipt:          edit through the window, git through the door
    """
    print("\n" + "=" * 60)
    print("PHASE 2 — THE DOOR   |   PHASE 3 — THE WINDOW")
    print("=" * 60)

    mount = fresh_mount()
    try:
        # ONE with-block wraps the ENTIRE phase — the lifecycle lesson:
        # the chamber stays alive for all tests below, dies at the end.
        with DockerWorkspace(str(mount), image_name=IMAGE) as ws:

            # ---------------- THE DOOR ----------------

            print("\n[D7] echo through the door")
            result = run_command(ws, "echo hello")
            check("hello" in result and "Exit code: 0" in result,
                  "D7: basic exec failed")
            print("  ✓ stdout + exit code 0")

            print("\n[D8] Failing command = normal result, not an error")
            result = run_command(ws, "ls /this_folder_does_not_exist")
            check("Exit code:" in result and "Exit code: 0" not in result,
                  "D8: failing command not reported as a normal result")
            print("  ✓ exit code + stderr returned as information")

            print("\n[D9] Timeout through the door (direct workspace call)")
            # Calling the workspace layer directly lets us pass a SHORT
            # timeout (2s) instead of the tool default — keeps the suite
            # fast. Facts packet, not a formatted message.
            facts = ws.run_command_in_folder("sleep 60", ".", 2)
            print("D9 FACTS:", facts)
            check(facts["timed_out"] is True,
                  "D9: timed_out flag not set after deadline")
            check(facts["exit_code"] == 124,
                  "D9b: expected exit 124 (GNU timeout self-kill), "
                  f"got {facts['exit_code']}")
            print("  ✓ killed at deadline, exit 124")

            print("\n[D9c] Partial output rescued before the kill")
            facts = ws.run_command_in_folder(
                "echo before-timeout && sleep 60", ".", 3)
            check(facts["timed_out"] is True
                  and "before-timeout" in facts["stdout"],
                  "D9c: partial stdout lost on timeout")
            print("  ✓ partial output survived")

            print("\n[D10] Identity proof: container Python ≠ host Python")
            result = run_command(ws, "python3 --version")
            # docker run --rm swebench/sweb.eval.x86_64.sympy_1776_sympy-14711:latest python3 --version
            check("Python 3.11" in result,
                  "D10: expected the container's Python 3.9 — if you see "
                  "3.10 here, the command ran on the HOST, not through "
                  "the door!")
            print("  ✓ the door really leads into the container")

            print("\n[D11] workdir outside root → rejected  "
                  "(⚠️ needs FIX 1 — see banner)")
            result = run_command(ws, "echo hello", workdir="..")
            check("outside the allowed root" in result,
                  "D11: workdir='..' was NOT rejected — "
                  "DockerWorkspace.run_command_in_folder is missing the "
                  "security dance (FIX 1 in the file banner)")
            print("  ✓ security boundary enforced at the door")

            print("\n[D12] workdir translation  "
                  "(⚠️ needs FIX 2 — see banner)")
            result = run_command(ws, "pwd")
            check("/testbed" in result,
                  "D12: default workdir is not /testbed")
            result = run_command(ws, "pwd", workdir="sympy")
            check("/testbed/sympy" in result,
                  "D12b: workdir='sympy' did not translate to "
                  "/testbed/sympy — exec is ignoring folder_path "
                  "(FIX 2 in the file banner)")
            print("  ✓ workdir honored through the door")

            print("\n[D13] THE ESCAPE INVERSION — the money shot")
            # On LocalWorkspace this exact command writes OUTSIDE the
            # root (test 36). Through the door, '../' from /testbed is
            # just the container's own filesystem — the host is untouchable.
            host_neighbor = mount.parent / "escaped_from_workspace.txt"
            host_neighbor.unlink(missing_ok=True)  # clean slate
            run_command(ws, "echo ESCAPED > ../escaped_from_workspace.txt")
            check(not host_neighbor.exists(),
                  "D13: the escape reached the HOST — the chamber is not "
                  "containing the blast!")
            print("  ✓ explosion contained: host file does NOT exist")
            print("  📸 screenshot this next to local test 36 — README gold")

            print("\n[D14] Window is bidirectional (container → host)")
            run_command(ws, "touch /testbed/created_from_container.txt")
            host_copy = mount / "created_from_container.txt"
            check(host_copy.exists(),
                  "D14: container-created file not visible on host")
            # Ownership is INFORMATION, not a failure — root-owned files
            # are the known Option-B yellow. We print it so you SEE it.
            stat = host_copy.stat()
            if stat.st_uid != os.getuid():
                print(f"  [yellow] file is uid={stat.st_uid} "
                      f"(you are {os.getuid()}) — root-owned, as predicted")
            else:
                print("  [info] file is owned by you — no permission quirk")
            print("  ✓ file crossed the window container→host")

            # ---------------- THE WINDOW ----------------

            print("\n[D15] read_file on REAL repo source")
            result = read_file(ws, "README.rst", 1, 10)
            check("1: " in result,
                  "D15: cat-n formatted output missing for real repo file")
            print("  ✓ real source served through the window")

            print("\n[D16] list_files on the real repo root")
            result = list_files(ws, ".", "*")
            check("sympy/" in result,
                  "D16: sympy/ not in the real repo listing")
            print("  ✓ real repo listed")

            print("\n[D17] search_code across the real codebase")
            result = search_code(ws, "def simplify", "*.py")
            check("Showing matches" in result,
                  "D17: no matches for 'def simplify' in sympy?!")
            check(str(mount) in result,
                  "D17b: results are not host-absolute paths")
            print("  ✓ grep-format results from real source")

            print("\n[D17b] definition search (AST) on the real repo")
            result = search_function_or_class_definition_in_code(
                ws, "simplify", "*.py")
            check("Showing matches" in result,
                  "D17b: definition of 'simplify' not found in sympy")
            print("  ✓ AST definition search works through the window")

            # ---------------- THE RECEIPT ----------------

            print("\n[D18] Edit through the window, git through the door")
            # Step 1: create a NEW file host-side (through the window).
            # Step 2: get_patch → the add -N machinery (running INSIDE
            #         the container) must include it in the diff.
            # Step 3: edit it with edit_file (window), patch again.
            # This single test proves: window + door + add -N +
            # safe.directory + git-through-container, all at once.
            marker = mount / "zz_agent_smith_test.py"
            marker.write_text("original_line = 1\n", encoding="utf-8")

            result = get_patch(ws)
            check("zz_agent_smith_test.py" in result,
                  "D18a: new file not in patch — add -N failed through "
                  "the door (or safe.directory landmine fired — read "
                  "the patch output above)")

            result = edit_file(ws, "zz_agent_smith_test.py",
                               "original_line = 1", "modified_line = 2")
            check("Successfully edited" in result,
                  "D18b: edit through the window failed")

            result = get_patch(ws)
            check("modified_line = 2" in result,
                  "D18c: the edit did not reach the patch — git (door) "
                  "and files (window) are seeing DIFFERENT worlds!")
            print("  ✓ window-edit → door-git → patch: one consistent world")

    finally:
        shutil.rmtree(mount, ignore_errors=True)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> None:
    # Preflight: fail friendly if Docker isn't even running.
    try:
        subprocess.run(["docker", "ps"], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print("ERROR: Docker daemon is not running. Start it first.")
        return

    try:
        phase_1_ceremony()
        phase_2_and_3()

        # The invariant, checked one final time with Docker's own eyes:
        # nothing of ours may remain on this machine.
        print("\n" + "=" * 60)
        print("FINAL INVARIANT — no agent-smith containers remain")
        print("=" * 60)
        leftovers = agent_smith_containers()
        check(len(leftovers) == 0,
              f"Leaked containers: {leftovers} — 'you are responsible "
              "to clean it' (PDF) — this is the exam's check, failing "
              "HERE, in your workshop")
        print("  ✓ docker ps -a is clean of agent-smith containers")

        print("\nALL GOOD — the duel is won: "
              "the tools never learned which world they were in.")
    finally:
        # Even on failure, never leave the planted orphan behind.
        remove_fake_orphan_best_effort()


if __name__ == "__main__":
    main()
    # to run: uv run python -m tests.test_docker   (from the repo root!)