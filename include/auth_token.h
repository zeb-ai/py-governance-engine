//
// Created by Samrat on 03/06/26.
//

#pragma once

typedef struct {
  char domain[512];
  char opentelemetry[512];
  char group_id[128];
  char user_id[128];
} AuthToken;

AuthToken *auth_token_decode(const char *api_key);
void auth_token_free(AuthToken *token);
