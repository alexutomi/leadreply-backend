import os
from openai import OpenAI

api_key = os.environ.get("OPENAI_API_KEY")
client  = OpenAI(api_key=api_key)

# Maximum number of previous messages to include as context
# Keeps costs low while giving the AI enough memory to hold a real conversation
MAX_HISTORY = 10

# ── DEFAULT SYSTEM PROMPT ─────────────────────────────────
DEFAULT_SYSTEM_PROMPT = """
You are a friendly SMS assistant for a local business.
A customer just called and missed the call.
Keep replies under 160 characters.
Sound like a real person from the business, not a robot.
End with a question to keep the conversation going.
Never mention you are an AI or automated system.
If the customer wants to schedule an appointment, ask for
their name, address, and preferred time.
""".strip()


# ── DYNAMIC SYSTEM PROMPT ─────────────────────────────────
def build_system_prompt(profile: dict, business: dict) -> str:
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

You are having an ongoing SMS conversation with a customer
who called {business_name} and no one answered.
Keep every reply under 160 characters.
Sound like a real person from the business, not a robot.
Remember everything said earlier in this conversation.
If the customer wants to schedule an appointment ask for
their name, address, and preferred time.
Never mention you are an AI or automated system.
""".strip()

    return prompt


# ── BUILD CONVERSATION HISTORY ────────────────────────────
def build_message_history(history: list) -> list:
    """
    Converts conversation history from Supabase into the
    OpenAI messages format.

    history: list of dicts with keys:
        - direction: 'inbound' (customer) or 'outbound' (AI)
        - message: the text content
        - created_at: timestamp (used for ordering)

    Returns list of OpenAI message dicts with role and content.
    Limits to MAX_HISTORY most recent messages to control cost.
    """
    if not history:
        return []

    # Sort by created_at ascending so oldest is first
    sorted_history = sorted(history, key=lambda x: x.get("created_at", ""))

    # Take only the most recent MAX_HISTORY messages
    recent = sorted_history[-MAX_HISTORY:]

    messages = []
    for msg in recent:
        direction = msg.get("direction", "inbound")
        content   = msg.get("message", "").strip()
        if not content:
            continue
        # inbound = customer = user role
        # outbound = AI = assistant role
        role = "user" if direction == "inbound" else "assistant"
        messages.append({"role": role, "content": content})

    return messages


# ── MAIN REPLY FUNCTION ───────────────────────────────────
def get_ai_reply(
    user: str,
    message: str,
    profile: dict = None,
    business: dict = None,
    history: list = None
) -> str:
    """
    Generates an AI reply using:
    - Business profile for personalization (if set up)
    - Full conversation history for context and memory
    - Current message from the customer

    Args:
        user:     caller phone number (for logging)
        message:  the current message from the customer
        profile:  AI profile dict from Supabase (optional)
        business: business dict from Supabase (optional)
        history:  list of previous conversation messages (optional)

    Returns:
        str: the AI-generated reply
    """
    # Build the system prompt
    if profile and business:
        system_prompt = build_system_prompt(profile, business)
    else:
        system_prompt = DEFAULT_SYSTEM_PROMPT

    # Start with system message
    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history so AI remembers previous exchanges
    if history:
        history_messages = build_message_history(history)
        messages.extend(history_messages)
        print(f"📚 Loaded {len(history_messages)} messages of conversation history")

    # Add the current message
    messages.append({"role": "user", "content": message})

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.4,
        max_tokens=120
    )

    return response.choices[0].message.content.strip()
