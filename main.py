from fastapi import FastAPI, Request
from fastapi.responses import Response
from sms import handle_sms, handle_missed_call
from provisioning import provision_new_business

app = FastAPI()

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
    """Onboards a new business — provisions their Twilio number automatically."""
    body = await request.json()
    business_name  = body.get("business_name")
    business_phone = body.get("business_phone")
    auto_reply     = body.get("auto_reply_message")

    if not business_name or not business_phone:
        return {"success": False, "error": "business_name and business_phone are required"}

    result = provision_new_business(business_name, business_phone, auto_reply)
    return result
