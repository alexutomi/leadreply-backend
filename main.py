import os
import stripe
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client
from sms import handle_sms, handle_missed_call
from provisioning import provision_new_business, create_business_account, create_agency_account
from email_service import send_business_welcome, send_agency_welcome, _send_email

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
stripe.api_key             = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET      = os.environ.get("STRIPE_WEBHOOK_SECRET")
SUPABASE_URL               = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY       = os.environ.get("SUPABASE_SERVICE_KEY")

sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


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


# ── CANCELLATION ENDPOINTS ────────────────────────────────
@app.post("/cancel-subscription")
async def cancel_subscription(request: Request):
    """
    Called from the business or agency dashboard.
    Cancels the Stripe subscription and deactivates the account.
    """
    body    = await request.json()
    user_id = body.get("user_id")
    role    = body.get("role")  # "business" or "agency"

    if not user_id or not role:
        return {"success": False, "error": "user_id and role are required"}

    try:
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

        stripe_sub_id = record.get("stripe_subscription_id")

        # Cancel Stripe subscription at period end
        if stripe_sub_id and not stripe_sub_id.startswith("TEST"):
            stripe.Subscription.modify(
                stripe_sub_id,
                cancel_at_period_end=True
            )
            print(f"✅ Stripe subscription set to cancel: {stripe_sub_id}")

        # Deactivate in database
        sb.table(table).update({"active": False}).eq("user_id", user_id).execute()
        print(f"✅ Account deactivated for user: {user_id}")

        # Send cancellation confirmation email
        email = record.get("agency_email") or record.get("business_phone", "")
        name  = record.get("agency_name") or record.get("business_name", "")

        _send_email(
            to_email=record.get("agency_email", "") or body.get("email", ""),
            subject="Your LeadReply Subscription Has Been Cancelled",
            html_content=f"""
<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
body{{font-family:Arial,sans-serif;background:#f8fafc;margin:0;padding:0;}}
.wrapper{{max-width:560px;margin:40px auto;background:white;border-radius:12px;overflow:hidden;}}
.header{{background:#1e293b;padding:28px 32px;}}
.header h1{{color:white;font-size:20px;margin:0;}}
.body{{padding:32px;}}
.text{{font-size:15px;color:#374151;line-height:1.7;margin-bottom:16px;}}
.box{{background:#f1f5f9;border-radius:10px;padding:16px 20px;margin:20px 0;}}
.footer{{background:#f8fafc;padding:20px 32px;text-align:center;border-top:1px solid #e2e8f0;font-size:12px;color:#94a3b8;}}
</style></head><body>
<div class="wrapper">
  <div class="header"><h1>Subscription Cancelled</h1></div>
  <div class="body">
    <p class="text">Hi {name},</p>
    <p class="text">Your LeadReply subscription has been successfully cancelled.</p>
    <div class="box">
      <p style="margin:0;font-size:14px;color:#374151;">Your service will remain active until the end of your current billing period. After that your dedicated number will be released and SMS automation will stop.</p>
    </div>
    <p class="text">We are sorry to see you go. If you ever want to restart your service you can sign up again at <a href="https://leadreplygroup.com" style="color:#2563eb;">leadreplygroup.com</a>.</p>
    <p class="text">If you cancelled by mistake or have questions please email us at <a href="mailto:support@leadreplygroup.com" style="color:#2563eb;">support@leadreplygroup.com</a> and we will sort it out.</p>
  </div>
  <div class="footer"><p>2026 LeadReply Group · Houston, TX 77056</p></div>
</div>
</body></html>
"""
        )

        return {"success": True, "message": "Subscription cancelled successfully"}

    except Exception as e:
        print(f"❌ Cancellation error: {e}")
        return {"success": False, "error": str(e)}


# ── STRIPE WEBHOOK ────────────────────────────────────────
@app.post("/stripe-webhook")
async def stripe_webhook(request: Request):
    """
    Handles Stripe events:
    - invoice.payment_failed → deactivate account + send email
    - customer.subscription.deleted → deactivate account
    """
    payload   = await request.body()
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


