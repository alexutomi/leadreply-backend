import os
import stripe
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from twilio.rest import Client as TwilioClient
from supabase import create_client
from sms import handle_sms, handle_missed_call
from provisioning import provision_new_business, create_business_account, create_agency_account
from email_service import (
    send_business_welcome,
    send_agency_welcome,
    send_payment_failed,
    send_cancellation_email,
    _send_email
)

app = FastAPI()

# ── CORS ──────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://leadreplygroup.com",
        "https://www.leadreplygroup.com",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── CREDENTIALS ───────────────────────────────────────────
stripe.api_key           = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET    = os.environ.get("STRIPE_WEBHOOK_SECRET")
SUPABASE_URL             = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY     = os.environ.get("SUPABASE_SERVICE_KEY")
TWILIO_ACCOUNT_SID       = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN        = os.environ.get("TWILIO_AUTH_TOKEN")

sb     = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
twilio = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


# ── ROOT ──────────────────────────────────────────────────
@app.get("/")
def home():
    return {"status": "LeadReply backend running"}


# ── SMS + MISSED CALL ─────────────────────────────────────
@app.post("/sms")
async def receive_sms(request: Request):
    form = await request.form()
    return Response(content=handle_sms(form), media_type="application/xml")

@app.post("/missed-call")
async def missed_call(request: Request):
    form = await request.form()
    return Response(content=handle_missed_call(form), media_type="application/xml")


# ── SIGNUP ENDPOINTS ──────────────────────────────────────
@app.post("/signup")
async def signup(request: Request):
    body           = await request.json()
    business_name  = body.get("business_name")
    business_phone = body.get("business_phone")
    auto_reply     = body.get("auto_reply_message")
    if not business_name or not business_phone:
        return {"success": False, "error": "business_name and business_phone are required"}
    result = await provision_new_business(business_name, business_phone, auto_reply)
    return result

@app.post("/create-business")
async def create_business(request: Request):
    body = await request.json()
    result = await create_business_account(body)
    return result

@app.post("/create-agency")
async def create_agency(request: Request):
    body = await request.json()
    result = await create_agency_account(body)
    return result


# ── TWILIO NUMBER RELEASE ─────────────────────────────────
def release_twilio_number(twilio_number_sid: str, business_name: str):
    """
    Releases a Twilio phone number back to Twilio.
    This stops the $1/mo charge immediately.
    Skips fake TEST_MODE numbers gracefully.
    """
    if not twilio_number_sid:
        print(f"⚠️ No Twilio SID for {business_name} — skipping release")
        return False

    if twilio_number_sid.startswith("TEST"):
        print(f"🧪 [TEST MODE] Skipping number release for {business_name}")
        return True

    try:
        twilio.incoming_phone_numbers(twilio_number_sid).delete()
        print(f"✅ Twilio number released for {business_name} (SID: {twilio_number_sid})")
        return True
    except Exception as e:
        print(f"❌ Failed to release Twilio number for {business_name}: {e}")
        return False


# ── CANCELLATION ENDPOINT ─────────────────────────────────
@app.post("/cancel-subscription")
async def cancel_subscription(request: Request):
    """
    Called from the business or agency dashboard cancel button.
    Steps:
    1. Cancel Stripe subscription (at period end)
    2. Release Twilio number if business account
    3. Deactivate account in Supabase
    4. Send cancellation confirmation email
    """
    body    = await request.json()
    user_id = body.get("user_id")
    role    = body.get("role")
    email   = body.get("email", "")

    if not user_id or not role:
        return {"success": False, "error": "user_id and role are required"}

    try:
        # ── Fetch account record ──────────────────────────
        if role == "business":
            result = sb.table("businesses").select("*").eq("user_id", user_id).single().execute()
            record = result.data
            table  = "businesses"
        else:
            result = sb.table("agencies").select("*").eq("user_id", user_id).single().execute()
            record = result.data
            table  = "agencies"

        if not record:
            return {"success": False, "error": "Account not found"}

        name          = record.get("business_name") or record.get("agency_name", "")
        stripe_sub_id = record.get("stripe_subscription_id")
        owner_email   = record.get("owner_email") or record.get("agency_email") or email

        # ── Step 1: Cancel Stripe subscription ───────────
        if stripe_sub_id and not stripe_sub_id.startswith("TEST"):
            try:
                stripe.Subscription.modify(
                    stripe_sub_id,
                    cancel_at_period_end=True
                )
                print(f"✅ Stripe subscription set to cancel at period end: {stripe_sub_id}")
            except Exception as e:
                print(f"⚠️ Stripe cancellation error: {e}")

        # ── Step 2: Release Twilio number (businesses only) ──
        if role == "business":
            twilio_sid = record.get("twilio_number_sid")
            biz_name   = record.get("business_name", "")
            release_twilio_number(twilio_sid, biz_name)

            # If agency — release all their client numbers
        elif role == "agency":
            agency_id = record.get("id")
            clients_result = sb.table("businesses").select("*").eq("agency_id", agency_id).execute()
            clients = clients_result.data or []
            for client in clients:
                release_twilio_number(
                    client.get("twilio_number_sid"),
                    client.get("business_name", "")
                )
                # Deactivate each client too
                sb.table("businesses").update({"active": False}).eq("id", client["id"]).execute()
            print(f"✅ Released {len(clients)} client numbers for agency {name}")

        # ── Step 3: Deactivate account in Supabase ────────
        sb.table(table).update({"active": False}).eq("user_id", user_id).execute()
        print(f"✅ Account deactivated for {name}")

        # ── Step 4: Send cancellation email ───────────────
        if owner_email:
            send_cancellation_email(name=name, email=owner_email)

        return {"success": True, "message": f"Subscription cancelled for {name}"}

    except Exception as e:
        print(f"❌ Cancellation error: {e}")
        return {"success": False, "error": str(e)}


