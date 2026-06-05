//
// Created by Samrat on 04/06/26.
//

#include "../include/response_parser.h"
#include "../lib/yyjson/yyjson.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static ParsedResponse parse_openai(const char *body, size_t body_len) {
  ParsedResponse result = {0};

  yyjson_doc *doc = yyjson_read(body, body_len, 0);
  if (!doc)
    return result;

  yyjson_val *root = yyjson_doc_get_root(doc);

  yyjson_val *model = yyjson_obj_get(root, "model");
  if (model)
    strncpy(result.model, yyjson_get_str(model), sizeof(result.model) - 1);

  yyjson_val *usage = yyjson_obj_get(root, "usage");
  if (usage) {
    yyjson_val *prompt = yyjson_obj_get(usage, "prompt_tokens");
    yyjson_val *completion = yyjson_obj_get(usage, "completion_tokens");

    if (prompt)
      result.usage.input_tokens = yyjson_get_int(prompt);
    if (completion)
      result.usage.output_tokens = yyjson_get_int(completion);

    yyjson_val *cache_read = yyjson_obj_get(usage, "prompt_tokens_details");
    if (cache_read) {
      yyjson_val *cached = yyjson_obj_get(cache_read, "cached_tokens");
      if (cached)
        result.usage.cache_read_tokens = yyjson_get_int(cached);
    }

    result.success = true;
  }

  yyjson_doc_free(doc);
  return result;
}

static ParsedResponse parse_anthropic(const char *body, size_t body_len) {
  ParsedResponse result = {0};

  yyjson_doc *doc = yyjson_read(body, body_len, 0);
  if (!doc)
    return result;

  yyjson_val *root = yyjson_doc_get_root(doc);

  yyjson_val *model = yyjson_obj_get(root, "model");
  if (model)
    strncpy(result.model, yyjson_get_str(model), sizeof(result.model) - 1);

  yyjson_val *usage = yyjson_obj_get(root, "usage");
  if (usage) {
    yyjson_val *input = yyjson_obj_get(usage, "input_tokens");
    yyjson_val *output = yyjson_obj_get(usage, "output_tokens");

    if (input)
      result.usage.input_tokens = yyjson_get_int(input);
    if (output)
      result.usage.output_tokens = yyjson_get_int(output);

    yyjson_val *cache_read = yyjson_obj_get(usage, "cache_read_input_tokens");
    yyjson_val *cache_write =
        yyjson_obj_get(usage, "cache_creation_input_tokens");

    if (cache_read)
      result.usage.cache_read_tokens = yyjson_get_int(cache_read);
    if (cache_write)
      result.usage.cache_write_tokens = yyjson_get_int(cache_write);

    result.success = true;
  }

  yyjson_doc_free(doc);
  return result;
}

static ParsedResponse parse_bedrock(const char *body, size_t body_len) {
  ParsedResponse result = {0};

  yyjson_doc *doc = yyjson_read(body, body_len, 0);
  if (!doc)
    return result;

  yyjson_val *root = yyjson_doc_get_root(doc);

  yyjson_val *usage = yyjson_obj_get(root, "usage");
  if (usage) {
    yyjson_val *input = yyjson_obj_get(usage, "inputTokens");
    yyjson_val *output = yyjson_obj_get(usage, "outputTokens");

    if (input)
      result.usage.input_tokens = yyjson_get_int(input);
    if (output)
      result.usage.output_tokens = yyjson_get_int(output);

    // cache read — Bedrock uses both field names
    yyjson_val *cache_read = yyjson_obj_get(usage, "cacheReadInputTokens");
    if (!cache_read)
      cache_read = yyjson_obj_get(usage, "cacheReadInputTokenCount");
    if (cache_read)
      result.usage.cache_read_tokens = yyjson_get_int(cache_read);

    // cache write — Bedrock uses both field names
    yyjson_val *cache_write = yyjson_obj_get(usage, "cacheWriteInputTokens");
    if (!cache_write)
      cache_write = yyjson_obj_get(usage, "cacheWriteInputTokenCount");
    if (cache_write)
      result.usage.cache_write_tokens = yyjson_get_int(cache_write);

    result.success = true;
  }

  yyjson_doc_free(doc);
  return result;
}

ParserRegistry *parser_registry_init(void) {
  ParserRegistry *reg = malloc(sizeof(ParserRegistry));
  if (!reg)
    return nullptr;

  reg->count = 0;

  // Register built-in parsers
  parser_registry_register(reg, "openai", parse_openai);
  parser_registry_register(reg, "anthropic", parse_anthropic);
  parser_registry_register(reg, "bedrock", parse_bedrock);

  return reg;
}

void parser_registry_register(ParserRegistry *reg, const char *provider,
                              ParserFn fn) {
  if (!reg || !provider || !fn)
    return;
  if (reg->count >= MAX_PARSERS)
    return;

  strncpy(reg->entries[reg->count].provider, provider,
          sizeof(reg->entries[reg->count].provider) - 1);
  reg->entries[reg->count].parse = fn;
  reg->count++;
}

ParserFn parser_registry_get(ParserRegistry *reg, const char *provider) {
  if (!reg || !provider)
    return nullptr;

  for (int i = 0; i < reg->count; i++) {
    if (strcmp(reg->entries[i].provider, provider) == 0) {
      return reg->entries[i].parse;
    }
  }
  return nullptr;
}

void parser_registry_free(ParserRegistry *reg) {
  if (reg)
    free(reg);
}

ParsedResponse parse_response(ParserRegistry *reg, const char *provider,
                              const char *body, size_t body_len) {
  ParsedResponse result = {0};

  ParserFn fn = parser_registry_get(reg, provider);
  if (!fn) {
    printf("[parse_response] no parser for provider: %s\n", provider);
    return result;
  }

  return fn(body, body_len);
}
