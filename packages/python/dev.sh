#!/bin/bash
set -e

cd "$(dirname "$0")"

rm -rf csrc build dist *.egg-info zgrc/_native*.so zgrc/_native*.pyd
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

python -c "import setup; setup.vendor_c_sources()"
python core_build.py
uv build

echo "Done!"
