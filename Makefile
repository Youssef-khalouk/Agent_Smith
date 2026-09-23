
export UV_CACHE_DIR=/tmp/uv_cache_dir
export UV_PROJECT_ENVIRONMENT=/tmp/uv_venv

test_ai:
	uv run python -m tests.test_ai

test_sbx:
	uv run python -m tests.test_sandbox_security

start_mcp_server:
	uv run python3 -m tests.dummy_mcp_server start_mcp --connection_type=$(CONNECTION_TYPE) &

stop_mcp_server:
	pkill -f "tests.dummy_mcp_server start_mcp"

test_client:
	uv run python3 -m tests.test_tools 