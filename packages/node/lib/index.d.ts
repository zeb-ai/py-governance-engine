export declare const LOG_DEBUG = 0;
export declare const LOG_INFO = 1;
export declare const LOG_WARN = 2;
export declare const LOG_ERROR = 3;

export type LogLevel =
  | typeof LOG_DEBUG
  | typeof LOG_INFO
  | typeof LOG_WARN
  | typeof LOG_ERROR;

export interface RequestResult {
  allowed: number;
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

export declare function init(apiKey: string, pricingFile?: string): boolean;
export declare function enableLogging(level: LogLevel, path: string): void;
export declare function interceptRequest(
  url: string,
  body?: string,
): RequestResult;
export declare function interceptResponse(
  url: string,
  body: string,
): ResponseResult;
export declare function destroy(): void;
