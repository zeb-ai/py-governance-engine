# capture

problem : need to capture the response and request of the llm calls, main goal is to capture
http(s) calls and get the users how much they have used and if the certain threshold is exceeded means
blocking the calls and producing 429 error, kind of say "hey u have consumed your allocated amount"

main goal this solution will run in all environments, local, deployed pod, EKS,
ECS, databricks notebook and other area where they can write a code.

approaches considered:

- eBPF
  - captures at kernel level, zero code changes
  - needs root/privileged access
  - fails: lambda, databricks, cloud run, managed services, macOS
  - only works where you own the kernel (EKS nodes)

- LD_PRELOAD / DYLD_INSERT_LIBRARIES
  - hooks libc connect/send/recv
  - fails: lambda, databricks, macOS SIP, Go static binaries
  - same kernel access problem

- forward proxy (separate server)
  - set HTTPS_PROXY env var, all traffic goes through
  - needs TLS decryption (MITM)
  - adds latency (extra hop)
  - needs a running server somewhere ~ not "one line integration"

- pure SDK per language (full rewrite each)
  - rewrite cost calculation, token extraction, pattern matching in every language
  - maintenance nightmare, logic drift between languages

what we are doing:

- auto-instrumentation pattern (same as datadog, open telemetry, new relic)
- core logic written in C (write once)
- thin language shims that hook HTTP at library level (10-20 lines per language)
- shims are dumb ~ just pass URL + request body + response body to C
- C does all the smart work

why HTTP hooking works for HTTPS:

- hook lives inside the app process, ABOVE the TLS layer
- sees plain text before encryption on request
- sees plain text after decryption on response
- no MITM, no certificate issues, no TLS decryption needed

flow:

1. user imports one line (`import grc` / `require('grc')`)
2. shim hooks the HTTP client for that language
3. before request:
   - pass URL to C
   - C matches against api_pattern (from data.json)
   - C checks quota
   - returns ALLOW or BLOCK
   - if BLOCK ~ return 429 immediately, never hits the API
4. after response:
   - pass response body to C
   - C extracts tokens using extractors (from data.json)
   - C calculates cost using hash map
   - C updates usage counter
   - returns cost info
5. response returned to user unchanged

C API (two functions):

```c
int grc_before_request(const char *url);
// returns: ALLOW (0) or BLOCK (1)

CostResult grc_after_response(const char *url, const char *response_body);
// extracts tokens, calculates cost, updates usage
```

language shims (all same pattern):

```
hook_http_client()
    before: decision = grc.before_request(url)
    if block: return 429
    actual call happens
    after: grc.after_response(url, response_body)
    return response to user
```

works in:

- local dev (any OS)
- EKS / ECS (container)
- lambda (as layer/dependency)
- databricks (pip install)
- cloud run, fargate, any compute

why data.json matters here:

- api_pattern ~ identifies which HTTP calls are LLM APIs
- extractors ~ knows how to pull token counts from each provider's response format
- pricing ~ calculates cost per model