async def handle_payment_failed(invoice):
    """Deactivates account and emails client when payment fails."""
    customer_id = invoice.get("customer")
    if not customer_id:
        return

    print(f"⚠️ Payment failed for customer: {customer_id}")

    # Find business
    biz = sb.table("businesses").select("*").eq("stripe_customer_id", customer_id).execute()
    if biz.data:
        record = biz.data[0]
        sb.table("businesses").update({"active": False}).eq("id", record["id"]).execute()
        print(f"✅ Business deactivated: {record['business_name']}")
        _send_payment_failed_email(record.get("business_name",""), customer_id)
        return

    # Find agency
    agency = sb.table("agencies").select("*").eq("stripe_customer_id", customer_id).execute()
    if agency.data:
        record = agency.data[0]
        sb.table("agencies").update({"active": False}).eq("id", record["id"]).execute()
        print(f"✅ Agency deactivated: {record['agency_name']}")
        _send_payment_failed_email(record.get("agency_name",""), customer_id)


async def handle_subscription_deleted(subscription):
    """Deactivates account when subscription is fully deleted."""
    customer_id = subscription.get("customer")
    if not customer_id:
        return

    print(f"⚠️ Subscription deleted for customer: {customer_id}")

    biz = sb.table("businesses").select("*").eq("stripe_customer_id", customer_id).execute()
    if biz.data:
        sb.table("businesses").update({"active": False}).eq("stripe_customer_id", customer_id).execute()
        print(f"✅ Business deactivated via subscription deletion")
        return

    agency = sb.table("agencies").select("*").eq("stripe_customer_id", customer_id).execute()
    if agency.data:
        sb.table("agencies").update({"active": False}).eq("stripe_customer_id", customer_id).execute()
        print(f"✅ Agency deactivated via subscription deletion")


def _send_payment_failed_email(name: str, customer_id: str):
    """Sends payment failure email to the client."""
    try:
        customer = stripe.Customer.retrieve(customer_id)
        email = customer.get("email", "")
        if not email:
            return

        _send_email(
            to_email=email,
            subject="Action Required — Payment Failed for LeadReply",
            html_content=f"""
<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
body{{font-family:Arial,sans-serif;background:#f8fafc;margin:0;padding:0;}}
.wrapper{{max-width:560px;margin:40px auto;background:white;border-radius:12px;overflow:hidden;}}
.header{{background:#dc2626;padding:28px 32px;}}
.header h1{{color:white;font-size:20px;margin:0;}}
.body{{padding:32px;}}
.text{{font-size:15px;color:#374151;line-height:1.7;margin-bottom:16px;}}
.box{{background:#fee2e2;border:1px solid #fecaca;border-radius:10px;padding:16px 20px;margin:20px 0;}}
.btn{{display:block;background:#2563eb;color:white;text-align:center;padding:14px 24px;border-radius:10px;text-decoration:none;font-size:15px;font-weight:700;margin:24px 0;}}
.footer{{background:#f8fafc;padding:20px 32px;text-align:center;border-top:1px solid #e2e8f0;font-size:12px;color:#94a3b8;}}
</style></head><body>
<div class="wrapper">
  <div class="header"><h1>Payment Failed</h1></div>
  <div class="body">
    <p class="text">Hi {name},</p>
    <p class="text">We were unable to process your LeadReply subscription payment. Your account has been temporarily paused.</p>
    <div class="box">
      <p style="margin:0;font-size:14px;color:#991b1b;font-weight:600;">Your missed call automation is currently inactive. Customers who call your LeadReply number will not receive auto-replies until your payment is resolved.</p>
    </div>
    <p class="text">To reactivate your account please update your payment method by logging into your dashboard.</p>
    <a href="https://leadreplygroup.com/login.html" class="btn">Update Payment Method</a>
    <p class="text">If you need help please email us at <a href="mailto:support@leadreplygroup.com" style="color:#2563eb;">support@leadreplygroup.com</a> and we will assist you immediately.</p>
  </div>
  <div class="footer"><p>2026 LeadReply Group · Houston, TX 77056</p></div>
</div>
</body></html>
"""
        )
        print(f"✅ Payment failed email sent to {email}")
    except Exception as e:
        print(f"❌ Error sending payment failed email: {e}")
