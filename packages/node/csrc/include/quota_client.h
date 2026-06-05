//
// Created by Samrat on 03/06/26.
//

#pragma once

#include <stdbool.h>

typedef struct {
  double used_quota;
  double remaining_quota;
} Quota;

typedef struct {
  char server_url[512];
  char user_id[128];
  char group_id[128];
  bool initialized;
} QuotaClient;

/* Initialize quota client with server details */
QuotaClient *quota_client_init(const char *server_url, const char *user_id,
                               const char *group_id);

/* GET /api/quota/user - fetch current quota */
Quota quota_client_get(QuotaClient *client);

/* POST /api/quota/consume - report usage */
Quota quota_client_post(QuotaClient *client, int tokens_used, double cost);

/* Cleanup */
void quota_client_free(QuotaClient *client);
