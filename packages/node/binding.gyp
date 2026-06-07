{
    "targets": [
        {
            "target_name": "grc_interceptor",
            "sources": [
                "src/addon.c",
                "../../src/interceptor.c",
                "../../src/logger.c",
                "../../src/auth_token.c",
                "../../src/cost_calculator.c",
                "../../src/quota_client.c",
                "../../src/response_parser.c",
                "../../lib/yyjson/yyjson.c",
                "../../lib/libb64/src/cdecode.c",
            ],
            "include_dirs": [
                "../../include",
                "../../lib/yyjson",
                "../../lib/libb64/include",
                "<!(node -p \"require('node-addon-api').include_dir\")",
            ],
            "libraries": ["-lcurl", "-lz"],
            "defines": ["NAPI_VERSION=8", "NAPI_DISABLE_CPP_EXCEPTIONS"],
            "cflags": ["-std=c23", "-Wall"],
            "xcode_settings": {"OTHER_CFLAGS": ["-std=c23"]},
        }
    ]
}
