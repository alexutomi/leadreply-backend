from fastapi import FastAPI, Request
from fastapi.responses import Response
from sms import handle_sms, handle_missed_call

app = FastAPI()

@app.get("/")
def home():
    return {"status": "LeadReply backend running"}

@app.post("/sms")
async def receive_sms(request: Request):
    """Handles inbound SMS messages."""
    form = await request.form()
    return Response(content=handle_sms(form), media_type="application/xml")  # ✅ fixed

@app.post("/missed-call")
async def missed_call(request: Request):
    """Handles missed call webhook — sends auto SMS to caller."""
    form = await request.form()
    return Response(content=handle_missed_call(form), media_type="application/xml")
