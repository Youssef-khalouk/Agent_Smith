
from models import MBPPTaskInput, SolutionOutput
from orchestrator import Agent
from pydantic import BaseModel, Field
from typing import List


task = MBPPTaskInput(
    task_id=1237,
    task_definition="Write a function called `is_even` that takes an integer and returns True if the number is even, otherwise False.",
    function_definition="is_even",
    test_imports=[],
    test_list=[
        "assert is_even(2) == True",
        "assert is_even(5) == False",
        "assert is_even(0) == True",
        "assert is_even(-4) == True",
    ]
)

agent = Agent()

result = agent.run(task)


for key, value in result:
    print(f"{key}:  {value}")
    print("")