from fastapi import FastAPI, Request
from sms import handle_sms

app = FastAPI()

@app.post("/sms")
async def receive_sms(request: Request):
    form = await request.form()
    # handle_sms already returns Twilio XML string
    return handle_sms(form)