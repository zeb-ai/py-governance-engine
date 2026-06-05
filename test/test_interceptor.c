//
// Created by Samrat on 04/06/26.
//

#include "../include/interceptor.h"
#include <stdio.h>
#include <string.h>

int main() {

  const char *api_key =
      "grc_"
      "eNp1zT0OgzAMQOG7eK75caw45jYhcaFSpVQQFhB3b6Zunb8nvQuOV4YJhlEtUMxIaoyi5FHN"
      "D-hGYzbJQuTgAWvZa6vXWj_71PcnLlvqTpu7VJqWau__"
      "uvxGSpyQHUcUcQlDbMtoz5l88EIS4P4Cmt4qiw";

  Interceptor *ctx = interceptor_init(api_key, "data/merged_pricing.json");
  if (!ctx) {
    printf("Failed to init interceptor\n");
    return 1;
  }
  printf("Interceptor initialized\n");
  printf("Patterns loaded: %d\n\n", ctx->calculator->pattern_count);

  const char *openai_url = "https://api.openai.com/v1/chat/completions";
  const char *body = "{\"model\": \"gpt-4o\", \"messages\": [{\"role\": "
                     "\"user\", \"content\": \"hello\"}]}";
  RequestResult r1 = intercept_request(ctx, openai_url, body, strlen(body));
  printf("Test 1 - OpenAI URL:\n");
  printf("  Allowed: %d\n", r1.allowed);
  printf("  Model:   %s\n\n", r1.model);

  const char *anthropic_url = "https://api.anthropic.com/v1/messages";
  const char *body2 = "{\"model\": \"claude-sonnet-4-20250514\", \"messages\": "
                      "[{\"role\": \"user\", \"content\": \"hi\"}]}";
  RequestResult r2 =
      intercept_request(ctx, anthropic_url, body2, strlen(body2));
  printf("Test 2 - Anthropic URL:\n");
  printf("  Allowed: %d\n", r2.allowed);
  printf("  Model:   %s\n\n", r2.model);

  const char *random_url = "https://api.github.com/repos";
  RequestResult r3 = intercept_request(ctx, random_url, NULL, 0);
  printf("Test 3 - Non-LLM URL:\n");
  printf("  Allowed: %d (expected -1)\n\n", r3.allowed);

  // Test 4: intercept_response - OpenAI format
  const char *openai_response =
      "{\"id\":\"chatcmpl-abc\",\"model\":\"gpt-4o\",\"usage\":{\"prompt_"
      "tokens\":1000,\"completion_tokens\":500,\"total_tokens\":1500}}";
  ResponseResult r4 = intercept_response(ctx, openai_url, openai_response,
                                         strlen(openai_response));
  printf("Test 4 - OpenAI Response:\n");
  printf("  Cost:            $%.6f\n", r4.cost);
  printf("  Input tokens:    %d\n", r4.input_tokens);
  printf("  Output tokens:   %d\n", r4.output_tokens);
  printf("  Used quota:      %.4f\n", r4.used_quota);
  printf("  Remaining quota: %.4f\n\n", r4.remaining_quota);

  // // Test 5: intercept_response - Anthropic format
  const char *anthropic_response =
      "{\"id\":\"msg_abc\",\"model\":\"claude-sonnet-4-20250514\",\"usage\":{"
      "\"input_tokens\":1000000000000,\"output_tokens\":1000000000000,\"cache_"
      "read_input_tokens\":1000000000000,\"cache_creation_input_tokens\":"
      "1000000000000}}";
  ResponseResult r5 = intercept_response(ctx, anthropic_url, anthropic_response,
                                         strlen(anthropic_response));
  printf("Test 5 - Anthropic Response:\n");
  printf("  Cost:            $%.6f\n", r5.cost);
  printf("  Input tokens:    %d\n", r5.input_tokens);
  printf("  Output tokens:   %d\n", r5.output_tokens);
  printf("  Used quota:      %.4f\n", r5.used_quota);
  printf("  Remaining quota: %.4f\n\n", r5.remaining_quota);

  // Test 6: intercept_response - Bedrock format
  const char *bedrock_url =
      "https://bedrock-runtime.us-east-1.amazonaws.com/model/"
      "us.anthropic.claude-sonnet-4-20250514-v1%3A0/converse";
  const char *bedrock_response =
      "{\"metrics\":{\"latencyMs\":896},\"output\":{\"message\":{\"content\":[{"
      "\"text\":\"Hello!\"}],\"role\":\"assistant\"}},\"stopReason\":\"end_"
      "turn\",\"usage\":{\"cacheReadInputTokenCount\":0,"
      "\"cacheReadInputTokens\":0,\"cacheWriteInputTokenCount\":0,"
      "\"cacheWriteInputTokens\":0,\"inputTokens\":8,\"outputTokens\":20,"
      "\"serverToolUsage\":{},\"totalTokens\":28}}";
  ResponseResult r6 = intercept_response(ctx, bedrock_url, bedrock_response,
                                         strlen(bedrock_response));
  printf("Test 6 - Bedrock Response:\n");
  printf("  Cost:            $%.6f\n", r6.cost);
  printf("  Input tokens:    %d\n", r6.input_tokens);
  printf("  Output tokens:   %d\n", r6.output_tokens);
  printf("  Used quota:      %.4f\n", r6.used_quota);
  printf("  Remaining quota: %.4f\n\n", r6.remaining_quota);

  interceptor_free(ctx);
  return 0;
}
