import re
from tools_common.workspace import LocalWorkspace, PathOutsideRootError


def search_code(
            workspace: LocalWorkspace,
            pattern: str,
            file_pattern: str = "*.py",
            offset: int = 0,
        ) -> str:
    formatted_result = []
    try:
        capped_matches, total_matches = workspace.search_files_for_pattern(
            pattern,
            file_pattern,
            offset
        )
    except re.error as err:
        return (
                f"INVALID REGEX ERROR: The pattern '{pattern}' is "
                f"invalid ({err}). fix the regex syntax and "
                f"try again."
                )
    except ValueError:
        return "ERROR: offset cannot be negative"
    for match in capped_matches:
        relative_path, line_number, line_text = match
        absolute_path = (workspace.root_dir / relative_path).resolve()
        formatted_result.append(
            f"{absolute_path}:{line_number} {line_text}"
        )
    if not formatted_result:
        return (f"No matches found for pattern {pattern} in files matching"
                f" {file_pattern}. Try a broader pattern or a different "
                f"file_pattern.")
    start = offset + 1
    end = len(capped_matches) + offset
    result = f"Showing matches {start}-{end} of {total_matches}.\n\n"
    result += "\n".join(formatted_result)
    if end < total_matches:
        result += (f"More matches are available. Call search_code "
                   f"with offset={end} to continue.")
    return result


def search_function_or_class_definition_in_code(
            workspace: LocalWorkspace,
            name: str,
            file_pattern: str = "*.py",
            offset: int = 0,
        ) -> str:
    formatted_result = []
    try:
        capped_matches, total_matches = (
            workspace.search_function_or_class_definitions(
                name, file_pattern, offset
            )
        )
    except ValueError:
        return "offset cannot be negative"
    for match in capped_matches:
        relative_path, line_number, line_text = match
        absolute_path = (workspace.root_dir / relative_path).resolve()
        formatted_result.append(
            f"{absolute_path}:{line_number} {line_text}"
        )
    if not formatted_result:
        return (f"No matches found for name {name} in files matching"
                f" {file_pattern}. Try a broader pattern or a different "
                f"file_pattern.")
    start = offset + 1
    end = len(capped_matches) + offset
    result = f"Showing matches {start}-{end} of {total_matches}.\n\n"
    result += "\n".join(formatted_result)
    if end < total_matches:
        result += (f"More matches are available. Call  "
                   f"search_function_or_class_definition_in_code "
                   f"with offset={end} to continue.")
    return result


def find_references(
            workspace: LocalWorkspace,
            name: str,
            filepath: str,
            line: int,
            offset: int = 0,
        ) -> str:
    # name: what we're looking for, e.g. "calculate"
    # filepath: which file, e.g. "src/math.py"
    # line: the definition line that should be excluded
    formatted_result = []
    try:
        capped_matches, total_matches = workspace.find_name_references(
            name, filepath, line, file_pattern="*.py", offset=offset)
    except PathOutsideRootError:
        return (f"Error: Path '{filepath}' is outside the allowed root "
                f"'{workspace.root_dir}'. Re-issue using a path inside "
                f"'{workspace.root_dir}'.")
    except FileNotFoundError:
        return (
            f"Error: File '{filepath}' was not found in the workspace. "
            f"Check the filepath and use list_files to find the correct path."
        )
    except IsADirectoryError:
        return (f"Error: Path {filepath} is a directory, not a file. Provide"
                f" the path to a file whose references you want to find.")
    except ValueError as err:
        return f"Error: {err}"
    for match in capped_matches:
        relative_path, line_number, line_text = match
        absolute_path = (workspace.root_dir / relative_path).resolve()
        formatted_result.append(
            f"{absolute_path}:{line_number} {line_text}")
    if not formatted_result:
        return (
            f"No matches found for reference '{name}' across the workspace "
            f"(excluding definition at {filepath}:{line})."
        )
    start = offset + 1
    end = len(capped_matches) + offset
    result = f"Showing matches {start}-{end} of {total_matches}.\n\n"
    result += "\n".join(formatted_result)
    if end < total_matches:
        result += (f"More matches are available. Call  "
                   f"find_references "
                   f"with offset={end} to continue.")
    return result
