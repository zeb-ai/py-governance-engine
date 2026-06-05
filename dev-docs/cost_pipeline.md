## Cost pipeline

Problem : consumption of multiple models, need to calculate the cost, it divides into the multiple factors where input, output, cache read and write tokens.

Don’t do:

- pricing should not be stale
- https://github.com/pydantic/genai-prices : cool thing, but gave warning the price shouldn’t accurate
  - only job is pricing alone
  - https://github.com/pydantic/genai-prices/blob/main/prices/data.json

- https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json - all models and its cost
  - this is thing where can be updated in the repo itself, package gets this json and using that
  - litellm use local fallback : https://github.com/BerriAI/litellm/blob/main/litellm/model_prices_and_context_window_backup.json
  - central cost control : **`litellm/litellm/cost_calculator.py`**

flow:

1. download the model cost json to local
   1. if failed use fallback in local
2. calculate the cost based on the provider
   1. get the model id
      1](). pass the classified tokens 2. returns the cost
   2. if model is inference profile ~ there is straight forward model name
      1. call AWS to get the name of the model name
      2. pass the classified tokens
      3. returns the cost

caveats:

- json read and looping may affect the performance
  - so choosing c to do this job
- need to 100x speed while accessing JSON
