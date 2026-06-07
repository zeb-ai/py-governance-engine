import { createRequire } from "module";
const require = createRequire(import.meta.url);
const grc = require("./index.js");

export const {
  init,
  enableLogging,
  destroy,
  interceptRequest,
  interceptResponse,
  LOG_DEBUG,
  LOG_INFO,
  LOG_WARN,
  LOG_ERROR,
} = grc;

export default grc;
