{
    "targets": [
        {
            "target_name": "grc_interceptor",
            "sources": [
                "src/addon.c",
                "csrc/src/interceptor.c",
                "csrc/src/logger.c",
                "csrc/src/auth_token.c",
                "csrc/src/cost_calculator.c",
                "csrc/src/quota_client.c",
                "csrc/src/response_parser.c",
                "csrc/src/otel_exporter.c",
                "csrc/lib/yyjson/yyjson.c",
                "csrc/lib/libb64/src/cdecode.c",
            ],
            "include_dirs": [
                "csrc/include",
                "csrc/lib/yyjson",
                "csrc/lib/libb64/include",
                "<!(node -p \"require('node-addon-api').include_dir\")",
            ],
            "defines": ["NAPI_VERSION=8", "NAPI_DISABLE_CPP_EXCEPTIONS"],
            "cflags": ["-std=c2x", "-Wall"],
            "xcode_settings": {"OTHER_CFLAGS": ["-std=c2x"]},
            "msvs_settings": {},
            "conditions": [
                [
                    "OS=='win'",
                    {
                        "defines": ["CURL_STATICLIB", "nullptr=NULL"],
                        "libraries": [
                            "-lws2_32",
                            "-lbcrypt",
                            "-ladvapi32",
                            "-lcrypt32",
                            "-lnormaliz",
                            "-lwldap32",
                        ],
                        "conditions": [
                            [
                                "'<!(node -e \"process.stdout.write(require('fs').existsSync('deps/lib/libcurl.lib')?'1':'0')\")'=='1'",
                                {
                                    "include_dirs": ["deps/include"],
                                    "libraries": [
                                        "<(module_root_dir)/deps/lib/libcurl.lib",
                                        "<(module_root_dir)/deps/lib/zlibstatic.lib",
                                    ],
                                },
                                {"libraries": ["-lcurl"]},
                            ]
                        ],
                    },
                    {
                        "conditions": [
                            [
                                "'<!(node -e \"process.stdout.write(require('fs').existsSync('deps/lib/libcurl.a')?'1':'0')\")'=='1'",
                                {
                                    "include_dirs": ["deps/include"],
                                    "libraries": [
                                        "<(module_root_dir)/deps/lib/libcurl.a",
                                        "<(module_root_dir)/deps/lib/libssl.a",
                                        "<(module_root_dir)/deps/lib/libcrypto.a",
                                        "<(module_root_dir)/deps/lib/libz.a",
                                    ],
                                },
                                {"libraries": ["-lcurl", "-lz"]},
                            ]
                        ]
                    },
                ]
            ],
        }
    ]
}
