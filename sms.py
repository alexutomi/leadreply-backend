from twilio.twiml.messaging_response import MessagingResponse
from model import get_ai_reply

def handle_sms(form):
    incoming_text = form.get("Body")
    sender_number = form.get("From")

    print(f"Incoming SMS from {sender_number}: {incoming_text}")  # debug

    try:
        ai_reply = get_ai_reply(sender_number, incoming_text)
        print(f"AI reply: {ai_reply}")  # debug
    except Exception as e:
        print(f"Error generating AI reply: {e}")
        ai_reply = "Sorry, something went wrong. Please try again."

    response = MessagingResponse()
    response.message(ai_reply)

# This works for Twilio
    return str(response)
