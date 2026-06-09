cmake_minimum_required(VERSION 4.2)
project(c_z_grc C)

set(CMAKE_C_STANDARD 23)

include_directories(include lib/yyjson lib/libb64/include)

find_package(CURL REQUIRED)
find_package(ZLIB REQUIRED)

add_executable(test_cost test/test_cost.c src/cost_calculator.c
                         lib/yyjson/yyjson.c)
target_link_libraries(test_cost m)

add_executable(test_quota test/test_quota.c src/quota_client.c
                          lib/yyjson/yyjson.c)
target_link_libraries(test_quota CURL::libcurl m)

add_executable(test_auth test/test_auth.c src/auth_token.c lib/yyjson/yyjson.c
                         lib/libb64/src/cdecode.c)
target_link_libraries(test_auth ZLIB::ZLIB)

add_executable(
  test_interceptor
  test/test_interceptor.c
  src/interceptor.c
  src/auth_token.c
  src/cost_calculator.c
  src/quota_client.c
  src/response_parser.c
  src/logger.c
  src/otel_exporter.c
  lib/yyjson/yyjson.c
  lib/libb64/src/cdecode.c)
target_link_libraries(test_interceptor CURL::libcurl ZLIB::ZLIB m)

add_executable(test_otel test/test_otel.c src/otel_exporter.c
                         lib/yyjson/yyjson.c)
target_link_libraries(test_otel CURL::libcurl m)
