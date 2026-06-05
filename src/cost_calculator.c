//
// Created by Samrat on 02/06/26.
//

#include "../include/cost_calculation.h"
#include "../lib/yyjson/yyjson.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MILLION 1000000.0

// djb2 algorithm
unsigned long hash_string(const char *str) {
  unsigned long hash = 5381; // magic number by algo itself <> prime number
  int i = 0;

  while (str[i] != '\0') { // check is not last value
    int c = str[i];

    unsigned long shift = hash << 5; // 2 power 5 = 32, 5381 x 32
    unsigned long times33 = shift + hash;
    hash = times33 + c;
    i++;
  }
  return hash;
};

// creating hashmap
HashMap *hashmap_create(size_t bucket_count) {
  HashMap *map = malloc(sizeof(HashMap));

  if (!map)
    return NULL;

  map->buckets = calloc(bucket_count, sizeof(HashNode *));
  if (!map->buckets) {
    free(map);
    return NULL;
  }

  map->bucket_count = bucket_count;
  map->model_count = 0;
  return map;
};

/*
 * Insert model pricing into hash map
 * Handles collision with linked list (chaining)
 */
void hashmap_insert(HashMap *map, const char *model_id, ModelPricing pricing) {
  // Calculate hash value and find which bucket to use
  unsigned long hash = hash_string(model_id);
  size_t bucket_index =
      hash % map->bucket_count; // modulo to fit within bucket count

  // Create new node in memory
  HashNode *node = malloc(sizeof(HashNode));
  if (!node)
    return;

  // Copy model_id into node's key
  int i = 0;
  while (model_id[i] != '\0' && i < MAX_MODEL_ID_LEN - 1) {
    node->key[i] = model_id[i];
    i++;
  }
  node->key[i] = '\0'; // null terminate the string

  // Copy pricing data into node
  node->pricing.input = pricing.input;
  node->pricing.output = pricing.output;
  node->pricing.cache_read = pricing.cache_read;
  node->pricing.cache_write = pricing.cache_write;
  node->pricing.input_audio = pricing.input_audio;
  node->pricing.output_audio = pricing.output_audio;

  // Insert at head of linked list (collision handling)
  node->next = map->buckets[bucket_index]; // point to current head
  map->buckets[bucket_index] = node;       // make this node the new head

  // Increment count
  map->model_count++;
}

ModelPricing *hashmap_get(HashMap *map, const char *model_id) {
  unsigned long hash = hash_string(model_id);
  size_t bucket_index = hash % map->bucket_count;

  HashNode *current = map->buckets[bucket_index];

  while (current != NULL) {
    int i = 0;
    int match = 1;

    while (current->key[i] != '\0' && model_id[i] != '\0') {
      if (current->key[i] != model_id[i]) {
        match = 0;
        break;
      }
      i++;
    }

    if (match && current->key[i] == '\0' && model_id[i] == '\0') {
      return &current->pricing;
    }

    current = current->next;
  }

  return nullptr;
}

CostCalculator *cost_calculator_init(const char *pricing_file) {
  CostCalculator *calc = malloc(sizeof(CostCalculator));
  if (!calc)
    return nullptr;

  yyjson_read_err err;
  yyjson_doc *doc = yyjson_read_file(pricing_file, 0, nullptr, &err);
  if (!doc) {
    free(calc);
    return nullptr;
  }

  calc->models = hashmap_create(2048);
  if (!calc->models) {
    yyjson_doc_free(doc);
    free(calc);
    return nullptr;
  }

  yyjson_val *root = yyjson_doc_get_root(doc);

  // Load api_patterns from providers
  yyjson_val *providers = yyjson_obj_get(root, "providers");
  calc->pattern_count = 0;
  size_t idx, max;
  yyjson_val *key, *val;
  yyjson_obj_foreach(providers, idx, max, key, val) {
    yyjson_val *pattern = yyjson_obj_get(val, "api_pattern");
    if (pattern && calc->pattern_count < 64) {
      strncpy(calc->api_patterns[calc->pattern_count], yyjson_get_str(pattern),
              511);
      calc->pattern_count++;
    }
  }

  // Load models
  yyjson_val *models = yyjson_obj_get(root, "models");
  calc->total_models = 0;
  yyjson_obj_foreach(models, idx, max, key, val) {
    const char *model_id = yyjson_get_str(key);
    yyjson_val *pricing_obj = yyjson_obj_get(val, "pricing");

    ModelPricing pricing = {0};
    yyjson_val *price_val;

    price_val = yyjson_obj_get(pricing_obj, "input");
    if (price_val)
      pricing.input = yyjson_get_num(price_val);

    price_val = yyjson_obj_get(pricing_obj, "output");
    if (price_val)
      pricing.output = yyjson_get_num(price_val);

    price_val = yyjson_obj_get(pricing_obj, "cache_read");
    if (price_val)
      pricing.cache_read = yyjson_get_num(price_val);

    price_val = yyjson_obj_get(pricing_obj, "cache_write");
    if (price_val)
      pricing.cache_write = yyjson_get_num(price_val);

    hashmap_insert(calc->models, model_id, pricing);
    calc->total_models++;
  }

  calc->initialized = true;
  yyjson_doc_free(doc);
  return calc;
}

CostResult cost_calculator_calculate(CostCalculator *calc, const char *model_id,
                                     const TokenUsage *usage) {
  CostResult result = {0};

  ModelPricing *pricing = hashmap_get(calc->models, model_id);
  if (!pricing) {
    result.error = COST_ERR_MODEL_NOT_FOUND;
    snprintf(result.error_message, sizeof(result.error_message),
             "Model not found: %s", model_id);
    return result;
  }

  result.input_cost = (usage->input_tokens / MILLION) * pricing->input;
  result.output_cost = (usage->output_tokens / MILLION) * pricing->output;
  result.cache_read_cost =
      (usage->cache_read_tokens / MILLION) * pricing->cache_read;
  result.cache_write_cost =
      (usage->cache_write_tokens / MILLION) * pricing->cache_write;

  result.total_cost = result.input_cost + result.output_cost +
                      result.cache_read_cost + result.cache_write_cost;

  result.error = COST_OK;
  return result;
}

void cost_calculator_free(CostCalculator *calc) {
  if (!calc)
    return;

  if (calc->models) {
    for (size_t i = 0; i < calc->models->bucket_count; i++) {
      HashNode *current = calc->models->buckets[i];
      while (current) {
        HashNode *next = current->next;
        free(current);
        current = next;
      }
    }
    free(calc->models->buckets);
    free(calc->models);
  }

  free(calc);
}
