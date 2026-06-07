"""
CFFI build script for zgrc._native

Sources are always resolved from csrc/ — setup.py vendors them there before
any setuptools command runs, so paths never escape the package directory.
"""

import os
import platform
from cffi import FFI

ffibuilder = FFI()

HERE = os.path.dirname(os.path.abspath(__file__))

root = "csrc"

ffibuilder.cdef(
    """
    typedef enum {
        LOG_DEBUG = 0,
        LOG_INFO = 1,
        LOG_WARN = 2,
        LOG_ERROR = 3,
    } LogLevel;

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
    void interceptor_enable_logging(Interceptor *ctx, LogLevel level, const char *path);
    RequestResult intercept_request(Interceptor *ctx, const char *url, const char *body, size_t body_len);
    ResponseResult intercept_response(Interceptor *ctx, const char *url, const char *body, size_t body_len);
    void interceptor_free(Interceptor *ctx);
    """
)

sources = [
    root + "/src/interceptor.c",
    root + "/src/logger.c",
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

static_curl = os.path.exists("/usr/local/lib/libcurl.a") or os.environ.get("LDFLAGS")

if system == "Windows":
    extra_compile_args = []
    deps_dir = os.environ.get("ZGRC_DEPS_DIR", "C:/deps")
    deps_include = os.path.join(deps_dir, "include")
    deps_lib = os.path.join(deps_dir, "lib")
    if os.path.isdir(deps_include):
        include_dirs.append(deps_include)
    if os.path.isdir(deps_lib):
        extra_link_args = ["/LIBPATH:" + deps_lib]
    libraries = [
        "libcurl",
        "zlib",
        "ws2_32",
        "advapi32",
        "crypt32",
        "normaliz",
        "wldap32",
    ]
elif system == "Darwin":
    extra_compile_args = ["-std=c23"]
    if static_curl:
        extra_link_args = [
            "/usr/local/lib/libcurl.a",
            "/usr/local/lib/libz.a",
            "-framework",
            "Security",
            "-framework",
            "SystemConfiguration",
        ]
    else:
        libraries = ["curl", "z"]
else:
    extra_compile_args = ["-std=c23"]
    if static_curl:
        extra_link_args = [
            "/usr/local/lib/libcurl.a",
            "/usr/local/lib/libssl.a",
            "/usr/local/lib/libcrypto.a",
            "/usr/local/lib/libz.a",
            "-lpthread",
            "-ldl",
        ]
    else:
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
