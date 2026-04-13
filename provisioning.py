import os
import stripe
from twilio.rest import Client
from supabase import create_client

# ── CREDENTIALS ──────────────────────────────────────────
TWILIO_ACCOUNT_SID   = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN    = os.environ.get("TWILIO_AUTH_TOKEN")
RENDER_URL           = os.environ.get("RENDER_URL")
SUPABASE_URL         = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
stripe.api_key       = os.environ.get("STRIPE_SECRET_KEY")

# ── TEST MODE ─────────────────────────────────────────────
# Set to True to skip real Twilio number purchases during testing.
# Set to False when you are ready to go live with real clients.
TEST_MODE = True

# ── SUPABASE CLIENT (service role) ────────────────────────
sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ── PLAN SMS LIMITS ───────────────────────────────────────
PLAN_SMS_LIMITS = {
    "starter":        500,
    "growth":         2000,
    "pro":            999999,
    "agency_starter": 999999,
    "agency_growth":  999999,
    "agency_pro":     999999,
}

AGENCY_CLIENT_LIMITS = {
    "agency_starter": 3,
    "agency_growth":  10,
    "agency_pro":     999999,
}

# ── TWILIO NUMBER PURCHASE ────────────────────────────────
def buy_twilio_number(business_phone):
    """
    Buys a real Twilio number or returns a fake one in TEST_MODE.
    """
    if TEST_MODE:
        fake_number = "+15550000000"
        fake_sid    = "TEST_SID_123"
        print(f"🧪 [TEST MODE] Skipping real Twilio purchase. Fake number: {fake_number}")
        return fake_number, fake_sid

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    try:
        area_code = business_phone.replace("+1", "")[:3]
        available = client.available_phone_numbers("US").local.list(
            area_code=area_code, limit=1
        )
        if not available:
            available = client.available_phone_numbers("US").local.list(limit=1)

        new_number = client.incoming_phone_numbers.create(
            phone_number=available[0].phone_number
        )
        client.incoming_phone_numbers(new_number.sid).update(
            voice_url=f"{RENDER_URL}/missed-call",
            voice_method="POST"
        )
        print(f"✅ Twilio number purchased: {new_number.phone_number}")
        return new_number.phone_number, new_number.sid

    except Exception as e:
        print(f"❌ Twilio error: {e}")
        raise


# ── CREATE BUSINESS ───────────────────────────────────────
async def create_business_account(data: dict):
    """
    Full business onboarding:
    1. Charge via Stripe
    2. Create Supabase auth user
    3. Buy Twilio number (or fake in TEST_MODE)
    4. Save to businesses table
    5. Assign business role
    """
    try:
        email          = data["email"]
        password       = data["password"]
        business_name  = data["business_name"]
        business_phone = data["business_phone"]
        industry       = data.get("industry", "")
        plan           = data["plan"]
        price_id       = data["price_id"]
        payment_method = data["payment_method"]
        auto_reply     = data.get(
            "auto_reply_message",
            "Hi! Sorry we missed your call. How can we help you today?"
        )

        # Step 1 — Stripe
        print(f"Creating Stripe customer for {email}")
        customer = stripe.Customer.create(
            email=email,
            payment_method=payment_method,
            invoice_settings={"default_payment_method": payment_method}
        )
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{"price": price_id}],
            expand=["latest_invoice.payment_intent"]
        )
        print(f"✅ Stripe subscription created: {subscription.id}")

        # Step 2 — Supabase auth user
        auth_response = sb.auth.admin.create_user({
            "email":          email,
            "password":       password,
            "email_confirm":  True
        })
        user_id = auth_response.user.id
        print(f"✅ Supabase user created: {user_id}")

        # Step 3 — Twilio number
        twilio_number, twilio_sid = buy_twilio_number(business_phone)

        # Step 4 — Save to businesses table
        biz_result = sb.table("businesses").insert({
            "user_id":                  user_id,
            "agency_id":                None,
            "business_name":            business_name,
            "business_phone":           business_phone,
            "industry":                 industry,
            "twilio_number":            twilio_number,
            "twilio_number_sid":        twilio_sid,
            "auto_reply_message":       auto_reply,
            "active":                   True,
            "sms_count":                0,
            "plan":                     plan,
            "stripe_customer_id":       customer.id,
            "stripe_subscription_id":   subscription.id
        }).execute()

        biz_id = biz_result.data[0]["id"]
        print(f"✅ Business saved to database with id: {biz_id}")

        # Step 5 — Assign role
        sb.table("user_roles").insert({
            "user_id":   user_id,
            "role":      "business",
            "linked_id": biz_id
        }).execute()
        print(f"✅ Role assigned: business")

        print(f"🎉 Business account fully created for {business_name}")
        return {
            "success":       True,
            "twilio_number": twilio_number,
            "message":       f"Account created for {business_name}"
        }

    except Exception as e:
        print(f"❌ create_business_account error: {e}")
        return {"success": False, "error": str(e)}


