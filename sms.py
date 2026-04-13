from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
from supabase import create_client
from model import get_ai_reply
import os

# ── CREDENTIALS ───────────────────────────────────────────
TWILIO_ACCOUNT_SID  = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN   = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")
SUPABASE_URL        = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY= os.environ.get("SUPABASE_SERVICE_KEY")

# Use service key so we can look up any business
sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ── LOOKUP BUSINESS BY TWILIO NUMBER ──────────────────────
def get_business_by_number(twilio_number: str):
    """
    Finds the business that owns this Twilio number.
    Returns (business, ai_profile) or (None, None).
    """
    try:
        biz_result = sb.table("businesses") \
            .select("*") \
            .eq("twilio_number", twilio_number) \
            .single() \
            .execute()

        if not biz_result.data:
            return None, None

        business = biz_result.data

        # Try to get their AI profile
        profile_result = sb.table("ai_profiles") \
            .select("*") \
            .eq("business_id", business["id"]) \
            .single() \
            .execute()

        profile = profile_result.data if profile_result.data else None

        return business, profile

    except Exception as e:
        print(f"⚠️ Error looking up business: {e}")
        return None, None


# ── HANDLE INBOUND SMS ────────────────────────────────────
def handle_sms(form):
    """
    Customer texts the Twilio number.
    Looks up the business and generates a personalized AI reply.
    """
    incoming_text  = form.get("Body")
    sender_number  = form.get("From")
    called_number  = form.get("To")  # which Twilio number was texted

    print(f"📩 Inbound SMS from {sender_number} to {called_number}: {incoming_text}")

    # Look up which business owns this number
    business, profile = get_business_by_number(called_number)

    if business:
        print(f"✅ Business found: {business['business_name']}")
    else:
        print("⚠️ No business found for this number — using default prompt")

    try:
        ai_reply = get_ai_reply(
            sender_number,
            incoming_text,
            profile=profile,
            business=business
        )
        print(f"🤖 AI reply: {ai_reply}")

        # Increment SMS count for this business
        if business:
            sb.table("businesses") \
                .update({"sms_count": (business.get("sms_count", 0) or 0) + 1}) \
                .eq("id", business["id"]) \
                .execute()

    except Exception as e:
        print(f"❌ Error generating AI reply: {e}")
        ai_reply = "Sorry, we missed your call. We'll get back to you shortly!"

    response = MessagingResponse()
    response.message(ai_reply)
    return str(response)


# ── HANDLE MISSED CALL ────────────────────────────────────
def handle_missed_call(form):
    """
    Customer calls the Twilio number and nobody answers.
    Looks up the business and sends a personalized SMS.
    """
    caller_number = form.get("From")
    called_number = form.get("To")

    print(f"📞 Missed call from {caller_number} to {called_number}")

    # Look up which business owns this number
    business, profile = get_business_by_number(called_number)

    if business:
        print(f"✅ Business found: {business['business_name']}")
    else:
        print("⚠️ No business found — using default prompt")

    if caller_number:
        try:
            ai_reply = get_ai_reply(
                caller_number,
                "I just called but no one answered.",
                profile=profile,
                business=business
            )
            print(f"🤖 Sending missed call SMS: {ai_reply}")

            twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

            # Send from the business's specific number if found
            from_number = business["twilio_number"] if business else TWILIO_PHONE_NUMBER

            twilio_client.messages.create(
                body=ai_reply,
                from_=from_number,
                to=caller_number
            )
            print(f"✅ SMS sent to {caller_number}")

            # Increment SMS count
            if business:
                sb.table("businesses") \
                    .update({"sms_count": (business.get("sms_count", 0) or 0) + 1}) \
                    .eq("id", business["id"]) \
                    .execute()

        except Exception as e:
            print(f"❌ Error sending missed call SMS: {e}")
    else:
        print("⚠️ No caller number in webhook data")

    # Tell Twilio what to do with the call
    response = VoiceResponse()
    response.say("Sorry, we missed your call. We are texting you right now!")
    response.hangup()
    return str(response)
