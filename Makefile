
export UV_CACHE_DIR=/tmp/uv_cache_dir
export UV_PROJECT_ENVIRONMENT=/tmp/uv_venv

test_ai:
	uv run python -m tests.test_ai
