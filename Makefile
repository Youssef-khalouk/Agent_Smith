CONNECTION_TYPE ?= "http"

ifeq ($(OS),Windows_NT)
    # Window
	export UV_CACHE_DIR=C:/rag_env/uv_cache_dir
	export UV_PROJECT_ENVIRONMENT=C:/rag_env/uv_venv

else
    ifneq ($(wildcard /mnt/c/RAG),)
        # WSL
		export UV_CACHE_DIR=$(HOME)/.cache/uv_cache_dir
		export UV_PROJECT_ENVIRONMENT=$(HOME)/.cache/uv_venv

    else
        # Linux cluster
		export UV_CACHE_DIR=/tmp/uv_cache_dir
		export UV_PROJECT_ENVIRONMENT=/tmp/uv_venv
    endif
endif

test_ai:
	uv run python -m tests.test_ai


test_sbx:
	uv run python -m tests.test_sandbox_security


test_orchestrator:
	uv run python -m tests.test_orchestrator

start_mcp_server:
	uv run python3 -m tests.dummy_mcp_server start_mcp --connection_type=$(CONNECTION_TYPE) >> log.txt 2>&1 &

stop_mcp_server:
	pkill -f "tests.dummy_mcp_server start_mcp"

test_client:
	uv run python3 -m tests.test_tools
test_tools:
	uv run python -m tests.test_tools


test_tools_in_container:
	uv run python -m tests.test_tools_with_docker




# this is the commands that is requaired in the subject
run_mbpp:
	uv run python -m agent_mbpp --task-file mbpp_task.json --output output/mbpp_solution.json --model-name "openai/gpt-4o" --provider-url "https://openrouter.ai/api/v1/chat/completions"

