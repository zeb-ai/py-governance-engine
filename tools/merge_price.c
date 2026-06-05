#include "yyjson.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

typedef struct {
  int total_providers;
  int total_models;
  int total_aliases;
  int data_json_models;
  int litellm_models;
} MergeStats;

/*
 * Normalize price value - handles tiered pricing by taking base price
 */
double normalize_price(yyjson_val *price_value, const char *field_name) {
  if (!price_value || yyjson_is_null(price_value)) {
    return 0.0;
  }

  if (yyjson_is_num(price_value)) {
    return yyjson_get_num(price_value);
  }

  // Handle tiered pricing
  if (yyjson_is_obj(price_value)) {
    yyjson_val *base = yyjson_obj_get(price_value, "base");
    if (base && yyjson_is_num(base)) {
      fprintf(stderr, "Warning: %s has tiered pricing, using base price\n",
              field_name);
      return yyjson_get_num(base);
    }
  }

  return 0.0;
}

/*
 * Extract provider information from data.json
 */
yyjson_mut_val *extract_providers(yyjson_doc *data_doc, yyjson_mut_doc *doc,
                                  MergeStats *stats) {
  yyjson_val *data_json = yyjson_doc_get_root(data_doc);
  yyjson_mut_val *providers = yyjson_mut_obj(doc);

  size_t idx, max;
  yyjson_val *provider_item;
  yyjson_arr_foreach(data_json, idx, max, provider_item) {
    yyjson_val *id = yyjson_obj_get(provider_item, "id");
    if (!id || !yyjson_is_str(id))
      continue;

    const char *provider_id = yyjson_get_str(id);
    yyjson_mut_val *provider_obj = yyjson_mut_obj(doc);

    // Add basic info
    yyjson_val *name = yyjson_obj_get(provider_item, "name");
    if (name && yyjson_is_str(name)) {
      yyjson_mut_obj_add_str(doc, provider_obj, "name", yyjson_get_str(name));
    }

    yyjson_val *api_pattern = yyjson_obj_get(provider_item, "api_pattern");
    if (api_pattern && yyjson_is_str(api_pattern)) {
      yyjson_mut_obj_add_str(doc, provider_obj, "api_pattern",
                             yyjson_get_str(api_pattern));
    }

    // Extract pricing URL
    yyjson_val *pricing_urls = yyjson_obj_get(provider_item, "pricing_urls");
    if (pricing_urls && yyjson_is_arr(pricing_urls)) {
      yyjson_val *first_url = yyjson_arr_get_first(pricing_urls);
      if (first_url && yyjson_is_str(first_url)) {
        yyjson_mut_obj_add_str(doc, provider_obj, "pricing_url",
                               yyjson_get_str(first_url));
      }
    }

    // Extract extractors
    yyjson_mut_val *extractors_array = yyjson_mut_arr(doc);
    yyjson_val *extractors = yyjson_obj_get(provider_item, "extractors");
    if (extractors && yyjson_is_arr(extractors)) {
      size_t ext_idx, ext_max;
      yyjson_val *extractor;
      yyjson_arr_foreach(extractors, ext_idx, ext_max, extractor) {
        yyjson_mut_val *extractor_obj = yyjson_mut_obj(doc);

        yyjson_val *api_flavor = yyjson_obj_get(extractor, "api_flavor");
        const char *flavor = (api_flavor && yyjson_is_str(api_flavor))
                                 ? yyjson_get_str(api_flavor)
                                 : "default";
        yyjson_mut_obj_add_str(doc, extractor_obj, "api_flavor", flavor);

        yyjson_val *root = yyjson_obj_get(extractor, "root");
        if (root && yyjson_is_str(root)) {
          yyjson_mut_obj_add_str(doc, extractor_obj, "usage_path",
                                 yyjson_get_str(root));
        }

        yyjson_val *model_path = yyjson_obj_get(extractor, "model_path");
        const char *mp = (model_path && yyjson_is_str(model_path))
                             ? yyjson_get_str(model_path)
                             : "model";
        yyjson_mut_obj_add_str(doc, extractor_obj, "model_path", mp);

        // Extract token mappings
        yyjson_mut_val *token_mappings = yyjson_mut_obj(doc);
        yyjson_val *mappings = yyjson_obj_get(extractor, "mappings");
        if (mappings && yyjson_is_arr(mappings)) {
          size_t map_idx, map_max;
          yyjson_val *mapping;
          yyjson_arr_foreach(mappings, map_idx, map_max, mapping) {
            yyjson_val *path = yyjson_obj_get(mapping, "path");
            yyjson_val *dest = yyjson_obj_get(mapping, "dest");
            if (path && dest && yyjson_is_str(path) && yyjson_is_str(dest)) {
              yyjson_mut_obj_add_str(doc, token_mappings, yyjson_get_str(path),
                                     yyjson_get_str(dest));
            }
          }
        }
        yyjson_mut_obj_add_val(doc, extractor_obj, "token_mappings",
                               token_mappings);

        yyjson_mut_arr_add_val(extractors_array, extractor_obj);
      }
    }
    yyjson_mut_obj_add_val(doc, provider_obj, "extractors", extractors_array);

    yyjson_mut_obj_add_val(doc, providers, provider_id, provider_obj);
    stats->total_providers++;
  }

  return providers;
}

