//
// Created by Samrat on 03/06/26.
//

#include "../include/auth_token.h"
#include "../lib/yyjson/yyjson.h"
#include <b64/cdecode.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <zlib.h>

#define MAX_DECODED_SIZE 4096
#define MAX_DECOMPRESSED_SIZE 8192
#define GRC_PREFIX "grc_"
#define GRC_PREFIX_LEN 4

static int base64url_decode(const char *input, size_t input_len,
                            unsigned char *output, size_t *output_len) {
  char *std_b64 = malloc(input_len + 4);
  if (!std_b64)
    return -1;

  for (size_t i = 0; i < input_len; i++) {
    if (input[i] == '-')
      std_b64[i] = '+';
    else if (input[i] == '_')
      std_b64[i] = '/';
    else
      std_b64[i] = input[i];
  }

  size_t padding = (4 - (input_len % 4)) % 4;
  for (size_t i = 0; i < padding; i++) {
    std_b64[input_len + i] = '=';
  }
  size_t padded_len = input_len + padding;

  base64_decodestate state;
  base64_init_decodestate(&state);
  *output_len = base64_decode_block(std_b64, padded_len, output, &state);

  free(std_b64);
  return 0;
}

// Zlib decompress
static int zlib_decompress(const unsigned char *input, size_t input_len,
                           unsigned char *output, size_t *output_len) {
  z_stream stream = {0};
  stream.next_in = (unsigned char *)input;
  stream.avail_in = input_len;
  stream.next_out = output;
  stream.avail_out = MAX_DECOMPRESSED_SIZE;

  // Use inflateInit2 with wbits = -15 for raw deflate (zlib.decompress uses
  // wbits=15 by default)
  if (inflateInit(&stream) != Z_OK)
    return -1;

  int ret = inflate(&stream, Z_FINISH);
  if (ret != Z_STREAM_END) {
    inflateEnd(&stream);
    return -1;
  }

  *output_len = stream.total_out;
  inflateEnd(&stream);
  return 0;
}

AuthToken *auth_token_decode(const char *api_key) {
  if (!api_key)
    return NULL;

  // Step 1: Strip "grc_" prefix
  if (strncmp(api_key, GRC_PREFIX, GRC_PREFIX_LEN) != 0)
    return NULL;
  const char *token = api_key + GRC_PREFIX_LEN;
  size_t token_len = strlen(token);

  // Step 2: Base64url decode
  unsigned char decoded[MAX_DECODED_SIZE];
  size_t decoded_len = 0;
  if (base64url_decode(token, token_len, decoded, &decoded_len) != 0)
    return NULL;

  // Step 3: Zlib decompress
  unsigned char decompressed[MAX_DECOMPRESSED_SIZE];
  size_t decompressed_len = 0;
  if (zlib_decompress(decoded, decoded_len, decompressed, &decompressed_len) !=
      0)
    return NULL;
  decompressed[decompressed_len] = '\0';

  // Step 4: Parse JSON
  yyjson_doc *doc =
      yyjson_read((const char *)decompressed, decompressed_len, 0);
  if (!doc)
    return NULL;

  yyjson_val *root = yyjson_doc_get_root(doc);

  AuthToken *auth = malloc(sizeof(AuthToken));
  if (!auth) {
    yyjson_doc_free(doc);
    return NULL;
  }
  memset(auth, 0, sizeof(AuthToken));

  yyjson_val *host = yyjson_obj_get(root, "host");
  if (host)
    strncpy(auth->domain, yyjson_get_str(host), sizeof(auth->domain) - 1);

  yyjson_val *otel = yyjson_obj_get(root, "otel");
  if (otel)
    strncpy(auth->opentelemetry, yyjson_get_str(otel),
            sizeof(auth->opentelemetry) - 1);

  yyjson_val *gid = yyjson_obj_get(root, "gid");
  if (gid)
    strncpy(auth->group_id, yyjson_get_str(gid), sizeof(auth->group_id) - 1);

  yyjson_val *uid = yyjson_obj_get(root, "uid");
  if (uid)
    strncpy(auth->user_id, yyjson_get_str(uid), sizeof(auth->user_id) - 1);

  yyjson_doc_free(doc);
  return auth;
}

void auth_token_free(AuthToken *token) {
  if (token)
    free(token);
}
