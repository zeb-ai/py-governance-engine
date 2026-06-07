import os
from dotenv import load_dotenv

from zgrc import init, enable_logging, LOG_DEBUG

load_dotenv()

api_key = os.getenv("API_KEY")

init(api_key)
enable_logging(LOG_DEBUG, "./zgrc.log")

# Now import pydantic-ai AFTER hooks are installed
from pydantic_ai import Agent  # noqa: E402
from pydantic_ai.models.bedrock import BedrockConverseModel  # noqa: E402
from pydantic_ai.providers.bedrock import BedrockProvider  # noqa: E402

provider = BedrockProvider(
    region_name="us-east-1",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)
model = BedrockConverseModel(
    "us.anthropic.claude-sonnet-4-20250514-v1:0", provider=provider
)
agent = Agent(name="agent", model=model)

if __name__ == "__main__":
    session_history = []
    while True:
        if (user_input := input("you > ")) is not None:
            response = agent.run_sync(user_input, message_history=session_history)
            session_history.extend(response.new_messages())
            print(f"AI  > {response}")
