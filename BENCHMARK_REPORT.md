
## 2. MBPP Results

| Model | Provider | Task | Pass | Iter | Input tok | Output tok | Time (s) |
|-------|----------|------|------|-----:|----------:|-----------:|---------:|
| llama3.1:8b | local | 442 | False | 6 | 6016 | 907 | 96.9 |
| llama3.1:8b | local | 442 | True | 2 | 1349 | 371 | 41.4 |
| llama3.1:8b | local | 308 | False | 5 | 5708 | 1233 | 125.9 |
| llama3.1:8b | local | 308 | False | 7 | 6189 | 506 | 50.0 |
| llama3.1:8b | local | 308 | True | 4 | 3025 | 539 | 52.1 |
| llama3.1:8b | local | 262 | True | 2 | 1234 | 196 | 24.1 |
| llama3.1:8b | local | 62 | True | 2 | 1146 | 145 | 13.1 |
| llama3.1:8b | local | 458 | True | 2 | 1107 | 117 | 10.7 |
| llama3.1:8b | local | 301 | True | 5 | 4255 | 743 | 71.5 |
| openai/gpt-oss-120b | groq | 287 | True | 3 | 2143 | 932 | 3.9 |
| openai/gpt-oss-120b | groq | 256 | True | 2 | 1391 | 557 | 2.8 |
| openai/gpt-oss-120b | groq | 252 | True | 4 | 3461 | 1438 | 5.0 |
| openai/gpt-oss-120b | groq | 14 | True | 3 | 2211 | 743 | 2.5 |
| openai/gpt-oss-120b | groq | 388 | True | 2 | 1408 | 338 | 2.3 |
| openai/gpt-oss-120b | groq | 248 | True | 1 | 602 | 415 | 1.2 |
| openai/gpt-oss-20b | gro q | 59 | True | 1 | 568 | 278 | 1.6 |
| openai/gpt-oss-20b | gro q | 123 | False | 2 | 1380 | 1670 | 4.6 |
| openai/gpt-oss-20b | gro q | 66 | True | 1 | 578 | 181 | 1.0 |
| openai/gpt-oss-20b | gro q | 116 | True | 3 | 2109 | 1278 | 4.3 |
| openai/gpt-oss-20b | gro q | 160 | True | 2 | 1646 | 981 | 5.4 |
| command-a-plus-05-2026 | cohere | 262 | True | 1 | 558 | 2094 | 16.8 |
| command-a-plus-05-2026 | cohere | 268 | False | 1 | 491 | 2232 | 17.2 |
| command-a-plus-05-2026 | cohere | 142 | True | 1 | 588 | 2044 | 12.1 |
| command-r7b-12-2024 | cohere | 462 | False | 5 | 7025 | 393 | 6.6 |
| command-r7b-12-2024 | cohere | 237 | False | 6 | 6624 | 1000 | 13.0 |
| north-mini-code | cohere | 88 | False | 4 | 3351 | 3188 | 38.6 |
| north-mini-code | cohere | 17 | False | 1 | 487 | 1723 | 21.6 |
| north-mini-code | cohere | 463 | False | 1 | 521 | 2443 | 9.3 |



## 2. SWE-bench Results

| Model | Provider | Task | Pass | Iter | Input tok | Output tok | Time (s) |
|-------|----------|------|------|-----:|----------:|-----------:|---------:|
| llama3.1:8b | local | psf__requests-1724 | True | 10 | 71227 | 627 | 225.3 |
| llama3.1:8b | local | psf__requests-1724 | False | 30 | 144162 | 1262 | 232.4 |
| llama3.1:8b | local | django__django-11066 | True | 6 | 17158 | 328 | 57.3 |
| llama3.1:8b | local | django__django-11066 | True | 6 | 14444 | 589 | 101.2 |
| llama3.1:8b | local | psf__requests-2317 | False | 30 | 100129 | 1939 | 248.7 |
| llama3.1:8b | local | pydata__xarray-4629 | True | 20 | 128318 | 1367 | 256.3 |
| llama3.1:8b | local | sympy__sympy-13480 | True | 4 | 10404 | 709 | 116.9 |
| llama3.1:8b | local | pydata__xarray-4629 | True | 9 | 24428 | 619 | 91.0 |
| llama3.1:8b | local | sympy__sympy-13480 | True | 25 | 62203 | 1402 | 183.6 |
| openai/gpt-oss-120b | groq | pydata__xarray-4629 | True | 5 | 13273 | 629 | 60.0 |
| openai/gpt-oss-120b | groq | sympy__sympy-13480 | True | 9 | 30939 | 2976 | 101.5 |
| openai/gpt-oss-120b | groq | pydata__xarray-4629 | True | 9 | 27447 | 4584 | 52.5 |
| openai/gpt-oss-120b | groq | sympy__sympy-18189 | True | 8 | 38218 | 2444 | 88.3 |
