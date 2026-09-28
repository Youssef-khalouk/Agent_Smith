from pathlib import Path
from tempfile import TemporaryDirectory
from tools_common.execution import run_command, get_patch
from tools_common.filesystem import edit_file, list_files, read_file
from tools_common.workspace import LocalWorkspace, DockerWorkspace
import subprocess
import tempfile
import shutil
from tools_common.code_search import (
    search_code,
    search_function_or_class_definition_in_code,
    find_references,
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    # Use a temporary workspace so the smoke test never modifies the project.
    with TemporaryDirectory() as tmp:
        root = Path(tmp)

        # Normal text/code files.
        (root / "notes.txt").write_text(
            "hello world\nsecond line\nthird line\n", encoding="utf-8"
        )
        (root / "code.py").write_text(
            "# smoke test\nprint('hello')\n", encoding="utf-8"
        )

        # Directory + nested file.
        (root / "src").mkdir()
        (root / "src" / "main.py").write_text(
            "def main():\n    print('hello')\n", encoding="utf-8"
        )

        # 106 .txt files so list_files pagination is tested.
        for i in range(1, 107):
            (root / f"file_{i:03}.txt").write_text(
                f"file {i}\n", encoding="utf-8"
            )

        # 201-line file so read_file's 200-line cap is tested.
        (root / "big.txt").write_text(
            "\n".join(f"line {i}" for i in range(1, 202)) + "\n",
            encoding="utf-8",
        )

        (root / "empty").mkdir()

        workspace = LocalWorkspace(str(root))
        # workspace = DockerWorkspace(str(root))

        print("1. read_file: normal file")
        result = read_file(workspace, "notes.txt")
        print(result)
        check("hello world" in result, "normal read_file failed")

        print("\n2. read_file: requested line range")
        result = read_file(workspace, "notes.txt", 2, 2)
        print(result)
        check("second line" in result, "read_file range failed")

        print("\n3. read_file: 200-line pagination")
        result = read_file(workspace, "big.txt")
        print(result[-300:])
        check("lines total" in result, "read_file truncation hint missing")
        check("start_line=201" in result, "read_file continuation hint missing")

        print("\n4. list_files: pattern matching")
        result = list_files(workspace, ".", "*.py")
        print(result)
        check("code.py" in result, "list_files pattern matching failed")

        print("\n5. list_files: workspace-relative path + directory slash")
        result = list_files(workspace, ".", "src*")
        print(result)
        check("src/" in result, "directory was not marked with '/'")
        check("src/main.py" not in result,
              "root listing should not include nested files")

        print("\n6. list_files: first pagination page")
        result = list_files(workspace, ".", "*.txt", offset=0)
        print(result[:500])
        check("Showing entries 1-100 of 108." in result,
              "first list_files page is incorrect")
        check("file_001.txt" in result and "file_099.txt" in result,
              "first page contains wrong entries")
        check("offset=100" in result,
              "list_files continuation hint is missing")

        print("\n7. list_files: second pagination page")
        result = list_files(workspace, ".", "*.txt", offset=100)
        print(result)
        check("Showing entries 101-108 of 108." in result,
              "second list_files page is incorrect")
        check("file_100.txt" in result and "notes.txt" in result,
              "second page contains wrong entries")
        check("offset=" not in result,
              "final page incorrectly offers another page")

        print("\n8. list_files: no matches")
        result = list_files(workspace, ".", "*.doesnotexist")
        print(result)
        check("No match" in result, "no-match message is missing")

        print("\n9. list_files: empty directory")
        result = list_files(workspace, "empty")
        print(result)
        check("empty" in result.lower(), "empty-directory message is missing")

        print("\n10. list_files: blank pattern defaults to '*'")
        result = list_files(workspace, ".", "   ")
        print(result[:300])
        check(
            "big.txt" in result and "file_001.txt" in result,
            "blank pattern did not default to '*'"
            )

        print("\n11. edit_file: normal edit")
        result = edit_file(workspace, "notes.txt", "hello world", "hello agent")
        print(result)
        check("Successfully edited" in result, "edit_file success failed")
        check(
            "hello agent" in (root / "notes.txt").read_text(encoding="utf-8"),
            "edit_file did not modify the file",
        )
        check("Context around the edit" in result,
              "edit_file did not return context")

        print("\n12. edit_file: identical strings")
        result = edit_file(workspace, "notes.txt", "hello agent", "hello agent")
        print(result)
        check("identical" in result, "identical-string error is missing")

        print("\n13. edit_file: empty old_str")
        result = edit_file(workspace, "notes.txt", "", "x")
        print(result)
        check("old_str cannot be empty" in result,
              "empty old_str error is missing")

        print("\n14. edit_file: string not found")
        result = edit_file(workspace, "notes.txt", "not here", "x")
        print(result)
        check("not found" in result, "StringNotFoundError message is missing")

        print("\n15. edit_file: multiple matches")
        (root / "multiple.txt").write_text(
            "apple\nbanana\napple\n", encoding="utf-8"
        )
        result = edit_file(workspace, "multiple.txt", "apple", "orange")
        print(result)
        check("multiple times" in result, "multiple-match error is missing")
        check("1" in result and "3" in result,
              "multiple-match line numbers are missing")

        print("\n16. read_file: missing file")
        result = read_file(workspace, "missing.txt")
        print(result)
        check("does not exist" in result, "missing-file error is missing")

        print("\n17. read_file: directory instead of file")
        result = read_file(workspace, "src")
        print(result)
        check("directory" in result.lower(),
              "directory-as-file error is missing")

        print("\n18. list_files: missing directory")
        result = list_files(workspace, "missing_dir")
        print(result)
        check("not found" in result.lower(),
              "missing-directory error is missing")

        print("\n19. list_files: file instead of directory")
        result = list_files(workspace, "notes.txt")
        print(result)
        check("not a directory" in result.lower(),
              "file-as-directory error is missing")

        print("\n20. path security: read outside root")
        result = read_file(workspace, "../outside.txt")
        print(result)
        check("outside" in result.lower() or "allowed root" in result.lower(),
              "outside-root read was not rejected")

        print("\n21. path security: edit outside root")
        result = edit_file(workspace, "../outside.txt", "x", "y")
        print(result)
        check("outside" in result.lower(),
              "outside-root edit was not rejected")

        print("\n22. negative list_files offset")

        result = list_files(workspace, ".", "*", offset=-1)
        check(
            "offset cannot be negative" in result,
            "negative offset did not return an error",
            )
        print(result)

        # 23. Inverted read_file bounds
        print("23. inverted read_file bounds")
        (root / "forty.txt").write_text(
            "\n".join(f"line {i}" for i in range(1, 41)) + "\n",
            encoding="utf-8",
        )

        result = read_file(workspace, "forty.txt", 10, 5)
        check(
            "Error" in result,
            "inverted start/end bounds did not return an error",
        )
        print(result)

        # 24. Read completely empty file
        print("24. empty file")
        (root / "empty.txt").write_text("", encoding="utf-8")

        result = read_file(workspace, "empty.txt")
        print("RESULT:", repr(result))
        check(
            "is empty" in result,
            "empty file did not return 'File is empty'",
        )
        print(result)

        # 25. File whose last line has no newline
        print("25. file without final newline")
        (root / "no_final_newline.txt").write_text(
            "line 1\nline 2\nline 3",
            encoding="utf-8",
        )

        result = read_file(workspace, "no_final_newline.txt")
        check(
            "line 1" in result
            and "line 2" in result
            and "line 3" in result,
            "file without final newline was corrupted",
        )
        print(result)

        # 26. Binary file
        print("26. binary file")
        (root / "image.bin").write_bytes(
            b"\x89PNG\r\n\x1a\n"
        )

        result = read_file(workspace, "image.bin")
        check(
            "binary" in result.lower()
            or "decode" in result.lower()
            or "utf-8" in result.lower(),
            "binary file did not return a binary-file error",
        )
        print(result)

        # 27. start_line = 0
        print("27. read_file start_line=0")

        result = read_file(workspace, "forty.txt", 0)
        check(
            "Error" in result,
            "start_line=0 did not return an error",
        )
        print(result)

        # 28. end_line = -5
        print("28. read_file end_line=-5")

        result = read_file(workspace, "forty.txt", 1, -5)
        check(
            "Error" in result,
            "end_line=-5 did not return an error",
        )
        print(result)

        # ============================================================
        # TEST 29 — Permission denied during edit
        # ============================================================

        print("\n[TEST 29] Permission denied during edit")

        # Create the file first
        (root / "readonly.txt").write_text(
            "original content",
            encoding="utf-8"
        )

        # Remove write permission from the ROOT DIRECTORY.
        # The file itself remains writable, but atomic_write() needs
        # permission to replace the file inside this directory.
        root.chmod(0o555)

        try:
            result = edit_file(
                workspace,
                filepath="readonly.txt",
                old_str="original content",
                new_str="new content",
            )

            print(result)

            check(
                "operating system refused to write" in result,
                "permission error was not returned",
            )

        finally:
            # Restore permissions so the temporary directory can be
            # cleaned up normally.
            root.chmod(0o755)
        # ============================================================
        # TEST 30 — Successful command
        # ============================================================

        print("\n[TEST 30] Successful command")
        
        result = run_command(workspace, "echo hello")

        print(result)

        assert "hello" in result
        assert "Exit code: 0" in result

        # ============================================================
        # TEST 31 — Failing command
        # ============================================================

        print("\n[TEST 31] Failing command")

        result = run_command(workspace, "ls /this_folder_does_not_exist")

        print(result)

        assert "Exit code:" in result
        assert "Exit code: 0" not in result

        # ============================================================
        # TEST 32 — Timeout
        # ============================================================

        print("\n[TEST 32] Command timeout")

        result = run_command(workspace, "sleep 35")

        print(result)

        assert "TIMEOUT" in result
        assert "10 seconds" in result

        # ============================================================
        # TEST 33 — Huge output / truncation
        # ============================================================

        print("\n[TEST 33] Huge command output")

        result = run_command(
            workspace,
            "python3 -c \"print('A' * 10000)\""
        )

        print(result)

        assert "truncated" in result
        assert "2000" in result

        # ============================================================
        # TEST 34 — Workdir outside root
        # ============================================================

        print("\n[TEST 34] Workdir outside root")

        result = run_command(
            workspace,
            "echo hello",
            workdir=".."
        )

        print(result)

        assert "outside the allowed root" in result

        # ============================================================
        # TEST 35 — Command does not exist
        # ============================================================

        print("\n[TEST 35] Non-existent command")

        result = run_command(
            workspace,
            "this_command_definitely_does_not_exist_12345"
        )

        print(result)

        assert "Exit code:" in result
        assert "Exit code: 0" not in result
        # TEST 36 — run_command can escape workspace through shell
        print("\n[TEST 36] run_command outside-root escape")

        escape_file = root.parent / "escaped_from_workspace.txt"
        escape_file.unlink(missing_ok=True)

        result = run_command(
            workspace,
            "echo ESCAPED > ../escaped_from_workspace.txt",
        )

        print(result)

        check(
            escape_file.exists(),
            "run_command did not demonstrate the outside-root write",
        )

        print("SECURITY TEST: command successfully wrote outside workspace.")

        escape_file.unlink(missing_ok=True)
        # ============================================================
        # TEST 32b — Timeout with partial stdout
        # ============================================================

        print("\n[TEST 32b] Timeout with partial output")

        result = run_command(
            workspace,
            "python3 -c \"print('before timeout', flush=True); import time; time.sleep(35)\""
        )

        print(result)

        assert "TIMEOUT" in result
        assert "before timeout" in result
        # ============================================================
        # Tests 37–41 — get_patch()
        # These tests use a SEPARATE temporary Git repository.
        # They do NOT touch the real project repository.
        # ============================================================

        print("\n========== GET_PATCH TESTS ==========")

        # Create a completely clean temporary Git workspace
        git_root = Path(tempfile.mkdtemp())
        git_workspace = LocalWorkspace(str(git_root))

        try:

            # --------------------------------------------------------
            # TEST 37 — Modify committed file → get_patch
            # --------------------------------------------------------
            print("\n[TEST 37] Modify committed file and get patch")

            subprocess.run(
                ["git", "init"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "config", "core.fileMode", "false"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            )
            # Git needs an identity for the test commit
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            )

            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            )

            # Create a file and commit it
            (git_root / "file1.txt").write_text(
                "original content\n",
                encoding="utf-8",
            )

            subprocess.run(
                ["git", "add", "file1.txt"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            )

            subprocess.run(
                ["git", "commit", "-m", "initial commit"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            )

            # Modify the committed file
            (git_root / "file1.txt").write_text(
                "modified content\n",
                encoding="utf-8",
            )

            result = get_patch(git_workspace)
            print(result)

            check(
                "file1.txt" in result,
                "file1.txt was not found in patch",
            )

            check(
                "modified content" in result,
                "modified content was not found in patch",
            )

            check(
                "git -c core.fileMode=false diff" in result,
                "expected diff command was not shown",
            )


            # --------------------------------------------------------
            # TEST 38 — No changes
            # --------------------------------------------------------
            print("\n[TEST 38] No changes")

            # Restore file to the committed version
            subprocess.run(
                ["git", "restore", "--staged", "."],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "restore", "."],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            )

            result = get_patch(git_workspace)
            print(result)

            check(
                "WARNING: No changes detected" in result,
                "empty-patch warning was not returned",
            )


            # --------------------------------------------------------
            # TEST 39 — Brand-new untracked file
            # --------------------------------------------------------
            print("\n[TEST 39] Brand-new untracked file")

            (git_root / "brand_new.py").write_text(
                "print('hello')\n",
                encoding="utf-8",
            )

            result = get_patch(git_workspace)
            print(result)

            check(
                "brand_new.py" in result,
                "new file was not included in patch",
            )

            check(
                "print('hello')" in result,
                "new file content was not included in patch",
            )


            # --------------------------------------------------------
            # TEST 40 — chmod +x committed file
            # --------------------------------------------------------
            print("\n[TEST 40] chmod +x committed file")

            # Remove the new file from the Git index
            subprocess.run(
                ["git", "restore", "--staged", "."],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            )

            # Remove the untracked new file
            subprocess.run(
                ["git", "clean", "-fd"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            )

            # Change only the permission of the committed file
            file1 = git_root / "file1.txt"
            file1.chmod(0o755)

            result = get_patch(git_workspace)
            print(result)

            check(
                "WARNING: No changes detected" in result,
                "chmod-only change was incorrectly included in patch",
            )

            # Restore normal permissions
            file1.chmod(0o644)


            # --------------------------------------------------------
            # TEST 41 — Stretch: clone repo and apply patch
            # --------------------------------------------------------
            print("\n[TEST 41] Apply patch to a fresh clone")

            # Make a real modification
            file1.write_text(
                "fresh clone test\n",
                encoding="utf-8",
            )

            patch_result = get_patch(git_workspace)
            print(patch_result)

            check(
                "--- patch ---" in patch_result,
                "patch section was not found",
            )

            # Extract the actual unified diff
            patch = patch_result.split(
                "--- patch ---\n\n",
                1,
            )[1]

            # Create clone OUTSIDE the source repository
            clone_root = git_root.parent / "fresh_clone"

            try:
                subprocess.run(
                    ["git", "clone", str(git_root), str(clone_root)],
                    check=True,
                    capture_output=True,
                    text=True,
                )

                # Apply the generated patch
                subprocess.run(
                    ["git", "apply"],
                    input=patch,
                    cwd=clone_root,
                    check=True,
                    capture_output=True,
                    text=True,
                )

                # Verify that the patch actually changed the cloned file
                cloned_file = clone_root / "file1.txt"

                check(
                    cloned_file.read_text(encoding="utf-8")
                    == "fresh clone test\n",
                    "patch did not correctly apply to the fresh clone",
                )

                print("Patch successfully applied to fresh clone.")

            finally:
                shutil.rmtree(clone_root, ignore_errors=True)
            # TEST 43 — Show the chmod mode-change ghost
            print("\n[TEST 43] Plain git diff shows chmod change")

            file1 = git_root / "file1.txt"

            # Make sure the repository itself considers file modes
            # when detecting changes.
            subprocess.run(
                ["git", "config", "core.fileMode", "true"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            )

            # Change only the executable bit.
            file1.chmod(0o755)

            plain_diff = subprocess.run(
                ["git", "diff"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            )

            print(plain_diff.stdout)

            check(
                "old mode 100644" in plain_diff.stdout,
                "plain git diff did not show the old file mode",
            )

            check(
                "new mode 100755" in plain_diff.stdout,
                "plain git diff did not show the new file mode",
            )

            print("Mode-change ghost confirmed.")

            # Clean up the mode change and restore the configuration
            file1.chmod(0o644)

            subprocess.run(
                ["git", "config", "core.fileMode", "false"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            )
            # TEST 4$ — get_patch outside a Git repository
            print("\n[TEST 4$] get_patch outside a Git repository")

            non_git_root = Path(tempfile.mkdtemp())
            non_git_workspace = LocalWorkspace(str(non_git_root))

            try:
                (non_git_root / "test.txt").write_text(
                    "hello\n",
                    encoding="utf-8",
                )

                result = get_patch(non_git_workspace)
                print(result)

                check(
                    "ERROR: this workspace is not a git repository" in result,
                    "get_patch did not return a proper Git error",
                )

                check(
                    "not a git repository" in result,
                    "Git repository error was not reported",
                )

            finally:
                shutil.rmtree(non_git_root, ignore_errors=True)

        # finally:
        #     # Remove the temporary Git repository
        #     shutil.rmtree(git_root, ignore_errors=True)
            # ============================================================
            # SMOKE TESTS 42–51
            # ============================================================

            # ------------------------------------------------------------
            # 42. Search a word that exists
            # ------------------------------------------------------------
            print("\n[TEST 42] Search existing word")
            test_file = workspace.root_dir / "smoke42.py"
            test_file.write_text(
                "first_line = 123\n"
                "smoke_search_target_42 = True\n"
                "last_line = 456\n",
                encoding="utf-8",
            )

            result = search_code(
                workspace,
                "smoke_search_target_42",
                "*.py",
            )

            expected_path = str(test_file.resolve())
            assert f"{expected_path}:2 smoke_search_target_42 = True" in result
            print("  ✓ Found target on expected line.")


            # ------------------------------------------------------------
            # 43. Search word that does not exist
            # ------------------------------------------------------------
            print("\n[TEST 43] Search no matches")
            result = search_code(
                workspace,
                "definitely_missing_symbol_43",
                "*.py",
            )

            assert "No matches found" in result
            assert (
                "spelling" in result.lower()
                or "definition" in result.lower()
                or "file_pattern" in result.lower()
            )
            print("  ✓ Correctly reported no matches.")

            # ------------------------------------------------------------
            # 44. Search using file_pattern="*.py"
            # ------------------------------------------------------------
            print("\n[TEST 44] Search file pattern")
            py_file = workspace.root_dir / "smoke44.py"
            txt_file = workspace.root_dir / "smoke44.txt"

            py_file.write_text(
                "smoke_pattern_target_44 = True\n",
                encoding="utf-8",
            )

            txt_file.write_text(
                "smoke_pattern_target_44 = True\n",
                encoding="utf-8",
            )

            result = search_code(
                workspace,
                "smoke_pattern_target_44",
                "*.py",
            )

            py_path = str(py_file.resolve())
            txt_path = str(txt_file.resolve())

            assert py_path in result
            assert txt_path not in result
            print("  ✓ Matched .py file and ignored .txt file.")

            # ------------------------------------------------------------
            # 45. Search must ignore .git/
            # ------------------------------------------------------------
            print("\n[TEST 45] Search ignores .git")
            git_dir = workspace.root_dir / ".git"
            git_dir.mkdir(exist_ok=True)

            git_file = git_dir / "internal.txt"
            git_file.write_text(
                "smoke_git_target_45 = True\n",
                encoding="utf-8",
            )

            normal_file = workspace.root_dir / "normal45.py"
            normal_file.write_text(
                "smoke_git_target_45 = True\n",
                encoding="utf-8",
            )

            result = search_code(
                workspace,
                "smoke_git_target_45",
                "*",
            )

            normal_path = str(normal_file.resolve())
            git_path = str(git_file.resolve())

            assert normal_path in result
            assert git_path not in result
            assert ".git" not in result
            print("  ✓ Skipped .git directory during search.")

            # ------------------------------------------------------------
            # 46. Broken regex
            # ------------------------------------------------------------
            print("\n[TEST 46] Broken regex")
            result = search_code(
                workspace,
                "(",
                "*.py",
            )

            assert "invalid regex" in result.lower()
            assert "error" in result.lower() or "regex" in result.lower()
            print("  ✓ Gracefully caught invalid regex syntax.")

            # ------------------------------------------------------------
            # 47. More than 100 matches
            # ------------------------------------------------------------
            print("\n[TEST 47] Search pagination")
            test_file = workspace.root_dir / "smoke47.py"

            lines = [
                f"smoke_pagination_target_47_{i} = True\n"
                for i in range(301)
            ]

            test_file.write_text(
                "".join(lines),
                encoding="utf-8",
            )

            # First page
            result_page_1 = search_code(
                workspace,
                "smoke_pagination_target_47",
                "*.py",
                offset=0,
            )

            assert "Showing matches 1-100 of 301" in result_page_1
            assert "offset=100" in result_page_1

            # Second page
            result_page_2 = search_code(
                workspace,
                "smoke_pagination_target_47",
                "*.py",
                offset=100,
            )

            assert "Showing matches 101-200 of 301" in result_page_2
            assert "offset=200" in result_page_2

            # Make sure page 2 actually contains a later match
            assert "smoke_pagination_target_47_100" in result_page_2

            # Make sure page 2 does not start with page 1's first result
            assert "smoke_pagination_target_47_0" not in result_page_2
            print("  ✓ Pagination pages 1 and 2 returned expected offsets.")

            # ------------------------------------------------------------
            # 48. Definition search — function
            # ------------------------------------------------------------
            print("\n[TEST 48] Definition search function")
            test_file = workspace.root_dir / "smoke48.py"

            test_file.write_text(
                "def something_else():\n"
                "    pass\n"
                "\n"
                "def SmokeFunction48():\n"
                "    return True\n",
                encoding="utf-8",
            )

            result = search_function_or_class_definition_in_code(
                workspace,
                "SmokeFunction48",
                "*.py",
            )

            expected_path = str(test_file.resolve())

            assert expected_path in result
            assert ":4 " in result
            assert "def SmokeFunction48():" in result
            print("  ✓ Located function definition at line 4.")

            # ------------------------------------------------------------
            # 49. Definition search — class
            # ------------------------------------------------------------
            print("\n[TEST 49] Definition search class")
            test_file = workspace.root_dir / "smoke49.py"

            test_file.write_text(
                "class SomethingElse:\n"
                "    pass\n"
                "\n"
                "class SmokeClass49:\n"
                "    pass\n",
                encoding="utf-8",
            )

            result = search_function_or_class_definition_in_code(
                workspace,
                "SmokeClass49",
                "*.py",
            )

            expected_path = str(test_file.resolve())

            assert expected_path in result
            assert ":4 " in result
            assert "class SmokeClass49:" in result
            print("  ✓ Located class definition at line 4.")

            # ------------------------------------------------------------
            # 50. Definition does not exist
            # ------------------------------------------------------------
            print("\n[TEST 50] Definition not found")
            result = search_function_or_class_definition_in_code(
                workspace,
                "definitely_missing_symbol_50",
                "*.py",
            )

            assert "No matches found" in result
            print("  ✓ Correctly reported missing definition.")

            # ------------------------------------------------------------
            # 51. Syntax-error file must not crash definition search
            # ------------------------------------------------------------
            print("\n[TEST 51] Definition search survives syntax error")
            broken_file = workspace.root_dir / "broken51.py"
            valid_file = workspace.root_dir / "valid51.py"

            # Deliberately invalid Python
            broken_file.write_text(
                "def broken_function_51(\n"
                "    this is invalid python\n",
                encoding="utf-8",
            )

            # Valid Python containing the definition we're searching for
            valid_file.write_text(
                "def SmokeFunction51():\n"
                "    return True\n",
                encoding="utf-8",
            )

            result = search_function_or_class_definition_in_code(
                workspace,
                "SmokeFunction51",
                "*.py",
            )

            expected_path = str(valid_file.resolve())

            # The valid file must still be searched
            assert expected_path in result
            assert "def SmokeFunction51():" in result

            # The broken file should not appear as a result
            assert str(broken_file.resolve()) not in result
            print("  ✓ Successfully ignored syntax-error file and found target in valid file.")
            # ============================================================
            # TEST 52 — find_references: absolute path inside workspace
            # ============================================================

            print("\n[TEST 52] find_references with absolute path")

            definition_file_52 = workspace.root_dir / "definition52.py"
            reference_file_52 = workspace.root_dir / "reference52.py"

            definition_file_52.write_text(
                "def ReferenceTarget52():\n"
                "    return True\n",
                encoding="utf-8",
            )

            reference_file_52.write_text(
                "result = ReferenceTarget52()\n",
                encoding="utf-8",
            )

            result = find_references(
                workspace,
                "ReferenceTarget52",
                str(definition_file_52.resolve()),
                1,
            )

            print(result)

            # The reference in the other file must be found.
            check(
                "reference52.py" in result,
                "absolute filepath inside workspace was not handled correctly",
            )

            # The definition itself must not be returned.
            check(
                "definition52.py:1" not in result,
                "definition itself was not excluded",
            )

            print("  ✓ Absolute path inside workspace accepted.")


            # ============================================================
            # TEST 53 — find_references: relative path
            # ============================================================

            print("\n[TEST 53] find_references with relative path")

            references53 = workspace.root_dir / "references53.py"

            references53.write_text(
                "def ReferenceTarget53():\n"
                "    return True\n",
                encoding="utf-8",
            )

            result = find_references(
                workspace,
                "ReferenceTarget53",
                "references53.py",
                1,
            )

            print(result)

            check(
                "references53.py" in result
                or str(references53.resolve()) in result,
                "relative filepath was not handled correctly",
            )

            print("  ✓ Relative path accepted.")


            # ============================================================
            # TEST 54 — find_references: filepath outside workspace
            # ============================================================

            print("\n[TEST 54] find_references outside workspace")

            result = find_references(
                workspace,
                "ReferenceTarget54",
                "../outside_references54.py",
                1,
            )

            print(result)

            check(
                "outside" in result.lower()
                or "allowed root" in result.lower(),
                "outside-root filepath was not rejected",
            )

            print("  ✓ Outside-root filepath correctly rejected.")


            # ============================================================
            # TEST 55 — find_references: hallucinated/non-existent filepath
            # ============================================================

            print("\n[TEST 55] find_references hallucinated filepath")

            result = find_references(
                workspace,
                "ReferenceTarget55",
                "this_file_does_not_exist_55.py",
                1,
            )

            print(result)

            check(
                "not found" in result.lower()
                or "does not exist" in result.lower()
                or "file not found" in result.lower(),
                "hallucinated filepath did not return a useful error",
            )

            print("  ✓ Non-existent filepath correctly rejected.")


            # ============================================================
            # TEST 56 — find_references:
            #          exclude definition + find cross-file references
            # ============================================================

            print("\n[TEST 56] find_references definition exclusion + cross-file")

            definition_file = workspace.root_dir / "definition56.py"
            reference_file = workspace.root_dir / "reference56.py"

            definition_file.write_text(
                "def ReferenceTarget56():\n"
                "    return True\n",
                encoding="utf-8",
            )

            reference_file.write_text(
                "from definition56 import ReferenceTarget56\n"
                "\n"
                "result = ReferenceTarget56()\n"
                "another = ReferenceTarget56()\n",
                encoding="utf-8",
            )

            result = find_references(
                workspace,
                "ReferenceTarget56",
                "definition56.py",
                1,
            )

            print(result)

            # The reference file must be found.
            check(
                "reference56.py" in result,
                "cross-file reference was not found",
            )

            # The actual definition line must NOT be returned.
            check(
                "definition56.py:1" not in result,
                "definition itself was not excluded",
            )

            # The actual references should be present.
            check(
                "reference56.py:1" in result,
                "import/reference on line 1 was not found",
            )

            check(
                "reference56.py:3" in result,
                "reference on line 3 was not found",
            )

            check(
                "reference56.py:4" in result,
                "reference on line 4 was not found",
            )

            print("  ✓ Definition excluded and cross-file references found.")


            # ============================================================
            # TEST 57 — find_references pagination
            # ============================================================

            print("\n[TEST 57] find_references pagination")

            definition_file_57 = workspace.root_dir / "definition57.py"
            definition_file_57.write_text(
                "def ReferenceTarget57():\n"
                "    return True\n",
                encoding="utf-8",
            )

            # Create more than 100 references across multiple files.
            for i in range(101):
                reference_file_57 = (
                    workspace.root_dir / f"reference57_{i:03}.py"
                )

                reference_file_57.write_text(
                    f"ReferenceTarget57()\n",
                    encoding="utf-8",
                )

            # First page.
            result_page_1 = find_references(
                workspace,
                "ReferenceTarget57",
                "definition57.py",
                1,
                offset=0,
            )

            print(result_page_1)

            check(
                "Showing matches 1-100 of 101" in result_page_1,
                "first find_references page is incorrect",
            )

            check(
                "offset=100" in result_page_1,
                "find_references continuation offset is missing",
            )

            # Second page.
            result_page_2 = find_references(
                workspace,
                "ReferenceTarget57",
                "definition57.py",
                1,
                offset=100,
            )

            print(result_page_2)

            check(
                "Showing matches 101-101 of 101" in result_page_2,
                "second find_references page is incorrect",
            )

            check(
                "reference57_" in result_page_2,
                "second page did not contain the final reference",
            )

            check(
                "reference57_000.py" not in result_page_2,
                "second page incorrectly repeated the first reference",
            )

            print("  ✓ find_references pagination works correctly.")
        finally:
        # Remove the temporary Git repository
            shutil.rmtree(git_root, ignore_errors=True)
    print("\nALL GOOD")


if __name__ == "__main__":
    main()
    # to run: uv run python -m tests.test_tools
