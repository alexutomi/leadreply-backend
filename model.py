import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
client  = OpenAI(api_key=api_key)

# ── DEFAULT SYSTEM PROMPT ─────────────────────────────────
# Used when no business profile is found
DEFAULT_SYSTEM_PROMPT = """
You are a friendly SMS assistant for a local business.
A customer just called and missed the call.
Send a warm, helpful SMS reply under 160 characters.
End with a question to keep the conversation going.
Never mention you are an AI.
"""

# ── DYNAMIC SYSTEM PROMPT ─────────────────────────────────
def build_system_prompt(profile: dict, business: dict) -> str:
    """
    Builds a personalized system prompt using the business's
    AI profile data stored in Supabase.
    """
    business_name = business.get("business_name", "our business")
    owner_name    = profile.get("owner_name", "")
    description   = profile.get("business_description", "")
    services      = profile.get("services", "")
    hours         = profile.get("hours", "")
    service_area  = profile.get("service_area", "")
    tone          = profile.get("tone", "friendly and professional")
    common_q      = profile.get("common_questions", "")
    cta           = profile.get("call_to_action", "Ask how we can help them today.")

    prompt = f"""
You are an SMS assistant representing {business_name}.
{"Owner: " + owner_name if owner_name else ""}
{"About: " + description if description else ""}
{"Services: " + services if services else ""}
{"Hours: " + hours if hours else ""}
{"Service area: " + service_area if service_area else ""}
Tone: {tone}
{"Common questions we get: " + common_q if common_q else ""}
Call to action: {cta}

A customer just called {business_name} and no one answered.
Write a warm, personalized SMS reply under 160 characters.
Sound like a real person from the business, not a robot.
End with a question or invitation to continue the conversation.
Never mention you are an AI or an automated system.
""".strip()

    return prompt


# ── MAIN REPLY FUNCTION ───────────────────────────────────
def get_ai_reply(user: str, message: str, profile: dict = None, business: dict = None) -> str:
    """
    Generates an AI reply using the business's profile if available,
    otherwise falls back to the default system prompt.
    """
    if profile and business:
        system_prompt = build_system_prompt(profile, business)
    else:
        system_prompt = DEFAULT_SYSTEM_PROMPT

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system",  "content": system_prompt},
            {"role": "user",    "content": message}
        ],
        temperature=0.4,
        max_tokens=120
    )

    return response.choices[0].message.content.strip()
