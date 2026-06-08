const path = require("path");
const native = require("node-gyp-build")(path.join(__dirname, ".."));
const { activate, deactivate } = require("./intercept");

const LOG_DEBUG = 0;
const LOG_INFO = 1;
const LOG_WARN = 2;
const LOG_ERROR = 3;

const DEFAULT_PRICING = path.join(
  __dirname,
  "..",
  "data",
  "merged_pricing.json",
);

let initialized = false;

function init(apiKey, pricingFile) {
  if (!apiKey) {
    throw new Error("init requires an API key");
  }
  const file = pricingFile || DEFAULT_PRICING;
  const result = native.init(apiKey, file);
  if (!result) {
    throw new Error(
      "init failed: native init returned false (token decode or pricing file error)",
    );
  }
  initialized = true;
  activate(native);
  return result;
}

function enableLogging(level, logPath) {
  if (!initialized) {
    throw new Error("enableLogging() called before successful init()");
  }
  native.enableLogging(level, logPath);
}

function destroy() {
  deactivate();
  native.destroy();
}

module.exports = {
  init,
  enableLogging,
  destroy,
  interceptRequest: native.interceptRequest,
  interceptResponse: native.interceptResponse,
  LOG_DEBUG,
  LOG_INFO,
  LOG_WARN,
  LOG_ERROR,
};
