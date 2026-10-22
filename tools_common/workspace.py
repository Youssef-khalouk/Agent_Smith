from pathlib import Path
from .docker_manager import ContainerManager
import os
import tempfile
import fnmatch
import subprocess
import re
import ast

# handles opening files, checking paths, and listing directory contents on
# your local computer. It acts as the worker that read_file talks to


# class EditError(Exception):
#     pass

LINE_CAP = 2000


class StringNotFoundError(Exception):
    pass


class MultipleMatchesError(Exception):
    def __init__(self, line_numbers, old_str):
        self.line_numbers = line_numbers
        self.old_str = old_str
        super().__init__(f"Multiple matches found at lines: {line_numbers}. "
                         f"Expand {old_str} with surrounding lines to make it "
                         f"unique.")


class EmptyStringError(Exception):
    pass


class PathOutsideRootError(Exception):
    pass


class LocalWorkspace():
    def __init__(self, root_dir: str):
        # Path(root_dir) converts root_dir into a Path object.
        # This gives us access to Path methods such as .resolve().
        # .resolve() converts the path into an absolute path.
        # The resulting Path object is stored in self.root_path.
        self.root_dir = Path(root_dir).resolve()

    def read_file_text(self, relative_path: str) -> str:
        # Combine the root directory with the requested relative path,
        # then resolve it to get the actual absolute path.
        target_file_path = (self.root_dir / relative_path).resolve()
        # Combine the root directory with the requested relative path.
        # .resolve() converts the resulting path into its absolute/real path.
        # This is important for the security check below, so paths like
        # "../file.txt"
        # can be detected if they try to escape the root directory.
        # Make sure the requested path did not escape the root directory.
        if not target_file_path.is_relative_to(self.root_dir):
            raise PathOutsideRootError("Path is outside the root directory")
        # Make sure the requested path actually exists.
        if not target_file_path.exists():
            raise FileNotFoundError(target_file_path)
        # Make sure the path points to a file, not a directory.
        if target_file_path.is_dir():
            raise IsADirectoryError(target_file_path)
        # Read the file's text content.
        content = target_file_path.read_text(encoding="utf-8")
        return content

    def atomic_write(self, target_path: Path, content: str) -> None:
        parent_folder = Path(target_path).parent
        # Create a temporary file in the same directory as the target.
        # Create and open a temporary file in the same directory as the target.
        # fd is the file descriptor (a number used by the OS to identify the
        # open file).
        # temp_path is the path of the temporary file.
        fd, temp_path = tempfile.mkstemp(dir=parent_folder)
        try:
            # Convert the file descriptor into a normal Python file object.
            # This lets us use methods like .write() and .flush().
            with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
                # Write the new content
                temp_file.write(content)
                # Make sure Python sends the data to the operating system.
                temp_file.flush()
                # .fileno() gets the file descriptor of the Python file object.
                # fileno() is needed because os.fsync() requires the file
                # descriptor
                # that represents the file we want to force to disk.
                # fsync() asks the operating system to physically write the
                # data to disk.
                os.fsync(temp_file.fileno())
            # Replace the old file with the temporary file.
            temp_file_path = Path(temp_path)
            temp_file_path.replace(target_path)
        except Exception:
            # If something went wrong before the replacement,
            # delete the temporary file. do not raise if it does not exist
            Path(temp_path).unlink(missing_ok=True)
            # Re-raise the original error.
            raise

    def edit_file_text(self, filepath: str, old_str: str, new_str: str) -> int:
        if old_str == "":
            raise EmptyStringError("Error: old_str cannot be empty")
        content = self.read_file_text(filepath)
        start = 0
        matches = []
        # read the whole thing until it finds it, if 0 occurences, break!
        while True:
            # idx is at 0 thanks to start = 0(starts from start)
            idx = content.find(old_str, start)
            # if the WHOLE file has no old_str, break!
            if idx == -1:
                break
            # found it! how many lines til idx did we cross to find it (+ 1
            # for 1 indexing)
            # that number of lines is the line number of where the change
            # needs to happen
            line_number = content[:idx].count("\n") + 1
            # put it in the list to check if one or many! HOPE JUST ONE!
            matches.append(line_number)
            # jump the rest of the word and keep searching again
            start = idx + len(old_str)
        if len(matches) > 1:
            raise MultipleMatchesError(matches, old_str)
        if len(matches) == 0:
            raise StringNotFoundError(
                f"Error:{old_str} not found in {filepath}."
                f" Call read_file to inspect and copy "
                f"exact lines and indentation.")
        # check if the original file ended with a new line or not
        ended_with_new_line = content.endswith("\n")
        # replace the old with new match (SINGULAR), 1: one time only
        new_content = content.replace(old_str, new_str, 1)
        # if content ends with "\n" and new content does not, add it!
        if ended_with_new_line and not new_content.endswith("\n"):
            new_content += "\n"
        target_file_path = (self.root_dir / filepath).resolve()
        self.atomic_write(target_file_path, new_content)
        # Return the line where the replacement happened
        return matches[0]

    def list_directory_entries(self, directory: str = ".",
                               pattern: str = "*", offset: int = 0) -> tuple[
                                list[str], int, bool]:
        # ".": Show me what's inside the workspace root.
        # pattern="*.py": show only .py but want EVERYTHING (files&folders)
        if offset < 0:
            raise ValueError("offset cannot be negative")
        dir_path = (self.root_dir / directory).resolve()
        if not dir_path.is_relative_to(self.root_dir):
            raise PathOutsideRootError("Path is outside the root directory")
        if not dir_path.exists():
            raise FileNotFoundError(dir_path)
        if not dir_path.is_dir():
            raise NotADirectoryError(dir_path)
        is_filled = any(dir_path.iterdir())
        matched_entries = []
        # entry (a path object) can be .py, an inner folder....
        for entry in dir_path.iterdir():
            # if we found what we are looking for
            if fnmatch.fnmatch(entry.name, pattern):
                # relative_path gives src/main.py instead of
                # /home/user/project/src/main.py
                # attaches only the parent directory
                relative_path = str(entry.relative_to(self.root_dir))
                # issue: entry name does not add "/" to the directory
                # which is needed to indicate that it is a dir not a file
                if entry.is_dir():
                    matched_entries.append(relative_path + "/")
                else:
                    matched_entries.append(relative_path)
        matched_entries = sorted(matched_entries)
        total_count = len(matched_entries)
        matched_entries = matched_entries[offset: offset + 100]
        return (matched_entries, total_count, is_filled)

    def run_command_in_folder(self, command: str, folder_path: str,
                              timeout: int = 60):
        # self.root = sandbox
        # folder_path = working directory that is HOPEFULLY inside sandbox
        target_folder = (self.root_dir / folder_path).resolve()
        if not target_folder.is_relative_to(self.root_dir):
            raise PathOutsideRootError("outside root")
        if not target_folder.exists():
            raise FileNotFoundError(target_folder)
        if not target_folder.is_dir():
            raise NotADirectoryError(target_folder)
        try:
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
                cwd=target_folder,
                # shell=True to support shell features (pipes, wildcards, &&)
                #  by spawning system shell to translate and allow passing
                # he command as a single raw string or with spaces.
                shell=True,
                timeout=timeout
                )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
                "timed_out": False,
            }
        except subprocess.TimeoutExpired as e:
            # Python stores whatever the process managed to print inside the
            # TimeoutExpired exception object
            stdout = e.stdout or ""
            stderr = e.stderr or ""
            # need to decode if they are bytes
            # Convert bytes to UTF-8 text. If invalid/corrupted bytes
            # are encountered, errors="replace" replaces them with '' instead
            # of throwing a UnicodeDecodeError
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            return {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": None,
                "timed_out": True,
            }

    def search_files_for_pattern(self, pattern, file_pattern, offset):
        # pattern → the regex we're searching for
        # file_pattern → which filenames to search, such as *.py
        # offset → pagination, just like list_files
        matches = []
        ignored_dir = {".git", "__pycache__", ".pytest_cache", "node_modules",
                       ".venv", "venv"}
        if offset < 0:
            raise ValueError("offset cannot be negative")
        if pattern.strip() == "":
            return ("The search pattern cannot be empty. "
                    "Provide a regex pattern to search for.")
        # check if llm provided broken regex: "def("
        # parses it upfront and stores it in memory
        # rejex_obj is like a pointer to it so we dont re-parse again
        # makes searching easier using regex object
        regex_obj = re.compile(pattern)
        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            # dirpath → the current directory absolute path from self.root_dir
            # til the current folder being visited
            # dirnames → list of subdirectory names inside dirpath
            # filenames → list of file names (non directories) inside dirpath
            # [:] in place so we modify the original list of dirs
            dirnames[:] = [d for d in dirnames if d not in ignored_dir]
            for filename in filenames:
                if not fnmatch.fnmatch(filename, file_pattern):
                    continue
                file_path = Path(dirpath) / filename
                try:
                    with open(file_path, "r", encoding="utf-8") as fd:
                        text = fd.read()
                except UnicodeDecodeError:
                    # skip .png or ....
                    continue
                text_lines = text.splitlines()
                for line_num, line in enumerate(text_lines, start=1):
                    if regex_obj.search(line):
                        # we do not want the full path, just relative
                        # so src/main.py NOT /home/.../workspace/src/main.py
                        # code_search.py will turn it to full path
                        relative_path = file_path.relative_to(self.root_dir)
                        line_number = line_num
                        line_text = line
                        line_length = len(line_text)
                        if len(line_text) > LINE_CAP:
                            line_text = line_text[:LINE_CAP]
                            line_text += (f"[line truncated: showing first "
                                          f"{LINE_CAP} of "
                                          f"{line_length} characters]")
                        matches.append((relative_path, line_number, line_text))
        matches_num = len(matches)
        matches = matches[offset: offset + 100]
        return (matches, matches_num)

    def search_function_or_class_definitions(self, name, file_pattern, offset):
        ignored_dir = {".git", "__pycache__", ".pytest_cache", "node_modules",
                       ".venv", "venv"}
        matches = []
        if offset < 0:
            raise ValueError("offset cannot be negative")
        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            dirnames[:] = [d for d in dirnames if d not in ignored_dir]
            for filename in filenames:
                if not fnmatch.fnmatch(filename, file_pattern):
                    continue
                try:
                    file_path = Path(dirpath) / filename
                    with open(file_path, "r", encoding="utf-8") as fd:
                        code = fd.read()
                except UnicodeDecodeError:
                    continue
                try:
                    tree = ast.parse(code)
                except SyntaxError:
                    continue
                lines = code.splitlines()
                relative_path = file_path.relative_to(self.root_dir)
                for node in ast.walk(tree):
                    if isinstance(
                        node, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
                        if node.name == name:
                            line_text = lines[node.lineno - 1]
                            line_length = len(line_text)
                            if len(line_text) > LINE_CAP:
                                line_text = line_text[:LINE_CAP]
                                line_text += (f"[line truncated: showing first"
                                              f" {LINE_CAP} of "
                                              f"{line_length} characters]")
                            matches.append(
                                (relative_path, node.lineno, line_text))
        matches_num = len(matches)
        matches = matches[offset: offset + 100]
        return (matches, matches_num)

    def find_name_references(
            self,
            name,
            filepath,
            line,
            file_pattern,
            offset):
        matches = []
        ignored_dir = {".git", "__pycache__", ".pytest_cache", "node_modules",
                       ".venv", "venv"}
        if name.strip() == "":
            raise ValueError("reference name cannot be empty")
        if offset < 0:
            raise ValueError("offset cannot be negative")
        try:
            unwanted_line = int(line)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid line number: '{line}'. "
                             f"Line must be an integer.")
        unwanted_file_path = (self.root_dir / filepath).resolve()
        if not unwanted_file_path.is_relative_to(self.root_dir):
            raise PathOutsideRootError("Path is outside the root directory")
        if not unwanted_file_path.exists():
            raise FileNotFoundError(
                f"Definition file '{filepath}' was not found in the workspace."
            )
        if not unwanted_file_path.is_file():
            raise IsADirectoryError(unwanted_file_path)
        unwanted_rel_path = unwanted_file_path.relative_to(
            self.root_dir.resolve())
        regex = re.compile(rf"\b{re.escape(name)}\b")
        # r (Raw string): Tells Python to treat backslashes literally (so \b
        # means a regex word boundary, not a backspace control character)
        # f (Formatted string): Allows to inject variables inside curly braces
        # \b matches a word boundary (the invisible edge between a word
        # character and a non-word character, like a space, parenthesis, or
        # punctuation). ex: runner or brunt will be ignored looking for "run"
        # re.escape() automatically puts a escape slash in front of any
        # special regex characters so they are treated as literal characters.
        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            dirnames[:] = [d for d in dirnames if d not in ignored_dir]
            for filename in filenames:
                if not fnmatch.fnmatch(filename, file_pattern):
                    continue
                try:
                    file_path = Path(dirpath) / filename
                    with open(file_path, "r", encoding="utf-8") as fd:
                        code = fd.read()
                except UnicodeDecodeError:
                    continue
                lines = code.splitlines()
                relative_path = file_path.relative_to(self.root_dir)
                for line_num, line_text in enumerate(lines, start=1):
                    if (relative_path == unwanted_rel_path and
                            line_num == unwanted_line):
                        continue
                    if regex.search(line_text):
                        line_length = len(line_text)
                        if len(line_text) > LINE_CAP:
                            line_text = line_text[:LINE_CAP]
                            line_text += (f"[line truncated: showing first "
                                          f"{LINE_CAP} of "
                                          f"{line_length} characters]")
                        matches.append((relative_path, line_num, line_text))
        matches_num = len(matches)
        matches = matches[offset: offset + 100]
        return (matches, matches_num)


