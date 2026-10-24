# Model Benchmark Report

## 1. Setup

- **Benchmarks:** MBPP (Mostly Basic Python Problems) and SWE-bench.
- **MBPP results:** 20 recorded runs across 4 model configurations, covering Python programming tasks identified by their MBPP task IDs.
- **SWE-bench results:** 13 recorded runs across 3 model configurations, covering bug-fixing tasks in Requests, Django, xarray, and SymPy.
- **Models (4 configurations, 3 providers):** The benchmark includes a locally hosted Llama model, two GPT-OSS models served by Groq, and a Cohere Command model.

  | # | Model | Provider | Family | Tier |
  |---|-------|----------|--------|------|
  | 1 | `llama3.1:8b` | Local | Meta Llama 3.1 | Local inference |
  | 2 | `openai/gpt-oss-120b` | Groq | OpenAI GPT-OSS | Provider-dependent |
  | 3 | `openai/gpt-oss-20b` | Groq | OpenAI GPT-OSS | Provider-dependent |
  | 4 | `command-a-plus-05-2026` | Cohere | Cohere Command | Trial/access-dependent |

- **Evaluation limits:** Iteration, token, and time limits should be specified from the actual benchmark configuration. The tables report observed iterations, input tokens, output tokens, and elapsed time for each run.
- **Pass definition:** A run is marked `True` or `False` according to the benchmark evaluator used by the agent. MBPP evaluates Python programming tasks, while SWE-bench evaluates repository-level bug fixes. The exact grading procedure should be documented alongside the evaluation configuration.
- **Interpretation:** Repeated task IDs represent separate runs and are retained to make variability and repeatability visible. Results are preliminary and should not be interpreted as a controlled comparison unless task selection, execution limits, and evaluation procedures are consistent across models.

## 2. MBPP Results

| Model | Provider | Task | Pass | Iter | Input tok | Output tok | Time (s) |
|-------|----------|-----:|:----:|-----:|----------:|-----------:|---------:|
| llama3.1:8b | Local | 442 | True | 2 | 1,349 | 371 | 41.4 |
| llama3.1:8b | Local | 308 | False | 7 | 6,189 | 506 | 50.0 |
| llama3.1:8b | Local | 308 | True | 4 | 3,025 | 539 | 52.1 |
| llama3.1:8b | Local | 262 | True | 2 | 1,234 | 196 | 24.1 |
| llama3.1:8b | Local | 62 | True | 2 | 1,146 | 145 | 13.1 |
| llama3.1:8b | Local | 458 | True | 2 | 1,107 | 117 | 10.7 |
| llama3.1:8b | Local | 301 | True | 5 | 4,255 | 743 | 71.5 |
| openai/gpt-oss-120b | Groq | 287 | True | 3 | 2,143 | 932 | 3.9 |
| openai/gpt-oss-120b | Groq | 256 | True | 2 | 1,391 | 557 | 2.8 |
| openai/gpt-oss-120b | Groq | 252 | True | 4 | 3,461 | 1,438 | 5.0 |
| openai/gpt-oss-120b | Groq | 14 | True | 3 | 2,211 | 743 | 2.5 |
| openai/gpt-oss-120b | Groq | 388 | True | 2 | 1,408 | 338 | 2.3 |
| openai/gpt-oss-120b | Groq | 248 | True | 1 | 602 | 415 | 1.2 |
| openai/gpt-oss-20b | Groq | 59 | True | 1 | 568 | 278 | 1.6 |
| openai/gpt-oss-20b | Groq | 66 | True | 1 | 578 | 181 | 1.0 |
| openai/gpt-oss-20b | Groq | 116 | True | 3 | 2,109 | 1,278 | 4.3 |
| openai/gpt-oss-20b | Groq | 160 | True | 2 | 1,646 | 981 | 5.4 |
| command-a-plus-05-2026 | Cohere | 262 | True | 1 | 558 | 2,094 | 16.8 |
| command-a-plus-05-2026 | Cohere | 268 | False | 1 | 491 | 2,232 | 17.2 |
| command-a-plus-05-2026 | Cohere | 142 | True | 1 | 588 | 2,044 | 12.1 |

