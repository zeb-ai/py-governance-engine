//
// Created by Samrat on 09/06/26.
//

#include "../include/otel.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main() {
  printf("=== OpenTelemetry Exporter Test ===\n\n");

  // Initialize exporter
  const char *endpoint = "https://z-grc.zeb.co";
  const char *service_name = "z-grc-test";
  const char *user_id = "test-user-123";
  const char *group_id = "test-group-456";

  printf("Initializing exporter...\n");
  printf("  Endpoint: %s\n", endpoint);
  printf("  Service: %s\n", service_name);
  printf("  User: %s\n", user_id);
  printf("  Group: %s\n\n", group_id);

  const char *app_name = "test-chatbot-app";

  OtelExporter *exporter =
      otel_exporter_init(endpoint, service_name, app_name, user_id, group_id);
  if (!exporter) {
    printf("Failed to initialize exporter\n");
    return 1;
  }

  printf("Exporter initialized successfully\n\n");

  // Test 1: Export a span
  printf("Test 1: Exporting a span...\n");

  OtelSpan span = {0};
  otel_generate_trace_id(span.trace_id);
  otel_generate_span_id(span.span_id);
  strncpy(span.name, "llm.request", sizeof(span.name) - 1);
  span.kind = OTEL_SPAN_KIND_CLIENT;
  span.start_time_ns = otel_now_ns();

  // Simulate some work
  for (volatile int i = 0; i < 1000000; i++)
    ;

  span.end_time_ns = otel_now_ns();
  span.status_code = 1; // OK

  // Add attributes
  span.attribute_count = 4;
  span.attributes = malloc(span.attribute_count * sizeof(OtelAttribute));

  strncpy(span.attributes[0].key, "llm.provider",
          sizeof(span.attributes[0].key) - 1);
  strncpy(span.attributes[0].value, "samrat",
          sizeof(span.attributes[0].value) - 1);

  strncpy(span.attributes[1].key, "llm.model",
          sizeof(span.attributes[1].key) - 1);
  strncpy(span.attributes[1].value, "gpt-4",
          sizeof(span.attributes[1].value) - 1);

  strncpy(span.attributes[2].key, "llm.input_tokens",
          sizeof(span.attributes[2].key) - 1);
  strncpy(span.attributes[2].value, "150",
          sizeof(span.attributes[2].value) - 1);

  strncpy(span.attributes[3].key, "llm.output_tokens",
          sizeof(span.attributes[3].key) - 1);
  strncpy(span.attributes[3].value, "75", sizeof(span.attributes[3].value) - 1);

  printf("  Trace ID: %s\n", span.trace_id);
  printf("  Span ID: %s\n", span.span_id);
  printf("  Name: %s\n", span.name);
  printf("  Duration: %llu ns\n",
         (unsigned long long)(span.end_time_ns - span.start_time_ns));
  printf("  Attributes: %d\n", span.attribute_count);

  otel_export_span(exporter, &span);
  printf("  Span exported to batch\n\n");

  // Test 2: Export log records
  printf("Test 2: Exporting log records...\n");

  OtelLog log1 = {0};
  log1.timestamp_ns = otel_now_ns();
  log1.severity = OTEL_SEVERITY_INFO;
  strncpy(log1.body, "LLM request initiated", sizeof(log1.body) - 1);
  log1.attribute_count = 1;
  log1.attributes = malloc(log1.attribute_count * sizeof(OtelAttribute));
  strncpy(log1.attributes[0].key, "request.url",
          sizeof(log1.attributes[0].key) - 1);
  strncpy(log1.attributes[0].value,
          "https://api.openai.com/v1/chat/completions",
          sizeof(log1.attributes[0].value) - 1);

  OtelLog log2 = {0};
  log2.timestamp_ns = otel_now_ns();
  log2.severity = OTEL_SEVERITY_WARN;
  strncpy(log2.body, "High token usage detected", sizeof(log2.body) - 1);
  log2.attribute_count = 0;
  log2.attributes = NULL;

  OtelLog log3 = {0};
  log3.timestamp_ns = otel_now_ns();
  log3.severity = OTEL_SEVERITY_ERROR;
  strncpy(log3.body, "Quota exceeded for user", sizeof(log3.body) - 1);
  log3.attribute_count = 2;
  log3.attributes = malloc(log3.attribute_count * sizeof(OtelAttribute));
  strncpy(log3.attributes[0].key, "quota.remaining",
          sizeof(log3.attributes[0].key) - 1);
  strncpy(log3.attributes[0].value, "0.00",
          sizeof(log3.attributes[0].value) - 1);
  strncpy(log3.attributes[1].key, "quota.used",
          sizeof(log3.attributes[1].key) - 1);
  strncpy(log3.attributes[1].value, "100.00",
          sizeof(log3.attributes[1].value) - 1);

  otel_export_log(exporter, &log1);
  otel_export_log(exporter, &log2);
  otel_export_log(exporter, &log3);

  printf("  Exported 3 log records\n\n");

  // Test 3: Export multiple spans to trigger batch flush
  printf("Test 3: Batch flush test (exporting 70 spans)...\n");

  for (int i = 0; i < 70; i++) {
    OtelSpan batch_span = {0};
    otel_generate_trace_id(batch_span.trace_id);
    otel_generate_span_id(batch_span.span_id);
    snprintf(batch_span.name, sizeof(batch_span.name), "batch.span.%d", i);
    batch_span.kind = OTEL_SPAN_KIND_INTERNAL;
    batch_span.start_time_ns = otel_now_ns();
    batch_span.end_time_ns = otel_now_ns() + 1000000;
    batch_span.status_code = 1;
    batch_span.attribute_count = 0;
    batch_span.attributes = NULL;

    otel_export_span(exporter, &batch_span);

    if ((i + 1) % 10 == 0) {
      printf("  Exported %d spans...\n", i + 1);
    }
  }

  printf("  Batch flush should have triggered at 64 spans\n\n");

  // Test 4: Manual flush
  printf("Test 4: Manual flush...\n");
  otel_flush(exporter);
  printf("  Flushed remaining data to collector\n\n");

  // Cleanup
  printf("Cleaning up...\n");
  otel_exporter_free(exporter);
  printf("Exporter freed\n\n");

  printf("=== Test Complete ===\n");
  printf("Check your OpenTelemetry collector at %s/v1/traces and %s/v1/logs\n",
         endpoint, endpoint);

  return 0;
}
