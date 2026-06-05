export interface RequestResult {
  /** 1 = proceed, 0 = quota exceeded, -1 = not an LLM call */
  allowed: -1 | 0 | 1;
  model: string;
  usedQuota: number;
  remainingQuota: number;
}

export interface ResponseResult {
  cost: number;
  inputTokens: number;
  outputTokens: number;
  usedQuota: number;
  remainingQuota: number;
}

/**
 * Initialize the interceptor with your API key and pricing file path.
 * Returns true on success.
 */
export function init(apiKey: string, pricingFile: string): boolean;

/**
 * Intercept an outgoing LLM request.
 * Call before forwarding the request to check quota.
 */
export function interceptRequest(url: string, body?: string): RequestResult;

/**
 * Intercept an LLM response.
 * Call after receiving the response to track cost/usage.
 */
export function interceptResponse(url: string, body: string): ResponseResult;

/**
 * Free all resources. Call on shutdown.
 */
export function destroy(): void;
