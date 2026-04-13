from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from sms import handle_sms, handle_missed_call
from provisioning import provision_new_business, create_business_account, create_agency_account

app = FastAPI()

# Allow your Vercel frontend to call this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://leadreplygroup.com",
        "https://www.leadreplygroup.com",
        "http://localhost:3000",  # for local testing
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "LeadReply backend running"}

@app.post("/sms")
async def receive_sms(request: Request):
    """Handles inbound SMS messages."""
    form = await request.form()
    return Response(content=handle_sms(form), media_type="application/xml")

@app.post("/missed-call")
async def missed_call(request: Request):
    """Handles missed call webhook — sends auto SMS to caller."""
    form = await request.form()
    return Response(content=handle_missed_call(form), media_type="application/xml")

@app.post("/signup")
async def signup(request: Request):
    """Legacy endpoint — provisions a Twilio number for an agency client."""
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
    """
    Full business onboarding:
    - Charges Stripe
    - Creates Supabase auth user
    - Buys Twilio number
    - Saves to database
    - Assigns business role
    """
    body = await request.json()
    result = await create_business_account(body)
    return result

@app.post("/create-agency")
async def create_agency(request: Request):
    """
    Full agency onboarding:
    - Charges Stripe
    - Creates Supabase auth user
    - Saves agency to database
    - Assigns agency role
    """
    body = await request.json()
    result = await create_agency_account(body)
    return result
