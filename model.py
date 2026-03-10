import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env
load_dotenv()

# Get API key
api_key = os.getenv("OPENAI_API_KEY")

# Create OpenAI client
client = OpenAI(api_key=api_key)

SYSTEM_PROMPT = """
You are a helpful SMS assistant.
Keep replies under 2 sentences.
Ask one question if needed.
"""

def get_ai_reply(user, message):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message}
        ],
        temperature=0.3,
        max_tokens=120
    )

    return response.choices[0].message.content