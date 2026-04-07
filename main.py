from fastapi import FastAPI, Request
from sms import handle_sms

app = FastAPI()


# Root route so Render URL works
@app.get("/")
def home():
    return {"status": "LeadReply backend running"}


@app.post("/sms")
async def receive_sms(request: Request):
    form = await request.form()
    return handle_sms(form)
