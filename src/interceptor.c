//
// Created by Samrat on 04/06/26.
//

#include "../include/interceptor.h"
#include "../include/logger.h"
#include "../include/otel.h"
#include "../lib/yyjson/yyjson.h"
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#ifndef _WIN32
#include <regex.h>
#endif

Interceptor *interceptor_init(const char *api_key, const char *pricing_file,
                              const char *app_name) {
  if (!api_key || !pricing_file)
    return NULL;

  AuthToken *auth = auth_token_decode(api_key);
  if (!auth)
    return NULL;

  CostCalculator *calculator = cost_calculator_init(pricing_file);
  if (!calculator) {
    auth_token_free(auth);
    return NULL;
  }

  QuotaClient *quota =
      quota_client_init(auth->domain, auth->user_id, auth->group_id);
  if (!quota) {
    cost_calculator_free(calculator);
    auth_token_free(auth);
    return NULL;
  }

  Interceptor *ctx = malloc(sizeof(Interceptor));
  if (!ctx) {
    quota_client_free(quota);
    cost_calculator_free(calculator);
    auth_token_free(auth);
    return NULL;
  }

  ParserRegistry *parsers = parser_registry_init();
  if (!parsers) {
    quota_client_free(quota);
    cost_calculator_free(calculator);
    auth_token_free(auth);
    free(ctx);
    return NULL;
  }

  Logger *logger = NULL;

  OtelExporter *otel = NULL;
  if (auth->opentelemetry[0] != '\0') {
    const char *service_name = app_name ? app_name : "unknown-service";
    otel = otel_exporter_init(auth->opentelemetry, service_name, app_name,
                              auth->user_id, auth->group_id);
  }

  ctx->auth = auth;
  ctx->calculator = calculator;
  ctx->quota = quota;
  ctx->parsers = parsers;
  ctx->logger = logger;
  ctx->otel = otel;
  ctx->current_trace_id[0] = '\0';
  ctx->current_span_id[0] = '\0';
  ctx->request_start_ns = 0;
  ctx->cached_used = -1;
  ctx->cached_remaining = -1;

  logger_log(logger, LOG_INFO, "interceptor initialized (user=%s, group=%s)",
             auth->user_id, auth->group_id);
  return ctx;
}

void interceptor_enable_logging(Interceptor *ctx, LogLevel level,
                                const char *path) {
  if (!ctx)
    return;
  if (ctx->logger)
    logger_free(ctx->logger);
  ctx->logger = logger_init(level, path);
}

