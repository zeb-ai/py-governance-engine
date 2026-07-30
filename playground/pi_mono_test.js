import grc from "@zeb_labs/zgrc";
import { join } from "path";
import {
  SessionManager,
  createAgentSessionFromServices,
  createAgentSessionServices,
} from "@mariozechner/pi-coding-agent";

grc.init(process.env.API_KEY);
grc.enableLogging(grc.LOG_DEBUG, join(process.cwd(), "grc.log"));

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
const modelArn = process.env.MODEL_ARN || process.env.MODEL_ID;
console.log("Starting Pi Mono test...");
console.log("AWS_REGION:", process.env.AWS_REGION || "us-east-1");
console.log("MODEL_ARN:", modelArn ? "set" : "NOT SET");
console.log(
  "AWS_ACCESS_KEY_ID:",
  process.env.AWS_ACCESS_KEY_ID ? "set" : "NOT SET",
);
console.log("\nSending prompt: 'Hello, my name is samrat'\n");

callPiMono("Hello, my name is samrat", {
  cwd: process.cwd(),
  region: process.env.AWS_REGION || "us-east-1",
  modelArn,
  awsAccessKeyId: process.env.AWS_ACCESS_KEY_ID,
  systemPrompt: "You are a helpful coding assistant.",
  onChunk: (chunk) => process.stdout.write(chunk),
})
  .then((result) => {
    console.log("\n\nDone.");
    console.log("Full response:", result);
  })
  .catch((err) => {
    console.error("Error:", err);
    console.error("Stack:", err.stack);
  });
