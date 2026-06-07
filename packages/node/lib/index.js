const path = require("path");
const native = require(
  path.join(__dirname, "..", "build", "Release", "grc_interceptor.node"),
);
const { activate, deactivate } = require("./intercept");

const LOG_DEBUG = 0;
const LOG_INFO = 1;
const LOG_WARN = 2;
const LOG_ERROR = 3;

const DEFAULT_PRICING = path.join(
  __dirname,
  "..",
  "..",
  "..",
  "data",
  "merged_pricing.json",
);

function init(apiKey, pricingFile) {
  const file = pricingFile || DEFAULT_PRICING;
  const result = native.init(apiKey, file);
  if (result) {
    activate(native);
  }
  return result;
}

function enableLogging(level, logPath) {
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
