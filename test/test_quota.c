//
// Created by Samrat on 03/06/26.
//

#include "../include/quota_client.h"
#include <stdio.h>

int main() {

  QuotaClient *client = quota_client_init(
      "https://z-grc.zeb.co", "019e82ad-29e4-7926-9e60-31e44e7d7223",
      "019e8d6a-1ad8-77e9-81e0-b3e38e7de774");

  if (!client) {
    printf("Failed to init quota client\n");
    return 1;
  }
  printf("Initialized: server=%s user=%s group=%s\n\n", client->server_url,
         client->user_id, client->group_id);

  Quota quota = quota_client_get(client);
  printf("  Used:      %.2f\n", quota.used_quota);
  printf("  Remaining: %.2f\n\n", quota.remaining_quota);

  Quota updated = quota_client_post(client, 1000, 0.003);
  printf("  Used:      %.2f\n", updated.used_quota);
  printf("  Remaining: %.2f\n\n", updated.remaining_quota);

  quota_client_free(client);

  return 0;
}
