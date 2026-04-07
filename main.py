from fastapi import FastAPI, Request
from sms import handle_sms, send_missed_call_text

app = FastAPI()


# Health check so Render root URL works
@app.get("/")
def home():
    return {"status": "LeadReply backend running"}


# Handle incoming SMS
@app.post("/sms")
async def receive_sms(request: Request):
    form = await request.form()
    return handle_sms(form)


# Handle incoming calls
@app.post("/voice")
async def handle_voice(request: Request):

    form = await request.form()

    caller = form.get("From")
    business_number = form.get("To")
    call_status = form.get("CallStatus")

    print("Incoming call:", caller)

    # If the call was missed
    if call_status in ["no-answer", "busy", "failed"]:
        send_missed_call_text(caller, business_number)

    return {"status": "ok"}
