//
// Created by Samrat on 04/06/26.
//

#pragma once

#include "cost_calculation.h"
#include <stddef.h>

#define MAX_PARSERS 16

typedef struct {
  char model[256];
  TokenUsage usage;
  bool success;
} ParsedResponse;

typedef ParsedResponse (*ParserFn)(const char *body, size_t body_len);

typedef struct {
  char provider[64];
  ParserFn parse;
} ParserEntry;

typedef struct {
  ParserEntry entries[MAX_PARSERS];
  int count;
} ParserRegistry;

ParserRegistry *parser_registry_init(void);
void parser_registry_register(ParserRegistry *reg, const char *provider,
                              ParserFn fn);
ParserFn parser_registry_get(ParserRegistry *reg, const char *provider);
void parser_registry_free(ParserRegistry *reg);

ParsedResponse parse_response(ParserRegistry *reg, const char *provider,
                              const char *body, size_t body_len);
