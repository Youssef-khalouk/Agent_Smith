
import json
import re
from dataclasses import dataclass, field

CLOSED_FENCE = re.compile(r"```(?:python|py)?[ \t]*\n(.*?)```", re.DOTALL)
THOUGHT = re.compile(r"Thought:\s*(.*?)(?=\n```|```)", re.DOTALL)


def extract_code(text: str) -> tuple[str, str]:
    """
    Extract a Python code block and the associated thought from text.

    Search the input text for a closed Markdown code fence containing Python
    code and extract its contents, removing surrounding whitespace. Treat an
    empty code block as absent. Also extract the thought text following the
    "Thought:" marker, if present.

    Args:
        text: The text to parse, typically an LLM response.

    Returns:
        A tuple containing the extracted code or None, and the extracted
        thought or an empty string if no thought is found.
    """
    result = None

    block = CLOSED_FENCE.search(text or "")
    if block:
        result = block.group(1).strip()
        if result == "":
            result = None
    
    match = THOUGHT.search(text or "")
    thought = ""
    if match:
        thought = match.group(1).strip()

    return (result, thought)
