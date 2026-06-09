#include "interceptor.h"
#include <node_api.h>
#include <stdlib.h>
#include <string.h>

static Interceptor *g_interceptor = NULL;

static napi_value throw_error(napi_env env, const char *msg) {
  napi_throw_error(env, NULL, msg);
  return NULL;
}

static int get_string(napi_env env, napi_value val, char *buf,
                      size_t buf_size) {
  size_t len;
  if (napi_get_value_string_utf8(env, val, buf, buf_size, &len) != napi_ok)
    return -1;
  return 0;
}

static napi_value napi_init(napi_env env, napi_callback_info info) {
  size_t argc = 3;
  napi_value argv[3];
  napi_get_cb_info(env, info, &argc, argv, NULL, NULL);

  if (argc < 2)
    return throw_error(env, "init requires (apiKey, pricingFile, appName?)");

  char api_key[2048];
  char pricing_file[1024];
  char app_name[256] = {0};

  if (get_string(env, argv[0], api_key, sizeof(api_key)) != 0)
    return throw_error(env, "apiKey must be a string");
  if (get_string(env, argv[1], pricing_file, sizeof(pricing_file)) != 0)
    return throw_error(env, "pricingFile must be a string");

  // Optional app_name parameter (defaults to env var or process title)
  if (argc >= 3) {
    get_string(env, argv[2], app_name, sizeof(app_name));
  }

  if (g_interceptor) {
    interceptor_free(g_interceptor);
    g_interceptor = NULL;
  }

  g_interceptor =
      interceptor_init(api_key, pricing_file, app_name[0] ? app_name : NULL);

  napi_value result;
  napi_get_boolean(env, g_interceptor != NULL, &result);
  return result;
}

// grc.enableLogging(level: number, path: string): void
static napi_value napi_enable_logging(napi_env env, napi_callback_info info) {
  if (!g_interceptor)
    return throw_error(env, "not initialized, call init() first");

  size_t argc = 2;
  napi_value argv[2];
  napi_get_cb_info(env, info, &argc, argv, NULL, NULL);

  if (argc < 2)
    return throw_error(env, "enableLogging requires (level, path)");

  int32_t level;
  if (napi_get_value_int32(env, argv[0], &level) != napi_ok)
    return throw_error(env, "level must be a number");

  char path[1024];
  if (get_string(env, argv[1], path, sizeof(path)) != 0)
    return throw_error(env, "path must be a string");

  interceptor_enable_logging(g_interceptor, (LogLevel)level, path);

  napi_value undefined;
  napi_get_undefined(env, &undefined);
  return undefined;
}

// grc.interceptRequest(url: string, body?: string): RequestResult
static napi_value napi_intercept_request(napi_env env,
                                         napi_callback_info info) {
  if (!g_interceptor)
    return throw_error(env, "not initialized, call init() first");

  size_t argc = 2;
  napi_value argv[2];
  napi_get_cb_info(env, info, &argc, argv, NULL, NULL);

  if (argc < 1)
    return throw_error(env, "interceptRequest requires (url, body?)");

  char url[2048];
  if (get_string(env, argv[0], url, sizeof(url)) != 0)
    return throw_error(env, "url must be a string");

  char *body = NULL;
  size_t body_len = 0;

  if (argc >= 2) {
    napi_valuetype type;
    napi_typeof(env, argv[1], &type);
    if (type == napi_string) {
      napi_get_value_string_utf8(env, argv[1], NULL, 0, &body_len);
      body = malloc(body_len + 1);
      if (body) {
        napi_get_value_string_utf8(env, argv[1], body, body_len + 1, &body_len);
      }
    }
  }

  RequestResult res = intercept_request(g_interceptor, url, body, body_len);
  free(body);

  napi_value obj;
  napi_create_object(env, &obj);

  napi_value val;
  napi_create_int32(env, res.allowed, &val);
  napi_set_named_property(env, obj, "allowed", val);

  napi_create_string_utf8(env, res.model, NAPI_AUTO_LENGTH, &val);
  napi_set_named_property(env, obj, "model", val);

  napi_create_double(env, res.used_quota, &val);
  napi_set_named_property(env, obj, "usedQuota", val);

  napi_create_double(env, res.remaining_quota, &val);
  napi_set_named_property(env, obj, "remainingQuota", val);

  return obj;
}

// grc.interceptResponse(url: string, body: string): ResponseResult
static napi_value napi_intercept_response(napi_env env,
                                          napi_callback_info info) {
  if (!g_interceptor)
    return throw_error(env, "not initialized, call init() first");

  size_t argc = 2;
  napi_value argv[2];
  napi_get_cb_info(env, info, &argc, argv, NULL, NULL);

  if (argc < 2)
    return throw_error(env, "interceptResponse requires (url, body)");

  char url[2048];
  if (get_string(env, argv[0], url, sizeof(url)) != 0)
    return throw_error(env, "url must be a string");

  size_t body_len = 0;
  napi_get_value_string_utf8(env, argv[1], NULL, 0, &body_len);
  char *body = malloc(body_len + 1);
  if (!body)
    return throw_error(env, "allocation failed");
  napi_get_value_string_utf8(env, argv[1], body, body_len + 1, &body_len);

  ResponseResult res = intercept_response(g_interceptor, url, body, body_len);
  free(body);

  napi_value obj;
  napi_create_object(env, &obj);

  napi_value val;
  napi_create_double(env, res.cost, &val);
  napi_set_named_property(env, obj, "cost", val);

  napi_create_int32(env, res.input_tokens, &val);
  napi_set_named_property(env, obj, "inputTokens", val);

  napi_create_int32(env, res.output_tokens, &val);
  napi_set_named_property(env, obj, "outputTokens", val);

  napi_create_double(env, res.used_quota, &val);
  napi_set_named_property(env, obj, "usedQuota", val);

  napi_create_double(env, res.remaining_quota, &val);
  napi_set_named_property(env, obj, "remainingQuota", val);

  return obj;
}

// grc.destroy(): void
static napi_value napi_destroy(napi_env env, napi_callback_info info) {
  if (g_interceptor) {
    interceptor_free(g_interceptor);
    g_interceptor = NULL;
  }

  napi_value undefined;
  napi_get_undefined(env, &undefined);
  return undefined;
}

NAPI_MODULE_INIT() {
  napi_property_descriptor props[] = {
      {"init", NULL, napi_init, NULL, NULL, NULL, napi_default_method, NULL},
      {"enableLogging", NULL, napi_enable_logging, NULL, NULL, NULL,
       napi_default_method, NULL},
      {"interceptRequest", NULL, napi_intercept_request, NULL, NULL, NULL,
       napi_default_method, NULL},
      {"interceptResponse", NULL, napi_intercept_response, NULL, NULL, NULL,
       napi_default_method, NULL},
      {"destroy", NULL, napi_destroy, NULL, NULL, NULL, napi_default_method,
       NULL},
  };

  napi_define_properties(env, exports, sizeof(props) / sizeof(props[0]), props);
  return exports;
}