RequestResult intercept_request(Interceptor *ctx, const char *url,
                                const char *body, size_t body_len) {
  RequestResult result = {0};

  if (!ctx || !url) {
    result.allowed = -1;
    return result;
  }

  logger_log(ctx->logger, LOG_DEBUG, "request url=%s", url);

  // Match URL against api_patterns
  int matched = 0;
  for (int i = 0; i < ctx->calculator->pattern_count; i++) {
#ifdef _WIN32
    if (strstr(url, ctx->calculator->api_patterns[i]) != NULL) {
      matched = 1;
      break;
    }
#else
    regex_t regex;
    if (regcomp(&regex, ctx->calculator->api_patterns[i],
                REG_EXTENDED | REG_NOSUB) == 0) {
      if (regexec(&regex, url, 0, NULL, 0) == 0) {
        matched = 1;
        regfree(&regex);
        break;
      }
      regfree(&regex);
    }
#endif
  }

  if (!matched) {
    logger_log(ctx->logger, LOG_DEBUG, "url not matched, skipping: %s", url);
    result.allowed = -1;
    return result;
  }

  // Check quota when there is no cache
  // when the quota is exceeded, calling again coz need cost may be updated
  // while application running bcoz we have cache for request checking when we
  // get the response also return same structure of data (remaining)
  if (ctx->cached_remaining < 0 || ctx->cached_remaining <= 0) {
    Quota quota = quota_client_get(ctx->quota);
    ctx->cached_used = quota.used_quota;
    ctx->cached_remaining = quota.remaining_quota;
    logger_log(ctx->logger, LOG_INFO, "quota fetched: used=%.4f remaining=%.4f",
               quota.used_quota, quota.remaining_quota);
  }

  if (ctx->cached_remaining <= 0) {
    logger_log(ctx->logger, LOG_WARN,
               "quota exceeded: used=%.4f remaining=%.4f", ctx->cached_used,
               ctx->cached_remaining);
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

  // starting span tracking >>>
  if (ctx->otel) {
    otel_generate_trace_id(ctx->current_trace_id);
    otel_generate_span_id(ctx->current_span_id);
    ctx->request_start_ns = otel_now_ns();
  }

  logger_log(ctx->logger, LOG_DEBUG, "request allowed, model=%s", result.model);
  result.allowed = 1;
  return result;
}

ResponseResult intercept_response(Interceptor *ctx, const char *url,
                                  const char *body, size_t body_len) {
  ResponseResult result = {0};
  if (!ctx || !body || body_len == 0)
    return result;

  logger_log(ctx->logger, LOG_DEBUG, "response url=%s body=%.*s", url,
             (int)(body_len > 512 ? 512 : body_len), body);

  // Detect provider from URL
  const char *provider = NULL;
  if (strstr(url, "openai.com"))
    provider = "openai";
  else if (strstr(url, "anthropic.com"))
    provider = "anthropic";
  else if (strstr(url, "bedrock-runtime"))
    provider = "bedrock";

  if (!provider) {
    logger_log(ctx->logger, LOG_WARN, "unknown provider for url=%s", url);
    return result;
  }

  logger_log(ctx->logger, LOG_DEBUG, "detected provider=%s", provider);

  ParsedResponse parsed =
      parse_response(ctx->parsers, provider, body, body_len);
  if (!parsed.success) {
    logger_log(ctx->logger, LOG_ERROR,
               "failed to parse response for provider=%s url=%s", provider,
               url);
    return result;
  }

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
          parsed.model[j++] = (char)strtol(hex, NULL, 16);
          i += 2;
        } else {
          parsed.model[j++] = m[i];
        }
      }
      parsed.model[j] = '\0';

      // Normalize to regional.<provider>.<model> for pricing lookup.
      //   us.anthropic.xxx          -> regional.anthropic.xxx  (strip region)
      //   anthropic.xxx             -> regional.anthropic.xxx  (just prepend)
      static const char *region_prefixes[] = {"us.", "eu.",     "apac.",
                                              "ap.", "us-gov.", NULL};
      const char *model_start = parsed.model;
      for (int i = 0; region_prefixes[i]; i++) {
        size_t plen = strlen(region_prefixes[i]);
        if (strncmp(parsed.model, region_prefixes[i], plen) == 0) {
          model_start = parsed.model + plen;
          break;
        }
      }
      if (strncmp(model_start, "regional.", 9) != 0) {
        char regional_model[256];
        snprintf(regional_model, sizeof(regional_model), "regional.%s",
                 model_start);
        strncpy(parsed.model, regional_model, sizeof(parsed.model) - 1);
        parsed.model[sizeof(parsed.model) - 1] = '\0';
      }
    }
  }

  logger_log(ctx->logger, LOG_DEBUG,
             "parsed: model=%s input_tokens=%d output_tokens=%d", parsed.model,
             parsed.usage.input_tokens, parsed.usage.output_tokens);

  CostResult cost =
      cost_calculator_calculate(ctx->calculator, parsed.model, &parsed.usage);
  if (cost.error != COST_OK) {
    logger_log(ctx->logger, LOG_ERROR, "cost calculation failed: %s",
               cost.error_message);
    return result;
  }

  logger_log(ctx->logger, LOG_INFO, "cost=%.6f (input=%.6f output=%.6f)",
             cost.total_cost, cost.input_cost, cost.output_cost);

  // Report to quota server
  int total_tokens = parsed.usage.input_tokens + parsed.usage.output_tokens;
  Quota quota = quota_client_post(ctx->quota, total_tokens, cost.total_cost);

  // Update cache
  ctx->cached_used = quota.used_quota;
  ctx->cached_remaining = quota.remaining_quota;

  logger_log(ctx->logger, LOG_INFO, "quota updated: used=%.4f remaining=%.4f",
             quota.used_quota, quota.remaining_quota);

  // Fill result
  result.cost = cost.total_cost;
  result.input_tokens = parsed.usage.input_tokens;
  result.output_tokens = parsed.usage.output_tokens;
  result.used_quota = quota.used_quota;
  result.remaining_quota = quota.remaining_quota;

  if (ctx->otel && ctx->current_trace_id[0] != '\0') {
    OtelSpan span = {0};
    strncpy(span.trace_id, ctx->current_trace_id, sizeof(span.trace_id) - 1);
    strncpy(span.span_id, ctx->current_span_id, sizeof(span.span_id) - 1);
    strncpy(span.name, "llm.completion", sizeof(span.name) - 1);
    span.kind = OTEL_SPAN_KIND_CLIENT;
    span.start_time_ns = ctx->request_start_ns;
    span.end_time_ns = otel_now_ns();
    span.status_code = 1; // OK

    // Add comprehensive LLM attributes
    span.attribute_count = 17;
    span.attributes = malloc(span.attribute_count * sizeof(OtelAttribute));
    if (span.attributes) {
      int idx = 0;

      // Provider and model
      strncpy(span.attributes[idx].key, "llm.provider", 63);
      strncpy(span.attributes[idx++].value, provider, 255);

      strncpy(span.attributes[idx].key, "llm.model", 63);
      strncpy(span.attributes[idx++].value, parsed.model, 255);

      // Token usage
      strncpy(span.attributes[idx].key, "llm.input_tokens", 63);
      snprintf(span.attributes[idx++].value, 255, "%d",
               parsed.usage.input_tokens);

      strncpy(span.attributes[idx].key, "llm.output_tokens", 63);
      snprintf(span.attributes[idx++].value, 255, "%d",
               parsed.usage.output_tokens);

      strncpy(span.attributes[idx].key, "llm.total_tokens", 63);
      snprintf(span.attributes[idx++].value, 255, "%d", total_tokens);

      strncpy(span.attributes[idx].key, "llm.cache_read_tokens", 63);
      snprintf(span.attributes[idx++].value, 255, "%d",
               parsed.usage.cache_read_tokens);

      strncpy(span.attributes[idx].key, "llm.cache_write_tokens", 63);
      snprintf(span.attributes[idx++].value, 255, "%d",
               parsed.usage.cache_write_tokens);

      // Cost breakdown
      strncpy(span.attributes[idx].key, "llm.cost.total", 63);
      snprintf(span.attributes[idx++].value, 255, "%.6f", cost.total_cost);

      strncpy(span.attributes[idx].key, "llm.cost.input", 63);
      snprintf(span.attributes[idx++].value, 255, "%.6f", cost.input_cost);

      strncpy(span.attributes[idx].key, "llm.cost.output", 63);
      snprintf(span.attributes[idx++].value, 255, "%.6f", cost.output_cost);

      strncpy(span.attributes[idx].key, "llm.cost.cache_read", 63);
      snprintf(span.attributes[idx++].value, 255, "%.6f", cost.cache_read_cost);

      strncpy(span.attributes[idx].key, "llm.cost.cache_write", 63);
      snprintf(span.attributes[idx++].value, 255, "%.6f",
               cost.cache_write_cost);

      // Quota information
      strncpy(span.attributes[idx].key, "quota.used", 63);
      snprintf(span.attributes[idx++].value, 255, "%.4f", quota.used_quota);

      strncpy(span.attributes[idx].key, "quota.remaining", 63);
      snprintf(span.attributes[idx++].value, 255, "%.4f",
               quota.remaining_quota);

      // User identification
      strncpy(span.attributes[idx].key, "user.id", 63);
      strncpy(span.attributes[idx++].value, ctx->auth->user_id, 255);

      strncpy(span.attributes[idx].key, "group.id", 63);
      strncpy(span.attributes[idx++].value, ctx->auth->group_id, 255);

      // Request URL
      strncpy(span.attributes[idx].key, "http.url", 63);
      strncpy(span.attributes[idx++].value, url, 255);

      otel_export_span(ctx->otel, &span);
    }

    // Reset span tracking for next request
    ctx->current_trace_id[0] = '\0';
    ctx->current_span_id[0] = '\0';
    ctx->request_start_ns = 0;
  }

  return result;
}

void interceptor_free(Interceptor *ctx) {
  if (!ctx)
    return;
  logger_log(ctx->logger, LOG_INFO, "interceptor shutting down");
  if (ctx->otel)
    otel_exporter_free(ctx->otel);
  auth_token_free(ctx->auth);
  cost_calculator_free(ctx->calculator);
  quota_client_free(ctx->quota);
  parser_registry_free(ctx->parsers);
  logger_free(ctx->logger);
  free(ctx);
}
