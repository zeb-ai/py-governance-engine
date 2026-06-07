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

clean:
	rm -rf build/
	rm -rf packages/node/build/
	rm -rf packages/node/csrc/
	rm -rf packages/node/deps/
	rm -rf packages/node/prebuilds/
	rm -rf packages/node/data/
	rm -rf packages/python/csrc/
	rm -rf packages/python/build/
	rm -rf packages/python/dist/
	rm -rf packages/python/wheelhouse/
	rm -rf packages/python/*.egg-info/
	rm -rf packages/python/zgrc/_native*.so
	rm -rf packages/python/zgrc/_native*.pyd
	rm -rf playground/node_modules/
	rm -f playground/package-lock.json
	rm -f playground/uv.lock
	rm -f tools/merge_price
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.o" -delete 2>/dev/null || true
	@echo "Clean complete."

.PHONY: merge_price clean
