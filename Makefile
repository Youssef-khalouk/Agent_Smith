-include .env
export

CONNECTION_TYPE ?= http

ifeq ($(OS),Windows_NT)
	# Window
	export VIRTUAL_ENV=C:/rag_env/uv_venv
	export UV_CACHE_DIR=C:/rag_env/uv_cache_dir
	export UV_PROJECT_ENVIRONMENT=C:/rag_env/uv_venv

else
	ifneq ($(wildcard /mnt/c/AGENT_SMITH),)
		# WSL
		export VIRTUAL_ENV=$(HOME)/.cache/uv_venv
		export UV_CACHE_DIR=$(HOME)/.cache/uv_cache_dir
		export UV_PROJECT_ENVIRONMENT=$(HOME)/.cache/uv_venv

	else
		# Linux cluster
		export VIRTUAL_ENV=/tmp/uv_venv
		export UV_CACHE_DIR=/tmp/uv_cache_dir
		export UV_PROJECT_ENVIRONMENT=/tmp/uv_venv
	endif
endif

pull_python:
	docker pull python:3.11-slim

install:
	uv sync

download:
	mkdir -p moulinette
	curl -L -o moulinette.zip https://cdn.intra.42.fr/document/document/48980/moulinette.zip
	unzip -o moulinette.zip -d .;
	rm -rf moulinette.zip

dump_mbpp:
	cd moulinette && uv run python3 -m moulinette dump --benchmark mbpp --output ../tasks/mbpp_task.json

dump_swebench:
	cd moulinette && uv run python3 -m moulinette dump --benchmark swebench --output ../tasks/swebench_task.json

run_mbpp:
	uv run python3 -m agent_mbpp --task-file tasks/mbpp_task.json --output output/mbpp_solution.json --model-name=$(MODEL_NAME) --provider-url=$(API_URL) --mcp-stdio mcp_tools_mbpp.py --verbose

run_swebench:
	uv run python3 -m agent_swebench --task-file tasks/swebench_task.json --output output/swebench_solution.json --model-name=$(MODEL_NAME) --provider-url=$(API_URL) --mcp-http http://localhost:8000/ --verbose

run_stdio_swebench:
	uv run python3 -m agent_swebench --task-file tasks/swebench_task.json --output output/swebench_solution.json --model-name=$(MODEL_NAME) --provider-url=$(API_URL) --mcp-stdio mcp_tools_swebench.py --verbose

validate_mbpp:
	cd moulinette && uv run python3 -m moulinette validate --benchmark mbpp --task_file ../tasks/mbpp_task.json  --solution_file ../output/mbpp_solution.json

validate_swebench:
	cd moulinette && uv run python3 -m moulinette validate --benchmark swebench --task_file ../tasks/swebench_task.json  --solution_file ../output/swebench_solution.json


mbpp:
	@echo "\n----------------------- DUMP MBPP ----------------------------\n"
	@$(MAKE) dump_mbpp
	@echo "\n----------------------- RUN MBPP -----------------------------\n"
	@$(MAKE) run_mbpp
	@echo "\n----------------------- VALIDATE MBPP ------------------------\n"
	@$(MAKE) validate_mbpp

swebench:
	@echo "\n----------------------- DUMP SWEBENCH ----------------------------\n"
	@$(MAKE) dump_swebench
	@echo "\n----------------------- RUN SWEBENCH -----------------------------\n"
	@$(MAKE) run_stdio_swebench
	@echo "\n----------------------- VALIDATE SWEBENCH ------------------------\n"
	@$(MAKE) validate_swebench

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

fclean: clean
	rm -rf output
	rm -rf tasks
	rm -rf log.txt
	rm -rf messages.txt

#######################################################

start_swebench_mcp_server_http:
	uv run python3 mcp_tools_swebench.py --http >> log.txt 2>&1 &

start_mbpp_mcp_server_http:
	uv run python3 mcp_tools_mbpp.py --http >> log.txt 2>&1 &

stop_mbpp_server:
	pkill -9 -f "mcp_tools_mbpp"

stop_swebench_server:
	pkill -9 -f "mcp_tools_swebench"



help:
	@echo "Available commands:"
	@echo ""
	@echo "  make install               Install/sync project dependencies"
	@echo "  make download              Download Moulinette"
	@echo "  make pull_python           Pull the Python 3.11 slim Docker image"
	@echo ""
	@echo "  make dump_mbpp             Dump MBPP tasks"
	@echo "  make dump_swebench         Dump SWE-bench tasks"
	@echo ""
	@echo "  make run_mbpp              Run Agent Smith on MBPP"
	@echo "  make run_swebench          Run Agent Smith on SWE-bench using HTTP"
	@echo "  make run_stdio_swebench    Run Agent Smith on SWE-bench using stdio"
	@echo ""
	@echo "  make start_swebench_mcp_server_http  Start the SWE-bench MCP HTTP server"
	@echo "  make start_mbpp_mcp_server_http     Start the MBPP MCP HTTP server"
	@echo "  make stop_swebench_server            Stop the SWE-bench MCP server"
	@echo "  make stop_mbpp_server                Stop the MBPP MCP server"
	@echo ""
	@echo "  make validate_mbpp         Validate the MBPP solution"
	@echo "  make validate_swebench     Validate the SWE-bench solution"
	@echo ""
	@echo "  make mbpp                  Run the complete MBPP pipeline"
	@echo "  make swebench              Run the complete SWE-bench pipeline"
	@echo ""
	@echo "  make clean                 Remove Python cache files"
	@echo "  make fclean                Remove caches, output, tasks, and logs"
	@echo "  make help                  Display this help message"
