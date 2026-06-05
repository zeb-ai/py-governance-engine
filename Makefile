CC = gcc
CFLAGS = -Wall -Wextra -O3 -Ilib/yyjson
LDFLAGS = -lm

LITELLM_URL = https://raw.githubusercontent.com/BerriAI/litellm/refs/heads/main/litellm/model_prices_and_context_window_backup.json
GENAI_URL = https://raw.githubusercontent.com/pydantic/genai-prices/refs/heads/main/prices/data.json

merge_price:
	@echo "Downloading LiteLLM pricing data..."
	@curl -sL $(LITELLM_URL) -o data/litellm_data.json
	@echo "Downloading GenAI pricing data..."
	@curl -sL $(GENAI_URL) -o data/genai_data.json
	@echo "Building merge tool..."
	$(CC) $(CFLAGS) -o tools/merge_price tools/merge_price.c lib/yyjson/yyjson.c $(LDFLAGS)
	@echo "Merging pricing data..."
	./tools/merge_price data/genai_data.json data/litellm_data.json data/merged_pricing.json

.PHONY: merge_price