## 3. SWE-bench Results

| Model | Provider | Task | Pass | Iter | Input tok | Output tok | Time (s) |
|-------|----------|----------------------|:----:|-----:|----------:|-----------:|---------:|
| llama3.1:8b | Local | psf__requests-1724 | True | 10 | 71,227 | 627 | 225.3 |
| llama3.1:8b | Local | psf__requests-1724 | False | 30 | 144,162 | 1,262 | 232.4 |
| llama3.1:8b | Local | django__django-11066 | True | 6 | 17,158 | 328 | 57.3 |
| llama3.1:8b | Local | django__django-11066 | True | 6 | 14,444 | 589 | 101.2 |
| llama3.1:8b | Local | psf__requests-2317 | False | 30 | 100,129 | 1,939 | 248.7 |
| llama3.1:8b | Local | pydata__xarray-4629 | True | 20 | 128,318 | 1,367 | 256.3 |
| llama3.1:8b | Local | sympy__sympy-13480 | True | 4 | 10,404 | 709 | 116.9 |
| llama3.1:8b | Local | pydata__xarray-4629 | True | 9 | 24,428 | 619 | 91.0 |
| llama3.1:8b | Local | sympy__sympy-13480 | True | 25 | 62,203 | 1,402 | 183.6 |
| openai/gpt-oss-120b | Groq | pydata__xarray-4629 | True | 5 | 13,273 | 629 | 60.0 |
| openai/gpt-oss-120b | Groq | sympy__sympy-13480 | True | 9 | 30,939 | 2,976 | 101.5 |
| openai/gpt-oss-120b | Groq | pydata__xarray-4629 | True | 9 | 27,447 | 4,584 | 52.5 |
| openai/gpt-oss-120b | Groq | sympy__sympy-18189 | True | 8 | 38,218 | 2,444 | 88.3 |

## 4. Preliminary Observations

- **MBPP:** `openai/gpt-oss-120b` passed all 6 recorded runs, and `openai/gpt-oss-20b` passed all 4 recorded runs. Both configurations were substantially faster than the local `llama3.1:8b` runs in these results.
- **MBPP consistency:** The local Llama model produced different outcomes on repeated runs of task 308. This suggests that repeatability deserves further investigation.
- **SWE-bench:** `openai/gpt-oss-120b` passed all 4 recorded runs. The local Llama model passed 7 of 9 runs (77.8%), with two failures involving Requests tasks.
- **Efficiency:** The Groq-hosted GPT-OSS 120B model completed the recorded SWE-bench tasks in 52.5–101.5 seconds. The local Llama runs ranged from 57.3–256.3 seconds.
- **Limitations:** The sample sizes are small, task coverage differs between models, and some tasks were repeated. These observations are descriptive rather than statistically conclusive.

## 5. Summary Statistics

| Benchmark | Model | Runs | Pass | Pass rate | Avg. iterations | Avg. time (s) |
|-----------|-------|-----:|-----:|----------:|----------------:|--------------:|
| MBPP | llama3.1:8b | 7 | 6 | 85.7% | 3.43 | 37.56 |
| MBPP | openai/gpt-oss-120b | 6 | 6 | 100.0% | 2.50 | 2.95 |
| MBPP | openai/gpt-oss-20b | 4 | 4 | 100.0% | 1.75 | 3.08 |
| MBPP | command-a-plus-05-2026 | 3 | 2 | 66.7% | 1.00 | 15.37 |
| SWE-bench | llama3.1:8b | 9 | 7 | 77.8% | 15.56 | 145.3 |
| SWE-bench | openai/gpt-oss-120b | 4 | 4 | 100.0% | 7.75 | 75.6 |

*Note: Average iterations and times are calculated across recorded runs, including failures. Pass rates use recorded runs, not unique task counts. The two benchmarks have different task types and should be interpreted separately.*