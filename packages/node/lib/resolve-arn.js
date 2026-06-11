const { createRequire } = require("module");
const cache = new Map();

function extractArnFromUrl(url) {
  try {
    const parts = url.split("/model/");
    if (parts.length < 2) return null;
    const raw = parts[1].split("/")[0];
    return decodeURIComponent(raw);
  } catch (_) {
    return null;
  }
}

function extractRegionFromUrl(url) {
  const match = url.match(/bedrock-runtime\.([a-z0-9-]+)\.amazonaws\.com/);
  return match ? match[1] : "us-east-1";
}

async function resolveAwsArn(url) {
  if (cache.has(url)) return cache.get(url);

  const arn = extractArnFromUrl(url);
  if (!arn) return null;

  try {
    const userRequire = createRequire(
      require.main?.filename || process.cwd() + "/index.js",
    );
    const { BedrockClient, GetInferenceProfileCommand } = userRequire(
      "@aws-sdk/client-bedrock",
    );

    const region = extractRegionFromUrl(url);
    const client = new BedrockClient({ region });
    const response = await client.send(
      new GetInferenceProfileCommand({ inferenceProfileIdentifier: arn }),
    );

    const modelArn =
      response.models && response.models[1] && response.models[1].modelArn;
    if (!modelArn) return null;

    const match = modelArn.match(/foundation-model\/(.+)$/);
    if (!match) return null;

    const model = match[1];
    cache.set(url, model);
    return model;
  } catch (_) {
    return null;
  }
}

function isArnUrl(url) {
  return url.includes("/model/") && url.includes("arn");
}

module.exports = { resolveAwsArn, isArnUrl };
