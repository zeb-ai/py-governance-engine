//
// Created by Samrat on 04/06/26.
//

#include "../include/interceptor.h"
#include "../lib/yyjson/yyjson.h"
#include <regex.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

Interceptor *interceptor_init(const char *api_key, const char *pricing_file) {
  if (!api_key || !pricing_file)
    return nullptr;

  AuthToken *auth = auth_token_decode(api_key);
  if (!auth)
    return nullptr;

  CostCalculator *calculator = cost_calculator_init(pricing_file);
  if (!calculator) {
    auth_token_free(auth);
    return nullptr;
  }

  QuotaClient *quota =
      quota_client_init(auth->domain, auth->user_id, auth->group_id);
  if (!quota) {
    cost_calculator_free(calculator);
    auth_token_free(auth);
    return nullptr;
  }

  Interceptor *ctx = malloc(sizeof(Interceptor));
  if (!ctx) {
    quota_client_free(quota);
    cost_calculator_free(calculator);
    auth_token_free(auth);
    return nullptr;
  }

  ParserRegistry *parsers = parser_registry_init();
  if (!parsers) {
    quota_client_free(quota);
    cost_calculator_free(calculator);
    auth_token_free(auth);
    free(ctx);
    return nullptr;
  }

  ctx->auth = auth;
  ctx->calculator = calculator;
  ctx->quota = quota;
  ctx->parsers = parsers;
  ctx->cached_used = -1;
  ctx->cached_remaining = -1;
  return ctx;
}

RequestResult intercept_request(Interceptor *ctx, const char *url,
                                const char *body, size_t body_len) {
  RequestResult result = {0};

  if (!ctx || !url) {
    result.allowed = -1;
    return result;
  }

  // Match URL against api_patterns
  int matched = 0;
  for (int i = 0; i < ctx->calculator->pattern_count; i++) {
    regex_t regex;
    if (regcomp(&regex, ctx->calculator->api_patterns[i],
                REG_EXTENDED | REG_NOSUB) == 0) {
      if (regexec(&regex, url, 0, nullptr, 0) == 0) {
        matched = 1;
        regfree(&regex);
        break;
      }
      regfree(&regex);
    }
  }

  if (!matched) {
    result.allowed = -1;
    return result;
  }

  // Check quota (fetch from server only on first call)
  if (ctx->cached_remaining < 0) {
    Quota quota = quota_client_get(ctx->quota);
    ctx->cached_used = quota.used_quota;
    ctx->cached_remaining = quota.remaining_quota;
  }

  if (ctx->cached_remaining <= 0) {
    result.allowed = 0;
    result.used_quota = ctx->cached_used;
    result.remaining_quota = ctx->cached_remaining;
    return result;
  }

  // Extract model from request body
  if (body && body_len > 0) {
    yyjson_doc *doc = yyjson_read(body, body_len, 0);
    if (doc) {
      yyjson_val *r = yyjson_doc_get_root(doc);
      yyjson_val *model = yyjson_obj_get(r, "model");
      if (model)
        strncpy(result.model, yyjson_get_str(model), sizeof(result.model) - 1);
      yyjson_doc_free(doc);
    }
  }

  result.allowed = 1;
  return result;
}

ResponseResult intercept_response(Interceptor *ctx, const char *url,
                                  const char *body, size_t body_len) {
  ResponseResult result = {0};
  if (!ctx || !body || body_len == 0)
    return result;

  // Detect provider from URL
  const char *provider = nullptr;
  if (strstr(url, "openai.com"))
    provider = "openai";
  else if (strstr(url, "anthropic.com"))
    provider = "anthropic";
  else if (strstr(url, "bedrock-runtime"))
    provider = "bedrock";

  if (!provider)
    return result;

  // Parse response to extract model + tokens
  printf("[intercept_response] provider: %s, body_len: %zu\n", provider,
         body_len);
  fflush(stdout);
  ParsedResponse parsed =
      parse_response(ctx->parsers, provider, body, body_len);
  printf("[intercept_response] parsed.success: %d, input: %d, output: %d\n",
         parsed.success, parsed.usage.input_tokens, parsed.usage.output_tokens);
  fflush(stdout);
  if (!parsed.success)
    return result;

  // Bedrock: model is in URL, not body. Extract from /model/<model_id>/
  if (strcmp(provider, "bedrock") == 0 && parsed.model[0] == '\0') {
    const char *m = strstr(url, "/model/");
    if (m) {
      m += 7;
      const char *end = strchr(m, '/');
      size_t len = end ? (size_t)(end - m) : strlen(m);

      // URL-decode into parsed.model (%3A → :)
      size_t j = 0;
      for (size_t i = 0; i < len && j < sizeof(parsed.model) - 1; i++) {
        if (m[i] == '%' && i + 2 < len) {
          char hex[3] = {m[i + 1], m[i + 2], '\0'};
          parsed.model[j++] = (char)strtol(hex, nullptr, 16);
          i += 2;
        } else {
          parsed.model[j++] = m[i];
        }
      }
      parsed.model[j] = '\0';

      // us.anthropic.xxx → regional.anthropic.xxx for pricing lookup
      const char *dot = strchr(parsed.model, '.');
      if (dot) {
        char regional_model[256];
        snprintf(regional_model, sizeof(regional_model), "regional%s", dot);
        strncpy(parsed.model, regional_model, sizeof(parsed.model) - 1);
      }
    }
  }

  // Calculate cost
  printf("[intercept_response] model: '%s', input: %d, output: %d\n",
         parsed.model, parsed.usage.input_tokens, parsed.usage.output_tokens);
  fflush(stdout);
  CostResult cost =
      cost_calculator_calculate(ctx->calculator, parsed.model, &parsed.usage);
  if (cost.error != COST_OK) {
    printf("[intercept_response] cost error: %s\n", cost.error_message);
    fflush(stdout);
    return result;
  }

  // Report to quota server
  int total_tokens = parsed.usage.input_tokens + parsed.usage.output_tokens;
  Quota quota = quota_client_post(ctx->quota, total_tokens, cost.total_cost);

  // Update cache
  ctx->cached_used = quota.used_quota;
  ctx->cached_remaining = quota.remaining_quota;

  // Fill result
  result.cost = cost.total_cost;
  result.input_tokens = parsed.usage.input_tokens;
  result.output_tokens = parsed.usage.output_tokens;
  result.used_quota = quota.used_quota;
  result.remaining_quota = quota.remaining_quota;

  return result;
}

void interceptor_free(Interceptor *ctx) {
  if (!ctx)
    return;
  auth_token_free(ctx->auth);
  cost_calculator_free(ctx->calculator);
  quota_client_free(ctx->quota);
  parser_registry_free(ctx->parsers);
  free(ctx);
}
