"""
CFFI build script for zgrc._native

Resolves C source paths in two scenarios:
1. Development (in-tree): sources live at ../../src, ../../lib, ../../include
2. sdist build: sources are vendored into ./csrc/ by setup.py

Note: setuptools requires relative paths (from setup.py directory), never absolute.
"""

import os
import platform
from cffi import FFI

ffibuilder = FFI()

HERE = os.path.dirname(os.path.abspath(__file__))

# Determine where C sources live: vendored csrc/ (sdist) or monorepo root (dev)
csrc_dir = os.path.join(HERE, "csrc")
if os.path.isdir(csrc_dir):
    # Building from sdist - sources are vendored
    root = "csrc"
else:
    # Building from repo checkout - use relative path to monorepo root
    root = os.path.relpath(os.path.join(HERE, "..", ".."), HERE)

ffibuilder.cdef(
    """
    typedef struct { ...; } Interceptor;

    typedef struct {
        int allowed;
        char model[256];
        double used_quota;
        double remaining_quota;
    } RequestResult;

    typedef struct {
        double cost;
        int input_tokens;
        int output_tokens;
        double used_quota;
        double remaining_quota;
    } ResponseResult;

    Interceptor* interceptor_init(const char *api_key, const char *pricing_file);
    RequestResult intercept_request(Interceptor *ctx, const char *url, const char *body, size_t body_len);
    ResponseResult intercept_response(Interceptor *ctx, const char *url, const char *body, size_t body_len);
    void interceptor_free(Interceptor *ctx);
    """
)

sources = [
    root + "/src/interceptor.c",
    root + "/src/cost_calculator.c",
    root + "/src/auth_token.c",
    root + "/src/quota_client.c",
    root + "/src/response_parser.c",
    root + "/lib/yyjson/yyjson.c",
    root + "/lib/libb64/src/cdecode.c",
]

include_dirs = [
    root + "/include",
    root + "/lib/yyjson",
    root + "/lib/libb64/include",
]

system = platform.system()

libraries = []
extra_compile_args = []
extra_link_args = []

if system == "Windows":
    extra_compile_args = ["/std:c2x"]
    libraries = ["ws2_32", "advapi32", "crypt32", "normaliz", "wldap32"]
elif system == "Darwin":
    extra_compile_args = ["-std=c2x"]
    libraries = ["curl", "z"]
else:
    extra_compile_args = ["-std=c2x"]
    libraries = ["curl", "z"]

ffibuilder.set_source(
    "zgrc._native",
    '#include "interceptor.h"',
    sources=sources,
    include_dirs=include_dirs,
    libraries=libraries,
    extra_compile_args=extra_compile_args,
    extra_link_args=extra_link_args,
)

if __name__ == "__main__":
    ffibuilder.compile(tmpdir=".", verbose=True)