# ── CREATE AGENCY ─────────────────────────────────────────
async def create_agency_account(data: dict):
    """
    Full agency onboarding:
    1. Charge via Stripe
    2. Create Supabase auth user
    3. Save to agencies table
    4. Assign agency role
    """
    try:
        email        = data["email"]
        password     = data["password"]
        agency_name  = data["agency_name"]
        agency_phone = data.get("agency_phone", "")
        plan         = data["plan"]
        price_id     = data["price_id"]
        payment_method = data["payment_method"]

        # Step 1 — Stripe
        print(f"Creating Stripe customer for agency {email}")
        customer = stripe.Customer.create(
            email=email,
            payment_method=payment_method,
            invoice_settings={"default_payment_method": payment_method}
        )
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{"price": price_id}],
            expand=["latest_invoice.payment_intent"]
        )
        print(f"✅ Stripe subscription created: {subscription.id}")

        # Step 2 — Supabase auth user
        auth_response = sb.auth.admin.create_user({
            "email":         email,
            "password":      password,
            "email_confirm": True
        })
        user_id = auth_response.user.id
        print(f"✅ Supabase user created: {user_id}")

        # Step 3 — Save to agencies table
        agency_result = sb.table("agencies").insert({
            "user_id":                  user_id,
            "agency_name":              agency_name,
            "agency_email":             email,
            "agency_phone":             agency_phone,
            "plan":                     plan,
            "active":                   True,
            "stripe_customer_id":       customer.id,
            "stripe_subscription_id":   subscription.id
        }).execute()

        agency_id = agency_result.data[0]["id"]
        print(f"✅ Agency saved to database with id: {agency_id}")

        # Step 4 — Assign role
        sb.table("user_roles").insert({
            "user_id":   user_id,
            "role":      "agency",
            "linked_id": agency_id
        }).execute()
        print(f"✅ Role assigned: agency")

        print(f"🎉 Agency account fully created for {agency_name}")
        return {
            "success": True,
            "message": f"Agency account created for {agency_name}"
        }

    except Exception as e:
        print(f"❌ create_agency_account error: {e}")
        return {"success": False, "error": str(e)}


# ── PROVISION NUMBER FOR AGENCY CLIENT ────────────────────
async def provision_new_business(business_name, business_phone, auto_reply_message=None):
    """
    Used by the agency dashboard to add a new client.
    Respects TEST_MODE flag.
    """
    try:
        twilio_number, twilio_sid = buy_twilio_number(business_phone)
        return {
            "success":       True,
            "twilio_number": twilio_number,
            "twilio_sid":    twilio_sid,
            "message":       f"Provisioned {twilio_number} for {business_name}"
        }
    except Exception as e:
        print(f"❌ Provisioning error: {e}")
        return {"success": False, "error": str(e)}