/*
 * Extract models from data.json
 */
yyjson_mut_val *extract_models_from_data_json(yyjson_doc *data_doc,
                                              yyjson_mut_doc *doc,
                                              MergeStats *stats) {
  yyjson_val *data_json = yyjson_doc_get_root(data_doc);
  yyjson_mut_val *models = yyjson_mut_obj(doc);

  size_t idx, max;
  yyjson_val *provider_item;
  yyjson_arr_foreach(data_json, idx, max, provider_item) {
    yyjson_val *provider_id = yyjson_obj_get(provider_item, "id");
    if (!provider_id || !yyjson_is_str(provider_id))
      continue;

    const char *prov_id_str = yyjson_get_str(provider_id);

    yyjson_val *provider_models = yyjson_obj_get(provider_item, "models");
    if (!provider_models || !yyjson_is_arr(provider_models))
      continue;

    size_t model_idx, model_max;
    yyjson_val *model;
    yyjson_arr_foreach(provider_models, model_idx, model_max, model) {
      yyjson_val *model_id = yyjson_obj_get(model, "id");
      if (!model_id || !yyjson_is_str(model_id))
        continue;

      const char *model_id_str = yyjson_get_str(model_id);
      yyjson_mut_val *model_obj = yyjson_mut_obj(doc);

      // Add provider
      yyjson_mut_obj_add_str(doc, model_obj, "provider", prov_id_str);

      // Add name and description
      yyjson_val *name = yyjson_obj_get(model, "name");
      if (name && yyjson_is_str(name)) {
        yyjson_mut_obj_add_str(doc, model_obj, "name", yyjson_get_str(name));
      }

      yyjson_val *description = yyjson_obj_get(model, "description");
      if (description && yyjson_is_str(description)) {
        yyjson_mut_obj_add_str(doc, model_obj, "description",
                               yyjson_get_str(description));
      }

      // Extract pricing
      yyjson_val *prices = yyjson_obj_get(model, "prices");
      if (prices) {
        // Handle conditional prices (list)
        if (yyjson_is_arr(prices)) {
          size_t count = yyjson_arr_size(prices);
          if (count > 0) {
            yyjson_val *last_price = yyjson_arr_get_last(prices);
            prices = yyjson_obj_get(last_price, "prices");
          }
        }

        if (prices && yyjson_is_obj(prices)) {
          yyjson_mut_val *pricing = yyjson_mut_obj(doc);

          yyjson_val *input = yyjson_obj_get(prices, "input_mtok");
          if (input) {
            double val = normalize_price(input, "input_mtok");
            if (val > 0)
              yyjson_mut_obj_add_real(doc, pricing, "input", val);
          }

          yyjson_val *output = yyjson_obj_get(prices, "output_mtok");
          if (output) {
            double val = normalize_price(output, "output_mtok");
            if (val > 0)
              yyjson_mut_obj_add_real(doc, pricing, "output", val);
          }

          yyjson_val *cache_read = yyjson_obj_get(prices, "cache_read_mtok");
          if (cache_read) {
            double val = normalize_price(cache_read, "cache_read_mtok");
            if (val > 0)
              yyjson_mut_obj_add_real(doc, pricing, "cache_read", val);
          }

          yyjson_val *cache_write = yyjson_obj_get(prices, "cache_write_mtok");
          if (cache_write) {
            double val = normalize_price(cache_write, "cache_write_mtok");
            if (val > 0)
              yyjson_mut_obj_add_real(doc, pricing, "cache_write", val);
          }

          yyjson_mut_obj_add_val(doc, model_obj, "pricing", pricing);
        }
      }

      // Add limits
      yyjson_mut_val *limits = yyjson_mut_obj(doc);
      yyjson_val *context_window = yyjson_obj_get(model, "context_window");
      if (context_window && yyjson_is_num(context_window)) {
        yyjson_mut_obj_add_real(doc, limits, "context_window",
                                yyjson_get_num(context_window));
      }
      yyjson_mut_obj_add_val(doc, model_obj, "limits", limits);

      // Add deprecated flag
      yyjson_val *deprecated = yyjson_obj_get(model, "deprecated");
      if (deprecated && yyjson_is_bool(deprecated)) {
        yyjson_mut_obj_add_bool(doc, model_obj, "deprecated",
                                yyjson_get_bool(deprecated));
      }

      yyjson_mut_obj_add_val(doc, models, model_id_str, model_obj);
      stats->data_json_models++;
    }
  }

  return models;
}

