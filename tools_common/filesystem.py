# contains the read_file tool that the LLM/Agent actually calls. It relies on
# workspace to fetch text, then formats it with line numbers and returns
# helpful error messages.
from tools_common.workspace import (
    StringNotFoundError,
    MultipleMatchesError,
    EmptyStringError,
    LocalWorkspace,
    PathOutsideRootError,
)

# Reading too many lines at once can produce a large amount of text,
# which means more tokens are sent to the LLM.
# The LLM also uses tokens when generating code/tool calls.
# Therefore, limiting each read helps the agent use its context/tokens
# efficiently while still allowing it to inspect larger files in chunks.
# Example:
# 200 lines -> manageable amount of context
# 10,000 lines -> thousands of tokens and lots of irrelevant information
# If the LLM needs more than 200 lines, it can request another chunk.
MAX_LINE_LIMIT = 200


def format_cat_n(lines: list[str], start_line_num: int = 1) -> str:
    formatted_lines = []
    for num, line in enumerate(lines, start=start_line_num):
        formatted_lines.append(f"{num:>6}: {line}")
    return "\n".join(formatted_lines)


def read_file(workspace: LocalWorkspace, filepath: str, start_line: int = 1,
              end_line: int = -1):
    try:
        raw_text = workspace.read_file_text(filepath)
    except FileNotFoundError:
        return (f"Error: File '{filepath}' does not exist. "
                f"Call list_files(directory='.') to discover valid files.")
    except IsADirectoryError:
        return (f"Error: '{filepath}' is a directory, not a file. "
                f"Call list_files(directory='{filepath}') to "
                f"explore its contents.")
    except PathOutsideRootError:
        return (f"Error: Path '{filepath}' is outside the allowed root "
                f"'{workspace.root_dir}'. Re-issue using a path inside "
                f"'{workspace.root_dir}'.")
    except UnicodeDecodeError:
        return (
            f"Error: File '{filepath}' is a binary or non-UTF-8 file — "
            f"reading it as line-by-line text is not supported. If you"
            f" expected source code or text, verify the path using list_files."
        )
    except PermissionError:
        return (
            "Error: the operating system refused to read — the file may "
            "be protected")
    lines = raw_text.splitlines()
    if not lines:
        return f"File '{filepath}' is empty."
    if start_line < 1:
        return (f"Error: start_line ({start_line}) "
                f"must be >= 1 (1-based indexing).")
    total_lines = len(lines)
    if start_line > len(lines):
        return (f"Error: start_line ({start_line}) is out of bounds. File "
                f"'{filepath}' contains {total_lines} lines "
                f"(valid range: 1–{total_lines}).")
    if end_line == -1:
        target_end = min(start_line + MAX_LINE_LIMIT - 1, total_lines)
    else:
        target_end = min(end_line, total_lines)
    if start_line > target_end:
        return (
            f"Error: start_line ({start_line}) cannot be greater than "
            f"end_line ({target_end}). "
            f"File has {total_lines} lines. Note that bounds "
            f"are 1-based and inclusive."
        )
    start_idx = start_line - 1
    # Prevent reading more than MAX_LINE_LIMIT lines in a single call
    if (target_end - start_idx) > MAX_LINE_LIMIT:
        target_end = start_idx + MAX_LINE_LIMIT

    sliced_lines = lines[start_idx:target_end]
    output = format_cat_n(sliced_lines, start_line_num=start_line)

    # 5. Append pagination hint if truncated
    if target_end < total_lines and (end_line == -1 or target_end < end_line):
        next_start = target_end + 1
        output += (f"\n\n... [Truncated: File '{filepath}' has {total_lines} "
                   f"lines total. Showing lines {start_line}–{target_end}. "
                   f"Call read_file with start_line={next_start} to continue.]"
                   )
    return output


def edit_file(workspace: LocalWorkspace, filepath: str,
              old_str: str, new_str: str) -> str:
    if old_str == new_str:
        return "Error: new_str is identical to old_str. No changes made."
    try:
        line_number = workspace.edit_file_text(filepath, old_str, new_str)
    except StringNotFoundError:
        return (f"Error: '{old_str}' not found in '{filepath}'. "
                f"Call read_file to"
                f" inspect exact lines, indentation and spacing")
    except MultipleMatchesError as e:
        # map: iterate on each number on the list and turn them to strings
        # map = ", ".join(["5", "18", "32"])
        lines = ", ".join(map(str, e.line_numbers))
        return (
            f"Error: '{old_str}' found multiple times at lines: {lines}."
            f" Expand '{old_str}' with surrounding lines to make it unique.")
    except EmptyStringError:
        return "Error: old_str cannot be empty."
    except FileNotFoundError:
        return (
            f"Error: file '{filepath}' not found. Call "
            f"list_files(directory='.') to inspect available files.")
    except IsADirectoryError:
        return (f"Error: '{filepath}' is a directory. Call"
                f" list_files(directory='{filepath}') instead.")
    except PathOutsideRootError:
        return (
            f"Error: '{filepath}' is outside the workspace root. "
            f"'{workspace.root_dir}'. Only files inside the workspace can be "
            "edited."
        )
    except PermissionError:
        return (
            "Error: the operating system refused to write — the file may be "
            "read-only or protected")
    context_start = max(1, line_number - 3)
    context_end = line_number + 3
    context = read_file(workspace, filepath, context_start, context_end)
    return (
        f"Successfully edited '{filepath}' on line {line_number}.\n\n"
        f"Context around the edit:\n{context}")


def list_files(workspace: LocalWorkspace, directory: str = ".",
               pattern: str = "*", offset: int = 0) -> str:
    if not pattern or not pattern.strip():
        pattern = "*"
    try:
        entries, total_count, is_filled = workspace.list_directory_entries(
            directory, pattern, offset)
    except FileNotFoundError:
        return (
            f"Error: directory '{directory}' not found. "
            f"Check the path and call list_files on the parent directory.")
    except NotADirectoryError:
        return (
            f"Error: '{directory}' is not a directory."
        )
    except PathOutsideRootError:
        return (
            f"Error: Path '{directory}' is outside the allowed root "
            f"workspace '{workspace.root_dir}'."
            )
    except PermissionError:
        return (
            "Error: the operating system refused to show files — the file may "
            "be protected")
    except ValueError:  # for negative offset
        return "Error: offset cannot be negative."
    if not is_filled:
        return (
            f"Directory '{directory}' is empty."
        )
    if total_count == 0:
        return (f"No match for '{pattern}' in '{directory}' check the parent "
                "directory with list_files")
    result = "\n".join(entries)
    start = offset + 1  # 101
    end = offset + len(entries)  # 200
    result = (
        f"Showing entries {start}-{end} of {total_count}.\n\n"
        + result
    )
    if end < total_count:
        result += (
            f"\n\nMore entries are available. "
            f"Call list_files with offset={end} to continue."
        )
    return result
