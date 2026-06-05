//
// Created by Samrat on 04/06/26.
//

#pragma once

#include "auth_token.h"
#include "cost_calculation.h"
#include "logger.h"
#include "quota_client.h"
#include "response_parser.h"

typedef struct {
  AuthToken *auth;
  CostCalculator *calculator;
  QuotaClient *quota;
  ParserRegistry *parsers;
  Logger *logger;
  double cached_used;
  double cached_remaining;
} Interceptor;

typedef struct {
  int allowed; // 1 = proceed, 0 = quota exceeded, -1 = not an LLM call
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

Interceptor *interceptor_init(const char *api_key, const char *pricing_file);
// need to expose in dev only, not planned for production usage
// not implemented file size control and duplication
void interceptor_enable_logging(Interceptor *ctx, LogLevel level,
                                const char *path);
RequestResult intercept_request(Interceptor *ctx, const char *url,
                                const char *body, size_t body_len);
ResponseResult intercept_response(Interceptor *ctx, const char *url,
                                  const char *body, size_t body_len);
void interceptor_free(Interceptor *ctx);
