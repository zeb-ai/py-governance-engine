//
// Created by Samrat on 03/06/26.
//

#include "../include/quota_client.h"
#include "../lib/yyjson/yyjson.h"
#include <curl/curl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Buffer to store response from server
typedef struct {
  char *data;
  size_t size;
} ResponseBuffer;

// Callback for curl to write response data into buffer
static size_t write_callback(void *contents, size_t size, size_t nmemb,
                             void *userp) {
  size_t total_size = size * nmemb;
  ResponseBuffer *buf = (ResponseBuffer *)userp;

  char *new_data = realloc(buf->data, buf->size + total_size + 1);
  if (!new_data)
    return 0;

  buf->data = new_data;
  memcpy(buf->data + buf->size, contents, total_size);
  buf->size += total_size;
  buf->data[buf->size] = '\0';

  return total_size;
}

QuotaClient *quota_client_init(const char *server_url, const char *user_id,
                               const char *group_id) {
  QuotaClient *client = malloc(sizeof(QuotaClient));
  if (!client)
    return NULL;

  // copies data to client :: structure -> destination, src, size
  strncpy(client->server_url, server_url, sizeof(client->server_url) - 1);
  strncpy(client->user_id, user_id, sizeof(client->user_id) - 1);
  strncpy(client->group_id, group_id, sizeof(client->group_id) - 1);

  client->initialized = true;
  curl_global_init(CURL_GLOBAL_DEFAULT);

  return client;
}

Quota quota_client_get(QuotaClient *client) {
  Quota quota = {0};
  if (!client || !client->initialized)
    return quota;

  CURL *curl = curl_easy_init();
  if (!curl)
    return quota;

  // Build URL with query params
  char url[1024];
  snprintf(url, sizeof(url), "%s/api/quota/user?group_id=%s&user_id=%s",
           client->server_url, client->group_id, client->user_id);

  ResponseBuffer response = {NULL, 0};

  struct curl_slist *headers = NULL;
  headers = curl_slist_append(headers, "Content-Type: application/json");

  curl_easy_setopt(curl, CURLOPT_URL, url);
  curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
  curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
  curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);

  CURLcode res = curl_easy_perform(curl);

  printf("[quota_get] URL: %s\n", url);

  if (res == CURLE_OK && response.data) {
    printf("[quota_get] %s\n", response.data);

    yyjson_doc *doc = yyjson_read(response.data, response.size, 0);
    if (doc) {
      yyjson_val *root = yyjson_doc_get_root(doc);
      yyjson_val *used = yyjson_obj_get(root, "used_cost");
      yyjson_val *remaining = yyjson_obj_get(root, "remaining_cost");

      if (used)
        quota.used_quota = yyjson_get_num(used);
      if (remaining)
        quota.remaining_quota = yyjson_get_num(remaining);

      yyjson_doc_free(doc);
    }
  } else {
    printf("[quota_get] request failed: %s\n", curl_easy_strerror(res));
  }

  free(response.data);
  curl_slist_free_all(headers);
  curl_easy_cleanup(curl);

  return quota;
}

Quota quota_client_post(QuotaClient *client, int tokens_used, double cost) {
  Quota quota = {0};
  if (!client || !client->initialized)
    return quota;

  CURL *curl = curl_easy_init();
  if (!curl)
    return quota;

  // Build URL
  char url[1024];
  snprintf(url, sizeof(url), "%s/api/quota/consume", client->server_url);

  // Build JSON body
  yyjson_mut_doc *doc = yyjson_mut_doc_new(NULL);
  yyjson_mut_val *root = yyjson_mut_obj(doc);
  yyjson_mut_doc_set_root(doc, root);
  yyjson_mut_obj_add_str(doc, root, "user_id", client->user_id);
  yyjson_mut_obj_add_str(doc, root, "policy_id", client->group_id);
  yyjson_mut_obj_add_int(doc, root, "amount", tokens_used);
  yyjson_mut_obj_add_real(doc, root, "cost", cost);

  char *body = yyjson_mut_write(doc, 0, NULL);
  yyjson_mut_doc_free(doc);

  ResponseBuffer response = {NULL, 0};

  // Set headers
  struct curl_slist *headers = NULL;
  headers = curl_slist_append(headers, "Content-Type: application/json");

  curl_easy_setopt(curl, CURLOPT_URL, url);
  curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
  curl_easy_setopt(curl, CURLOPT_POSTFIELDS, body);
  curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
  curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);

  CURLcode res = curl_easy_perform(curl);

  if (res == CURLE_OK && response.data) {
    // Parse JSON response
    yyjson_doc *resp_doc = yyjson_read(response.data, response.size, 0);
    if (resp_doc) {
      yyjson_val *resp_root = yyjson_doc_get_root(resp_doc);
      yyjson_val *used = yyjson_obj_get(resp_root, "used_cost");
      yyjson_val *remaining = yyjson_obj_get(resp_root, "remaining_cost");

      if (used)
        quota.used_quota = yyjson_get_num(used);
      if (remaining)
        quota.remaining_quota = yyjson_get_num(remaining);

      yyjson_doc_free(resp_doc);
    }
  }

  free(body);
  free(response.data);
  curl_slist_free_all(headers);
  curl_easy_cleanup(curl);

  return quota;
}

void quota_client_free(QuotaClient *client) {
  if (!client)
    return;
  curl_global_cleanup();
  free(client);
}
