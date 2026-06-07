import boto3
import os

from zgrc import init, enable_logging, LOG_DEBUG
from dotenv import load_dotenv
from strands import Agent  # noqa: E402
from strands_tools import current_time  # noqa: E402
from strands.models import BedrockModel


load_dotenv()

api_key = os.getenv("API_KEY")

init(api_key)
enable_logging(LOG_DEBUG, "./zgrc.log")


boto_session = boto3.Session(
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name="us-east-1",
)

model = BedrockModel(
    boto_session=boto_session,
    model_id=os.getenv("MODEL_ID"),
)

agent = Agent(
    agent_id="Greeting agent",
    name="Samrat Greeting machine",
    description="Greet the user based on the time",
    system_prompt="You are Greeter, a agent that greets the user based on the time. Other than you have only greets only other don't do anything",
    tools=[current_time],
    model=model,
)


if __name__ == "__main__":
    while True:
        if (user_input := input("you > ")) is not None:
            response = agent(user_input)
            print(f"AI  > {response}")
