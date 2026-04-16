.PHONY: help setup build clean lint fix up-proxy grpc-proxy-build grpc-proxy-build-linux grpc-proxy-build-windows grpc-proxy-checksums grpc-proxy-release

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
	@echo "  make grpc-proxy-build         - Build grc-proxy for current platform only"
	@echo "  make grpc-proxy-build-linux   - Build grc-proxy for Linux (run on Linux)"
	@echo "  make grpc-proxy-build-windows - Build grc-proxy for Windows (run on Windows)"
	@echo "  make grpc-proxy-checksums     - Generate SHA256 checksums for built binaries"
	@echo "  make grpc-proxy-release       - Build + checksums (ready for distribution)"
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
	uv run grc/proxy/main.py --api-key $(GRC_API_KEY)

grpc-proxy-build:
	@echo "Building grc-proxy for current platform ($(shell uname -s)-$(shell uname -m))..."
	uv run pyinstaller grc-proxy.spec
	@echo
	@echo "Binary created at: dist/grc-proxy"

grpc-proxy-build-linux:
	@echo "Building grc-proxy for Linux..."
	uv run pyinstaller grc-proxy.spec
	@mv dist/grc-proxy dist/grc-proxy-linux-x86_64
	@echo "Binary created at: dist/grc-proxy-linux-x86_64"

grpc-proxy-build-windows:
	@echo "Building grc-proxy for Windows..."
	uv run pyinstaller grc-proxy.spec
	@move dist\grc-proxy.exe dist\grc-proxy-windows-x86_64.exe
	@echo "Binary created at: dist/grc-proxy-windows-x86_64.exe"

grpc-proxy-checksums:
	@echo "Generating checksums..."
	@cd dist && shasum -a 256 grc-proxy-* > checksums.txt
	@echo "Checksums saved to: dist/checksums.txt"
	@cat dist/checksums.txt

grpc-proxy-release: clean grpc-proxy-build grpc-proxy-checksums
	@echo
	@echo "Release build complete! Ready for distribution:"
	@ls -lh dist/grc-proxy-*
	@echo
	@echo "NOTE: This builds for current platform only ($(shell uname -s)-$(shell uname -m))."
