
import json
import re
from dataclasses import dataclass, field

CLOSED_FENCE = re.compile(r"```(?:python|py)?[ \t]*\n(.*?)```", re.DOTALL)
THOUGHT = re.compile(r"Thought:\s*(.*?)(?=\n```)", re.DOTALL)


def extract_code(text: str) -> tuple[str, str]:
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


################### i need to check this later should i add all the code in one block and sand it to the sand box ?
# ex = """

# ```python
# search_code(\"class Pipeline\", \"sklearn/pipeline.py\", 0)
# ``````python
# read_file(\"sklearn/pipeline.py\", 76, 160)
# ```

# """

# print(extract_code(ex))