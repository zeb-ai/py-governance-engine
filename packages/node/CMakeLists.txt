# IDE-only: helps JetBrains resolve includes. Not used for building. main reason
# : not showing error on the addon.c
cmake_minimum_required(VERSION 3.20)
project(grc_node_addon C)

set(CMAKE_C_STANDARD 23)

add_library(
  grc_interceptor SHARED
  src/addon.c
  ../../src/interceptor.c
  ../../src/logger.c
  ../../src/auth_token.c
  ../../src/cost_calculator.c
  ../../src/quota_client.c
  ../../src/response_parser.c
  ../../lib/yyjson/yyjson.c
  ../../lib/libb64/src/cdecode.c)

target_include_directories(
  grc_interceptor
  PRIVATE ../../include ../../lib/yyjson ../../lib/libb64/include
          /opt/homebrew/Cellar/node/25.9.0_2/include/node
          ${CMAKE_CURRENT_SOURCE_DIR}/node_modules/node-addon-api)
