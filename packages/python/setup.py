"""
Custom setup.py that vendors C sources into csrc/ for sdist builds.

When building an sdist, the C source files from the monorepo root are copied
into a csrc/ directory so the sdist is self-contained. The wheel build (from
the sdist) then finds them via core_build.py's path resolution.
"""

import os
import shutil

from setuptools import setup
from setuptools.command.sdist import sdist as _sdist

HERE = os.path.dirname(os.path.abspath(__file__))
MONOREPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CSRC_DIR = os.path.join(HERE, "csrc")

# Directories from the monorepo root to vendor into csrc/
VENDOR_DIRS = [
    "src",
    "include",
    os.path.join("lib", "yyjson"),
    os.path.join("lib", "libb64"),
]


def vendor_c_sources():
    """Copy C sources from the monorepo into csrc/ for sdist packaging."""
    if os.path.exists(CSRC_DIR):
        shutil.rmtree(CSRC_DIR)

    for rel_dir in VENDOR_DIRS:
        src_path = os.path.join(MONOREPO_ROOT, rel_dir)
        dst_path = os.path.join(CSRC_DIR, rel_dir)
        if os.path.isdir(src_path):
            shutil.copytree(
                src_path,
                dst_path,
                ignore=shutil.ignore_patterns("*.o", "*.obj", "*.d", "build"),
            )


class sdist(_sdist):
    """Custom sdist that vendors C sources before packaging."""

    def run(self):
        vendor_c_sources()
        super().run()
        # Clean up after sdist is created
        if os.path.exists(CSRC_DIR):
            shutil.rmtree(CSRC_DIR)


if __name__ == "__main__":
    setup(
        cffi_modules=["core_build.py:ffibuilder"],
        cmdclass={"sdist": sdist},
    )
