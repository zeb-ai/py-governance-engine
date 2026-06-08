import grc from "@z-grc/node";
import { join } from "path";
import {
  SessionManager,
  createAgentSessionFromServices,
  createAgentSessionServices,
} from "@mariozechner/pi-coding-agent";

if (!process.env.GRC_API_KEY) {
  console.error("Missing GRC_API_KEY env var");
  process.exit(1);
}
const grcReady = grc.init(process.env.GRC_API_KEY);
console.log("[grc] init result:", grcReady);
grc.enableLogging(grc.LOG_DEBUG, "./zgrc_node.log");

export async function callPiMono(userPrompt, options = {}) {
  const {
    cwd = process.cwd(),
    region = "us-east-1",
    modelArn,
    awsAccessKeyId,
    systemPrompt = "",
    tools = [],
    onChunk = () => {},
  } = options;

  const agentDir = join(cwd, ".pi");
  const sessionDir = join(cwd, ".sessions");

  const services = await createAgentSessionServices({
    cwd,
    agentDir,
    resourceLoaderOptions: {
      noPromptTemplates: true,
      noThemes: true,
      noContextFiles: true,
      systemPrompt,
    },
  });

  services.modelRegistry.registerProvider("amazon-bedrock-substrate", {
    baseUrl: `https://bedrock-runtime.${region}.amazonaws.com`,
    api: "bedrock-converse-stream",
    apiKey: awsAccessKeyId,
    models: [
      {
        id: modelArn,
        name: "Substrate Agent (Bedrock)",
        reasoning: false,
        input: ["text"],
        cost: { input: 3.0, output: 15.0, cacheRead: 0.3, cacheWrite: 3.75 },
        contextWindow: 200_000,
        maxTokens: 8_192,
      },
    ],
  });

  const model = services.modelRegistry.find(
    "amazon-bedrock-substrate",
    modelArn,
  );
  if (!model) throw new Error("Model not found after registration");

  const sessionManager = SessionManager.create(cwd, sessionDir);

  const { session } = await createAgentSessionFromServices({
    services,
    sessionManager,
    model,
    tools,
    customTools: [],
  });

  const chunks = [];

  session.subscribe((event) => {
    if (event.type === "message_update") {
      const ev = event.assistantMessageEvent;
      if (ev.type === "text_delta") {
        onChunk(ev.delta);
        chunks.push(ev.delta);
      }
    }
  });

  await session.prompt(userPrompt);

  return chunks.join("");
}

// Run
callPiMono("Hello, what can you help me with?", {
  cwd: process.cwd(),
  region: process.env.AWS_REGION || "us-east-1",
  modelArn: process.env.MODEL_ARN,
  awsAccessKeyId: process.env.AWS_ACCESS_KEY_ID,
  systemPrompt: "You are a helpful coding assistant.",
  onChunk: (chunk) => process.stdout.write(chunk),
})
  .then((response) => {
    console.log("\n\nDone.");
  })
  .catch((err) => {
    console.error("Error:", err);
  });
