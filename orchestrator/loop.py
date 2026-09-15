

# def agent_loop(task, max_iterations):
#     conversation = [system_prompt, task_description]

#     for i in range(max_iterations):
#         llm_response = call_llm(conversation, stop=["<end_code>"])
#         code = extract_code(llm_response)  # your extraction layer

#         if code is None:
#             observation = "Error: no valid code block found in your response."
#         else:
#             try:
#                 observation = sandbox.execute(code)  # persistent namespace!
#             except FinalAnswerCalled as fa:
#                 return fa.answer  # done!
#             except Exception as e:
#                 observation = f"Error: {type(e).__name__}: {e}"

#         conversation.append(llm_response)
#         conversation.append(f"Observation: {observation}")

#     return None  # hit max_iterations without finishing