/*
 * Extract models from LiteLLM JSON
 */
yyjson_mut_val *extract_models_from_litellm(yyjson_doc *litellm_doc,
                                            yyjson_mut_doc *doc,
                                            MergeStats *stats) {
  yyjson_val *litellm_json = yyjson_doc_get_root(litellm_doc);
  yyjson_mut_val *models = yyjson_mut_obj(doc);

  size_t idx, max;
  yyjson_val *key, *model_val;
  yyjson_obj_foreach(litellm_json, idx, max, key, model_val) {
    const char *model_id = yyjson_get_str(key);

    // Skip sample_spec
    if (strcmp(model_id, "sample_spec") == 0)
      continue;
    if (!yyjson_is_obj(model_val))
      continue;

    yyjson_mut_val *model_obj = yyjson_mut_obj(doc);

    // Extract provider
    yyjson_val *litellm_provider =
        yyjson_obj_get(model_val, "litellm_provider");
    if (litellm_provider && yyjson_is_str(litellm_provider)) {
      yyjson_mut_obj_add_str(doc, model_obj, "provider",
                             yyjson_get_str(litellm_provider));
    } else {
      yyjson_mut_obj_add_str(doc, model_obj, "provider", "unknown");
    }

    // Add name (use model_id as name for LiteLLM)
    yyjson_mut_obj_add_str(doc, model_obj, "name", model_id);

    // Extract pricing - convert from per-token to per-MTok
    yyjson_mut_val *pricing = yyjson_mut_obj(doc);
    int has_pricing = 0;

    yyjson_val *input_cost = yyjson_obj_get(model_val, "input_cost_per_token");
    if (input_cost && yyjson_is_num(input_cost)) {
      double val = yyjson_get_num(input_cost);
      if (val > 0) {
        yyjson_mut_obj_add_real(doc, pricing, "input", val * 1000000);
        has_pricing = 1;
      }
    }

    yyjson_val *output_cost =
        yyjson_obj_get(model_val, "output_cost_per_token");
    if (output_cost && yyjson_is_num(output_cost)) {
      double val = yyjson_get_num(output_cost);
      if (val > 0) {
        yyjson_mut_obj_add_real(doc, pricing, "output", val * 1000000);
        has_pricing = 1;
      }
    }

    yyjson_val *cache_read_cost =
        yyjson_obj_get(model_val, "cache_read_input_token_cost");
    if (cache_read_cost && yyjson_is_num(cache_read_cost)) {
      double val = yyjson_get_num(cache_read_cost);
      if (val > 0) {
        yyjson_mut_obj_add_real(doc, pricing, "cache_read", val * 1000000);
        has_pricing = 1;
      }
    }

    yyjson_val *cache_write_cost =
        yyjson_obj_get(model_val, "cache_creation_input_token_cost");
    if (cache_write_cost && yyjson_is_num(cache_write_cost)) {
      double val = yyjson_get_num(cache_write_cost);
      if (val > 0) {
        yyjson_mut_obj_add_real(doc, pricing, "cache_write", val * 1000000);
        has_pricing = 1;
      }
    }

    if (!has_pricing) {
      continue; // Skip models without pricing
    }

    yyjson_mut_obj_add_val(doc, model_obj, "pricing", pricing);

    // Add limits
    yyjson_mut_val *limits = yyjson_mut_obj(doc);
    yyjson_val *max_input = yyjson_obj_get(model_val, "max_input_tokens");
    if (!max_input)
      max_input = yyjson_obj_get(model_val, "max_tokens");
    if (max_input && yyjson_is_num(max_input)) {
      yyjson_mut_obj_add_real(doc, limits, "context_window",
                              yyjson_get_num(max_input));
    }

    yyjson_val *max_output = yyjson_obj_get(model_val, "max_output_tokens");
    if (max_output && yyjson_is_num(max_output)) {
      yyjson_mut_obj_add_real(doc, limits, "max_output",
                              yyjson_get_num(max_output));
    }
    yyjson_mut_obj_add_val(doc, model_obj, "limits", limits);

    // Add mode
    yyjson_val *mode = yyjson_obj_get(model_val, "mode");
    if (mode && yyjson_is_str(mode)) {
      yyjson_mut_obj_add_str(doc, model_obj, "mode", yyjson_get_str(mode));
    }

    yyjson_mut_obj_add_val(doc, models, model_id, model_obj);
    stats->litellm_models++;
  }

  return models;
}

