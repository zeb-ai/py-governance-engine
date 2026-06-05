//
// Created by Samrat on 03/06/26.
//

#include "../include/auth_token.h"
#include <stdio.h>

int main() {

  // const char *api_key =
  // "grc_eJxNyssKgzAQheFXkVl3NDcyGd8mmoMWCik13Vj67m12rg785_vQXo9G80B7a89jnqaTt9c6nljGtdJtoNrw6H_fS97upVdjFcnlwk4RWNRFVkTD3iIESBHnfOfvCy8xs80lsQiUk4XhxcOnP4dIoO8PkDco2A";
  // grc_eNp1zUEOgyAQRuG7zNpRGAgD3gblj5o0oal0o-ndy66rrr-XvJveR6GZjE2IkgtLgmdNEjghGHYW3kOLijgaaK9n6_Xe2vOcp-ni7bWOF5ZxrV1rw-O_br9RCZltLpFVkThaGF4cXOwjqHr6fAGjsiry

  char api_key[255];
  scanf("%s", api_key);

  AuthToken *token = auth_token_decode(api_key);
  if (!token) {
    printf("Failed to decode token\n");
    return 1;
  }

  printf("Domain: %s\n", token->domain);
  printf("OpenTelemetry: %s\n", token->opentelemetry);
  printf("Group ID: %s\n", token->group_id);
  printf("User ID: %s\n", token->user_id);

  auth_token_free(token);
  return 0;
}
