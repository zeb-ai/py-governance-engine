import os

from dotenv import load_dotenv
from openai import OpenAI

import zgrc

load_dotenv()

zgrc.init(api_key=os.getenv("API_KEY"))

DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN")

client = OpenAI(api_key=DATABRICKS_TOKEN, base_url=os.getenv("DATABRICKS_BASEURL"))

messages = [{"role": "system", "content": "You are a helpful assistant."}]


while True:
    user_input = input("\nYou: ").strip()

    if not user_input:
        continue

    if user_input.lower() in {"exit", "quit"}:
        print("Bye!")
        break

    if user_input.lower() == "clear":
        messages = [{"role": "system", "content": "You are a helpful assistant."}]
        print("Memory cleared.")
        continue

    messages.append({"role": "user", "content": user_input})

    try:
        chat_completion = client.chat.completions.create(
            model="zeb-demo-uk-ai-gateway", messages=messages, max_tokens=1024
        )

        assistant_reply = chat_completion.choices[0].message.content
        print(f"\nAssistant: {assistant_reply}")

        messages.append({"role": "assistant", "content": assistant_reply})

    except Exception as e:
        print(f"\nError: {e}")
        messages.pop()
