import os
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def add_business(business_name, business_phone, twilio_number, twilio_number_sid, auto_reply_message):
    """Add a new business to the database when they sign up."""
    data = {
        "business_name": business_name,
        "business_phone": business_phone,
        "twilio_number": twilio_number,
        "twilio_number_sid": twilio_number_sid,
        "auto_reply_message": auto_reply_message,
        "active": True
    }
    result = supabase.table("businesses").insert(data).execute()
    return result


def get_business_by_twilio_number(twilio_number):
    """Look up a business by their Twilio number when a call comes in."""
    result = supabase.table("businesses").select("*").eq("twilio_number", twilio_number).execute()
    if result.data:
        return result.data[0]
    return None


def get_all_businesses():
    """Get all active businesses."""
    result = supabase.table("businesses").select("*").eq("active", True).execute()
    return result.data