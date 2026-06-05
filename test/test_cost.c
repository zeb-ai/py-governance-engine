//
// Created by Samrat on 03/06/26.
//

#include "../include/cost_calculation.h"
#include <stdio.h>

int main() {
  const char *path = "data/merged_pricing.json";

  CostCalculator *calc = cost_calculator_init(path);
  if (!calc) {
    printf("Failed to initialize calculator\n");
    printf("Check if file exists: %s\n", path);
    return 1;
  }

  printf("Loaded %d models\n\n", calc->total_models);

  TokenUsage usage = {.input_tokens = 1000,
                      .output_tokens = 500,
                      .cache_read_tokens = 0,
                      .cache_write_tokens = 0};

  printf("Testing model: claude-3-5-sonnet\n");
  printf("Input tokens: %d\n", usage.input_tokens);
  printf("Output tokens: %d\n\n", usage.output_tokens);

  CostResult result =
      cost_calculator_calculate(calc, "claude-3-5-sonnet", &usage);

  if (result.error == COST_OK) {
    printf("Calculation successful!\n");
    printf("Input cost:  $%.6f\n", result.input_cost);
    printf("Output cost: $%.6f\n", result.output_cost);
    printf("TOTAL COST:  $%.6f\n", result.total_cost);
  } else {
    printf("Error: %s\n", result.error_message);
  }

  cost_calculator_free(calc);
  return 0;
}
