from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
from supabase import create_client
from model import get_ai_reply
import os
from datetime import date

# ── CREDENTIALS ───────────────────────────────────────────
TWILIO_ACCOUNT_SID   = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN    = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER  = os.environ.get("TWILIO_PHONE_NUMBER")
SUPABASE_URL         = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ── PLAN SMS LIMITS ───────────────────────────────────────
PLAN_LIMITS = {
    "starter":        500,
    "growth":         2000,
    "pro":            999999,
    "agency_starter": 999999,
    "agency_growth":  999999,
    "agency_pro":     999999,
}

# Message sent when a business exceeds their monthly limit
LIMIT_REACHED_MESSAGE = (
    "Hi! Sorry we missed your call. "
    "Please call us back directly and we will be happy to help you. "
    "Reply STOP to unsubscribe."
)


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


# ── CHECK AND RESET SMS LIMIT ─────────────────────────────
def check_sms_limit(business: dict) -> bool:
    """
    Returns True if the business can still send SMS this month.
    Returns False if they have hit their plan limit.
    Also resets the counter if a new month has started.
    """
    plan       = business.get("plan", "starter")
    sms_count  = business.get("sms_count", 0) or 0
    reset_date = business.get("sms_reset_date")
    limit      = PLAN_LIMITS.get(plan, 500)

    # Check if we need to reset the monthly counter
    today = date.today()
    if reset_date:
        try:
            reset = date.fromisoformat(str(reset_date))
            if today.month != reset.month or today.year != reset.year:
                # New month — reset the counter
                sb.table("businesses").update({
                    "sms_count":      0,
                    "sms_reset_date": today.isoformat()
                }).eq("id", business["id"]).execute()
                print(f"🔄 SMS count reset for {business['business_name']} — new month")
                return True
        except Exception as e:
            print(f"⚠️ Error parsing reset date: {e}")

    # Check if under limit
    if limit == 999999:
        return True  # Unlimited plan

    if sms_count < limit:
        return True

    print(f"⚠️ SMS limit reached for {business['business_name']} — {sms_count}/{limit} used")
    return False


# ── INCREMENT SMS COUNT ───────────────────────────────────
def increment_sms_count(business: dict):
    """Adds 1 to the business SMS counter after sending."""
    try:
        current = business.get("sms_count", 0) or 0
        sb.table("businesses") \
            .update({"sms_count": current + 1}) \
            .eq("id", business["id"]) \
            .execute()
    except Exception as e:
        print(f"⚠️ Error incrementing SMS count: {e}")


# ── HANDLE INBOUND SMS ────────────────────────────────────
def handle_sms(form):
    """
    Customer texts the Twilio number.
    Checks plan limit before generating AI reply.
    """
    incoming_text = form.get("Body")
    sender_number = form.get("From")
    called_number = form.get("To")

    print(f"📩 Inbound SMS from {sender_number} to {called_number}: {incoming_text}")

    business, profile = get_business_by_number(called_number)

    if business:
        print(f"✅ Business found: {business['business_name']} — Plan: {business.get('plan', 'starter')}")
    else:
        print("⚠️ No business found — using default prompt")

    try:
        # Check SMS limit
        if business and not check_sms_limit(business):
            ai_reply = LIMIT_REACHED_MESSAGE
            print(f"🚫 SMS limit reached — sending fallback message")
        else:
            ai_reply = get_ai_reply(
                sender_number,
                incoming_text,
                profile=profile,
                business=business
            )
            print(f"🤖 AI reply: {ai_reply}")

            # Increment counter
            if business:
                increment_sms_count(business)

    except Exception as e:
        print(f"❌ Error generating AI reply: {e}")
        ai_reply = "Sorry we missed your call. Please call us back directly. Reply STOP to unsubscribe."

    response = MessagingResponse()
    response.message(ai_reply)
    return str(response)


# ── HANDLE MISSED CALL ────────────────────────────────────
def handle_missed_call(form):
    """
    Customer calls and nobody answers.
    Checks plan limit before sending auto SMS.
    """
    caller_number = form.get("From")
    called_number = form.get("To")

    print(f"📞 Missed call from {caller_number} to {called_number}")

    business, profile = get_business_by_number(called_number)

    if business:
        print(f"✅ Business found: {business['business_name']} — Plan: {business.get('plan', 'starter')}")
    else:
        print("⚠️ No business found — using default prompt")

    if caller_number:
        try:
            # Check SMS limit
            if business and not check_sms_limit(business):
                ai_reply = LIMIT_REACHED_MESSAGE
                print(f"🚫 SMS limit reached — sending fallback message")
            else:
                ai_reply = get_ai_reply(
                    caller_number,
                    "I just called but no one answered.",
                    profile=profile,
                    business=business
                )
                print(f"🤖 Sending missed call SMS: {ai_reply}")

            twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            from_number = business["twilio_number"] if business else TWILIO_PHONE_NUMBER

            twilio_client.messages.create(
                body=ai_reply,
                from_=from_number,
                to=caller_number
            )
            print(f"✅ SMS sent to {caller_number}")

            # Increment counter only if under limit
            if business and check_sms_limit(business):
                increment_sms_count(business)

        except Exception as e:
            print(f"❌ Error sending missed call SMS: {e}")
    else:
        print("⚠️ No caller number in webhook data")

    response = VoiceResponse()
    response.say("Sorry, we missed your call. We are texting you right now!")
    response.hangup()
    return str(response)
