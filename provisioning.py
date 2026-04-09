import os
from twilio.rest import Client
from database import add_business

TWILIO_ACCOUNT_SID  = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN   = os.environ.get("TWILIO_AUTH_TOKEN")
RENDER_URL          = os.environ.get("RENDER_URL")  # your full render URL

def provision_new_business(business_name, business_phone, auto_reply_message="Hi! Sorry we missed your call. How can we help you today?"):
    """
    Automatically:
    1. Buys a new Twilio number
    2. Configures its webhook
    3. Sets up call forwarding to the business phone
    4. Saves everything to the database
    """
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    try:
        # Step 1 — Buy a new Twilio number in the same area code as the business
        area_code = business_phone[2:5]  # extracts area code from +1XXXXXXXXXX
        available_numbers = client.available_phone_numbers("US").local.list(
            area_code=area_code,
            limit=1
        )

        # Fallback to any US number if none available in that area code
        if not available_numbers:
            available_numbers = client.available_phone_numbers("US").local.list(limit=1)

        new_number = client.incoming_phone_numbers.create(
            phone_number=available_numbers[0].phone_number
        )

        print(f"✅ Purchased Twilio number: {new_number.phone_number}")

        # Step 2 — Configure the webhook for missed calls
        client.incoming_phone_numbers(new_number.sid).update(
            voice_url=f"{RENDER_URL}/missed-call",
            voice_method="POST"
        )

        print(f"✅ Webhook configured for {new_number.phone_number}")

        # Step 3 — Save business to database
        add_business(
            business_name=business_name,
            business_phone=business_phone,
            twilio_number=new_number.phone_number,
            twilio_number_sid=new_number.sid,
            auto_reply_message=auto_reply_message
        )

        print(f"✅ Business saved to database")

        return {
            "success": True,
            "twilio_number": new_number.phone_number,
            "message": f"Successfully provisioned {new_number.phone_number} for {business_name}"
        }

    except Exception as e:
        print(f"❌ Provisioning error: {e}")
        return {
            "success": False,
            "error": str(e)
        }