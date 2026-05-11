import os
import zgrc
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("API_KEY")

zgrc.init(api_key)


from strands import Agent  # noqa: E402
from strands_tools import current_time  # noqa: E402

agent = Agent(
    agent_id="Greeting agent",
    name="Samrat Greeting machine",
    description="Greet the user based on the time",
    system_prompt="You are Greeter, a agent that greets the user based on the time. Other than you have only greets only other don't do anything",
    tools=[current_time],
)


if __name__ == "__main__":
    while True:
        if (user_input := input("you > ")) is not None:
            response = agent(user_input)
            print(f"AI  > {response}")