class DockerWorkspace:
    def __init__(self, host_repo_path,
                 image_name="swebench/sweb.eval.x86_64.sympy_1776_sympy-14711"
                 ):
        self.host_repo_path = host_repo_path
        self.root_dir = self.host_repo_path
        self.image_name = image_name
        self.container_manager = ContainerManager(image_name, host_repo_path)
        self.local_workspace = LocalWorkspace(self.host_repo_path)

    def start(self):
        self.container_manager.pull()
        self.container_manager.extract()
        self.container_manager.start()

    def die(self):
        self.container_manager.die()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.die()

    def read_file_text(self, relative_path: str):
        return self.local_workspace.read_file_text(relative_path)

    def edit_file_text(self, filepath: str, old_str: str, new_str: str):
        return self.local_workspace.edit_file_text(filepath, old_str, new_str)

    def list_directory_entries(self, directory: str = ".",
                               pattern: str = "*", offset: int = 0):
        return self.local_workspace.list_directory_entries(
            directory, pattern, offset)

    def search_files_for_pattern(self, pattern, file_pattern, offset):
        return self.local_workspace.search_files_for_pattern(
            pattern, file_pattern, offset
        )

    def search_function_or_class_definitions(
            self, name, file_pattern, offset
                ):
        return self.local_workspace.search_function_or_class_definitions(
            name, file_pattern, offset
        )

    def find_name_references(
            self, name, file_path, line, file_pattern, offset
            ):
        return self.local_workspace.find_name_references(
            name, file_path, line, file_pattern, offset
        )

    def run_command_in_folder(self, command: str, folder_path: str,
                              timeout: int = 60):
        # executes the command inside the container in /testbed and returns
        # standard facts packet (stdout, stderr, exit_code, timed_out).
        # git command will use this too to run it inside container.
        target_folder = (Path(self.root_dir) / folder_path).resolve()
        if not target_folder.is_relative_to(self.root_dir):
            raise PathOutsideRootError("outside root")
        return self.container_manager.exec(command, folder_path, timeout)


# with DockerWorkspace("/home/ouchouir/agent") as dw:
#     print(dw.container_manager.container.status)
# print(dw.container_manager.container)
# dw = DockerWorkspace("/home/ouchouir/agent")
# dw.start()
# first = dw.container_manager.container.id
# dw.start()
# second = dw.container_manager.container.id
# assert first == second, "start() must be idempotent — same container!"
# dw.die()
# ----------------------------------------
# # run with uv run python -m tools_common.workspace
