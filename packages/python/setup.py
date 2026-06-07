"""
Custom setup.py that vendors C sources into csrc/ for sdist/wheel builds.

The C source files from the monorepo root are copied into a csrc/ directory
so that (1) the sdist is self-contained and (2) setuptools never records
path-escaping ../../ references in SOURCES.txt.
"""

import os
import shutil

from setuptools import setup
from setuptools.command.sdist import sdist as _sdist
from setuptools.command.egg_info import egg_info as _egg_info
from setuptools.command.build_ext import build_ext as _build_ext

HERE = os.path.dirname(os.path.abspath(__file__))
MONOREPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CSRC_DIR = os.path.join(HERE, "csrc")

VENDOR_DIRS = [
    "src",
    "include",
    os.path.join("lib", "yyjson"),
    os.path.join("lib", "libb64"),
]


def vendor_c_sources():
    """Copy C sources from the monorepo into csrc/ for packaging."""
    if os.path.isdir(CSRC_DIR):
        return

    for rel_dir in VENDOR_DIRS:
        src_path = os.path.join(MONOREPO_ROOT, rel_dir)
        dst_path = os.path.join(CSRC_DIR, rel_dir)
        if os.path.isdir(src_path):
            shutil.copytree(
                src_path,
                dst_path,
                ignore=shutil.ignore_patterns(
                    "*.o", "*.obj", "*.d", "build", ".DS_Store", "main.c"
                ),
            )


class egg_info(_egg_info):
    """Vendor C sources before egg_info so SOURCES.txt uses csrc/ paths."""

    def run(self):
        vendor_c_sources()
        super().run()


class build_ext(_build_ext):
    """Vendor C sources before building the extension."""

    def run(self):
        vendor_c_sources()
        super().run()


class sdist(_sdist):
    """Vendor C sources before sdist packaging."""

    def run(self):
        vendor_c_sources()
        super().run()


if __name__ == "__main__":
    setup(
        cffi_modules=["core_build.py:ffibuilder"],
        cmdclass={
            "egg_info": egg_info,
            "build_ext": build_ext,
            "sdist": sdist,
        },
    )
