const path = require("path");
const grc = require("./build/Release/grc_interceptor.node");

const PRICING_FILE = path.resolve(__dirname, "../../data/merged_pricing.json");

let grc_keys =
  "grc_eNp1zT0OgzAMQOG7eK75caw45jYhcaFSpVQQFhB3b6Zunb8nvQuOV4YJhlEtUMxIaoyi5FHND-hGYzbJQuTgAWvZa6vXWj_71PcnLlvqTpu7VJqWau__uvxGSpyQHUcUcQlDbMtoz5l88EIS4P4Cmt4qiw";

const ok = grc.init(grc_keys, PRICING_FILE);
if (!ok) {
  console.error("Failed to initialize GRC interceptor");
  process.exit(1);
}

const req = grc.interceptRequest(
  "https://api.openai.com/v1/chat/completions",
  JSON.stringify({
    model: "gpt-4o",
    messages: [{ role: "user", content: "hello" }],
  }),
);

if (req.allowed === 0) {
  console.log(
    "Quota exceeded! Used:",
    req.usedQuota,
    "Remaining:",
    req.remainingQuota,
  );
} else if (req.allowed === 1) {
  console.log("Allowed. Model:", req.model);

  const mockResponse = JSON.stringify({
    model: "gpt-4o",
    usage: { prompt_tokens: 100, completion_tokens: 50 },
  });

  const res = grc.interceptResponse(
    "https://api.openai.com/v1/chat/completions",
    mockResponse,
  );
  console.log("Response tracked:", res);
} else {
  console.log("Not an LLM call, passthrough");
}

grc.destroy();
