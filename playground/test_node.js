import grc from "@zeb_labs/zgrc";

grc.init(process.env.API_KEY);
grc.enableLogging(grc.LOG_DEBUG, "./zgrc_node.log");

import {
  BedrockRuntimeClient,
  ConverseCommand,
} from "@aws-sdk/client-bedrock-runtime";

const client = new BedrockRuntimeClient({
  region: process.env.region,
});

async function generateText() {
  const params = {
    modelId: process.env.MODEL_ID,
    messages: [
      {
        role: "user",
        content: [{ text: "hi." }],
      },
    ],
    inferenceConfig: {
      maxTokens: 500,
      temperature: 0.7,
    },
  };

  try {
    const command = new ConverseCommand(params);
    const response = await client.send(command);

    const replyText = response.output.message.content[0].text;
    console.log("Model Response:\n", replyText);
  } catch (error) {
    console.error("Error calling Amazon Bedrock:", error);
  }
}

generateText();
//grc.destroy();
