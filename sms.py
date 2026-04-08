from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
from model import get_ai_reply
import os

TWILIO_ACCOUNT_SID  = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN   = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

def handle_sms(form):
    incoming_text = form.get("Body")
    sender_number = form.get("From")
    print(f"Incoming SMS from {sender_number}: {incoming_text}")

    try:
        ai_reply = get_ai_reply(sender_number, incoming_text)
        print(f"AI reply: {ai_reply}")
    except Exception as e:
        print(f"Error generating AI reply: {e}")
        ai_reply = "Sorry, something went wrong. Please try again."

    response = MessagingResponse()
    response.message(ai_reply)
    return str(response)  # ✅ this line was missing


def handle_missed_call(form):
    caller_number = form.get("From")
    print(f"Missed call from: {caller_number}")

    if caller_number:
        try:
            # Generate an AI-powered missed call message
            ai_reply = get_ai_reply(caller_number, "I just called but no one answered.")
            print(f"Sending missed call SMS: {ai_reply}")

            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=ai_reply,
                from_=TWILIO_PHONE_NUMBER,
                to=caller_number
            )
            print(f"✅ SMS sent to {caller_number}")
        except Exception as e:
            print(f"❌ Error sending missed call SMS: {e}")
    else:
        print("⚠️ No caller number in webhook data")

    # Tell Twilio what to do with the call itself
    response = VoiceResponse()
    response.say("Sorry, we missed your call. We are texting you right now!")
    response.hangup()
    return str(response)
