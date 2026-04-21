.PHONY: help setup build clean lint fix up-proxy grpc-proxy-build docs-serve docs-build

help:
	@clear 2>/dev/null || true
	@echo
	@echo "Available commands:"
	@echo "  make setup                    - Install dependencies and setup pre-commit hooks"
	@echo "  make build                    - Build the package for distribution"
	@echo "  make lint                     - Run ruff check on the codebase"
	@echo "  make fix                      - Run ruff check and fix issues automatically"
	@echo "  make clean                    - Clean build artifacts, cache files, and Python bytecode"
	@echo
	@echo "Executable builds:"
	@echo "  make grpc-proxy-build         - Build z-grc-proxy for current platform only"
	@echo
	@echo "Documentation:"
	@echo "  make docs-serve               - Start local documentation server"
	@echo "  make docs-build               - Build documentation site"
	@echo

setup:
	@clear 2>/dev/null || true
	@echo "Installing dependencies..."
	uv sync --all-groups
	@echo
	@echo "Installing pre-commit hooks..."
	uv run pre-commit install
	@echo
	@echo "Running pre-commit on all files..."
	uv run pre-commit run --all-files || true
	@echo
	@echo "Setup complete!"

build:
	@clear 2>/dev/null || true
	uv build

lint:
	@clear 2>/dev/null || true
	@echo
	uv run ruff check .

fix:
	@clear 2>/dev/null || true
	@echo
	uv run ruff check --fix .

clean:
	@clear 2>/dev/null || true
	@echo
	rm -rf dist/
	rm -rf build/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +

# dev
up-proxy:
	uv run zgrc/proxy.main.py --api-key $(GRC_API_KEY)

grpc-proxy-build:
	@echo "Building z-grc-proxy for current platform ($(shell uname -s)-$(shell uname -m))..."
	uv run pyinstaller z-grc-proxy.spec
	@echo
	@echo "Binary created at: dist/z-grc-proxy"

docs-serve:
	@clear 2>/dev/null || true
	uv run mkdocs serve

docs-build:
	@clear 2>/dev/null || true
	@echo "Building documentation site..."
	uv run mkdocs build
	@echo "Documentation built in site/ directory"
