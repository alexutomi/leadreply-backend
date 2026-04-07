from twilio.rest import Client
import os

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")

client = Client(account_sid, auth_token)


def send_missed_call_text(to_number, from_number):

    client.messages.create(
        to=to_number,
        from_=from_number,
        body="Hi! Sorry we missed your call. How can we help you today?"
    )