/*
 * Merge models from both sources
 */
void merge_models(yyjson_mut_val *data_models, yyjson_mut_val *litellm_models,
                  yyjson_mut_doc *doc, MergeStats *stats) {
  size_t idx, max;
  yyjson_mut_val *key, *model_val;

  yyjson_mut_obj_foreach(litellm_models, idx, max, key, model_val) {
    const char *model_id = yyjson_mut_get_str(key);

    // Check if already exists
    if (yyjson_mut_obj_get(data_models, model_id)) {
      continue; // Skip, data.json has better metadata
    }

    // Add to data_models
    yyjson_mut_obj_add_val(doc, data_models, model_id, model_val);
    stats->total_models++;
  }
}

/*
 * Get current date string
 */
void get_current_date(char *buffer, size_t size) {
  time_t now = time(NULL);
  struct tm *tm_info = localtime(&now);
  strftime(buffer, size, "%Y-%m-%d", tm_info);
}

/*
 * Main merge function
 */
int merge_pricing_data(const char *data_json_path,
                       const char *litellm_json_path, const char *output_path) {
  MergeStats stats = {0};

  // Load data.json
  printf("Loading %s...\n", data_json_path);
  yyjson_read_err err;
  yyjson_doc *data_doc = yyjson_read_file(data_json_path, 0, NULL, &err);
  if (!data_doc) {
    fprintf(stderr, "Error parsing data.json: %s at position %zu\n", err.msg,
            err.pos);
    return 1;
  }

  // Load LiteLLM JSON
  printf("Loading %s...\n", litellm_json_path);
  yyjson_doc *litellm_doc = yyjson_read_file(litellm_json_path, 0, NULL, &err);
  if (!litellm_doc) {
    fprintf(stderr, "Error parsing litellm json: %s at position %zu\n", err.msg,
            err.pos);
    yyjson_doc_free(data_doc);
    return 1;
  }

  // Create mutable document for output
  yyjson_mut_doc *doc = yyjson_mut_doc_new(NULL);

  // Extract providers
  printf("\nExtracting provider information...\n");
  yyjson_mut_val *providers = extract_providers(data_doc, doc, &stats);
  printf("  Found %d providers\n", stats.total_providers);

  // Extract models from data.json
  printf("\nExtracting models from data.json...\n");
  yyjson_mut_val *data_models =
      extract_models_from_data_json(data_doc, doc, &stats);
  printf("  Found %d models\n", stats.data_json_models);
  stats.total_models = stats.data_json_models;

  // Extract models from LiteLLM
  printf("\nExtracting models from LiteLLM...\n");
  yyjson_mut_val *litellm_models =
      extract_models_from_litellm(litellm_doc, doc, &stats);
  printf("  Found %d models\n", stats.litellm_models);

  // Merge models
  printf("\nMerging models...\n");
  merge_models(data_models, litellm_models, doc, &stats);
  printf("  Total merged models: %d\n", stats.total_models);

  // Build final structure
  yyjson_mut_val *root = yyjson_mut_obj(doc);
  yyjson_mut_obj_add_str(doc, root, "version", "1.0");

  char date_str[32];
  get_current_date(date_str, sizeof(date_str));
  yyjson_mut_obj_add_str(doc, root, "last_updated", date_str);

  yyjson_mut_obj_add_val(doc, root, "providers", providers);
  yyjson_mut_obj_add_val(doc, root, "models", data_models);

  yyjson_mut_val *aliases = yyjson_mut_obj(doc);
  yyjson_mut_obj_add_val(doc, root, "model_aliases", aliases);

  yyjson_mut_val *stats_obj = yyjson_mut_obj(doc);
  yyjson_mut_obj_add_int(doc, stats_obj, "total_providers",
                         stats.total_providers);
  yyjson_mut_obj_add_int(doc, stats_obj, "total_models", stats.total_models);
  yyjson_mut_obj_add_int(doc, stats_obj, "total_aliases", stats.total_aliases);
  yyjson_mut_obj_add_val(doc, root, "stats", stats_obj);

  // Save output
  printf("\nSaving merged data to %s...\n", output_path);
  yyjson_write_err write_err;
  yyjson_mut_doc_set_root(doc, root);
  if (!yyjson_mut_write_file(output_path, doc, YYJSON_WRITE_PRETTY, NULL,
                             &write_err)) {
    fprintf(stderr, "Error writing output: %s\n", write_err.msg);
    yyjson_mut_doc_free(doc);
    yyjson_doc_free(data_doc);
    yyjson_doc_free(litellm_doc);
    return 1;
  }

  printf("\nMerge complete!\n");
  printf("  Providers: %d\n", stats.total_providers);
  printf("  Models: %d\n", stats.total_models);
  printf("  Aliases: %d\n", stats.total_aliases);

  // Cleanup
  yyjson_mut_doc_free(doc);
  yyjson_doc_free(data_doc);
  yyjson_doc_free(litellm_doc);

  return 0;
}

int main(int argc, char *argv[]) {
  if (argc != 4) {
    fprintf(stderr, "Usage: %s <data.json> <litellm.json> <output.json>\n",
            argv[0]);
    return 1;
  }

  return merge_pricing_data(argv[1], argv[2], argv[3]);
}
