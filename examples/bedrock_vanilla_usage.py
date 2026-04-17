import json
import os
from typing import Dict, List

import boto3
from dotenv import load_dotenv

import zgrc
import logging

# Load environment variables from .env file
load_dotenv()

# Configure logging for the application
logging.basicConfig(
    level=logging.INFO,
    format="[%(name)s] %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class BedrockChatREPL:
    def __init__(self, model_id: str = None, region: str = "us-east-1"):
        self.model_id = model_id
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )
        self.history: List[Dict] = []

    def add_user_message(self, content: str):
        self.history.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str):
        self.history.append({"role": "assistant", "content": content})

    def build_request(self):
        return {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": self.history,
        }

    def call_model(self) -> str:
        request_body = self.build_request()

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(request_body),
        )

        response_body = json.loads(response["body"].read())

        output_text = response_body["content"][0]["text"]

        return output_text

    def run(self):
        print("\n=== Bedrock Chat REPL ===")
        print("Commands: /exit | /reset\n")

        while True:
            user_input = input("You: ")

            if user_input.strip() == "/exit":
                print("Exiting...")
                break

            if user_input.strip() == "/reset":
                self.history = []
                print("History cleared.")
                continue

            try:
                self.add_user_message(user_input)

                response = self.call_model()

                self.add_assistant_message(response)

                print(f"\nAssistant: {response}\n")
                logger.info(">>>>>")

            except Exception as e:
                print(f"\n[ERROR] {e}\n")


if __name__ == "__main__":
    # MAIN
    zgrc.init(
        api_key=os.getenv("API_KEY"),
        auto_instrument=True,
        app_name="bedrock-chat-demo",
        environment="development",
        log_level=logging.DEBUG,
    )

    try:
        repl = BedrockChatREPL(
            model_id=os.getenv("MODEL_ID"),
        )
        repl.run()

    finally:
        zgrc.teardown()
