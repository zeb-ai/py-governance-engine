//
// Created by Samrat on 09/06/26.
//

#include "../include/otel.h"
#include "../lib/yyjson/yyjson.h"
#include <curl/curl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define MAX_BATCH_SIZE 64

uint64_t otel_now_ns(void) {
  struct timespec ts;
  timespec_get(&ts, TIME_UTC);
  return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

void otel_generate_trace_id(char *out) {
  // Generate 16 random bytes = 32 hex chars
  for (int i = 0; i < 32; i++) {
    sprintf(out + i, "%x", rand() % 16);
  }
  out[32] = '\0';
}

void otel_generate_span_id(char *out) {
  // Generate 8 random bytes = 16 hex chars
  for (int i = 0; i < 16; i++) {
    sprintf(out + i, "%x", rand() % 16);
  }
  out[16] = '\0';
}

OtelExporter *otel_exporter_init(const char *endpoint, const char *service_name,
                                 const char *app_name, const char *user_id,
                                 const char *group_id) {
  if (!endpoint || !service_name)
    return nullptr;

  OtelExporter *exporter = malloc(sizeof(OtelExporter));
  if (!exporter)
    return nullptr;

  strncpy(exporter->endpoint, endpoint, sizeof(exporter->endpoint) - 1);
  strncpy(exporter->service_name, service_name,
          sizeof(exporter->service_name) - 1);
  strncpy(exporter->app_name, app_name ? app_name : "unknown",
          sizeof(exporter->app_name) - 1);
  strncpy(exporter->user_id, user_id ? user_id : "",
          sizeof(exporter->user_id) - 1);
  strncpy(exporter->group_id, group_id ? group_id : "",
          sizeof(exporter->group_id) - 1);

  exporter->batch.spans = calloc(MAX_BATCH_SIZE, sizeof(OtelSpan));
  exporter->batch.logs = calloc(MAX_BATCH_SIZE, sizeof(OtelLog));
  exporter->batch.span_count = 0;
  exporter->batch.log_count = 0;

  exporter->curl = curl_easy_init();
  if (!exporter->curl) {
    free(exporter->batch.spans);
    free(exporter->batch.logs);
    free(exporter);
    return nullptr;
  }

  srand((unsigned int)time(nullptr));
  return exporter;
}

static size_t write_callback(void *contents, size_t size, size_t nmemb,
                             void *userp) {
  // Discard response body
  (void)contents;
  (void)userp;
  return size * nmemb;
}

static void flush_spans(OtelExporter *exporter) {
  if (exporter->batch.span_count == 0)
    return;

  yyjson_mut_doc *doc = yyjson_mut_doc_new(nullptr);
  yyjson_mut_val *root = yyjson_mut_obj(doc);
  yyjson_mut_doc_set_root(doc, root);

  // resourceSpans array
  yyjson_mut_val *resource_spans_arr = yyjson_mut_arr(doc);
  yyjson_mut_obj_add_val(doc, root, "resourceSpans", resource_spans_arr);

  yyjson_mut_val *resource_spans = yyjson_mut_obj(doc);
  yyjson_mut_arr_add_val(resource_spans_arr, resource_spans);

  // resource
  yyjson_mut_val *resource = yyjson_mut_obj(doc);
  yyjson_mut_obj_add_val(doc, resource_spans, "resource", resource);

  yyjson_mut_val *resource_attrs = yyjson_mut_arr(doc);
  yyjson_mut_obj_add_val(doc, resource, "attributes", resource_attrs);

  // service.name (use app_name for UI filtering)
  yyjson_mut_val *attr_service = yyjson_mut_obj(doc);
  yyjson_mut_obj_add_str(doc, attr_service, "key", "service.name");
  yyjson_mut_val *attr_service_val = yyjson_mut_obj(doc);
  yyjson_mut_obj_add_str(doc, attr_service_val, "stringValue",
                         exporter->app_name);
  yyjson_mut_obj_add_val(doc, attr_service, "value", attr_service_val);
  yyjson_mut_arr_add_val(resource_attrs, attr_service);

  // user.id
  if (exporter->user_id[0]) {
    yyjson_mut_val *attr_user = yyjson_mut_obj(doc);
    yyjson_mut_obj_add_str(doc, attr_user, "key", "user.id");
    yyjson_mut_val *attr_user_val = yyjson_mut_obj(doc);
    yyjson_mut_obj_add_str(doc, attr_user_val, "stringValue",
                           exporter->user_id);
    yyjson_mut_obj_add_val(doc, attr_user, "value", attr_user_val);
    yyjson_mut_arr_add_val(resource_attrs, attr_user);
  }

  // group.id
  if (exporter->group_id[0]) {
    yyjson_mut_val *attr_group = yyjson_mut_obj(doc);
    yyjson_mut_obj_add_str(doc, attr_group, "key", "group.id");
    yyjson_mut_val *attr_group_val = yyjson_mut_obj(doc);
    yyjson_mut_obj_add_str(doc, attr_group_val, "stringValue",
                           exporter->group_id);
    yyjson_mut_obj_add_val(doc, attr_group, "value", attr_group_val);
    yyjson_mut_arr_add_val(resource_attrs, attr_group);
  }

  // scopeSpans
  yyjson_mut_val *scope_spans_arr = yyjson_mut_arr(doc);
  yyjson_mut_obj_add_val(doc, resource_spans, "scopeSpans", scope_spans_arr);

  yyjson_mut_val *scope_spans = yyjson_mut_obj(doc);
  yyjson_mut_arr_add_val(scope_spans_arr, scope_spans);

  // scope (use app_name for filtering in UI)
  yyjson_mut_val *scope = yyjson_mut_obj(doc);
  yyjson_mut_obj_add_str(doc, scope, "name", exporter->app_name);
  yyjson_mut_obj_add_val(doc, scope_spans, "scope", scope);

  // spans array
  yyjson_mut_val *spans_arr = yyjson_mut_arr(doc);
  yyjson_mut_obj_add_val(doc, scope_spans, "spans", spans_arr);

  for (int i = 0; i < exporter->batch.span_count; i++) {
    OtelSpan *span = &exporter->batch.spans[i];
    yyjson_mut_val *span_obj = yyjson_mut_obj(doc);

    yyjson_mut_obj_add_str(doc, span_obj, "traceId", span->trace_id);
    yyjson_mut_obj_add_str(doc, span_obj, "spanId", span->span_id);
    if (span->parent_span_id[0])
      yyjson_mut_obj_add_str(doc, span_obj, "parentSpanId",
                             span->parent_span_id);
    yyjson_mut_obj_add_str(doc, span_obj, "name", span->name);
    yyjson_mut_obj_add_int(doc, span_obj, "kind", span->kind);

    char start_str[32], end_str[32];
    snprintf(start_str, sizeof(start_str), "%llu",
             (unsigned long long)span->start_time_ns);
    snprintf(end_str, sizeof(end_str), "%llu",
             (unsigned long long)span->end_time_ns);
    yyjson_mut_obj_add_str(doc, span_obj, "startTimeUnixNano", start_str);
    yyjson_mut_obj_add_str(doc, span_obj, "endTimeUnixNano", end_str);

    // attributes
    if (span->attribute_count > 0) {
      yyjson_mut_val *attrs_arr = yyjson_mut_arr(doc);
      for (int j = 0; j < span->attribute_count; j++) {
        yyjson_mut_val *attr = yyjson_mut_obj(doc);
        yyjson_mut_obj_add_str(doc, attr, "key", span->attributes[j].key);
        yyjson_mut_val *attr_val = yyjson_mut_obj(doc);
        yyjson_mut_obj_add_str(doc, attr_val, "stringValue",
                               span->attributes[j].value);
        yyjson_mut_obj_add_val(doc, attr, "value", attr_val);
        yyjson_mut_arr_add_val(attrs_arr, attr);
      }
      yyjson_mut_obj_add_val(doc, span_obj, "attributes", attrs_arr);
    }

    // status
    if (span->status_code != 0) {
      yyjson_mut_val *status = yyjson_mut_obj(doc);
      yyjson_mut_obj_add_int(doc, status, "code", span->status_code);
      if (span->status_message[0])
        yyjson_mut_obj_add_str(doc, status, "message", span->status_message);
      yyjson_mut_obj_add_val(doc, span_obj, "status", status);
    }

    yyjson_mut_arr_add_val(spans_arr, span_obj);

    // Free attributes
    if (span->attributes)
      free(span->attributes);
  }

  // Serialize and send
  size_t json_len;
  char *json_str = yyjson_mut_write(doc, 0, &json_len);
  if (json_str) {
    char url[600];
    snprintf(url, sizeof(url), "%s/v1/traces", exporter->endpoint);

    curl_easy_setopt(exporter->curl, CURLOPT_URL, url);
    curl_easy_setopt(exporter->curl, CURLOPT_POSTFIELDS, json_str);
    curl_easy_setopt(exporter->curl, CURLOPT_POSTFIELDSIZE, (long)json_len);
    curl_easy_setopt(exporter->curl, CURLOPT_WRITEFUNCTION, write_callback);

    struct curl_slist *headers = nullptr;
    headers = curl_slist_append(headers, "Content-Type: application/json");
    curl_easy_setopt(exporter->curl, CURLOPT_HTTPHEADER, headers);

    CURLcode res = curl_easy_perform(exporter->curl);
    long http_code = 0;
    curl_easy_getinfo(exporter->curl, CURLINFO_RESPONSE_CODE, &http_code);

    if (res != CURLE_OK) {
      fprintf(stderr, "[z-grc] otel export failed: %s\n",
              curl_easy_strerror(res));
    } else if (http_code >= 400) {
      fprintf(stderr,
              "[z-grc] otel export HTTP error: %ld (sent %zu bytes to %s)\n",
              http_code, json_len, url);
    } else {
      fprintf(stderr,
              "[z-grc] otel export success: HTTP %ld (%zu bytes to %s)\n",
              http_code, json_len, url);
    }

    curl_slist_free_all(headers);
    free(json_str);
  }

  yyjson_mut_doc_free(doc);
  exporter->batch.span_count = 0;
}

static void flush_logs(OtelExporter *exporter) {
  if (exporter->batch.log_count == 0)
    return;

  yyjson_mut_doc *doc = yyjson_mut_doc_new(nullptr);
  yyjson_mut_val *root = yyjson_mut_obj(doc);
  yyjson_mut_doc_set_root(doc, root);

  // resourceLogs array
  yyjson_mut_val *resource_logs_arr = yyjson_mut_arr(doc);
  yyjson_mut_obj_add_val(doc, root, "resourceLogs", resource_logs_arr);

  yyjson_mut_val *resource_logs = yyjson_mut_obj(doc);
  yyjson_mut_arr_add_val(resource_logs_arr, resource_logs);

  // resource (same as spans)
  yyjson_mut_val *resource = yyjson_mut_obj(doc);
  yyjson_mut_obj_add_val(doc, resource_logs, "resource", resource);

  yyjson_mut_val *resource_attrs = yyjson_mut_arr(doc);
  yyjson_mut_obj_add_val(doc, resource, "attributes", resource_attrs);

  yyjson_mut_val *attr_service = yyjson_mut_obj(doc);
  yyjson_mut_obj_add_str(doc, attr_service, "key", "service.name");
  yyjson_mut_val *attr_service_val = yyjson_mut_obj(doc);
  yyjson_mut_obj_add_str(doc, attr_service_val, "stringValue",
                         exporter->app_name);
  yyjson_mut_obj_add_val(doc, attr_service, "value", attr_service_val);
  yyjson_mut_arr_add_val(resource_attrs, attr_service);

  if (exporter->user_id[0]) {
    yyjson_mut_val *attr_user = yyjson_mut_obj(doc);
    yyjson_mut_obj_add_str(doc, attr_user, "key", "user.id");
    yyjson_mut_val *attr_user_val = yyjson_mut_obj(doc);
    yyjson_mut_obj_add_str(doc, attr_user_val, "stringValue",
                           exporter->user_id);
    yyjson_mut_obj_add_val(doc, attr_user, "value", attr_user_val);
    yyjson_mut_arr_add_val(resource_attrs, attr_user);
  }

  if (exporter->group_id[0]) {
    yyjson_mut_val *attr_group = yyjson_mut_obj(doc);
    yyjson_mut_obj_add_str(doc, attr_group, "key", "group.id");
    yyjson_mut_val *attr_group_val = yyjson_mut_obj(doc);
    yyjson_mut_obj_add_str(doc, attr_group_val, "stringValue",
                           exporter->group_id);
    yyjson_mut_obj_add_val(doc, attr_group, "value", attr_group_val);
    yyjson_mut_arr_add_val(resource_attrs, attr_group);
  }

  // scopeLogs
  yyjson_mut_val *scope_logs_arr = yyjson_mut_arr(doc);
  yyjson_mut_obj_add_val(doc, resource_logs, "scopeLogs", scope_logs_arr);

  yyjson_mut_val *scope_logs = yyjson_mut_obj(doc);
  yyjson_mut_arr_add_val(scope_logs_arr, scope_logs);

  yyjson_mut_val *scope = yyjson_mut_obj(doc);
  yyjson_mut_obj_add_str(doc, scope, "name", exporter->app_name);
  yyjson_mut_obj_add_val(doc, scope_logs, "scope", scope);

  // logRecords array
  yyjson_mut_val *logs_arr = yyjson_mut_arr(doc);
  yyjson_mut_obj_add_val(doc, scope_logs, "logRecords", logs_arr);

  for (int i = 0; i < exporter->batch.log_count; i++) {
    OtelLog *log = &exporter->batch.logs[i];
    yyjson_mut_val *log_obj = yyjson_mut_obj(doc);

    char ts_str[32];
    snprintf(ts_str, sizeof(ts_str), "%llu",
             (unsigned long long)log->timestamp_ns);
    yyjson_mut_obj_add_str(doc, log_obj, "timeUnixNano", ts_str);
    yyjson_mut_obj_add_int(doc, log_obj, "severityNumber", log->severity);

    // body must be AnyValue object with stringValue
    yyjson_mut_val *body_val = yyjson_mut_obj(doc);
    yyjson_mut_obj_add_str(doc, body_val, "stringValue", log->body);
    yyjson_mut_obj_add_val(doc, log_obj, "body", body_val);

    if (log->attribute_count > 0) {
      yyjson_mut_val *attrs_arr = yyjson_mut_arr(doc);
      for (int j = 0; j < log->attribute_count; j++) {
        yyjson_mut_val *attr = yyjson_mut_obj(doc);
        yyjson_mut_obj_add_str(doc, attr, "key", log->attributes[j].key);
        yyjson_mut_val *attr_val = yyjson_mut_obj(doc);
        yyjson_mut_obj_add_str(doc, attr_val, "stringValue",
                               log->attributes[j].value);
        yyjson_mut_obj_add_val(doc, attr, "value", attr_val);
        yyjson_mut_arr_add_val(attrs_arr, attr);
      }
      yyjson_mut_obj_add_val(doc, log_obj, "attributes", attrs_arr);
    }

    yyjson_mut_arr_add_val(logs_arr, log_obj);

    if (log->attributes)
      free(log->attributes);
  }

  size_t json_len;
  char *json_str = yyjson_mut_write(doc, 0, &json_len);
  if (json_str) {
    char url[600];
    snprintf(url, sizeof(url), "%s/v1/logs", exporter->endpoint);

    curl_easy_setopt(exporter->curl, CURLOPT_URL, url);
    curl_easy_setopt(exporter->curl, CURLOPT_POSTFIELDS, json_str);
    curl_easy_setopt(exporter->curl, CURLOPT_POSTFIELDSIZE, (long)json_len);
    curl_easy_setopt(exporter->curl, CURLOPT_WRITEFUNCTION, write_callback);

    struct curl_slist *headers = nullptr;
    headers = curl_slist_append(headers, "Content-Type: application/json");
    curl_easy_setopt(exporter->curl, CURLOPT_HTTPHEADER, headers);

    CURLcode res = curl_easy_perform(exporter->curl);
    long http_code = 0;
    curl_easy_getinfo(exporter->curl, CURLINFO_RESPONSE_CODE, &http_code);

    if (res != CURLE_OK) {
      fprintf(stderr, "[z-grc] otel export failed: %s\n",
              curl_easy_strerror(res));
    } else if (http_code >= 400) {
      fprintf(stderr,
              "[z-grc] otel export HTTP error: %ld (sent %zu bytes to %s)\n",
              http_code, json_len, url);
    } else {
      fprintf(stderr,
              "[z-grc] otel export success: HTTP %ld (%zu bytes to %s)\n",
              http_code, json_len, url);
    }

    curl_slist_free_all(headers);
    free(json_str);
  }

  yyjson_mut_doc_free(doc);
  exporter->batch.log_count = 0;
}

void otel_export_span(OtelExporter *exporter, OtelSpan *span) {
  if (!exporter || !span)
    return;

  exporter->batch.spans[exporter->batch.span_count++] = *span;

  if (exporter->batch.span_count >= MAX_BATCH_SIZE) {
    flush_spans(exporter);
  }
}

void otel_export_log(OtelExporter *exporter, OtelLog *log) {
  if (!exporter || !log)
    return;

  exporter->batch.logs[exporter->batch.log_count++] = *log;

  if (exporter->batch.log_count >= MAX_BATCH_SIZE) {
    flush_logs(exporter);
  }
}

void otel_flush(OtelExporter *exporter) {
  if (!exporter)
    return;
  fprintf(stderr, "[z-grc] flushing: %d spans, %d logs\n",
          exporter->batch.span_count, exporter->batch.log_count);
  flush_spans(exporter);
  flush_logs(exporter);
}

void otel_exporter_free(OtelExporter *exporter) {
  if (!exporter)
    return;
  otel_flush(exporter);
  curl_easy_cleanup(exporter->curl);
  free(exporter->batch.spans);
  free(exporter->batch.logs);
  free(exporter);
}
