//
// Created by Samrat on 02/06/26.
//

#pragma once

#include <stdbool.h>
#include <stddef.h>

#define MAX_MODEL_ID_LEN 256
#define MAX_PROVIDER_LEN 64
#define MAX_MODEL_NAME_LEN 256

typedef enum {
  COST_OK = 0,
  COST_ERR_MODEL_NOT_FOUND = -1,
  COST_ERR_INVALID_TOKENS = -2,
  COST_ERR_NO_PRICING = -3,
  COST_ERR_INIT_FAILED = -4,
  COST_ERR_FILE_NOT_FOUND = -5,
  COST_ERR_PARSE_ERROR = -6
} CostError;

/**
 * Model pricing information (all in $/MTok)
 */
typedef struct {
  double input;
  double output;
  double cache_read;
  double cache_write;
  double input_audio;
  double output_audio;
} ModelPricing;

/**
 * Model limits
 */
typedef struct {
  int context_window;
  int max_output;
} ModelLimits;

/**
 * Complete model information
 */
typedef struct {
  char model_id[MAX_MODEL_ID_LEN];
  char provider[MAX_PROVIDER_LEN];
  char name[MAX_MODEL_NAME_LEN];
  ModelPricing pricing;
  ModelLimits limits;
  bool deprecated;
} Model;

/**
 * Token usage breakdown
 */
typedef struct {
  int input_tokens;
  int output_tokens;
  int cache_read_tokens;
  int cache_write_tokens;
  int input_audio_tokens;
  int output_audio_tokens;
} TokenUsage;

/**
 * Cost calculation result
 */
typedef struct {
  double total_cost;
  double input_cost;
  double output_cost;
  double cache_read_cost;
  double cache_write_cost;
  double input_audio_cost;
  double output_audio_cost;
  CostError error; /* Error code (COST_OK if successful) */
  char error_message[256];
} CostResult;

/**
 * Hash map node for model lookup
 */
typedef struct HashNode {
  char key[MAX_MODEL_ID_LEN];
  ModelPricing pricing;
  struct HashNode *next;
} HashNode;

/**
 * Hash map for O(1) model lookup
 */
typedef struct {
  HashNode **buckets;
  size_t bucket_count;
  size_t model_count;
} HashMap;

/**
 * Cost calculator context (holds all loaded data)
 */
typedef struct {
  HashMap *models;
  HashMap *aliases;
  char api_patterns[64][512];
  int pattern_count;
  int total_models;
  int total_providers;
  bool initialized;
} CostCalculator;

/**
 * Initialize cost calculator from merged pricing JSON file
 *
 * @param pricing_file Path to merged_pricing.json
 * @return CostCalculator context or NULL on failure
 */
CostCalculator *cost_calculator_init(const char *pricing_file);

/**
 * Clean up and free all resources
 *
 * @param calc Calculator context to free
 */
void cost_calculator_free(CostCalculator *calc);

/**
 * Calculate cost for a model given token usage
 *
 * @param calc Calculator context
 * @param model_id Model identifier (e.g., "claude-3-5-sonnet", "gpt-4o")
 * @param usage Token usage breakdown
 * @return Cost result with breakdown and error status
 */
CostResult cost_calculator_calculate(CostCalculator *calc, const char *model_id,
                                     const TokenUsage *usage);