# ── STRIPE WEBHOOK ────────────────────────────────────────
@app.post("/stripe-webhook")
async def stripe_webhook(request: Request):
    """
    Handles Stripe events:
    - invoice.payment_failed    → deactivate + send payment failed email
    - customer.subscription.deleted → deactivate + release Twilio number
    """
    payload    = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        print("❌ Invalid Stripe webhook signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    data       = event["data"]["object"]

    print(f"📨 Stripe webhook received: {event_type}")

    if event_type == "invoice.payment_failed":
        await handle_payment_failed(data)

    elif event_type == "customer.subscription.deleted":
        await handle_subscription_deleted(data)

    return {"status": "ok"}


# ── PAYMENT FAILED HANDLER ────────────────────────────────
async def handle_payment_failed(invoice):
    customer_id = invoice.get("customer")
    if not customer_id:
        return

    print(f"⚠️ Payment failed for Stripe customer: {customer_id}")

    # Check businesses first
    biz = sb.table("businesses").select("*").eq("stripe_customer_id", customer_id).execute()
    if biz.data:
        record = biz.data[0]
        sb.table("businesses").update({"active": False}).eq("id", record["id"]).execute()
        print(f"✅ Business deactivated: {record['business_name']}")
        owner_email = record.get("owner_email", "")
        if owner_email:
            send_payment_failed(name=record["business_name"], email=owner_email)
        return

    # Check agencies
    agency = sb.table("agencies").select("*").eq("stripe_customer_id", customer_id).execute()
    if agency.data:
        record = agency.data[0]
        sb.table("agencies").update({"active": False}).eq("id", record["id"]).execute()
        print(f"✅ Agency deactivated: {record['agency_name']}")
        agency_email = record.get("agency_email", "")
        if agency_email:
            send_payment_failed(name=record["agency_name"], email=agency_email)


# ── SUBSCRIPTION DELETED HANDLER ──────────────────────────
async def handle_subscription_deleted(subscription):
    """
    Fires when a subscription is fully deleted on Stripe.
    Releases Twilio number and deactivates the account.
    """
    customer_id = subscription.get("customer")
    if not customer_id:
        return

    print(f"⚠️ Subscription deleted for Stripe customer: {customer_id}")

    # Check businesses
    biz = sb.table("businesses").select("*").eq("stripe_customer_id", customer_id).execute()
    if biz.data:
        record = biz.data[0]

        # Release Twilio number
        release_twilio_number(
            record.get("twilio_number_sid"),
            record.get("business_name", "")
        )

        # Deactivate account
        sb.table("businesses").update({"active": False}).eq("id", record["id"]).execute()
        print(f"✅ Business fully deactivated via subscription deletion: {record['business_name']}")
        return

    # Check agencies
    agency = sb.table("agencies").select("*").eq("stripe_customer_id", customer_id).execute()
    if agency.data:
        record = agency.data[0]
        agency_id = record["id"]

        # Release all client numbers
        clients = sb.table("businesses").select("*").eq("agency_id", agency_id).execute()
        for client in (clients.data or []):
            release_twilio_number(
                client.get("twilio_number_sid"),
                client.get("business_name", "")
            )
            sb.table("businesses").update({"active": False}).eq("id", client["id"]).execute()

        # Deactivate agency
        sb.table("agencies").update({"active": False}).eq("id", agency_id).execute()
        print(f"✅ Agency fully deactivated via subscription deletion: {record['agency_name']}")
