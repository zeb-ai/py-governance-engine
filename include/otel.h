//
// Created by Samrat on 09/06/26.
//

#pragma once

#include <curl/curl.h>
#include <stddef.h>
#include <stdint.h>

typedef enum {
  OTEL_SPAN_KIND_INTERNAL = 0,
  OTEL_SPAN_KIND_CLIENT = 2,
} OtelSpanKind;

typedef enum {
  OTEL_SEVERITY_DEBUG = 5,
  OTEL_SEVERITY_INFO = 9,
  OTEL_SEVERITY_WARN = 13,
  OTEL_SEVERITY_ERROR = 17,
} OtelSeverity;

typedef struct {
  char key[64];
  char value[256];
} OtelAttribute;

typedef struct {
  char trace_id[33]; // 32 hex chars + null
  char span_id[17];  // 16 hex chars + null
  char parent_span_id[17];
  char name[128];
  OtelSpanKind kind;
  uint64_t start_time_ns;
  uint64_t end_time_ns;
  OtelAttribute *attributes;
  int attribute_count;
  int status_code; // 0=unset, 1=ok, 2=error
  char status_message[256];
} OtelSpan;

typedef struct {
  uint64_t timestamp_ns;
  OtelSeverity severity;
  char body[512];
  OtelAttribute *attributes;
  int attribute_count;
} OtelLog;

typedef struct {
  OtelSpan *spans;
  OtelLog *logs;
  int span_count;
  int log_count;
} Batch;

typedef struct {
  char endpoint[512];
  char service_name[128];
  char app_name[128];
  char user_id[128];
  char group_id[128];
  Batch batch;
  CURL *curl;
} OtelExporter;

OtelExporter *otel_exporter_init(const char *endpoint, const char *service_name,
                                 const char *app_name, const char *user_id,
                                 const char *group_id);

void otel_export_span(OtelExporter *exporter, OtelSpan *span);

void otel_export_log(OtelExporter *exporter, OtelLog *log);

void otel_flush(OtelExporter *exporter);

void otel_exporter_free(OtelExporter *exporter);

void otel_generate_trace_id(char *out);
void otel_generate_span_id(char *out);
uint64_t otel_now_ns(void);
